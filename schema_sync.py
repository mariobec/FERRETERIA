from __future__ import annotations

from sqlalchemy import inspect as sa_inspect, text


def listar_diferencias_esquema(db):
    """Compara `db.metadata` (modelos cargados) con columnas/tablas reales en la BD.

    Retorna:
      - tablas_solo_en_bd: tablas en BD sin clase modelo correspondiente en este metadata.
      - tablas_ausentes_en_bd: tablas del modelo que no existen en BD (create_all las creará).
      - columnas_faltantes_en_bd: lista "tabla.columna" esperadas por el modelo y no halladas.
    """
    insp = sa_inspect(db.engine)
    bd_tables = set(insp.get_table_names())
    model_tables = [t.name for t in db.metadata.sorted_tables]
    modelo_set = set(model_tables)

    solo_en_bd = sorted(bd_tables - modelo_set)
    ausentes = sorted(modelo_set - bd_tables)

    columnas_faltantes = []
    for table in db.metadata.sorted_tables:
        tname = table.name
        if not insp.has_table(tname):
            columnas_faltantes.append(f"{tname}.* (tabla completa ausente en BD)")
            continue
        try:
            columnas_bd = {c["name"] for c in insp.get_columns(tname)}
        except Exception:
            db.session.rollback()
            columnas_faltantes.append(f"{tname}: error inspección columnas")
            continue
        for col in table.columns:
            if col.name not in columnas_bd:
                columnas_faltantes.append(f"{tname}.{col.name}")

    return {
        "tablas_solo_en_bd": solo_en_bd,
        "tablas_ausentes_en_bd": ausentes,
        "columnas_faltantes_en_bd": columnas_faltantes,
    }


def sincronizar_esquema_modelos(app, db):
    """Sincroniza columnas faltantes desde los modelos SQLAlchemy hacia la BD.

    `db.create_all()` crea tablas nuevas, pero no modifica tablas existentes.
    Esta rutina cubre ese hueco para despliegues simples en Render/Neon:
    inspecciona cada tabla del modelo y agrega columnas que falten.

    No elimina columnas ni cambia tipos existentes.
    No agrega constraints/foreign keys retroactivas para evitar bloqueos sobre datos legacy.
    """
    resultados = {"tablas_creadas": 0, "columnas_agregadas": 0, "errores": []}

    # Primero crea tablas completamente ausentes.
    insp = sa_inspect(db.engine)
    tablas_antes = set(insp.get_table_names())
    db.create_all()
    insp = sa_inspect(db.engine)
    tablas_despues = set(insp.get_table_names())
    resultados["tablas_creadas"] = len(tablas_despues - tablas_antes)

    preparer = db.engine.dialect.identifier_preparer

    for table in db.metadata.sorted_tables:
        tname = table.name
        try:
            if not insp.has_table(tname):
                continue
            columnas_bd = {c["name"] for c in insp.get_columns(tname)}
        except Exception as ex:
            resultados["errores"].append(f"{tname}: no se pudo inspeccionar ({ex})")
            db.session.rollback()
            continue

        for col in table.columns:
            if col.name in columnas_bd:
                continue
            if col.primary_key:
                # Una tabla existente sin PK del modelo requiere migración manual.
                resultados["errores"].append(f"{tname}.{col.name}: PK faltante omitida")
                continue

            sql = _sql_add_column(preparer, table, col, db.engine.dialect)
            try:
                db.session.execute(text(sql))
                db.session.commit()
                columnas_bd.add(col.name)
                resultados["columnas_agregadas"] += 1
                app.logger.info("Schema sync: columna agregada %s.%s", tname, col.name)
            except Exception as ex:
                db.session.rollback()
                resultados["errores"].append(f"{tname}.{col.name}: {ex}")
                app.logger.exception("Schema sync: no se pudo agregar %s.%s", tname, col.name)

    return resultados


def _sql_add_column(preparer, table, col, dialect):
    table_name = preparer.format_table(table)
    col_name = preparer.quote(col.name)
    col_type = col.type.compile(dialect=dialect)
    dn = (dialect.name or "").lower()
    add_kw = " IF NOT EXISTS" if dn == "postgresql" else ""
    parts = [f"ALTER TABLE {table_name} ADD COLUMN{add_kw} {col_name} {col_type}"]

    default_sql = _default_sql(col)
    if default_sql:
        parts.append(f"DEFAULT {default_sql}")

    # En bases con datos legacy, agregar NOT NULL sin backfill puede fallar.
    # Mantenemos nullable para desbloquear producción; la app valida en inserts.
    parts.append("NULL")
    return " ".join(parts)


def _default_sql(col):
    if col.server_default is not None:
        try:
            arg = col.server_default.arg
            return arg.text if hasattr(arg, "text") else str(arg)
        except Exception:
            return None
    if col.default is not None and getattr(col.default, "is_scalar", False):
        value = col.default.arg
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        if value is not None:
            return str(value)
    return None

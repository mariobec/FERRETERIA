"""Motor de Promociones Comerciales (LX-PROMO-COM).

Precio de lista en línea intacto; el beneficio es un renglón de descuento.
Feature flag: empresa_config `motor_promociones_activo` o env MOTOR_PROMOCIONES_ACTIVO
(default apagado). POS/ticket se cablean en LX-PROMO-COM-2.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

TIPOS_MVP = frozenset({'NXM', 'SEGUNDO_PCT', 'ESCALA_QTY', 'PRECIO_PAR'})


@dataclass
class LineaCarrito:
    """Línea a precio lista (descuento % de línea ya aplicado en subtotal_clp)."""

    producto_id: int
    cantidad: float
    precio_unitario: int  # CLP entero
    subtotal_clp: int  # qty * precio * (1 - dto%/100), redondeado
    detalle_id: Optional[int] = None
    marca: str = ''
    categoria_id: Optional[int] = None
    descuento_pct: float = 0.0


@dataclass
class AplicacionPromo:
    promocion_id: Optional[int]
    codigo: str
    etiqueta_ticket: str
    monto_descuento: int
    tipo: str
    producto_ids: list[int] = field(default_factory=list)
    detalle_ids: list[int] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResultadoPromociones:
    subtotal_clp: int
    descuento_promos_clp: int
    total_clp: int
    aplicaciones: list[AplicacionPromo] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            'subtotal_clp': self.subtotal_clp,
            'descuento_promos_clp': self.descuento_promos_clp,
            'total_clp': self.total_clp,
            'aplicaciones': [a.as_dict() for a in self.aplicaciones],
        }


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def motor_promociones_activo(cfg: Optional[dict] = None) -> bool:
    """Default OFF. Env gana sobre empresa_config."""
    env = (os.environ.get('MOTOR_PROMOCIONES_ACTIVO') or '').strip().lower()
    if env in ('1', 'true', 'yes', 'on'):
        return True
    if env in ('0', 'false', 'no', 'off'):
        return False
    if cfg is not None:
        v = str((cfg or {}).get('motor_promociones_activo', '0')).strip().lower()
        return v in ('1', 'true', 'yes', 'on')
    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clp(n: float) -> int:
    return int(round(float(n or 0)))


def _hoy(d: Optional[date] = None) -> date:
    return d or date.today()


def _vigente(regla: dict, hoy: date) -> bool:
    if not regla.get('activo', True):
        return False
    desde = regla.get('vigencia_desde')
    hasta = regla.get('vigencia_hasta')
    if desde:
        if isinstance(desde, str):
            desde = date.fromisoformat(desde[:10])
        if hoy < desde:
            return False
    if hasta:
        if isinstance(hasta, str):
            hasta = date.fromisoformat(hasta[:10])
        if hoy > hasta:
            return False
    return True


def _lineas_elegibles(lineas: list[LineaCarrito], cond: dict) -> list[LineaCarrito]:
    pids = set(int(x) for x in (cond.get('producto_ids') or []) if x is not None)
    marcas = {str(m).strip().upper() for m in (cond.get('marcas') or []) if str(m).strip()}
    cats = set(int(x) for x in (cond.get('categoria_ids') or []) if x is not None)
    out: list[LineaCarrito] = []
    for ln in lineas:
        if pids and int(ln.producto_id) not in pids:
            continue
        if marcas and (ln.marca or '').strip().upper() not in marcas:
            continue
        if cats and (ln.categoria_id is None or int(ln.categoria_id) not in cats):
            continue
        if not pids and not marcas and not cats:
            # Sin filtro = no aplica (evita promo global accidental en MVP)
            continue
        out.append(ln)
    return out


def _qty_total(lineas: Iterable[LineaCarrito]) -> float:
    return sum(float(ln.cantidad or 0) for ln in lineas)


def _precio_efectivo_unit(ln: LineaCarrito) -> int:
    """Precio unitario tras dto % de línea."""
    q = float(ln.cantidad or 0)
    if q <= 0:
        return int(ln.precio_unitario or 0)
    return _clp(ln.subtotal_clp / q)


def _unidades_precios(lineas: list[LineaCarrito]) -> list[tuple[int, Optional[int]]]:
    """Expande a unidades individuales (precio_efectivo, detalle_id)."""
    unidades: list[tuple[int, Optional[int]]] = []
    for ln in lineas:
        q = int(round(float(ln.cantidad or 0)))
        if q <= 0:
            continue
        pu = _precio_efectivo_unit(ln)
        for _ in range(q):
            unidades.append((pu, ln.detalle_id))
    return unidades


# ---------------------------------------------------------------------------
# Beneficios MVP
# ---------------------------------------------------------------------------

def _aplicar_nxm(lineas: list[LineaCarrito], regla: dict) -> Optional[AplicacionPromo]:
    ben = regla.get('beneficio') or {}
    n = int(ben.get('n') or 0)
    m = int(ben.get('m') or 0)
    if n < 2 or m < 1 or m >= n:
        return None
    unidades = _unidades_precios(lineas)
    if len(unidades) < n:
        return None
    # Ordenar: las más baratas se "regalan" (beneficio al cliente)
    unidades.sort(key=lambda u: u[0])
    sets = len(unidades) // n
    gratis = sets * (n - m)
    if gratis <= 0:
        return None
    desc = sum(u[0] for u in unidades[:gratis])
    if desc <= 0:
        return None
    dets = sorted({d for _, d in unidades[:gratis] if d is not None})
    pids = sorted({int(ln.producto_id) for ln in lineas})
    etiqueta = (regla.get('nombre') or regla.get('codigo') or f'{n}x{m}').strip()
    return AplicacionPromo(
        promocion_id=regla.get('id'),
        codigo=str(regla.get('codigo') or f'NXM-{n}X{m}'),
        etiqueta_ticket=etiqueta,
        monto_descuento=_clp(desc),
        tipo='NXM',
        producto_ids=pids,
        detalle_ids=dets,
        snapshot={'n': n, 'm': m, 'sets': sets, 'unidades_gratis': gratis},
    )


def _aplicar_segundo_pct(lineas: list[LineaCarrito], regla: dict) -> Optional[AplicacionPromo]:
    ben = regla.get('beneficio') or {}
    pct = float(ben.get('pct') or 0)
    if pct <= 0 or pct > 100:
        return None
    unidades_asc = sorted(_unidades_precios(lineas), key=lambda u: u[0])
    if len(unidades_asc) < 2:
        return None
    pares = len(unidades_asc) // 2
    desc = 0
    detalle_hit: set[int] = set()
    # Pares (u0,u1), (u2,u3)…: la más barata del par recibe pct%
    for i in range(0, len(unidades_asc) - 1, 2):
        a, da = unidades_asc[i]
        b, db = unidades_asc[i + 1]
        menor = a if a <= b else b
        det_m = da if a <= b else db
        desc += _clp(menor * (pct / 100.0))
        if det_m is not None:
            detalle_hit.add(int(det_m))
    if desc <= 0:
        return None
    pids = sorted({int(ln.producto_id) for ln in lineas})
    etiqueta = (regla.get('nombre') or regla.get('codigo') or f'2ª al {int(pct)}%').strip()
    return AplicacionPromo(
        promocion_id=regla.get('id'),
        codigo=str(regla.get('codigo') or f'SEGUNDO-{int(pct)}'),
        etiqueta_ticket=etiqueta,
        monto_descuento=_clp(desc),
        tipo='SEGUNDO_PCT',
        producto_ids=pids,
        detalle_ids=sorted(detalle_hit),
        snapshot={'pct': pct, 'pares': pares},
    )


def _aplicar_escala_qty(lineas: list[LineaCarrito], regla: dict) -> Optional[AplicacionPromo]:
    ben = regla.get('beneficio') or {}
    tramos = ben.get('tramos') or []
    if not tramos:
        return None
    qty = _qty_total(lineas)
    if qty <= 0:
        return None
    tramo = None
    for t in tramos:
        desde = float(t.get('desde') or 0)
        hasta = t.get('hasta')
        if qty < desde:
            continue
        if hasta is not None and qty > float(hasta):
            continue
        tramo = t
        break
    if not tramo:
        # Si tramos no cubren, tomar el último cuyo desde <= qty
        candidatos = [t for t in tramos if qty >= float(t.get('desde') or 0)]
        if not candidatos:
            return None
        tramo = max(candidatos, key=lambda t: float(t.get('desde') or 0))

    subtotal_lista = sum(int(ln.subtotal_clp or 0) for ln in lineas)
    if 'precio_unitario' in tramo and tramo['precio_unitario'] is not None:
        precio_esc = _clp(tramo['precio_unitario'])
        subtotal_promo = _clp(precio_esc * qty)
        desc = subtotal_lista - subtotal_promo
    elif 'porcentaje' in tramo or 'pct' in tramo:
        pct = float(tramo.get('porcentaje', tramo.get('pct')) or 0)
        desc = _clp(subtotal_lista * (pct / 100.0))
    else:
        return None
    if desc <= 0:
        return None
    pids = sorted({int(ln.producto_id) for ln in lineas})
    dets = sorted({int(ln.detalle_id) for ln in lineas if ln.detalle_id is not None})
    etiqueta = (regla.get('nombre') or regla.get('codigo') or 'Escala cantidad').strip()
    return AplicacionPromo(
        promocion_id=regla.get('id'),
        codigo=str(regla.get('codigo') or 'ESCALA'),
        etiqueta_ticket=etiqueta,
        monto_descuento=_clp(desc),
        tipo='ESCALA_QTY',
        producto_ids=pids,
        detalle_ids=dets,
        snapshot={'qty': qty, 'tramo': tramo, 'subtotal_lista': subtotal_lista},
    )


def _aplicar_precio_par(lineas: list[LineaCarrito], regla: dict) -> Optional[AplicacionPromo]:
    """Pack a precio fijo: ej. 2 unidades por $3.200; la suelta queda a precio lista.

    Con lista $1.700 y pack 2→$3.200:
      2 → $3.200 · 3 → $4.900 · 4 → $6.400
    """
    ben = regla.get('beneficio') or {}
    try:
        pack_qty = int(ben.get('pack_qty') or ben.get('n') or 2)
        precio_pack = int(ben.get('precio_pack') or ben.get('precio_par') or 0)
    except (TypeError, ValueError):
        return None
    if pack_qty < 2 or precio_pack <= 0:
        return None
    unidades = sorted(_unidades_precios(lineas), key=lambda u: u[0])
    if len(unidades) < pack_qty:
        return None
    packs = len(unidades) // pack_qty
    desc = 0
    detalle_hit: set[int] = set()
    for p in range(packs):
        chunk = unidades[p * pack_qty : (p + 1) * pack_qty]
        lista_pack = sum(int(u[0] or 0) for u in chunk)
        d = lista_pack - precio_pack
        if d <= 0:
            continue
        desc += d
        for _, det in chunk:
            if det is not None:
                detalle_hit.add(int(det))
    if desc <= 0:
        return None
    pids = sorted({int(ln.producto_id) for ln in lineas})
    etiqueta = (regla.get('nombre') or regla.get('codigo') or f'{pack_qty} por ${precio_pack:,}'.replace(',', '.')).strip()
    return AplicacionPromo(
        promocion_id=regla.get('id'),
        codigo=str(regla.get('codigo') or f'PAR-{precio_pack}'),
        etiqueta_ticket=etiqueta,
        monto_descuento=_clp(desc),
        tipo='PRECIO_PAR',
        producto_ids=pids,
        detalle_ids=sorted(detalle_hit),
        snapshot={
            'pack_qty': pack_qty,
            'precio_pack': precio_pack,
            'packs': packs,
            'descuento': _clp(desc),
        },
    )


_APLICADORES = {
    'NXM': _aplicar_nxm,
    'SEGUNDO_PCT': _aplicar_segundo_pct,
    'ESCALA_QTY': _aplicar_escala_qty,
    'PRECIO_PAR': _aplicar_precio_par,
}


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

def evaluar_promociones(
    lineas: list[LineaCarrito],
    reglas: list[dict],
    *,
    hoy: Optional[date] = None,
    activo: bool = True,
) -> ResultadoPromociones:
    """Evalúa reglas sobre el carrito. No muta precios de línea.

    Prioridad: menor número = primero. Si `exclusiva` aplica a productos,
    otras reglas que toquen los mismos producto_ids se omiten.
    """
    subtotal = sum(int(ln.subtotal_clp or 0) for ln in lineas)
    if not activo or not lineas or not reglas:
        return ResultadoPromociones(
            subtotal_clp=subtotal,
            descuento_promos_clp=0,
            total_clp=subtotal,
            aplicaciones=[],
        )

    dia = _hoy(hoy)
    vigentes = [r for r in reglas if _vigente(r, dia) and str(r.get('tipo') or '') in TIPOS_MVP]
    vigentes.sort(key=lambda r: (int(r.get('prioridad') or 100), int(r.get('id') or 0)))

    aplicaciones: list[AplicacionPromo] = []
    productos_bloqueados: set[int] = set()

    for regla in vigentes:
        cond = regla.get('condiciones') or {}
        elegibles = _lineas_elegibles(lineas, cond)
        if not elegibles:
            continue
        pids = {int(ln.producto_id) for ln in elegibles}
        if pids & productos_bloqueados:
            continue
        tipo = str(regla.get('tipo') or '')
        fn = _APLICADORES.get(tipo)
        if not fn:
            continue
        app = fn(elegibles, regla)
        if not app or app.monto_descuento <= 0:
            continue
        aplicaciones.append(app)
        if regla.get('exclusiva', True):
            productos_bloqueados |= pids

    desc_total = sum(a.monto_descuento for a in aplicaciones)
    if desc_total > subtotal:
        # Cap de seguridad: no total negativo
        factor = subtotal / desc_total if desc_total else 1
        for a in aplicaciones:
            a.monto_descuento = _clp(a.monto_descuento * factor)
        desc_total = sum(a.monto_descuento for a in aplicaciones)

    total = max(0, subtotal - desc_total)
    return ResultadoPromociones(
        subtotal_clp=subtotal,
        descuento_promos_clp=desc_total,
        total_clp=total,
        aplicaciones=aplicaciones,
    )


def lineas_desde_detalles_venta(detalles: Iterable[Any]) -> list[LineaCarrito]:
    """Adapta DetalleVenta (o duck-type) a LineaCarrito."""
    out: list[LineaCarrito] = []
    for d in detalles or []:
        qty = float(getattr(d, 'cantidad', 0) or 0)
        pu = _clp(getattr(d, 'precio_unitario', 0) or 0)
        dto = float(getattr(d, 'descuento', 0) or 0)
        sub = getattr(d, 'subtotal', None)
        if sub is None:
            sub = qty * pu * (1 - dto / 100.0)
        prod = getattr(d, 'producto', None)
        marca = ''
        cat = None
        if prod is not None:
            marca = str(getattr(prod, 'marca', '') or getattr(prod, 'marca_nombre', '') or '')
            cat = getattr(prod, 'categoria_id', None)
        # DetalleVenta usa id_producto; otros duck-types pueden traer producto_id.
        pid = getattr(d, 'producto_id', None)
        if pid is None:
            pid = getattr(d, 'id_producto', None)
        if pid is None and prod is not None:
            pid = getattr(prod, 'id', None)
        if pid is None:
            continue
        out.append(
            LineaCarrito(
                producto_id=int(pid),
                cantidad=qty,
                precio_unitario=pu,
                subtotal_clp=_clp(sub),
                detalle_id=getattr(d, 'id', None),
                marca=marca,
                categoria_id=int(cat) if cat is not None else None,
                descuento_pct=dto,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Persistencia (esquema) — COM-1
# ---------------------------------------------------------------------------

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS promocion (
        id SERIAL PRIMARY KEY,
        codigo VARCHAR(40) NOT NULL UNIQUE,
        nombre VARCHAR(120) NOT NULL,
        tipo VARCHAR(32) NOT NULL,
        prioridad INTEGER NOT NULL DEFAULT 100,
        vigencia_desde DATE NULL,
        vigencia_hasta DATE NULL,
        activo BOOLEAN NOT NULL DEFAULT TRUE,
        exclusiva BOOLEAN NOT NULL DEFAULT TRUE,
        beneficio_json TEXT NOT NULL DEFAULT '{}',
        condiciones_json TEXT NOT NULL DEFAULT '{}',
        notas TEXT NULL,
        creado_en TIMESTAMP NULL,
        actualizado_en TIMESTAMP NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS venta_promocion (
        id SERIAL PRIMARY KEY,
        venta_id INTEGER NOT NULL,
        promocion_id INTEGER NULL,
        codigo VARCHAR(40) NOT NULL,
        etiqueta_ticket VARCHAR(160) NOT NULL,
        monto_descuento NUMERIC(14, 2) NOT NULL DEFAULT 0,
        tipo VARCHAR(32) NOT NULL,
        snapshot_json TEXT NULL,
        creado_en TIMESTAMP NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_venta_promocion_venta_id ON venta_promocion (venta_id)
    """,
]


def asegurar_tablas_promociones(app, db) -> bool:
    """Crea tablas promocion / venta_promocion si no existen (Postgres)."""
    if app.config.get('_PROMOCIONES_TABLES_OK'):
        return True
    try:
        from sqlalchemy import text

        for ddl in _DDL:
            db.session.execute(text(ddl))
        db.session.commit()
        app.config['_PROMOCIONES_TABLES_OK'] = True
        return True
    except Exception as ex:
        db.session.rollback()
        try:
            app.logger.warning('No se pudo crear tablas promociones: %s', ex)
        except Exception:
            pass
        return False


def regla_desde_fila_db(row: Any) -> dict:
    """Normaliza fila SQL/ORM a dict de regla para el motor."""
    def _json(val, default):
        if val is None:
            return default
        if isinstance(val, (dict, list)):
            return val
        try:
            return json.loads(val)
        except Exception:
            return default

    return {
        'id': int(getattr(row, 'id', 0) or 0),
        'codigo': str(getattr(row, 'codigo', '') or ''),
        'nombre': str(getattr(row, 'nombre', '') or ''),
        'tipo': str(getattr(row, 'tipo', '') or ''),
        'prioridad': int(getattr(row, 'prioridad', 100) or 100),
        'vigencia_desde': getattr(row, 'vigencia_desde', None),
        'vigencia_hasta': getattr(row, 'vigencia_hasta', None),
        'activo': bool(getattr(row, 'activo', True)),
        'exclusiva': bool(getattr(row, 'exclusiva', True)),
        'beneficio': _json(getattr(row, 'beneficio_json', None), {}),
        'condiciones': _json(getattr(row, 'condiciones_json', None), {}),
    }


def persistir_aplicaciones_venta(
    db,
    venta_id: int,
    resultado: ResultadoPromociones,
    *,
    reemplazar: bool = True,
) -> None:
    """Guarda aplicaciones en venta_promocion (borra previas si reemplazar)."""
    from sqlalchemy import text

    if reemplazar:
        db.session.execute(
            text('DELETE FROM venta_promocion WHERE venta_id = :vid'),
            {'vid': int(venta_id)},
        )
    now = datetime.utcnow()
    for a in resultado.aplicaciones:
        db.session.execute(
            text(
                """
                INSERT INTO venta_promocion
                    (venta_id, promocion_id, codigo, etiqueta_ticket, monto_descuento,
                     tipo, snapshot_json, creado_en)
                VALUES
                    (:venta_id, :promocion_id, :codigo, :etiqueta, :monto,
                     :tipo, :snap, :creado)
                """
            ),
            {
                'venta_id': int(venta_id),
                'promocion_id': a.promocion_id,
                'codigo': a.codigo[:40],
                'etiqueta': a.etiqueta_ticket[:160],
                'monto': float(a.monto_descuento),
                'tipo': a.tipo[:32],
                'snap': json.dumps(a.snapshot, ensure_ascii=False),
                'creado': now,
            },
        )


def cargar_reglas_activas(db, *, hoy: Optional[date] = None) -> list[dict]:
    """Lee promociones activas vigentes desde BD."""
    from sqlalchemy import text

    dia = _hoy(hoy)
    rows = db.session.execute(
        text(
            """
            SELECT id, codigo, nombre, tipo, prioridad, vigencia_desde, vigencia_hasta,
                   activo, exclusiva, beneficio_json, condiciones_json
            FROM promocion
            WHERE activo = TRUE
              AND (vigencia_desde IS NULL OR vigencia_desde <= :hoy)
              AND (vigencia_hasta IS NULL OR vigencia_hasta >= :hoy)
            ORDER BY prioridad ASC, id ASC
            """
        ),
        {'hoy': dia},
    ).mappings().all()
    return [regla_desde_fila_db(type('R', (), dict(r))()) for r in rows]


def listar_aplicaciones_venta(db, venta_id: int) -> list[dict]:
    """Aplicaciones persistidas de una venta (para ticket/dock)."""
    from sqlalchemy import text

    try:
        rows = db.session.execute(
            text(
                """
                SELECT id, promocion_id, codigo, etiqueta_ticket, monto_descuento, tipo
                FROM venta_promocion
                WHERE venta_id = :vid
                ORDER BY id ASC
                """
            ),
            {'vid': int(venta_id)},
        ).mappings().all()
    except Exception:
        return []
    out = []
    for r in rows:
        out.append({
            'id': r['id'],
            'promocion_id': r['promocion_id'],
            'codigo': r['codigo'],
            'etiqueta_ticket': r['etiqueta_ticket'],
            'monto_descuento': int(round(float(r['monto_descuento'] or 0))),
            'tipo': r['tipo'],
        })
    return out


def descuento_promos_venta_clp(db, venta_id: int) -> int:
    return sum(a['monto_descuento'] for a in listar_aplicaciones_venta(db, venta_id))


def reaplicar_promociones_venta(db, venta, *, cfg: Optional[dict] = None) -> ResultadoPromociones:
    """Recalcula aplicaciones y ajusta venta.monto_total al total post-promo.

    Si el motor está apagado: limpia venta_promocion y deja monto = bruto líneas
    (ya seteado por recalcular_total antes de llamar esto).
    No hace commit — el caller controla la transacción.
    """
    vid = getattr(venta, 'id', None)
    bruto = int(round(float(getattr(venta, 'monto_total', 0) or 0)))
    vacio = ResultadoPromociones(
        subtotal_clp=bruto, descuento_promos_clp=0, total_clp=bruto, aplicaciones=[]
    )
    if not vid:
        return vacio

    activo = motor_promociones_activo(cfg)
    if not activo:
        try:
            from sqlalchemy import text

            db.session.execute(
                text('DELETE FROM venta_promocion WHERE venta_id = :vid'),
                {'vid': int(vid)},
            )
        except Exception:
            pass
        return vacio

    try:
        lineas = lineas_desde_detalles_venta(getattr(venta, 'detalles', None) or [])
        if not lineas:
            persistir_aplicaciones_venta(db, int(vid), vacio, reemplazar=True)
            return vacio
        reglas = cargar_reglas_activas(db)
        resultado = evaluar_promociones(lineas, reglas, activo=True)
        persistir_aplicaciones_venta(db, int(vid), resultado, reemplazar=True)
        venta.monto_total = float(resultado.total_clp)
        if hasattr(venta, 'desglosar_iva'):
            venta.desglosar_iva()
        return resultado
    except Exception:
        # No hacer rollback aquí: el caller (recalcular_total / POS) tiene la TX abierta.
        try:
            app_logger = getattr(db, 'app', None)
            if app_logger is None:
                import logging
                logging.getLogger(__name__).exception('reaplicar_promociones_venta')
        except Exception:
            pass
        return vacio


def listar_promociones_admin(db, *, solo_activas: bool = False) -> list[dict]:
    from sqlalchemy import text

    sql = """
        SELECT id, codigo, nombre, tipo, prioridad, vigencia_desde, vigencia_hasta,
               activo, exclusiva, beneficio_json, condiciones_json, notas
        FROM promocion
    """
    if solo_activas:
        sql += ' WHERE activo = TRUE'
    sql += ' ORDER BY prioridad ASC, id DESC'
    rows = db.session.execute(text(sql)).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d['beneficio'] = json.loads(d.pop('beneficio_json') or '{}')
        d['condiciones'] = json.loads(d.pop('condiciones_json') or '{}')
        out.append(d)
    return out


def obtener_promocion(db, promo_id: int) -> Optional[dict]:
    from sqlalchemy import text

    row = db.session.execute(
        text(
            """
            SELECT id, codigo, nombre, tipo, prioridad, vigencia_desde, vigencia_hasta,
                   activo, exclusiva, beneficio_json, condiciones_json, notas
            FROM promocion WHERE id = :id
            """
        ),
        {'id': int(promo_id)},
    ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d['beneficio'] = json.loads(d.pop('beneficio_json') or '{}')
    d['condiciones'] = json.loads(d.pop('condiciones_json') or '{}')
    return d


def sugerir_codigo_promocion(
    db,
    *,
    tipo: str = 'NXM',
    nombre: str = '',
    beneficio: Optional[dict] = None,
    excluir_id: Optional[int] = None,
) -> str:
    """
    Código interno tipo retail (Walmart/Líder): lo genera el sistema.
    El ticket usa `nombre`; este código es solo para admin / auditoría.
    """
    import re
    from sqlalchemy import text

    tipo_u = (tipo or 'NXM').strip().upper()
    ben = beneficio or {}
    if tipo_u == 'NXM':
        try:
            n = int(ben.get('n') or 2)
            m = int(ben.get('m') or 1)
        except (TypeError, ValueError):
            n, m = 2, 1
        prefix = f'{n}X{m}'
    elif tipo_u == 'SEGUNDO_PCT':
        try:
            pct = int(float(ben.get('pct') or 50))
        except (TypeError, ValueError):
            pct = 50
        prefix = f'2PCT{pct}'
    elif tipo_u == 'ESCALA_QTY':
        prefix = 'ESCALA'
    elif tipo_u == 'PRECIO_PAR':
        try:
            pp = int(ben.get('precio_pack') or ben.get('precio_par') or 0)
        except (TypeError, ValueError):
            pp = 0
        prefix = f'PAR{pp}' if pp > 0 else 'PAR'
    else:
        prefix = 'PROMO'

    slug = re.sub(r'[^A-Z0-9]+', '-', (nombre or '').upper())
    slug = re.sub(r'-+', '-', slug).strip('-')[:14]
    # Evitar "2X1-2X1-TORNILLOS" si el nombre ya trae el patrón
    if slug.startswith(prefix + '-'):
        slug = slug[len(prefix) + 1 :]
    elif slug == prefix:
        slug = ''
    base = f'{prefix}-{slug}' if slug else f'{prefix}-{datetime.utcnow().strftime("%y%m%d")}'
    base = base[:36].rstrip('-') or prefix

    candidato = base
    for i in range(0, 50):
        if i > 0:
            candidato = f'{base}-{i + 1}'[:40]
        sql = 'SELECT id FROM promocion WHERE codigo = :c'
        params: dict[str, Any] = {'c': candidato}
        if excluir_id:
            sql += ' AND id <> :id'
            params['id'] = int(excluir_id)
        row = db.session.execute(text(sql), params).first()
        if not row:
            return candidato
    return f'{prefix}-{int(datetime.utcnow().timestamp())}'[:40]


def guardar_promocion(db, data: dict, *, promo_id: Optional[int] = None) -> int:
    """Inserta o actualiza. data ya normalizado."""
    from sqlalchemy import text

    def _as_date(v):
        if not v:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        return date.fromisoformat(str(v)[:10])

    codigo = str(data.get('codigo') or '').strip().upper()
    if not codigo:
        codigo = sugerir_codigo_promocion(
            db,
            tipo=str(data.get('tipo') or 'NXM'),
            nombre=str(data.get('nombre') or ''),
            beneficio=data.get('beneficio') or {},
            excluir_id=promo_id,
        )
    data = {**data, 'codigo': codigo}

    now = datetime.utcnow()
    payload = {
        'codigo': str(data['codigo'])[:40],
        'nombre': str(data['nombre'])[:120],
        'tipo': str(data['tipo'])[:32],
        'prioridad': int(data.get('prioridad') or 100),
        'vigencia_desde': _as_date(data.get('vigencia_desde')),
        'vigencia_hasta': _as_date(data.get('vigencia_hasta')),
        'activo': bool(data.get('activo', True)),
        'exclusiva': bool(data.get('exclusiva', True)),
        'beneficio_json': json.dumps(data.get('beneficio') or {}, ensure_ascii=False),
        'condiciones_json': json.dumps(data.get('condiciones') or {}, ensure_ascii=False),
        'notas': (data.get('notas') or None),
        'actualizado_en': now,
    }
    if promo_id:
        payload['id'] = int(promo_id)
        db.session.execute(
            text(
                """
                UPDATE promocion SET
                    codigo=:codigo, nombre=:nombre, tipo=:tipo, prioridad=:prioridad,
                    vigencia_desde=:vigencia_desde, vigencia_hasta=:vigencia_hasta,
                    activo=:activo, exclusiva=:exclusiva,
                    beneficio_json=:beneficio_json, condiciones_json=:condiciones_json,
                    notas=:notas, actualizado_en=:actualizado_en
                WHERE id=:id
                """
            ),
            payload,
        )
        return int(promo_id)
    payload['creado_en'] = now
    row = db.session.execute(
        text(
            """
            INSERT INTO promocion
                (codigo, nombre, tipo, prioridad, vigencia_desde, vigencia_hasta,
                 activo, exclusiva, beneficio_json, condiciones_json, notas,
                 creado_en, actualizado_en)
            VALUES
                (:codigo, :nombre, :tipo, :prioridad, :vigencia_desde, :vigencia_hasta,
                 :activo, :exclusiva, :beneficio_json, :condiciones_json, :notas,
                 :creado_en, :actualizado_en)
            RETURNING id
            """
        ),
        payload,
    ).first()
    return int(row[0])


def toggle_promocion_activa(db, promo_id: int) -> Optional[bool]:
    from sqlalchemy import text

    row = db.session.execute(
        text('SELECT activo FROM promocion WHERE id = :id'),
        {'id': int(promo_id)},
    ).first()
    if not row:
        return None
    nuevo = not bool(row[0])
    db.session.execute(
        text('UPDATE promocion SET activo = :a, actualizado_en = :u WHERE id = :id'),
        {'a': nuevo, 'u': datetime.utcnow(), 'id': int(promo_id)},
    )
    return nuevo

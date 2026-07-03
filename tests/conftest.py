"""
Fixtures compartidas para la suite end-to-end del ERP LhexIA v4.

Fixtures session-scope para datos compartidos, helpers reutilizables,
factory functions, app_client para pruebas HTTP, y utilidades de audit.

IMPORTANTE: Esta suite NUNCA debe ejecutarse contra la BD de produccion.
La guardia _verificar_no_es_produccion() aborta el proceso si detecta
que DATABASE_URL apunta a un host de produccion conocido.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ── Guardia anti-produccion ─────────────────────────────────────────
_HOSTS_PRODUCCION = [
    'neon.tech', 'render.com', 'railway.app', 'supabase.co',
    'amazonaws.com', 'azure.com', 'elephantsql.com',
]


def _verificar_no_es_produccion():
    """Aborta si la BD parece ser de produccion."""
    uri = (os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI') or '').lower()
    if os.getenv('ALLOW_TESTS_ON_REMOTE') == '1':
        return
    for host in _HOSTS_PRODUCCION:
        if host in uri:
            raise RuntimeError(
                f'\n\n*** ABORTADO: DATABASE_URL contiene "{host}" ***\n'
                f'No se pueden ejecutar tests contra la BD de produccion.\n'
                f'Opciones:\n'
                f'  1. Usar BD local (mysql/postgres localhost)\n'
                f'  2. Crear .env.qa con DATABASE_URL apuntando a BD de QA\n'
                f'  3. export ALLOW_TESTS_ON_REMOTE=1 (bajo tu responsabilidad)\n'
            )


_verificar_no_es_produccion()

from tests.sql_test_helpers import sa_text_in

import app as m

db = m.db
QA_USER = 'QA_TEST'


# ── Blindaje de config empresa ──────────────────────────────────────
@pytest.fixture(scope='session', autouse=True)
def _preservar_empresa_config():
    """Respalda data/empresa_config.json y lo restaura al cerrar la sesion.

    Varios tests escriben la config real compartida via guardar_config_empresa()
    (p.ej. cierre_caja_modo, razon_social='QA', modulos en 0). Sin este blindaje,
    correr la suite deja el config dev contaminado con valores QA. Se respaldan
    los bytes crudos para preservar formato/encoding exactos.
    """
    try:
        ruta = m._ruta_config_empresa()
    except Exception:
        ruta = None
    respaldo = None
    if ruta and os.path.exists(ruta):
        try:
            with open(ruta, 'rb') as fh:
                respaldo = fh.read()
        except Exception:
            respaldo = None
    try:
        yield
    finally:
        if ruta and respaldo is not None:
            try:
                with open(ruta, 'wb') as fh:
                    fh.write(respaldo)
            except Exception:
                pass
        # Invalida la cache en memoria para que la proxima lectura tome el archivo restaurado.
        try:
            m._CONFIG_EMPRESA_CACHE = None
            m._CONFIG_EMPRESA_CACHE_AT = 0.0
        except Exception:
            pass


# ── Datos semilla ───────────────────────────────────────────────────
PRODUCTOS_TEST = [
    dict(nombre='TEST Martillo carpintero 16oz Stanley', codigo_barra='TEST-MART-001',
         codigo_interno='T-MART-001', precio_compra=8500, precio_venta=14990, precio_venta_sd=14990,
         stock=50, unidad='Unidad', categoria='Herramientas', subcategoria='Martillos', activo=True),
    dict(nombre='TEST Clavo 2.5" caja 1kg', codigo_barra='TEST-CLAV-002',
         codigo_interno='T-CLAV-002', precio_compra=1200, precio_venta=2490, precio_venta_sd=2490,
         stock=200, unidad='Caja', categoria='Fijaciones', subcategoria='Clavos', activo=True),
    dict(nombre='TEST Pintura latex blanco 1gal Sherwin', codigo_barra='TEST-PINT-003',
         codigo_interno='T-PINT-003', precio_compra=15000, precio_venta=24990, precio_venta_sd=24990,
         stock=30, unidad='Galon', categoria='Pinturas', subcategoria='Latex', activo=True),
    dict(nombre='TEST Cable electrico 2.5mm 100mt', codigo_barra='TEST-CABL-004',
         codigo_interno='T-CABL-004', precio_compra=22000, precio_venta=38990, precio_venta_sd=38990,
         stock=15, unidad='Rollo', categoria='Electrico', subcategoria='Cables', activo=True),
    dict(nombre='TEST Tornillo madera 6x1.5" 100un', codigo_barra='TEST-TORN-005',
         codigo_interno='T-TORN-005', precio_compra=800, precio_venta=1690, precio_venta_sd=1690,
         stock=300, unidad='Bolsa', categoria='Fijaciones', subcategoria='Tornillos', activo=True),
]

CLIENTE_TEST = dict(
    rut='11.111.111-1', nombre='TEST Constructora Demo SpA', giro='Construccion',
    direccion='Av. Test 1234, Santiago', telefono='+56998765432',
    correo='test@constructorademo.cl', limite_credito=1_000_000,
)

PROVEEDOR_TEST = dict(
    nombre='TEST Distribuidora Ferretera Nacional S.A.',
    contacto='Juan Perez', telefono='+56912345678', email='test@proveedortest.cl',
)


def _borrar_cliente_test(sa_text):
    """Borra el cliente de test y todas sus dependencias FK en orden seguro."""
    db.session.rollback()
    try:
        cli_ids = [r[0] for r in db.session.execute(
            sa_text("SELECT id FROM clientes WHERE rut = :r"),
            {'r': CLIENTE_TEST['rut']}).fetchall()]
        if not cli_ids:
            return
        ct = tuple(cli_ids)
        for dep in ('cliente_prediccion_log', 'c360_llamadas_snapshot_dia', 'c360_proactiva_ofertas'):
            try:
                db.session.execute(sa_text_in(
                    f"DELETE FROM {dep} WHERE cliente_id IN :c", "c"), {'c': list(ct)})
            except Exception:
                db.session.rollback()
        vids_cli = [r[0] for r in db.session.execute(
            sa_text_in("SELECT id FROM ventas WHERE cliente_id IN :c", "c"), {'c': list(ct)}).fetchall()]
        if vids_cli:
            vt = list(vids_cli)
            for tbl in ('ventas_cuotas_credito', 'ventas_a_pedido', 'detalle_ventas', 'movimientos_inventario'):
                try:
                    col = 'venta_id' if tbl in ('ventas_cuotas_credito', 'ventas_a_pedido') else \
                          'id_venta' if tbl == 'detalle_ventas' else 'referencia_id'
                    db.session.execute(sa_text_in(
                        f"DELETE FROM {tbl} WHERE {col} IN :v", "v"), {'v': vt})
                except Exception:
                    db.session.rollback()
            try:
                db.session.execute(sa_text_in(
                    "DELETE FROM agente_ejecuciones WHERE venta_id IN :v", "v"), {'v': vt})
            except Exception:
                db.session.rollback()
            try:
                db.session.execute(sa_text_in("DELETE FROM ventas WHERE id IN :v", "v"), {'v': vt})
            except Exception:
                db.session.rollback()
        for dep in ('abonos_credito', 'saldo_favor_movimientos'):
            try:
                db.session.execute(sa_text_in(
                    f"DELETE FROM {dep} WHERE cliente_id IN :c", "c"), {'c': list(ct)})
            except Exception:
                db.session.rollback()
        try:
            db.session.execute(sa_text_in("DELETE FROM clientes WHERE id IN :c", "c"), {'c': list(ct)})
            db.session.commit()
        except Exception:
            db.session.rollback()
    except Exception:
        db.session.rollback()


# ── Limpieza FK-safe ───────────────────────────────────────────────
def _borrar_agente_ejecuciones_por_ventas_qa(sa_text, usuarios: tuple[str, ...]) -> None:
    """FK agente_ejecuciones.venta_id — antes de DELETE ventas."""
    try:
        db.session.execute(
            sa_text_in(
                "DELETE FROM agente_ejecuciones WHERE venta_id IN ("
                "SELECT id FROM ventas WHERE usuario IN :u)",
                "u",
            ),
            {'u': list(usuarios)},
        )
    except Exception:
        db.session.rollback()


def _limpiar_datos_qa():
    from sqlalchemy import text as sa_text
    from tests.qa_catalogo_casuisticas import QA_CAS_USER, limpiar_catalogo_casuisticas

    db.session.rollback()
    try:
        try:
            db.session.execute(
                sa_text("DELETE FROM agente_ejecuciones WHERE dedupe_key LIKE :p"),
                {'p': 'vertex:maestro:%'},
            )
        except Exception:
            db.session.rollback()

        limpiar_catalogo_casuisticas(db, m, sa_text)
        _usuarios_qa = (QA_USER, QA_CAS_USER)
        _borrar_agente_ejecuciones_por_ventas_qa(sa_text, _usuarios_qa)
        vids = [r[0] for r in db.session.execute(
            sa_text_in("SELECT id FROM ventas WHERE usuario IN :u", "u"),
            {'u': list(_usuarios_qa)}).fetchall()]
        if vids:
            vt = list(vids)
            db.session.execute(sa_text_in("DELETE FROM ventas_cuotas_credito WHERE venta_id IN :v", "v"), {'v': vt})
            try:
                db.session.execute(sa_text_in("DELETE FROM ventas_a_pedido WHERE venta_id IN :v", "v"), {'v': vt})
            except Exception:
                db.session.rollback()
            db.session.execute(sa_text_in("DELETE FROM detalle_ventas WHERE id_venta IN :v", "v"), {'v': vt})
            db.session.execute(sa_text("DELETE FROM movimiento_caja WHERE concepto LIKE :p"), {'p': '%QA test%'})
            db.session.execute(sa_text_in("DELETE FROM ventas WHERE id IN :v", "v"), {'v': vt})

        pids = [r[0] for r in db.session.execute(
            sa_text("SELECT id FROM productos WHERE codigo_barra LIKE 'TEST-%' OR codigo_barra LIKE '99988877760%'")
        ).fetchall()]
        if pids:
            pt = list(pids)
            dv_vids = [r[0] for r in db.session.execute(
                sa_text_in("SELECT DISTINCT id_venta FROM detalle_ventas WHERE id_producto IN :p", "p"),
                {'p': pt}).fetchall()]
            if dv_vids:
                dvt = list(dv_vids)
                db.session.execute(sa_text_in("DELETE FROM ventas_cuotas_credito WHERE venta_id IN :v", "v"), {'v': dvt})
                try:
                    db.session.execute(sa_text_in("DELETE FROM ventas_a_pedido WHERE venta_id IN :v", "v"), {'v': dvt})
                except Exception:
                    db.session.rollback()
                db.session.execute(sa_text_in("DELETE FROM detalle_ventas WHERE id_venta IN :v", "v"), {'v': dvt})
                db.session.execute(
                    sa_text_in("DELETE FROM agente_ejecuciones WHERE venta_id IN :v", "v"), {'v': dvt})
                db.session.execute(sa_text_in("DELETE FROM ventas WHERE id IN :v", "v"), {'v': dvt})
            db.session.execute(sa_text_in("DELETE FROM movimientos_inventario WHERE id_producto IN :p", "p"), {'p': pt})
            try:
                db.session.execute(
                    sa_text_in("DELETE FROM bitacora_piloto_mostrador WHERE producto_id IN :p", "p"),
                    {'p': pt},
                )
            except Exception:
                db.session.rollback()
            try:
                db.session.execute(
                    sa_text_in("DELETE FROM bitacora_precios_venta WHERE producto_id IN :p", "p"),
                    {'p': pt},
                )
            except Exception:
                db.session.rollback()
            db.session.execute(sa_text_in("DELETE FROM stock_por_almacen WHERE id_producto IN :p", "p"), {'p': pt})
            db.session.execute(sa_text_in("DELETE FROM detalle_recepcion WHERE producto_id IN :p", "p"), {'p': pt})
            db.session.execute(sa_text_in("DELETE FROM detalle_orden_compra WHERE producto_id IN :p", "p"), {'p': pt})
            try:
                db.session.execute(
                    sa_text_in("DELETE FROM producto_codigo_proveedor WHERE producto_id IN :p", "p"),
                    {'p': pt},
                )
            except Exception:
                db.session.rollback()
            try:
                db.session.execute(
                    sa_text_in("DELETE FROM producto_codigo_escaneo WHERE producto_id IN :p", "p"),
                    {'p': pt},
                )
            except Exception:
                db.session.rollback()
            db.session.execute(sa_text_in("DELETE FROM productos WHERE id IN :p", "p"), {'p': pt})

        prvs = [r[0] for r in db.session.execute(
            sa_text("SELECT id FROM proveedores WHERE nombre LIKE 'TEST %'")).fetchall()]
        if prvs:
            pt2 = list(prvs)
            recv_ids = [r[0] for r in db.session.execute(
                sa_text_in("SELECT id FROM recepciones_compra WHERE proveedor_id IN :i", "i"),
                {'i': pt2}).fetchall()]
            if recv_ids:
                try:
                    db.session.execute(
                        sa_text_in("DELETE FROM detalle_recepcion WHERE recepcion_id IN :r", "r"),
                        {'r': list(recv_ids)},
                    )
                except Exception:
                    db.session.rollback()
            try:
                db.session.execute(
                    sa_text_in("DELETE FROM recepciones_compra WHERE proveedor_id IN :i", "i"), {'i': pt2})
            except Exception:
                db.session.rollback()
            try:
                db.session.execute(sa_text_in("DELETE FROM ordenes_compra WHERE proveedor_id IN :i", "i"), {'i': pt2})
            except Exception:
                db.session.rollback()
            try:
                db.session.execute(sa_text_in("DELETE FROM proveedores WHERE id IN :i", "i"), {'i': pt2})
            except Exception:
                db.session.rollback()

        _borrar_cliente_test(sa_text)

        try:
            db.session.execute(sa_text(
                "DELETE FROM erp_audit_log WHERE usuario = :u"), {'u': QA_USER})
        except Exception:
            pass

        qa_caja = m.Caja.query.filter_by(usuario_apertura=QA_USER, estado='Abierta').first()
        if qa_caja:
            m.MovimientoCaja.query.filter_by(caja_id=qa_caja.id).delete(synchronize_session=False)
            qa_caja.estado = 'Cerrada'
            qa_caja.fecha_cierre = datetime.now()

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# ── Fixtures ────────────────────────────────────────────────────────
@pytest.fixture(scope='session')
def app_ctx():
    with m.app.app_context():
        db.session.rollback()
        if hasattr(m, '_asegurar_columnas_caja_cuadratura'):
            m._asegurar_columnas_caja_cuadratura()
        if hasattr(m, '_asegurar_columnas_transferencia_caja'):
            m._asegurar_columnas_transferencia_caja()
        if hasattr(m, '_asegurar_tabla_transferencia_correo'):
            m._asegurar_tabla_transferencia_correo()
        if hasattr(m, '_asegurar_tabla_agente_ejecuciones'):
            m._asegurar_tabla_agente_ejecuciones()
        if hasattr(m, '_asegurar_tablas_chilemat_relaciones'):
            m._asegurar_tablas_chilemat_relaciones()
        db.session.rollback()
        yield m.app


@pytest.fixture(scope='session', autouse=True)
def limpieza_qa(app_ctx):
    _limpiar_datos_qa()
    yield
    _limpiar_datos_qa()


_ADMIN_ROLES_QA = ['Admin', 'admin', 'Administrador', 'administrador', 'SuperAdmin']
_PERFILES_BLOQUEO_CLAVE = ('FORZAR_CLAVE', 'ACTIVO_FORZAR_CLAVE')


def _normalizar_admin_qa_para_http():
    """Evita redirects a /cambiar_password en suite HTTP (orden de tests)."""
    admin = m.Usuario.query.join(m.Rol).filter(m.Rol.nombre.in_(_ADMIN_ROLES_QA)).first()
    if admin and m.usuario_requiere_cambio_clave(admin):
        admin.perfil = 'ACTIVO'
        db.session.commit()


def _asegurar_caja_abierta_qa():
    """Caja Abierta con fecha de hoy (evita redirect a cerrar_caja en @caja_requerida)."""
    ahora = datetime.now()
    caja = m.Caja.query.filter_by(estado='Abierta').order_by(m.Caja.id.desc()).first()
    if caja:
        fa = caja.fecha_apertura.date() if caja.fecha_apertura else None
        if fa and fa < ahora.date():
            caja.fecha_apertura = ahora
            db.session.commit()
        return caja
    caja = m.Caja(
        monto_inicial=50000,
        usuario_apertura=QA_USER,
        estado='Abierta',
        fecha_apertura=ahora,
    )
    db.session.add(caja)
    db.session.commit()
    return caja


@pytest.fixture(autouse=True)
def _estado_qa_http_listo(app_ctx):
    """Antes de cada test: admin sin FORZAR_CLAVE y caja abierta para @caja_requerida."""
    db.session.rollback()
    try:
        _normalizar_admin_qa_para_http()
        _asegurar_caja_abierta_qa()
    except Exception:
        db.session.rollback()
        raise
    yield
    db.session.rollback()


@pytest.fixture(scope='session')
def app_client(app_ctx):
    """Flask test client autenticado como admin para pruebas HTTP."""
    m.app.config['TESTING'] = True
    m.app.config['WTF_CSRF_ENABLED'] = False
    m.app.config['LOGIN_DISABLED'] = False

    admin = (
        m.Usuario.query.join(m.Rol)
        .filter(
            m.Rol.nombre.in_(_ADMIN_ROLES_QA),
            db.or_(
                m.Usuario.perfil.is_(None),
                ~m.Usuario.perfil.in_(_PERFILES_BLOQUEO_CLAVE),
            ),
        )
        .first()
    )
    if not admin:
        admin = m.Usuario.query.join(m.Rol).filter(m.Rol.nombre.in_(_ADMIN_ROLES_QA)).first()
    if not admin:
        admin = m.Usuario.query.first()
    _normalizar_admin_qa_para_http()

    if admin:
        admin.set_password('test123')
        db.session.commit()

    client = m.app.test_client()
    if admin:
        r = client.post(
            '/login',
            data={'correo': admin.correo, 'password': 'test123'},
            follow_redirects=True,
        )
        assert r.status_code in (200, 302)
    return client


@pytest.fixture(scope='session')
def catalogo_casuisticas_qa(app_ctx, limpieza_qa, productos_con_stock):
    """Productos/clientes SD-PRUEBA para flujos venta→caja→entrega."""
    from tests.qa_catalogo_casuisticas import (
        BC_ARENA,
        BC_CEMENTO,
        BC_OFERTA_CLAVO,
        BC_PVC,
        upsert_catalogo_casuisticas,
    )

    productos, clientes = upsert_catalogo_casuisticas(db, m)
    by_barcode = {p.codigo_barra: p for p in productos}
    by_rut = {c.rut: c for c in clientes}
    return dict(
        productos=productos,
        clientes=clientes,
        by_barcode=by_barcode,
        cliente_saldo_favor=by_rut.get('22.222.222-2'),
        cliente_obra=by_rut.get('33.333.333-3'),
        cliente_credito_cas=by_rut.get('44.444.444-4'),
        oferta_clavo=by_barcode.get(BC_OFERTA_CLAVO),
        cemento=by_barcode.get(BC_CEMENTO),
        arena=by_barcode.get(BC_ARENA),
        pvc=by_barcode.get(BC_PVC),
    )


@pytest.fixture(scope='session')
def productos_con_stock(app_ctx, limpieza_qa):
    productos = []
    for data in PRODUCTOS_TEST:
        p = m.Producto.query.filter_by(codigo_barra=data['codigo_barra']).first()
        if not p:
            p = m.Producto(**data)
            db.session.add(p)
        else:
            for k, v in data.items():
                setattr(p, k, v)
        productos.append(p)
    db.session.flush()

    aid = m.id_almacen_tienda()
    if aid:
        for p in productos:
            spa = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid).first()
            if not spa:
                db.session.add(m.StockPorAlmacen(id_producto=p.id, id_almacen=aid, cantidad=p.stock or 0))
            else:
                spa.cantidad = p.stock or 0
    db.session.commit()
    return productos


@pytest.fixture(scope='session')
def cliente_credito(app_ctx, limpieza_qa):
    cli = m.Cliente.query.filter_by(rut=CLIENTE_TEST['rut']).first()
    if not cli:
        cli = m.Cliente(**CLIENTE_TEST)
        db.session.add(cli)
    else:
        cli.saldo_deudor = 0
        cli.limite_credito = CLIENTE_TEST['limite_credito']
    db.session.commit()
    return cli


@pytest.fixture(scope='session')
def proveedor_test(app_ctx, limpieza_qa):
    prov = m.Proveedor.query.filter(m.Proveedor.nombre.like('TEST %')).first()
    if not prov:
        prov = m.Proveedor(**PROVEEDOR_TEST)
        db.session.add(prov)
        db.session.commit()
    return prov


@pytest.fixture(scope='session')
def caja_abierta(app_ctx, limpieza_qa):
    return _asegurar_caja_abierta_qa()


@pytest.fixture()
def cliente_final(app_ctx):
    return m.obtener_o_crear_cliente_final()


@pytest.fixture()
def audit_snapshot(app_ctx):
    """Captura el max(id) de erp_audit_log antes del test.

    Retorna funcion filtro para obtener solo los registros nuevos.
    """
    m._asegurar_tabla_erp_audit_log()
    from sqlalchemy import text as sa_text
    try:
        row = db.session.execute(sa_text(
            "SELECT COALESCE(MAX(id), 0) FROM erp_audit_log")).scalar()
    except Exception:
        row = 0
    baseline = row or 0

    def get_new_entries(evento=None):
        q = m.ErpAuditLog.query.filter(m.ErpAuditLog.id > baseline)
        if evento:
            q = q.filter(m.ErpAuditLog.evento == evento)
        return q.all()

    return get_new_entries


# ── Helpers / Factories ─────────────────────────────────────────────
def crear_venta_pendiente(productos_cantidades, caja, cliente, punto_retiro='Tienda', usuario=None):
    venta = m.Venta(
        fecha=datetime.now(), monto_total=0, usuario=usuario or QA_USER,
        estado='Abierta', caja_id=caja.id, cliente_id=cliente.id,
        punto_retiro=punto_retiro)
    db.session.add(venta)
    db.session.flush()
    dets = []
    for item in productos_cantidades:
        if len(item) == 3:
            prod, qty, retiro_linea = item
        else:
            prod, qty = item
            retiro_linea = punto_retiro
        pu = float(m.precio_efectivo_pos_producto(prod) or prod.precio_venta or 0)
        d = m.DetalleVenta(
            id_venta=venta.id, id_producto=prod.id,
            cantidad=qty, precio_unitario=pu,
            subtotal=qty * pu,
            punto_retiro_linea=(retiro_linea or punto_retiro or 'Tienda').strip())
        db.session.add(d)
        dets.append(d)
    venta.recalcular_total()
    retiros = {(getattr(d, 'punto_retiro_linea', None) or punto_retiro or 'Tienda').strip() for d in dets}
    if len(retiros) > 1:
        venta.punto_retiro = 'Mixto'
    venta.estado = 'Pendiente'
    db.session.commit()
    return venta, dets


def ultima_venta_pendiente(caja_id=None):
    q = m.Venta.query.filter_by(estado='Pendiente').order_by(m.Venta.id.desc())
    if caja_id:
        q = q.filter_by(caja_id=caja_id)
    return q.first()


def procesar_cobro_http(app_client, venta, *, metodo_pago='Efectivo', monto_recibido=None,
                        usar_saldo_favor=0, tipo_documento='Boleta'):
    total = float(venta.monto_total or 0)
    if monto_recibido is None:
        monto_recibido = total + 500 if metodo_pago != 'Credito' else 0
    return app_client.post(
        f'/procesar_cobro_caja/{venta.id}',
        data={
            'metodo_pago': metodo_pago,
            'tipo_documento': tipo_documento,
            'monto_recibido': str(int(monto_recibido)),
            'usar_saldo_favor': str(int(usar_saldo_favor or 0)),
        },
        follow_redirects=True,
    )


def pos_escanear_agregar(app_client, codigo_barra, *, punto_retiro_linea=None, a_pedido=False):
    payload = {'codigo': codigo_barra}
    if punto_retiro_linea:
        payload['punto_retiro_linea'] = punto_retiro_linea
    if a_pedido:
        payload['a_pedido'] = True
    return app_client.post(
        '/api/pos/escanear-agregar',
        json=payload,
        content_type='application/json',
    )


def pos_emitir_vale_http(app_client, lineas, *, cliente_rut=None, cliente_final=True,
                         punto_retiro='Tienda', compromiso_confirmado=False):
    """lineas: lista de dict {codigo, qty?, retiro?, a_pedido?} o codigos str."""
    app_client.get('/punto_venta')
    for linea in lineas:
        if isinstance(linea, str):
            codigo, qty, retiro, a_ped = linea, 1, None, False
        else:
            codigo = linea['codigo']
            qty = int(linea.get('qty') or 1)
            retiro = linea.get('retiro')
            a_ped = bool(linea.get('a_pedido'))
        for _ in range(qty):
            r = pos_escanear_agregar(app_client, codigo, punto_retiro_linea=retiro, a_pedido=a_ped)
            if r.status_code == 409 and (r.get_json() or {}).get('error') == 'en_vale_pendiente':
                return r
            if r.status_code != 200:
                return r
    data = {
        'punto_retiro': punto_retiro,
        'compromiso_confirmado': '1' if compromiso_confirmado else '',
    }
    if cliente_final:
        data['cliente_final'] = '1'
    else:
        data['cliente_final'] = '0'
        data['cliente_rut'] = cliente_rut or ''
        data['cliente_nombre'] = data.get('cliente_nombre') or 'Cliente QA'
    return app_client.post('/finalizar_venta', data=data, follow_redirects=False)


def cobrar_venta_efectivo(venta, caja):
    """Cobro QA alineado a producción: use case core + descontar stock/kardex."""
    from core.application.bootstrap import (
        build_descontar_stock_cobro_service,
        build_procesar_cobro_use_case,
    )
    from core.application.ventas.commands import ProcesarCobroCommand
    from services.venta_service import transaccion_critica

    monto_rec = float(venta.monto_total or 0) + 10
    stock_svc = build_descontar_stock_cobro_service()
    lineas = stock_svc.preparar_lineas(venta.id)

    with transaccion_critica():
        build_procesar_cobro_use_case(transaccion_critica=None).execute(
            ProcesarCobroCommand(
                venta_id=venta.id,
                caja_id=caja.id,
                metodo_pago='Efectivo',
                tipo_documento='Boleta',
                monto_recibido=monto_rec,
                saldo_favor_usado=0.0,
            )
        )
        stock_svc.aplicar_descontos(venta.id, lineas, 'Efectivo', QA_USER)
        vr = db.session.get(m.Venta, venta.id)
        db.session.add(
            m.MovimientoCaja(
                caja_id=caja.id,
                tipo='Ingreso',
                concepto=f'Cobro vale #{venta.id} (QA test)',
                monto=vr.monto_total,
                usuario_registro=QA_USER,
            )
        )
    db.session.commit()
    db.session.refresh(venta)


def cobrar_venta_efectivo_con_audit(venta, caja):
    """Cobra venta y registra audit_log como lo hace el cobro real."""
    cobrar_venta_efectivo(venta, caja)
    m._audit_log(
        'cobro_vale', 'venta', venta.id,
        usuario=QA_USER,
        datos_antes={'estado': 'Pendiente'},
        datos_despues={'estado': 'Pagado', 'metodo_pago': 'Efectivo'})
    db.session.commit()


def anular_venta_con_audit(venta, motivo='QA anulacion'):
    """Anula venta, revierte stock tienda, registra audit_log."""
    from services.venta_service import transaccion_critica
    with transaccion_critica():
        datos_antes = {'estado': venta.estado}
        venta.estado = 'Anulada'
        venta.motivo_anulacion = motivo
        venta.fecha_anulacion = datetime.now()
        venta.usuario_anulacion = QA_USER
        aid_t = m.id_almacen_tienda() or 1
        for det in venta.detalles:
            prod = db.session.get(m.Producto, det.id_producto)
            consumo = int(det.cantidad * m._factor_venta_a_stock(prod))
            m.incrementar_stock_venta_tienda(prod, consumo)
            m.registrar_movimiento_kardex(
                id_producto=prod.id, tipo_movimiento='ENTRADA', cantidad=consumo,
                motivo=f'Anulacion QA #{venta.id}', usuario=QA_USER, id_almacen=aid_t,
                referencia_tipo='venta', referencia_id=venta.id)
        m._audit_log(
            'anular_vale', 'venta', venta.id,
            usuario=QA_USER,
            datos_antes=datos_antes,
            datos_despues={'estado': 'Anulada', 'motivo': motivo})
    db.session.commit()


def simular_comando_voz(vale_id, producto_codigo, cantidad):
    """Simula despacho de voz sin audio real."""
    venta = db.session.get(m.Venta, vale_id)
    assert venta, f'Venta #{vale_id} no encontrada'
    producto = m.Producto.query.filter_by(codigo_barra=producto_codigo).first()
    assert producto, f'Producto {producto_codigo} no encontrado'
    det = m.DetalleVenta.query.filter_by(
        id_venta=vale_id, id_producto=producto.id).first()
    assert det, f'Detalle no encontrado para prod #{producto.id} en venta #{vale_id}'

    aid_b = m.id_almacen_bodega()
    assert aid_b, 'No hay almacen BODEGA'
    spa = m.StockPorAlmacen.query.filter_by(
        id_producto=producto.id, id_almacen=aid_b).first()
    assert spa and (spa.cantidad or 0) >= cantidad, \
        f'Stock bodega insuficiente: {spa.cantidad if spa else 0} < {cantidad}'

    from services.venta_service import transaccion_critica
    with transaccion_critica():
        desp = json.loads(venta.bodega_despacho_json or '{}')
        prev = int(desp.get(str(det.id), 0))
        desp[str(det.id)] = prev + cantidad
        venta.bodega_despacho_json = json.dumps(desp)
        venta.bodega_despacho_ultimo_at = datetime.now()
        total_desp = sum(int(v) for v in desp.values())
        total_req = sum(d.cantidad for d in venta.detalles)
        venta.bodega_despacho_estado = 'DESPACHADO' if total_desp >= total_req else 'SALIDA_PARCIAL'
        spa.cantidad -= cantidad
        m.registrar_movimiento_kardex(
            id_producto=producto.id, tipo_movimiento='SALIDA',
            cantidad=cantidad, motivo=f'Voz QA #{vale_id}',
            usuario=QA_USER, id_almacen=aid_b,
            referencia_tipo='venta', referencia_id=vale_id)
    db.session.commit()
    return {'despachado': desp, 'estado': venta.bodega_despacho_estado, 'stock_bodega': spa.cantidad}


def asegurar_stock_bodega(producto, cantidad_exacta=100):
    """Fuerza el stock de bodega a un valor exacto (no condicional)."""
    aid_b = m.id_almacen_bodega()
    spa = m.StockPorAlmacen.query.filter_by(id_producto=producto.id, id_almacen=aid_b).first()
    if not spa:
        spa = m.StockPorAlmacen(id_producto=producto.id, id_almacen=aid_b, cantidad=cantidad_exacta)
        db.session.add(spa)
    else:
        spa.cantidad = cantidad_exacta
    db.session.commit()
    db.session.expire(spa)
    return spa


def trasladar_stock(producto, origen_almacen_id, destino_almacen_id, cantidad):
    """Traslada stock entre almacenes con kardex bidireccional."""
    from sqlalchemy import text as sa_text
    from services.venta_service import transaccion_critica

    db.session.expire_all()

    with transaccion_critica():
        db.session.execute(sa_text(
            "UPDATE stock_por_almacen SET cantidad = cantidad - :q "
            "WHERE id_producto = :p AND id_almacen = :a"
        ), {'q': cantidad, 'p': producto.id, 'a': origen_almacen_id})

        exists = db.session.execute(sa_text(
            "SELECT 1 FROM stock_por_almacen WHERE id_producto = :p AND id_almacen = :a"
        ), {'p': producto.id, 'a': destino_almacen_id}).scalar()
        if exists:
            db.session.execute(sa_text(
                "UPDATE stock_por_almacen SET cantidad = cantidad + :q "
                "WHERE id_producto = :p AND id_almacen = :a"
            ), {'q': cantidad, 'p': producto.id, 'a': destino_almacen_id})
        else:
            db.session.execute(sa_text(
                "INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad) VALUES (:p, :a, :q)"
            ), {'p': producto.id, 'a': destino_almacen_id, 'q': cantidad})

        m.registrar_movimiento_kardex(
            id_producto=producto.id, tipo_movimiento='SALIDA', cantidad=cantidad,
            motivo=f'Traslado QA alm{origen_almacen_id}->alm{destino_almacen_id}',
            usuario=QA_USER, id_almacen=origen_almacen_id,
            referencia_tipo='traslado', referencia_id=0)
        m.registrar_movimiento_kardex(
            id_producto=producto.id, tipo_movimiento='ENTRADA', cantidad=cantidad,
            motivo=f'Traslado QA alm{origen_almacen_id}->alm{destino_almacen_id}',
            usuario=QA_USER, id_almacen=destino_almacen_id,
            referencia_tipo='traslado', referencia_id=0)
    db.session.commit()
    db.session.expire_all()

    so = db.session.execute(sa_text(
        "SELECT cantidad FROM stock_por_almacen WHERE id_producto = :p AND id_almacen = :a"
    ), {'p': producto.id, 'a': origen_almacen_id}).scalar() or 0
    sd = db.session.execute(sa_text(
        "SELECT cantidad FROM stock_por_almacen WHERE id_producto = :p AND id_almacen = :a"
    ), {'p': producto.id, 'a': destino_almacen_id}).scalar() or 0
    return so, sd


class LoginAsRole:
    """Context manager to switch app_client session to a user with a specific role."""

    _role_cache = {}

    def __init__(self, client, role_name):
        self.client = client
        self.role_name = role_name
        self._prev_user_id = None

    def __enter__(self):
        cache_key = self.role_name
        if cache_key not in LoginAsRole._role_cache:
            user = self._find_or_create_user()
            LoginAsRole._role_cache[cache_key] = user.id
        uid = LoginAsRole._role_cache[cache_key]
        with self.client.session_transaction() as sess:
            self._prev_user_id = sess.get('_user_id')
            sess['_user_id'] = str(uid)
            sess['login_at'] = datetime.now().isoformat()
        return self.client

    def __exit__(self, *args):
        with self.client.session_transaction() as sess:
            if self._prev_user_id:
                sess['_user_id'] = self._prev_user_id
            else:
                sess.pop('_user_id', None)

    def _find_or_create_user(self):
        role_map = {
            'admin': ['Admin', 'admin', 'Administrador', 'administrador', 'SuperAdmin'],
            'cajera': ['Cajera', 'cajera', 'Cajero'],
            'vendedor': ['Vendedor', 'vendedor'],
            'bodeguero': ['Bodeguero', 'bodeguero'],
        }
        names = role_map.get(self.role_name.lower(), [self.role_name])
        for name in names:
            user = m.Usuario.query.join(m.Rol).filter(m.Rol.nombre == name).first()
            if user:
                return user
        rol = m.Rol.query.filter(m.Rol.nombre.in_(names)).first()
        if not rol:
            rol = m.Rol(nombre=names[0])
            db.session.add(rol)
            db.session.flush()
        from werkzeug.security import generate_password_hash
        u = m.Usuario(
            nombre=f'QA {self.role_name.title()}',
            correo=f'qa_{self.role_name}@test.cl',
            password_hash=generate_password_hash('test123'),
            rol_id=rol.id, perfil='ACTIVO')
        db.session.add(u)
        db.session.commit()
        return u


def login_as(client, role_name):
    """Shorthand: `with login_as(client, 'cajera') as c:`"""
    return LoginAsRole(client, role_name)


def venta_rapida_thread_safe(idx, producto_id, caja_id, cliente_id):
    """Crea y cobra una venta completa en un thread independiente.

    Retorna dict con resultado para pruebas de carga.
    """
    try:
        with m.app.app_context():
            prod = db.session.get(m.Producto, producto_id)
            caja = db.session.get(m.Caja, caja_id)
            cli = db.session.get(m.Cliente, cliente_id)
            if not all([prod, caja, cli]):
                return {'idx': idx, 'ok': False, 'error': 'entidades no encontradas'}

            venta, _ = crear_venta_pendiente([(prod, 1)], caja, cli)
            cobrar_venta_efectivo(venta, caja)
            return {'idx': idx, 'ok': True, 'venta_id': venta.id, 'total': venta.monto_total}
    except Exception as ex:
        try:
            db.session.rollback()
        except Exception:
            pass
        return {'idx': idx, 'ok': False, 'error': str(ex)[:200]}

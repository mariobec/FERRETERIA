# --- IMPORTS ---
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify, send_from_directory, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import csv
import os
import json
import html
from collections import defaultdict
from functools import wraps
from flask_login import current_user, login_required, UserMixin, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import inspect as sa_inspect, and_, func, or_, text, UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
import qrcode
import io
import base64
import re
import urllib.error
import urllib.request
import pdfkit
from flask import make_response, render_template


def _load_env_archivos():
    """Carga variables desde archivos en la carpeta del proyecto (sin dependencia python-dotenv).
    Orden: env_qa.txt (visible en el Explorador) solo rellena claves no definidas en el sistema;
    .env.qa puede sobrescribir claves ya cargadas desde env_qa.txt."""
    root = os.path.dirname(os.path.abspath(__file__))

    def _parse_line(line):
        if not line or line.startswith('#') or '=' not in line:
            return None, None
        k, _, v = line.partition('=')
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        return (k, v) if k else (None, None)

    path_env_qa = os.path.join(root, 'env_qa.txt')
    if os.path.isfile(path_env_qa):
        with open(path_env_qa, encoding='utf-8-sig', errors='replace') as f:
            for raw in f:
                k, v = _parse_line(raw.strip())
                if k:
                    os.environ.setdefault(k, v)

    path_dot = os.path.join(root, '.env.qa')
    if os.path.isfile(path_dot):
        with open(path_dot, encoding='utf-8-sig', errors='replace') as f:
            for raw in f:
                k, v = _parse_line(raw.strip())
                if k:
                    os.environ[k] = v


try:
    _load_env_archivos()
except Exception:
    pass
# --- CONFIGURACIÓN DE LA APP ---
app = Flask(__name__)


def _resolver_database_uri():
    """Resuelve la URI de BD priorizando variables estándar de hosting (Render/Neon/Heroku).

    Orden:
      1. SQLALCHEMY_DATABASE_URI (override explícito)
      2. DATABASE_URL (estándar Render/Neon/Heroku)
      3. Default local MySQL para desarrollo.
    """
    uri = (os.getenv('SQLALCHEMY_DATABASE_URI') or '').strip()
    if not uri:
        uri = (os.getenv('DATABASE_URL') or '').strip()
    if not uri:
        return 'mysql+pymysql://mbecerra:clave_segura@localhost/ferreteria'
    if uri.startswith('postgres://'):
        uri = 'postgresql+psycopg2://' + uri[len('postgres://'):]
    elif uri.startswith('postgresql://') and '+psycopg2' not in uri.split('://', 1)[0]:
        uri = 'postgresql+psycopg2://' + uri[len('postgresql://'):]
    return uri


db_uri = _resolver_database_uri()
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
if db_uri.startswith('postgresql'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {
        'connect_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', '8')),
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 3,
    }
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clave_secreta_segura')
# En desarrollo, recargar plantillas al guardar (sin depender de debug=True).
# Desactivar explícitamente con FLASK_TEMPLATE_RELOAD=0 si no lo deseas.
if os.getenv('FLASK_TEMPLATE_RELOAD', '1') != '0':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
db = SQLAlchemy(app)


class Almacen(db.Model):
    __tablename__ = 'almacenes'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, default=True)


class StockPorAlmacen(db.Model):
    __tablename__ = 'stock_por_almacen'
    id_producto = db.Column(db.Integer, db.ForeignKey('productos.id', ondelete='CASCADE'), primary_key=True)
    id_almacen = db.Column(db.Integer, db.ForeignKey('almacenes.id', ondelete='RESTRICT'), primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False, default=0)

    producto = db.relationship('Producto', backref='stocks_almacen')


# --- Inventario multi-almacén (opcional según tablas en BD) ---
_INV_TABLAS_OK = None
_ENROL_TABLAS_OK = None
_ID_ALMACEN_TIENDA = None
_ID_ALMACEN_BODEGA = None


def _tablas_inventario_almacen_existen():
    global _INV_TABLAS_OK
    if _INV_TABLAS_OK is not None:
        return _INV_TABLAS_OK
    try:
        insp = sa_inspect(db.engine)
        _INV_TABLAS_OK = bool(
            insp.has_table('almacenes') and insp.has_table('stock_por_almacen')
        )
    except Exception:
        _INV_TABLAS_OK = False
    return _INV_TABLAS_OK


def _tablas_enrolamiento_existen():
    global _ENROL_TABLAS_OK
    if _ENROL_TABLAS_OK is not None:
        return _ENROL_TABLAS_OK
    try:
        insp = sa_inspect(db.engine)
        _ENROL_TABLAS_OK = bool(
            insp.has_table('enrolamiento_toma_sesion') and insp.has_table('enrolamiento_toma_linea')
        )
    except Exception:
        _ENROL_TABLAS_OK = False
    return _ENROL_TABLAS_OK


_CATALOGO_TABLAS_OK = None
_ORDEN_COMPRA_TABLAS_OK = None


def _tablas_orden_compra_existen():
    global _ORDEN_COMPRA_TABLAS_OK
    if _ORDEN_COMPRA_TABLAS_OK is not None:
        return _ORDEN_COMPRA_TABLAS_OK
    try:
        insp = sa_inspect(db.engine)
        if not (insp.has_table('ordenes_compra') and insp.has_table('detalle_orden_compra')):
            _ORDEN_COMPRA_TABLAS_OK = False
        else:
            cols = {c['name'] for c in insp.get_columns('recepciones_compra')}
            _ORDEN_COMPRA_TABLAS_OK = 'orden_compra_id' in cols
    except Exception:
        _ORDEN_COMPRA_TABLAS_OK = False
    return _ORDEN_COMPRA_TABLAS_OK


def _tablas_catalogo_producto_existen():
    global _CATALOGO_TABLAS_OK
    if _CATALOGO_TABLAS_OK is not None:
        return _CATALOGO_TABLAS_OK
    try:
        insp = sa_inspect(db.engine)
        _CATALOGO_TABLAS_OK = bool(
            insp.has_table('catalogo_categorias') and insp.has_table('catalogo_subcategorias')
        )
    except Exception:
        _CATALOGO_TABLAS_OK = False
    return _CATALOGO_TABLAS_OK


def _catalogo_ui_disponible():
    if not _tablas_catalogo_producto_existen():
        return False
    try:
        return CatalogoCategoria.query.filter_by(activo=True).first() is not None
    except Exception:
        return False


def _categorias_filtro_lista():
    if _catalogo_ui_disponible():
        rows = (
            CatalogoCategoria.query.filter_by(activo=True)
            .order_by(CatalogoCategoria.orden.asc(), CatalogoCategoria.nombre.asc())
            .all()
        )
        return [r.nombre for r in rows]
    return [
        c[0]
        for c in db.session.query(Producto.categoria)
        .filter(Producto.categoria.isnot(None), Producto.categoria != '')
        .distinct()
        .order_by(Producto.categoria.asc())
        .all()
    ]


def _subcategorias_filtro_legacy(categoria):
    subcategorias_q = db.session.query(Producto.subcategoria).filter(
        Producto.subcategoria.isnot(None),
        Producto.subcategoria != '',
    )
    if categoria:
        subcategorias_q = subcategorias_q.filter(Producto.categoria == categoria)
    return [s[0] for s in subcategorias_q.distinct().order_by(Producto.subcategoria.asc()).all()]


def _catalogo_sub_opciones_filtro(categoria_nombre):
    """Opciones para filtrar por subcategoria_catalogo_id bajo una categoría de maestro."""
    if not categoria_nombre or not _catalogo_ui_disponible():
        return []
    cat = CatalogoCategoria.query.filter_by(nombre=categoria_nombre.strip(), activo=True).first()
    if not cat:
        return []
    subs = (
        cat.subcategorias.filter_by(activo=True)
        .order_by(
            CatalogoSubcategoria.nivel2.asc(),
            CatalogoSubcategoria.orden.asc(),
            CatalogoSubcategoria.nombre.asc(),
        )
        .all()
    )
    out = []
    for s in subs:
        n2 = (s.nivel2 or '').strip()
        label = f"{n2} — {s.nombre}" if n2 else (s.nombre or '')
        out.append({'id': s.id, 'etiqueta': label})
    return out


def _catalogo_arbol_registro():
    """Árbol para selects encadenados al registrar producto (categoría → nivel2 → hoja)."""
    if not _catalogo_ui_disponible():
        return None
    try:
        cats = (
            CatalogoCategoria.query.filter_by(activo=True)
            .order_by(CatalogoCategoria.orden.asc(), CatalogoCategoria.nombre.asc())
            .all()
        )
        if not cats:
            return None
        tree = []
        for c in cats:
            subs = (
                c.subcategorias.filter_by(activo=True)
                .order_by(
                    CatalogoSubcategoria.nivel2.asc(),
                    CatalogoSubcategoria.orden.asc(),
                    CatalogoSubcategoria.nombre.asc(),
                )
                .all()
            )
            by_n2 = {}
            for s in subs:
                k = (s.nivel2 or '').strip()
                by_n2.setdefault(k, []).append({'id': s.id, 'n3': s.nombre or ''})
            n2_blocks = [{'n2': k, 'subs': v} for k, v in sorted(by_n2.items(), key=lambda x: x[0])]
            tree.append({'id': c.id, 'nombre': c.nombre, 'nivel2': n2_blocks})
        return tree
    except Exception:
        return None


def _sincronizar_producto_desde_subcatalogo(producto, sub_id):
    """Rellena categoria, subcategoria (texto) y FK desde una hoja del catálogo."""
    if not sub_id:
        return
    sub = CatalogoSubcategoria.query.options(joinedload(CatalogoSubcategoria.categoria)).get(int(sub_id))
    if not sub or not sub.categoria:
        return
    producto.subcategoria_catalogo_id = sub.id
    producto.categoria = (sub.categoria.nombre or '')[:50]
    leaf = (sub.nombre or '').strip()
    n2 = (sub.nivel2 or '').strip()
    if n2:
        producto.subcategoria = f'{n2} / {leaf}'[:50]
    else:
        producto.subcategoria = leaf[:50]


def _opciones_hojas_catalogo_para_select():
    """Pares (id_sub, etiqueta) para asignación masiva; jerarquía categoría › sub1 (nivel2) › sub2 (hoja)."""
    if not _tablas_catalogo_producto_existen():
        return []
    rows = (
        db.session.query(
            CatalogoSubcategoria.id,
            CatalogoCategoria.nombre,
            CatalogoSubcategoria.nivel2,
            CatalogoSubcategoria.nombre,
        )
        .join(CatalogoCategoria, CatalogoCategoria.id == CatalogoSubcategoria.categoria_id)
        .filter(CatalogoSubcategoria.activo.is_(True), CatalogoCategoria.activo.is_(True))
        .order_by(
            CatalogoCategoria.orden,
            CatalogoCategoria.nombre,
            CatalogoSubcategoria.nivel2,
            CatalogoSubcategoria.orden,
            CatalogoSubcategoria.nombre,
        )
        .all()
    )
    out = []
    for sid, cn, n2, leaf in rows:
        n2s = (n2 or '').strip()
        lab = f'{cn} › {n2s} › {leaf}' if n2s else f'{cn} › {leaf}'
        out.append((sid, lab))
    return out


def _codigo_almacen_tienda():
    return (os.getenv('ALMACEN_CODIGO_TIENDA') or 'TIENDA').strip().upper() or 'TIENDA'


def _codigo_almacen_bodega():
    return (os.getenv('ALMACEN_CODIGO_BODEGA') or 'BODEGA').strip().upper() or 'BODEGA'


def _resolver_id_almacen_por_codigo(codigo):
    if not codigo or not _tablas_inventario_almacen_existen():
        return None
    try:
        row = db.session.execute(
            text(
                "SELECT id FROM almacenes "
                "WHERE UPPER(TRIM(codigo)) = :c AND activo IS NOT FALSE "
                "ORDER BY id ASC LIMIT 1"
            ),
            {"c": codigo.strip().upper()},
        ).scalar()
        return int(row) if row is not None else None
    except Exception:
        db.session.rollback()
        return None


def id_almacen_tienda():
    """Almacén desde el que vende el POS (por defecto TIENDA)."""
    global _ID_ALMACEN_TIENDA
    if _ID_ALMACEN_TIENDA is not None:
        return _ID_ALMACEN_TIENDA
    env_id = (os.getenv('ALMACEN_ID_TIENDA') or '').strip()
    if env_id.isdigit():
        _ID_ALMACEN_TIENDA = int(env_id)
        return _ID_ALMACEN_TIENDA
    _ID_ALMACEN_TIENDA = _resolver_id_almacen_por_codigo(_codigo_almacen_tienda())
    return _ID_ALMACEN_TIENDA


def id_almacen_bodega():
    """Almacén donde ingresa mercadería por recepción (por defecto BODEGA)."""
    global _ID_ALMACEN_BODEGA
    if _ID_ALMACEN_BODEGA is not None:
        return _ID_ALMACEN_BODEGA
    env_id = (os.getenv('ALMACEN_ID_BODEGA') or '').strip()
    if env_id.isdigit():
        _ID_ALMACEN_BODEGA = int(env_id)
        return _ID_ALMACEN_BODEGA
    _ID_ALMACEN_BODEGA = _resolver_id_almacen_por_codigo(_codigo_almacen_bodega())
    return _ID_ALMACEN_BODEGA


def _invalidar_cache_ids_almacen():
    """Tras cambiar codigo/activo de almacenes, forzar nueva resolución TIENDA/BODEGA."""
    global _ID_ALMACEN_TIENDA, _ID_ALMACEN_BODEGA
    _ID_ALMACEN_TIENDA = None
    _ID_ALMACEN_BODEGA = None


def stock_producto_en_almacen(id_producto, id_almacen):
    if not id_almacen or not _tablas_inventario_almacen_existen():
        return None
    try:
        v = db.session.execute(
            text(
                "SELECT cantidad FROM stock_por_almacen "
                "WHERE id_producto = :p AND id_almacen = :a LIMIT 1"
            ),
            {"p": int(id_producto), "a": int(id_almacen)},
        ).scalar()
        # Diferenciar entre "sin fila en stock_por_almacen" (None) y "fila con cantidad 0".
        # Esto permite fallback a productos.stock en POS cuando aún no existe distribución por almacén.
        return None if v is None else int(v)
    except Exception:
        db.session.rollback()
        return None


def _refrescar_stock_total_producto(producto):
    """Mantiene productos.stock = suma por almacén cuando aplica."""
    if not producto or not _tablas_inventario_almacen_existen():
        return
    try:
        # Asegura que cambios pendientes en stock_por_almacen se reflejen en el SUM.
        db.session.flush()
        s = db.session.execute(
            text("SELECT COALESCE(SUM(cantidad), 0) FROM stock_por_almacen WHERE id_producto = :p"),
            {"p": int(producto.id)},
        ).scalar()
        producto.stock = int(s or 0)
    except Exception:
        db.session.rollback()
        pass


def ajustar_stock_almacen(producto_id, id_almacen, delta, allow_negative=False):
    """
    delta > 0 suma stock en el almacén; delta < 0 resta.
    Devuelve (nuevo_stock_almacén|None, error_str|None).
    """
    if not id_almacen or not _tablas_inventario_almacen_existen():
        return None, None
    try:
        d = int(delta)
    except (TypeError, ValueError):
        return None, "Delta de stock inválido."
    pid = int(producto_id)
    aid = int(id_almacen)
    actual = stock_producto_en_almacen(pid, aid)
    if actual is None:
        actual = 0
    nuevo = actual + d
    if not allow_negative and nuevo < 0:
        return actual, "Stock insuficiente en almacén."
    row = StockPorAlmacen.query.filter_by(id_producto=pid, id_almacen=aid).first()
    if row:
        row.cantidad = int(nuevo)
    else:
        db.session.add(StockPorAlmacen(id_producto=pid, id_almacen=aid, cantidad=int(nuevo)))
    return int(nuevo), None


def fijar_stock_almacen(producto_id, id_almacen, cantidad):
    """Ajuste absoluto de stock en un almacén (auditoría)."""
    if not id_almacen or not _tablas_inventario_almacen_existen():
        return None
    try:
        c = int(cantidad)
    except (TypeError, ValueError):
        return None
    pid = int(producto_id)
    aid = int(id_almacen)
    row = StockPorAlmacen.query.filter_by(id_producto=pid, id_almacen=aid).first()
    if row:
        row.cantidad = c
    else:
        db.session.add(StockPorAlmacen(id_producto=pid, id_almacen=aid, cantidad=c))
    return c


def _ruta_config_empresa():
    carpeta_cfg = os.path.join(app.root_path, 'data')
    os.makedirs(carpeta_cfg, exist_ok=True)
    return os.path.join(carpeta_cfg, 'empresa_config.json')


def _config_empresa_default():
    nombre = (os.getenv("EMPRESA_NOMBRE_COMERCIAL") or "Ferretería Santo Domingo").strip() or "Ferretería Santo Domingo"
    return {
        "nombre_comercial": nombre,
        "razon_social": (os.getenv("EMPRESA_RAZON_SOCIAL") or nombre).strip() or nombre,
        "eslogan": (os.getenv("EMPRESA_ESLOGAN") or "Chilemat®").strip() or "Chilemat®",
        "telefono": (os.getenv("EMPRESA_TELEFONO") or "").strip(),
        "correo": (os.getenv("EMPRESA_CORREO") or "").strip(),
        "direccion": (os.getenv("EMPRESA_DIRECCION") or "").strip(),
        # ERP componible: módulos activables por cliente
        "mod_ventas": "1",
        "mod_caja": "1",
        "mod_inventario": "1",
        "mod_bi": "1",
        "mod_ia": "1",
    }


def obtener_config_empresa():
    ruta = _ruta_config_empresa()
    cfg = _config_empresa_default()
    if not os.path.exists(ruta):
        return cfg
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            cfg.update({k: (str(v).strip() if v is not None else "") for k, v in data.items() if k in cfg})
    except Exception:
        return cfg
    return cfg


def guardar_config_empresa(data):
    # Parte desde config actual para no perder llaves adicionales al guardar.
    cfg = obtener_config_empresa()
    cfg.update({k: (str(v).strip() if v is not None else "") for k, v in data.items() if k in cfg})
    with open(_ruta_config_empresa(), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


CANALES_COMPRA_VALIDOS = (
    "chilemat_portal",
    "whatsapp",
    "email",
    "manual",
)


def _ruta_config_proveedores():
    carpeta_cfg = os.path.join(app.root_path, 'data')
    os.makedirs(carpeta_cfg, exist_ok=True)
    return os.path.join(carpeta_cfg, 'proveedores_config.json')


def _cargar_config_proveedores():
    ruta = _ruta_config_proveedores()
    base = {"canales_compra": {}}
    if not os.path.exists(ruta):
        return base
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            raw = json.load(f) or {}
        if isinstance(raw, dict):
            cc = raw.get("canales_compra", {})
            if isinstance(cc, dict):
                base["canales_compra"] = {str(k): str(v) for k, v in cc.items()}
    except Exception:
        return base
    return base


def _guardar_config_proveedores(cfg):
    data = {"canales_compra": dict(cfg.get("canales_compra", {}))}
    with open(_ruta_config_proveedores(), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def obtener_canales_proveedor():
    cfg = _cargar_config_proveedores()
    return cfg.get("canales_compra", {})


def canal_compra_proveedor(proveedor_id):
    canales = obtener_canales_proveedor()
    canal = str(canales.get(str(int(proveedor_id)), "manual")).strip().lower() if proveedor_id else "manual"
    return canal if canal in CANALES_COMPRA_VALIDOS else "manual"


def guardar_canal_compra_proveedor(proveedor_id, canal):
    if not proveedor_id:
        return
    canal_norm = (str(canal or "manual").strip().lower() or "manual")
    if canal_norm not in CANALES_COMPRA_VALIDOS:
        canal_norm = "manual"
    cfg = _cargar_config_proveedores()
    cc = cfg.setdefault("canales_compra", {})
    cc[str(int(proveedor_id))] = canal_norm
    _guardar_config_proveedores(cfg)


def eliminar_canal_compra_proveedor(proveedor_id):
    if not proveedor_id:
        return
    cfg = _cargar_config_proveedores()
    cc = cfg.setdefault("canales_compra", {})
    cc.pop(str(int(proveedor_id)), None)
    _guardar_config_proveedores(cfg)


def modulo_activo(nombre_modulo):
    cfg = obtener_config_empresa()
    key = f"mod_{(nombre_modulo or '').strip().lower()}"
    raw = str(cfg.get(key, "1")).strip().lower()
    return raw in ("1", "true", "si", "yes", "on")


def usuario_tiene_permiso(nombre_permiso):
    try:
        if not current_user.is_authenticated or not getattr(current_user, 'rol', None):
            return False
        rol_nombre = (current_user.rol.nombre or '').strip().lower()
        if rol_nombre in ('admin', 'administrador', 'superadmin', 'super admin'):
            return True
        return any(
            (rp.permiso and rp.permiso.nombre == nombre_permiso) for rp in (current_user.rol.rol_permisos or [])
        )
    except Exception:
        return False


def usuario_obj_tiene_permiso(usuario, nombre_permiso):
    """Misma regla que usuario_tiene_permiso pero sobre una instancia Usuario (p.ej. supervisor que autoriza)."""
    if not usuario or not getattr(usuario, 'rol', None):
        return False
    rol_nombre = (usuario.rol.nombre or '').strip().lower()
    if rol_nombre in ('admin', 'administrador', 'superadmin', 'super admin'):
        return True
    return any(
        (rp.permiso and rp.permiso.nombre == nombre_permiso) for rp in (usuario.rol.rol_permisos or [])
    )


def usuario_esta_activo(usuario):
    """Compatibilidad: usamos 'perfil' como estado ACTIVO/INACTIVO."""
    return (getattr(usuario, 'perfil', None) or 'ACTIVO').strip().upper() != 'INACTIVO'


def resolver_usuario_por_identificador_pos(raw):
    """
    Identifica un usuario para autorización POS sin obligar al correo completo:
    - Correo exacto (sin distinguir mayúsculas)
    - Texto antes del @ si solo hay un correo que coincida (ej. \"ana\" → ana@empresa.cl)
    - Nombre exacto si solo hay un usuario con ese nombre (sin distinguir mayúsculas)
    Retorna (usuario|None, código_error|None). código_error: ambiguous_email_local, ambiguous_nombre, not_found, empty
    """
    raw = (raw or '').strip()
    if not raw:
        return None, 'empty'
    low = raw.lower()
    u = Usuario.query.filter(db.func.lower(Usuario.correo) == low).first()
    if u:
        return u, None
    candidatos = Usuario.query.filter(db.func.lower(Usuario.correo).like(low + '@%')).all()
    if len(candidatos) == 1:
        return candidatos[0], None
    if len(candidatos) > 1:
        return None, 'ambiguous_email_local'
    candidatos = Usuario.query.filter(db.func.lower(Usuario.nombre) == low).all()
    if len(candidatos) == 1:
        return candidatos[0], None
    if len(candidatos) > 1:
        return None, 'ambiguous_nombre'
    return None, 'not_found'


def usuario_requiere_cambio_clave(usuario):
    perfil = (getattr(usuario, 'perfil', None) or '').strip().upper()
    return perfil in ('FORZAR_CLAVE', 'ACTIVO_FORZAR_CLAVE')


@app.context_processor
def inject_company_context():
    from flask import current_app

    try:
        ep = set(current_app.view_functions.keys())
    except Exception:
        ep = set()
    nav_flags = {
        'nav_inventario_enrolamiento': 'inventario_enrolamiento' in ep,
        'nav_inventario_salud': 'inventario_salud' in ep,
    }
    try:
        return {
            'empresa_cfg': obtener_config_empresa(),
            'puede_administrar': usuario_tiene_permiso('gestionar_usuarios'),
            'usuario_tiene_permiso': usuario_tiene_permiso,
            'modulo_activo': modulo_activo,
            **nav_flags,
        }
    except Exception:
        return {
            'empresa_cfg': _config_empresa_default(),
            'puede_administrar': False,
            'usuario_tiene_permiso': lambda _nombre: False,
            'modulo_activo': lambda _nombre: True,
            **nav_flags,
        }


# --- LOGIN MANAGER ---.........................................................................
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # nombre de la ruta de login
login_manager.login_message = "Debes iniciar sesión para acceder a esta página."
login_manager.login_message_category = "warning"

# Función para cargar el usuario desde la base de datos

@login_manager.user_loader
def load_user(user_id):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    try:
        return db.session.get(Usuario, uid)
    except Exception:
        return None

# --- MODELOS DE BASE DE DATOS ---...............................................................
def permisos_required(*permisos):
    def wrapper(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.rol:
                rol_nombre = (current_user.rol.nombre or '').strip().lower()
                if rol_nombre in ('admin', 'administrador', 'superadmin', 'super admin'):
                    return f(*args, **kwargs)
                permisos_rol = [rp.permiso.nombre for rp in current_user.rol.rol_permisos if rp.permiso]
                if any(p in permisos_rol for p in permisos):
                    return f(*args, **kwargs)
            flash("No tienes permisos para acceder a esta acción.", "danger")
            return redirect(url_for('index'))
        return decorated_function
    return wrapper

    # --- FUNCIÓN DE VALIDACIÓN DE RUT ---............................................................
def validar_rut(rut: str) -> bool:
    rut = rut.replace(".", "").replace("-", "").upper()
    if len(rut) < 9 or len(rut) > 10:
        return False
    cuerpo, dv = rut[:-1], rut[-1]
    try:
        reverso = map(int, reversed(cuerpo))
        factores = [2, 3, 4, 5, 6, 7]
        suma = sum(d * factores[i % 6] for i, d in enumerate(reverso))
        residuos = 11 - (suma % 11)
        dv_esperado = 'K' if residuos == 10 else '0' if residuos == 11 else str(residuos)
        return dv == dv_esperado
    except ValueError:
        return False
    # NUEVO: Decorador para obligar apertura de caja
_ENDPOINTS_CAJA_ESTRICTA = {
    # POS venta directa
    'punto_venta',
    'guardar_venta',
    'agregar_producto_venta',
    'eliminar_detalle',
    'finalizar_venta',
    'actualizar_item',
    'pos_usuarios_autorizar_descuento',
    # Caja operativa / cobranzas
    'caja_pendientes',
    'procesar_cobro_caja',
    'anular_vale_caja',
    'ver_ticket_cobro',
    # Cambios
    'caja_cambios',
    'api_cambios_producto',
    'api_cambios_buscar_venta',
    'api_cambios_venta_detalle',
    'ticket_cambio',
    'caja_cambios_historial',
    # Crédito (movimiento de dinero)
    'registrar_abono',
}


def _endpoint_requiere_caja_activa():
    ep = (request.endpoint or '').strip()
    return ep in _ENDPOINTS_CAJA_ESTRICTA


def caja_requerida(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Permite navegación general/reportes sin exigir apertura de caja.
        if not _endpoint_requiere_caja_activa():
            return f(*args, **kwargs)
        _asegurar_columnas_caja_cuadratura()
        # Buscamos si existe una caja que esté en estado 'Abierta'
        caja_activa = Caja.query.filter_by(estado='Abierta').order_by(Caja.id.desc()).first()
        if not caja_activa:
            flash("⚠️ Debe abrir caja para operar ventas/cobranza.", "warning")
            return redirect(url_for('abrir_caja'))
        # Si la caja abierta es de un día anterior, obligamos su cierre.
        fecha_apertura = caja_activa.fecha_apertura.date() if caja_activa.fecha_apertura else None
        if fecha_apertura and fecha_apertura < datetime.now().date():
            flash(
                f"La caja N°{caja_activa.id} quedó abierta desde {fecha_apertura.strftime('%d/%m/%Y')}. "
                "Debe cerrar esa caja antes de continuar en el POS.",
                "warning",
            )
            return redirect(url_for('cerrar_caja'))
        return f(*args, **kwargs)
    return decorated_function


def obtener_caja_activa():
    """Retorna la caja abierta más reciente o None."""
    _asegurar_columnas_caja_cuadratura()
    _asegurar_columnas_ventas_legacy()
    return Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()


def _rol_es_administrador_por_nombre(rol):
    if not rol:
        return False
    n = (rol.nombre or '').strip().lower()
    return n in ('admin', 'administrador', 'adminisrtador', 'superadmin', 'super admin')


def _usuario_puede_ajustar_stock():
    return _rol_es_administrador_por_nombre(getattr(current_user, 'rol', None)) or usuario_tiene_permiso('admin_inventario')


def _usuario_enrol_autorizado():
    return usuario_tiene_permiso('enrolamiento_inventario') or usuario_tiene_permiso('admin_inventario')


def _rut_cliente_final_normalizado():
    rut_cfg = (os.getenv('POS_RUT_CLIENTE_FINAL') or '66.666.666-6').strip()
    if not validar_rut(rut_cfg):
        rut_cfg = '66.666.666-6'
    return rut_cfg


def _cliente_es_sistema_final(cli):
    if not cli:
        return False
    return (cli.rut or '').strip() == _rut_cliente_final_normalizado()


_PERMISOS_SISTEMA_INICIAL = (
    'gestionar_usuarios',
    'admin_inventario',
    'enrolamiento_inventario',
    'panel_gerencia',
    'anular_vale_caja',
    'autorizar_descuento_pos',
    'revision_precios',
    'pos_emitir_vale',
    'caja_cobrar_vale',
    'caja_abrir',
    'caja_movimientos',
    'caja_cerrar',
)


def _normalizar_nombre_rol(nombre):
    n = (nombre or '').strip().lower()
    reemplazos = (
        ('á', 'a'),
        ('é', 'e'),
        ('í', 'i'),
        ('ó', 'o'),
        ('ú', 'u'),
    )
    for a, b in reemplazos:
        n = n.replace(a, b)
    return n


def _seed_permisos_roles_operativos():
    """
    Asigna permisos base por rol operativo sin quitar permisos existentes.
    """
    try:
        permisos = {p.nombre: p for p in Permiso.query.all()}
        if not permisos:
            return

        mapa_por_rol = {
            'vendedor': {'pos_emitir_vale'},
            'vendedora': {'pos_emitir_vale'},
            'ventas': {'pos_emitir_vale'},
            'meson': {'pos_emitir_vale'},
            'cajera': {'pos_emitir_vale', 'caja_cobrar_vale', 'caja_abrir', 'caja_movimientos', 'caja_cerrar'},
            'cajero': {'pos_emitir_vale', 'caja_cobrar_vale', 'caja_abrir', 'caja_movimientos', 'caja_cerrar'},
            'caja': {'pos_emitir_vale', 'caja_cobrar_vale', 'caja_abrir', 'caja_movimientos', 'caja_cerrar'},
            'supervisor': {
                'pos_emitir_vale',
                'caja_cobrar_vale',
                'caja_abrir',
                'caja_movimientos',
                'caja_cerrar',
                'anular_vale_caja',
                'autorizar_descuento_pos',
            },
            'encargado': {
                'pos_emitir_vale',
                'caja_cobrar_vale',
                'caja_abrir',
                'caja_movimientos',
                'caja_cerrar',
                'anular_vale_caja',
                'autorizar_descuento_pos',
            },
        }

        cambios = False
        for rol in Rol.query.options(joinedload(Rol.rol_permisos)).all():
            clave = _normalizar_nombre_rol(rol.nombre)
            if clave not in mapa_por_rol:
                continue
            actuales = {rp.permiso_id for rp in (rol.rol_permisos or []) if rp.permiso_id}
            for nombre_perm in mapa_por_rol[clave]:
                perm = permisos.get(nombre_perm)
                if not perm or perm.id in actuales:
                    continue
                db.session.add(RolPermiso(rol_id=rol.id, permiso_id=perm.id))
                cambios = True
        if cambios:
            db.session.commit()
    except Exception:
        db.session.rollback()


def _seed_permisos_catalogo_si_vacio():
    """Asegura filas en `permisos` para los nombres usados en @permisos_required."""
    try:
        existentes = {p.nombre for p in Permiso.query.all()}
        nuevos = [Permiso(nombre=n) for n in _PERMISOS_SISTEMA_INICIAL if n not in existentes]
        if nuevos:
            for p in nuevos:
                db.session.add(p)
            db.session.commit()
        _seed_permisos_roles_operativos()
    except Exception:
        db.session.rollback()


@app.before_request
def forzar_cambio_clave_si_corresponde():
    if not current_user.is_authenticated:
        return None
    # Auto-migraciones idempotentes para instancias con esquema legacy (Render/Neon).
    _asegurar_columnas_caja_cuadratura()
    _asegurar_columnas_ventas_legacy()
    _asegurar_columnas_productos_legacy()
    _asegurar_columnas_detalle_ventas_legacy()
    # Si alguna comprobación legacy dejó Postgres en estado abortado, limpiamos antes de la ruta.
    db.session.rollback()
    ep = request.endpoint or ''
    permitidos = {'cambiar_password', 'logout', 'logout_forzar', 'centro_ayuda', 'static'}
    if ep in permitidos:
        return None
    if usuario_requiere_cambio_clave(current_user):
        flash("Debes actualizar tu contraseña para continuar.", "warning")
        return redirect(url_for('cambiar_password'))
    return None


def obtener_o_crear_cliente_final():
    """Cliente genérico para vales sin identificación (RUT configurable, por defecto 66.666.666-6)."""
    rut_cfg = (os.getenv("POS_RUT_CLIENTE_FINAL") or "66.666.666-6").strip()
    if not validar_rut(rut_cfg):
        rut_cfg = "66.666.666-6"
    cli = Cliente.query.filter_by(rut=rut_cfg).first()
    if cli:
        return cli
    nombre_cf = (os.getenv("POS_NOMBRE_CLIENTE_FINAL") or "Cliente final").strip() or "Cliente final"
    cli = Cliente(nombre=nombre_cf, rut=rut_cfg)
    db.session.add(cli)
    db.session.flush()
    return cli


def clave_ubicacion_producto(prod):
    """Clave estable para ordenar picking por Pasillo-Estante-Nivel."""
    if not prod:
        return ("ZZZ", "ZZZ", "ZZZ", "")
    p = (prod.ubicacion_pasillo or "ZZZ").strip().upper()
    e = (prod.ubicacion_estante or "ZZZ").strip().upper()
    n = (prod.ubicacion_nivel or "ZZZ").strip().upper()
    return (p, e, n, (prod.nombre or "").strip().upper())


# --- MODELOS DE BASE DE DATOS --- --------------------------------------------------

# Catálogo jerárquico (categoría → subcategoría). CatalogoSubcategoria va primero para order_by con columnas reales (SQLAlchemy 2.x).
class CatalogoSubcategoria(db.Model):
    __tablename__ = 'catalogo_subcategorias'
    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('catalogo_categorias.id', ondelete='CASCADE'), nullable=False)
    nivel2 = db.Column(db.String(80), nullable=False, default='')
    nombre = db.Column(db.String(80), nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=0)
    activo = db.Column(db.Boolean, default=True)

    categoria = db.relationship('CatalogoCategoria', back_populates='subcategorias')

    __table_args__ = (
        db.UniqueConstraint('categoria_id', 'nivel2', 'nombre', name='uq_catalogo_sub_cat_nivel_nombre'),
    )


class CatalogoCategoria(db.Model):
    __tablename__ = 'catalogo_categorias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False, unique=True)
    orden = db.Column(db.Integer, nullable=False, default=0)
    activo = db.Column(db.Boolean, default=True)
    subcategorias = db.relationship(
        CatalogoSubcategoria,
        back_populates='categoria',
        lazy='dynamic',
        order_by=(CatalogoSubcategoria.nivel2, CatalogoSubcategoria.orden, CatalogoSubcategoria.nombre),
        cascade='all, delete-orphan',
    )


# 1. PRODUCTO: base de todo, se usa en los detalles de venta
class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    codigo_barra = db.Column(db.String(50), unique=True)
    codigo_chilemat = db.Column(db.String(80))
    codigo_interno = db.Column(db.String(32))
    imagen_url = db.Column(db.String(500))
    precio_compra = db.Column(db.Float)
    precio_venta = db.Column(db.Float)
    precio_mayoreo = db.Column(db.Float)
    unidad = db.Column(db.String(20))
    unidad_compra = db.Column(db.String(20))
    unidad_venta = db.Column(db.String(20))
    factor_conversion = db.Column(db.Float, default=1.0)
    stock = db.Column(db.Integer)
    categoria = db.Column(db.String(50))
    subcategoria = db.Column(db.String(50))
    subcategoria_catalogo_id = db.Column(
        db.Integer,
        db.ForeignKey('catalogo_subcategorias.id', ondelete='SET NULL'),
        nullable=True,
    )
    ubicacion_pasillo = db.Column(db.String(12))
    ubicacion_estante = db.Column(db.String(12))
    ubicacion_nivel = db.Column(db.String(12))
    activo = db.Column(db.Boolean, default=True)

    subcategoria_catalogo = db.relationship(
        'CatalogoSubcategoria',
        foreign_keys=[subcategoria_catalogo_id],
        backref=db.backref('productos', lazy='dynamic'),
    )

    @property
    def ubicacion_codigo(self):
        p = (self.ubicacion_pasillo or "").strip()
        e = (self.ubicacion_estante or "").strip()
        n = (self.ubicacion_nivel or "").strip()
        if p or e or n:
            return f"{p}-{e}-{n}".strip("-")
        return ""

    @property
    def unidad_venta_final(self):
        return (self.unidad_venta or self.unidad or "Unidad")


class EnrolamientoTomaSesion(db.Model):
    __tablename__ = 'enrolamiento_toma_sesion'
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80))
    id_almacen = db.Column(db.Integer)
    iniciado_at = db.Column(db.DateTime, default=datetime.utcnow)


class EnrolamientoTomaLinea(db.Model):
    __tablename__ = 'enrolamiento_toma_linea'
    id = db.Column(db.Integer, primary_key=True)
    sesion_id = db.Column(db.Integer, db.ForeignKey('enrolamiento_toma_sesion.id', ondelete='CASCADE'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id', ondelete='CASCADE'), nullable=False)
    conteo = db.Column(db.Integer, nullable=False, default=0)

    sesion = db.relationship('EnrolamientoTomaSesion', backref=db.backref('lineas', lazy='dynamic', cascade='all,delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('sesion_id', 'producto_id', name='uq_enrol_linea_sesion_prod'),
    )


def _enrol_resumen_almacen_codigo(a):
    tid = id_almacen_tienda()
    bid = id_almacen_bodega()
    if tid and a.id == tid:
        return 'tienda'
    if bid and a.id == bid:
        return 'bodega'
    return ''


def _enrol_almacenes_ui():
    if not _tablas_inventario_almacen_existen():
        return []
    rows = Almacen.query.filter_by(activo=True).order_by(Almacen.nombre.asc()).all()
    out = []
    for a in rows:
        out.append({'id': a.id, 'nombre': (a.nombre or a.codigo or '').strip() or f'#{a.id}', 'rol': _enrol_resumen_almacen_codigo(a)})
    return out


def _enrol_permite_traslado_ui():
    return _tablas_inventario_almacen_existen() and Almacen.query.filter_by(activo=True).count() >= 2


def _enrol_normalizar_codigo(c):
    return (c or '').strip()


def _enrol_buscar_producto_por_codigo(codigo):
    c = _enrol_normalizar_codigo(codigo)
    if not c:
        return None
    p = Producto.query.filter(Producto.codigo_barra == c).first()
    if p:
        return p
    p = Producto.query.filter(Producto.codigo_interno == c).first()
    if p:
        return p
    p = Producto.query.filter(Producto.codigo_chilemat == c).first()
    return p


def _enrol_codigo_barra_ocupado(codigo, excluir_producto_id=None):
    c = _enrol_normalizar_codigo(codigo)
    if not c:
        return False
    q = Producto.query.filter(Producto.codigo_barra == c)
    if excluir_producto_id:
        q = q.filter(Producto.id != int(excluir_producto_id))
    return q.first() is not None


def _enrol_linea_conteo_sumar(sesion_id, producto_id, delta):
    if not _tablas_enrolamiento_existen():
        return
    sid = int(sesion_id)
    pid = int(producto_id)
    try:
        d = int(delta)
    except (TypeError, ValueError):
        return
    if d == 0:
        return
    line = EnrolamientoTomaLinea.query.filter_by(sesion_id=sid, producto_id=pid).first()
    if not line:
        line = EnrolamientoTomaLinea(sesion_id=sid, producto_id=pid, conteo=0)
        db.session.add(line)
    line.conteo = int(line.conteo or 0) + d


def _enrol_serializar_producto(producto, sesion_id=None, sesion_almacen_id=None):
    tid = id_almacen_tienda()
    bid = id_almacen_bodega()
    mult = _tablas_inventario_almacen_existen()
    if mult:
        st_t = int(stock_producto_en_almacen(producto.id, tid) or 0) if tid else int(producto.stock or 0)
        st_b = int(stock_producto_en_almacen(producto.id, bid) or 0) if bid else 0
    else:
        st_t = int(producto.stock or 0)
        st_b = 0

    conteo = 0
    if sesion_id and _tablas_enrolamiento_existen():
        line = EnrolamientoTomaLinea.query.filter_by(sesion_id=int(sesion_id), producto_id=producto.id).first()
        if line:
            conteo = int(line.conteo or 0)

    stock_rows = []
    nom_sesion = ''
    if mult:
        for a in Almacen.query.filter_by(activo=True).order_by(Almacen.nombre.asc()).all():
            cant = int(stock_producto_en_almacen(producto.id, a.id) or 0)
            rol = _enrol_resumen_almacen_codigo(a)
            es_tienda = rol == 'tienda'
            es_sesion = bool(sesion_almacen_id and int(sesion_almacen_id) == int(a.id))
            if es_sesion:
                nom_sesion = (a.nombre or a.codigo or '').strip()
            stock_rows.append({
                'nombre': (a.nombre or a.codigo or '').strip() or f'#{a.id}',
                'cantidad': cant,
                'rol': rol,
                'es_tienda_pos': es_tienda,
                'es_sesion': es_sesion,
            })

    return {
        'id': producto.id,
        'nombre': producto.nombre,
        'categoria': producto.categoria or '',
        'subcategoria': producto.subcategoria or '',
        'codigo_chilemat': (producto.codigo_chilemat or '').strip(),
        'codigo_interno': (producto.codigo_interno or '').strip(),
        'imagen_url': (producto.imagen_url or '').strip(),
        'precio_venta': float(producto.precio_venta or 0),
        'precio_compra': float(producto.precio_compra or 0),
        'precio_mayoreo': float(producto.precio_mayoreo or 0),
        'stock_tienda': st_t,
        'stock_bodega': st_b,
        'stock_total_maestro': int(producto.stock or 0),
        'stock_por_almacen': stock_rows,
        'conteo_sesion': conteo,
        'stock_almacen_sesion_nombre': nom_sesion,
    }


def _enrol_sesion_get_or_404(sid):
    if not _tablas_enrolamiento_existen():
        return None
    return EnrolamientoTomaSesion.query.get(int(sid))


def _enrol_destino_almacen(sesion_row, id_almacen_destino):
    if id_almacen_destino:
        try:
            aid = int(id_almacen_destino)
        except (TypeError, ValueError):
            aid = None
        if aid:
            a = Almacen.query.filter_by(id=aid, activo=True).first()
            if a:
                return aid
    if sesion_row and sesion_row.id_almacen:
        return int(sesion_row.id_almacen)
    aid_def = id_almacen_tienda()
    return aid_def


def stock_disponible_venta_tienda(producto):
    """Stock usable en POS: solo almacén TIENDA (fuente única definitiva)."""
    if not producto:
        return 0
    aid = id_almacen_tienda()
    if aid and _tablas_inventario_almacen_existen():
        v = stock_producto_en_almacen(producto.id, aid)
        return int(v or 0)
    return int(producto.stock or 0)


def stock_tienda_por_producto_ids(ids):
    """Mapa id_producto -> stock en TIENDA (fuente única definitiva)."""
    ids = [int(x) for x in ids if x is not None]
    if not ids:
        return {}
    aid = id_almacen_tienda()
    if aid and _tablas_inventario_almacen_existen():
        rows = (
            db.session.query(StockPorAlmacen.id_producto, StockPorAlmacen.cantidad)
            .filter(
                StockPorAlmacen.id_almacen == aid,
                StockPorAlmacen.id_producto.in_(ids),
            )
            .all()
        )
        por_id = {int(pid): int(cant or 0) for pid, cant in rows}
        faltan = [i for i in ids if i not in por_id]
        if faltan:
            # Si no hay fila en TIENDA, se considera 0.
            for pid in faltan:
                por_id[int(pid)] = 0
        return por_id
    prods = Producto.query.filter(Producto.id.in_(ids)).all()
    return {p.id: int(p.stock or 0) for p in prods}


def _stock_ui_producto(producto):
    """Resumen consistente para vistas de inventario: maestro vs almacenes."""
    total_maestro = int(producto.stock or 0)
    if not producto or not _tablas_inventario_almacen_existen():
        return {
            'tienda': total_maestro,
            'bodega': 0,
            'total_almacenes': total_maestro,
            'total_maestro': total_maestro,
            'desajustado': False,
        }
    tid = id_almacen_tienda()
    bid = id_almacen_bodega()
    tienda = int(stock_producto_en_almacen(producto.id, tid) or 0) if tid else 0
    bodega = int(stock_producto_en_almacen(producto.id, bid) or 0) if bid else 0
    try:
        total_almacenes = int(db.session.execute(
            text("SELECT COALESCE(SUM(cantidad), 0) FROM stock_por_almacen WHERE id_producto = :p"),
            {"p": int(producto.id)},
        ).scalar() or 0)
    except Exception:
        db.session.rollback()
        total_almacenes = total_maestro
    return {
        'tienda': tienda,
        'bodega': bodega,
        'total_almacenes': total_almacenes,
        'total_maestro': total_maestro,
        'desajustado': total_almacenes != total_maestro,
    }


def _adjuntar_stock_ui(productos):
    for producto in productos or []:
        producto.stock_ui = _stock_ui_producto(producto)
    return productos


def precio_efectivo_pos_producto(producto):
    """Precio unitario para POS y filtros: mayor entre precio_venta y precio_mayoreo."""
    if not producto:
        return 0.0
    return max(float(producto.precio_venta or 0), float(producto.precio_mayoreo or 0))


def descontar_stock_venta_tienda(producto, consumo_stock):
    """
    Descuenta stock de venta (almacén TIENDA). Mantiene productos.stock como suma por almacén.
    Devuelve mensaje de error o None.
    """
    if consumo_stock <= 0:
        return "Consumo de stock inválido."
    aid = id_almacen_tienda()
    if aid and _tablas_inventario_almacen_existen():
        _, err = ajustar_stock_almacen(producto.id, aid, -int(consumo_stock))
        if err:
            return err
        _refrescar_stock_total_producto(producto)
    else:
        if (producto.stock or 0) < consumo_stock:
            return "Stock insuficiente."
        producto.stock = (producto.stock or 0) - int(consumo_stock)
    return None


def aplicar_stock_desde_catalogo_a_tienda(producto):
    """
    Tras importar/editar productos.stock masivamente: todo el saldo del catálogo se interpreta como TIENDA.
    Reinicia BODEGA a 0 para ese producto y recalcula el total como suma por almacén.
    """
    if not producto or not _tablas_inventario_almacen_existen():
        return
    aid_t = id_almacen_tienda()
    aid_b = id_almacen_bodega()
    if not aid_t:
        return
    try:
        tgt = int(producto.stock or 0)
    except (TypeError, ValueError):
        tgt = 0
    if aid_b:
        fijar_stock_almacen(producto.id, aid_b, 0)
    fijar_stock_almacen(producto.id, aid_t, tgt)
    _refrescar_stock_total_producto(producto)


# --- VENTA ---
class Venta(db.Model):
    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    monto_total = db.Column(db.Float, nullable=False, default=0.0)
    usuario = db.Column(db.String(50))
    estado = db.Column(db.String(20), default="Pendiente")
    
    # --- NUEVOS CAMPOS TRIBUTARIOS ---
    tipo_documento = db.Column(db.String(20), default="Boleta") # Boleta o Factura
    nro_documento = db.Column(db.Integer, nullable=True)        # Folio del SII
    neto = db.Column(db.Float, default=0.0)
    iva = db.Column(db.Float, default=0.0)
    # ---------------------------------

    metodo_pago = db.Column(db.String(20), nullable=True)
    monto_recibido = db.Column(db.Float, nullable=True)
    vuelto = db.Column(db.Float, nullable=True)
    saldo_favor_usado = db.Column(db.Float, nullable=False, default=0.0)
    prioridad = db.Column(db.Integer)

    motivo_anulacion = db.Column(db.String(500), nullable=True)
    fecha_anulacion = db.Column(db.DateTime, nullable=True)
    usuario_anulacion = db.Column(db.String(80), nullable=True)
    punto_retiro = db.Column(db.String(30), nullable=True, default='Bodega')

    # Relaciones
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=True)
    caja = db.relationship('Caja', back_populates='ventas')

    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    cliente = db.relationship('Cliente', backref='ventas')

    detalles = db.relationship(
        'DetalleVenta',
        backref='venta',
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Lógica Tributaria: Desglose de IVA (Chile 19%)
    def desglosar_iva(self):
        """Calcula Neto e IVA a partir del Monto Total"""
        if self.monto_total > 0:
            self.neto = round(self.monto_total / 1.19)
            self.iva = self.monto_total - self.neto
        else:
            self.neto = 0.0
            self.iva = 0.0

    # Método para recalcular el total automáticamente
    def recalcular_total(self):
        bruto = sum(
            (d.cantidad * d.precio_unitario) * (1 - ((d.descuento or 0) / 100))
            for d in self.detalles
        )
        # En CLP no se cobran centavos: redondeamos al peso entero más cercano
        # para evitar inputs HTML con step inválidos (ej. 538893.48 vs 550000).
        self.monto_total = float(round(bruto or 0))
        # Aprovechamos de actualizar impuestos si ya tenemos el total
        self.desglosar_iva()

    @property
    def total(self):
        return self.monto_total

    @total.setter
    def total(self, value):
        self.monto_total = float(value) if value else 0.0
        self.desglosar_iva() # Sincroniza impuestos al cambiar el total

        
# --- DETALLE VENTA ---

class DetalleVenta(db.Model):
    __tablename__ = 'detalle_ventas'   # nombre exacto de la tabla en MySQL

    id = db.Column(db.Integer, primary_key=True)
    id_venta = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    id_producto = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)

    cantidad = db.Column(db.Integer, default=1)
    precio_unitario = db.Column(db.Float, nullable=False, default=0.0)
    descuento = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, default=0.0)

    # Relación con producto
    producto = db.relationship('Producto')

# 4. CAJA: se define después de Venta para que la relación funcione
class Caja(db.Model):
    __tablename__ = 'caja'
    id = db.Column(db.Integer, primary_key=True)
    fecha_apertura = db.Column(db.DateTime, default=db.func.current_timestamp())
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    monto_inicial = db.Column(db.Float, nullable=False)
    monto_final = db.Column(db.Float, nullable=True)
    monto_teorico_cierre = db.Column(db.Float, nullable=True)
    monto_contado_cierre = db.Column(db.Float, nullable=True)
    diferencia_cierre = db.Column(db.Float, nullable=True)
    observacion_cierre = db.Column(db.String(255), nullable=True)
    supervisor_cierre = db.Column(db.String(80), nullable=True)
    estado = db.Column(db.String(20), default="Abierta")
    usuario_apertura = db.Column(db.String(50))
    usuario_cierre = db.Column(db.String(50))

    # Relación con ventas
    ventas = db.relationship('Venta', back_populates='caja', lazy=True)

    # Relación con movimientos
    movimientos = db.relationship('MovimientoCaja', backref='caja', lazy=True)


# 5. MOVIMIENTO CAJA: ingresos/egresos asociados a una caja
class MovimientoCaja(db.Model):
    __tablename__ = 'movimiento_caja'
    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    tipo = db.Column(db.String(20))
    concepto = db.Column(db.String(255))
    monto = db.Column(db.Float, nullable=False)
    responsable_retiro = db.Column(db.String(120), nullable=True)
    usuario_registro = db.Column(db.String(80), nullable=True)


# 6. PROVEEDOR: datos de proveedores
class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(100))
    # Nota: en algunas instalaciones la tabla no tiene columna RFC.
    # Se omite del modelo para mantener compatibilidad.


class OrdenCompra(db.Model):
    """Orden de compra a proveedor (base para conciliar con recepción y factura en fases futuras)."""
    __tablename__ = 'ordenes_compra'
    __table_args__ = (UniqueConstraint('proveedor_id', 'numero', name='uq_oc_proveedor_numero'),)

    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    numero = db.Column(db.String(50), nullable=False)
    fecha_emision = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default='Borrador')
    observacion = db.Column(db.String(500))
    usuario_creador = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())

    proveedor = db.relationship('Proveedor', backref='ordenes_compra')
    detalles = db.relationship(
        'DetalleOrdenCompra',
        backref='orden',
        lazy=True,
        cascade='all, delete-orphan',
    )

    @property
    def total_estimado(self):
        """Suma cantidad × precio_unitario de las líneas (no hay columna en BD)."""
        return sum(
            float(d.cantidad or 0) * float(d.precio_unitario or 0) for d in (self.detalles or [])
        )


class DetalleOrdenCompra(db.Model):
    __tablename__ = 'detalle_orden_compra'
    id = db.Column(db.Integer, primary_key=True)
    orden_compra_id = db.Column(db.Integer, db.ForeignKey('ordenes_compra.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Float, nullable=False, default=0.0)
    precio_unitario = db.Column(db.Float, nullable=False, default=0.0)

    producto = db.relationship('Producto', backref='detalles_orden_compra')


# 7. CLIENTE: datos de clientes con Control de Crédito
class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    rut = db.Column(db.String(12), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    giro = db.Column(db.String(100))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    correo = db.Column(db.String(100))
    comuna = db.Column(db.String(80))
    ciudad = db.Column(db.String(80))

    # --- CAMPOS PREMIUM PARA CRÉDITO ---
    saldo_deudor = db.Column(db.Float, default=0.0)      # Cuánto debe actualmente
    limite_credito = db.Column(db.Float, default=500000.0) # Máximo que le podemos fiar
    estado_credito = db.Column(db.String(20), default="Activo") # Activo o Bloqueado

    # Relación con sus abonos (Historial de pagos)
    abonos = db.relationship('AbonoCredito', backref='cliente', lazy=True)

    @property
    def cupo_disponible(self):
        """Calcula cuánto más le podemos fiar"""
        return self.limite_credito - self.saldo_deudor

    @property
    def tiene_deuda(self):
        """Devuelve True si debe dinero, útil para alertas en el POS"""
        return self.saldo_deudor > 0

# 8. ROLES Y USUARIOS: control de acceso y permisos
class Rol(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(20), unique=True, nullable=False)
    descripcion = db.Column(db.String(100))

    usuarios = db.relationship('Usuario', back_populates='rol')
    rol_permisos = db.relationship('RolPermiso', back_populates='rol')

# 9. USUARIO: para login y control de acceso
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    rol_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    perfil = db.Column(db.String(20))

    rol = db.relationship('Rol', back_populates='usuarios')

    # Guardar contraseña encriptada
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Verificar contraseña
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 10. Permisos y relación con roles para control de acceso granular
class Permiso(db.Model):
    __tablename__ = 'permisos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)

# 11. Tabla intermedia para relación muchos a muchos entre roles y permisos
class RolPermiso(db.Model):
    __tablename__ = 'rol_permisos'
    id = db.Column(db.Integer, primary_key=True)
    rol_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    permiso_id = db.Column(db.Integer, db.ForeignKey('permisos.id'))

    rol = db.relationship('Rol', back_populates='rol_permisos')
    permiso = db.relationship('Permiso', backref='rol_permisos')


class UnidadMedida(db.Model):
    __tablename__ = 'unidades_medida'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)
    nombre = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='unidad')
    activo = db.Column(db.Boolean, default=True)


class ConversionUnidad(db.Model):
    __tablename__ = 'conversiones_unidad'
    id = db.Column(db.Integer, primary_key=True)
    unidad_origen_id = db.Column(db.Integer, db.ForeignKey('unidades_medida.id'), nullable=False)
    unidad_destino_id = db.Column(db.Integer, db.ForeignKey('unidades_medida.id'), nullable=False)
    factor = db.Column(db.Float, nullable=False, default=1.0)
    activo = db.Column(db.Boolean, default=True)

    unidad_origen = db.relationship('UnidadMedida', foreign_keys=[unidad_origen_id])
    unidad_destino = db.relationship('UnidadMedida', foreign_keys=[unidad_destino_id])

# --- MODELOS PARA LOGÍSTICA Y BODEGA ---

class RecepcionCompra(db.Model):
    __tablename__ = 'recepciones_compra'
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    orden_compra_id = db.Column(db.Integer, db.ForeignKey('ordenes_compra.id'), nullable=True)
    documento_tipo = db.Column(
        db.Enum('Factura', 'Guia de Despacho', name='recepciones_documento_tipo_enum'),
        nullable=False
    )
    documento_numero = db.Column(db.String(50), nullable=False)
    fecha_recepcion = db.Column(db.DateTime, default=db.func.current_timestamp())
    usuario_bodega = db.Column(db.String(100))
    estado = db.Column(
        db.Enum('Pendiente', 'Incompleta', 'Finalizada', name='recepciones_estado_enum'),
        default='Pendiente'
    )

    proveedor = db.relationship('Proveedor', backref='recepciones')
    orden_compra = db.relationship('OrdenCompra', backref='recepciones')
    detalles = db.relationship('DetalleRecepcion', backref='recepcion', lazy=True)


class DetalleRecepcion(db.Model):
    __tablename__ = 'detalle_recepcion'
    id = db.Column(db.Integer, primary_key=True)
    recepcion_id = db.Column(db.Integer, db.ForeignKey('recepciones_compra.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad_documento = db.Column(db.Integer, nullable=False)
    cantidad_recibida = db.Column(db.Integer, nullable=False)

    producto = db.relationship('Producto', backref='detalles_recepcion')


class MovimientoInventario(db.Model):
    """Kardex / historial de movimientos de stock (entradas, salidas, ajustes)."""
    __tablename__ = 'movimientos_inventario'
    id = db.Column(db.Integer, primary_key=True)
    id_producto = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    id_almacen = db.Column(db.Integer, nullable=False, default=1)
    tipo_movimiento = db.Column(db.String(20), nullable=False)  # ENTRADA, SALIDA, AJUSTE
    cantidad = db.Column(db.Integer, nullable=False)
    motivo = db.Column(db.String(500))
    usuario = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    referencia_tipo = db.Column(db.String(40), nullable=True)
    referencia_id = db.Column(db.Integer, nullable=True)
    stock_saldo = db.Column(db.Integer, nullable=True)

    producto = db.relationship('Producto', backref='movimientos_kardex')


class BitacoraCostoCompra(db.Model):
    __tablename__ = 'bitacora_costos_compra'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=True)
    recepcion_id = db.Column(db.Integer, db.ForeignKey('recepciones_compra.id'), nullable=True)
    costo_anterior = db.Column(db.Float, nullable=False, default=0.0)
    costo_nuevo = db.Column(db.Float, nullable=False, default=0.0)
    variacion_pct = db.Column(db.Float, nullable=True)
    precio_venta_referencia = db.Column(db.Float, nullable=True)
    margen_proyectado = db.Column(db.Float, nullable=True)
    usuario = db.Column(db.String(100), nullable=True)
    observacion = db.Column(db.String(255), nullable=True)

    producto = db.relationship('Producto')
    proveedor = db.relationship('Proveedor')


class BitacoraPrecioVenta(db.Model):
    __tablename__ = 'bitacora_precios_venta'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    precio_anterior = db.Column(db.Float, nullable=False, default=0.0)
    precio_nuevo = db.Column(db.Float, nullable=False, default=0.0)
    costo_referencia = db.Column(db.Float, nullable=True)
    margen_objetivo = db.Column(db.Float, nullable=True)
    usuario = db.Column(db.String(100), nullable=True)
    motivo = db.Column(db.String(255), nullable=True)

    producto = db.relationship('Producto')


class CambioOperacion(db.Model):
    __tablename__ = 'cambios_operacion'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    venta_origen_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=True)
    total_devuelto = db.Column(db.Float, nullable=False, default=0.0)
    total_entregado = db.Column(db.Float, nullable=False, default=0.0)
    saldo_usado = db.Column(db.Float, nullable=False, default=0.0)
    monto_pagado = db.Column(db.Float, nullable=False, default=0.0)
    monto_devuelto_efectivo = db.Column(db.Float, nullable=False, default=0.0)
    saldo_generado = db.Column(db.Float, nullable=False, default=0.0)
    observacion = db.Column(db.String(500), nullable=True)

    cliente = db.relationship('Cliente', backref='cambios_operacion')
    caja = db.relationship('Caja')
    usuario = db.relationship('Usuario')
    venta_origen = db.relationship('Venta', foreign_keys=[venta_origen_id])


class CambioDetalle(db.Model):
    __tablename__ = 'cambios_detalle'
    id = db.Column(db.Integer, primary_key=True)
    cambio_id = db.Column(db.Integer, db.ForeignKey('cambios_operacion.id', ondelete='CASCADE'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id', ondelete='RESTRICT'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # DEVUELTO / ENTREGADO
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Float, nullable=False, default=0.0)
    subtotal = db.Column(db.Float, nullable=False, default=0.0)

    cambio = db.relationship('CambioOperacion', backref='detalles')
    producto = db.relationship('Producto')


class ClienteSaldoFavor(db.Model):
    __tablename__ = 'clientes_saldos_favor'
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id', ondelete='CASCADE'), primary_key=True)
    saldo = db.Column(db.Float, nullable=False, default=0.0)
    actualizado_en = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    cliente = db.relationship('Cliente', backref=db.backref('saldo_favor_registro', uselist=False))


class MovimientoSaldoFavor(db.Model):
    __tablename__ = 'movimientos_saldo_favor'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id', ondelete='CASCADE'), nullable=False)
    cambio_id = db.Column(db.Integer, db.ForeignKey('cambios_operacion.id', ondelete='SET NULL'), nullable=True)
    tipo = db.Column(db.String(20), nullable=False)  # CREDITO / DEBITO
    monto = db.Column(db.Float, nullable=False, default=0.0)
    saldo_resultante = db.Column(db.Float, nullable=False, default=0.0)
    observacion = db.Column(db.String(255), nullable=True)

    cliente = db.relationship('Cliente', backref='movimientos_saldo_favor')
    cambio = db.relationship('CambioOperacion')


def registrar_movimiento_kardex(
    id_producto,
    tipo_movimiento,
    cantidad,
    motivo,
    usuario=None,
    id_almacen=1,
    referencia_tipo=None,
    referencia_id=None,
    stock_saldo=None,
):
    """Registra una línea de kardex. La cantidad se guarda siempre como entero positivo."""
    try:
        c = int(cantidad)
    except (TypeError, ValueError):
        return
    if c <= 0:
        return
    ref_t = (referencia_tipo or '')[:40] if referencia_tipo else None
    ref_id = int(referencia_id) if referencia_id is not None else None
    almacen_id = None
    if _tablas_inventario_almacen_existen():
        try:
            if id_almacen:
                existe = db.session.execute(
                    text("SELECT 1 FROM almacenes WHERE id = :id LIMIT 1"),
                    {"id": int(id_almacen)},
                ).scalar()
                if existe:
                    almacen_id = int(id_almacen)
            if not almacen_id:
                almacen_id = db.session.execute(
                    text("SELECT id FROM almacenes ORDER BY id ASC LIMIT 1")
                ).scalar()
        except Exception:
            almacen_id = None
        if not almacen_id:
            return
    else:
        try:
            almacen_id = int(id_almacen) if id_almacen else 1
        except (TypeError, ValueError):
            almacen_id = 1

    saldo = int(stock_saldo) if stock_saldo is not None else None
    if _tablas_inventario_almacen_existen():
        s_alm = stock_producto_en_almacen(int(id_producto), int(almacen_id))
        if s_alm is not None:
            saldo = s_alm
    elif saldo is None:
        try:
            p = Producto.query.get(int(id_producto))
            saldo = int(p.stock) if p and p.stock is not None else 0
        except Exception:
            saldo = None

    mov = MovimientoInventario(
        id_producto=id_producto,
        id_almacen=almacen_id,
        tipo_movimiento=(tipo_movimiento or '')[:20],
        cantidad=c,
        motivo=(motivo or '')[:500] if motivo else None,
        usuario=(usuario or '')[:100] if usuario else None,
        fecha=datetime.now(),
        referencia_tipo=ref_t or None,
        referencia_id=ref_id,
        stock_saldo=saldo,
    )
    db.session.add(mov)


def _bitacora_costos_disponible():
    estado = app.config.get("_BITACORA_COSTOS_OK")
    if estado is not None:
        return bool(estado)
    try:
        ok = db.session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'bitacora_costos_compra' LIMIT 1"
            )
        ).scalar() is not None
    except Exception:
        ok = False
    app.config["_BITACORA_COSTOS_OK"] = bool(ok)
    return bool(ok)


def registrar_bitacora_costo(
    producto_id,
    proveedor_id,
    recepcion_id,
    costo_anterior,
    costo_nuevo,
    precio_venta_referencia,
    usuario,
    observacion=None,
):
    if not _bitacora_costos_disponible():
        return
    try:
        ca = float(costo_anterior or 0)
        cn = float(costo_nuevo or 0)
        pv = float(precio_venta_referencia or 0)
        variacion = ((cn - ca) / ca) if ca > 0 else None
        margen_proj = ((pv - cn) / cn) if cn > 0 and pv > 0 else None
        db.session.add(
            BitacoraCostoCompra(
                producto_id=producto_id,
                proveedor_id=proveedor_id,
                recepcion_id=recepcion_id,
                costo_anterior=ca,
                costo_nuevo=cn,
                variacion_pct=variacion,
                precio_venta_referencia=pv if pv > 0 else None,
                margen_proyectado=margen_proj,
                usuario=(usuario or "")[:100] if usuario else None,
                observacion=(observacion or "")[:255] if observacion else None,
            )
        )
    except Exception:
        # Nunca bloquea la recepción por bitácora auxiliar.
        pass


def _bitacora_precios_disponible():
    estado = app.config.get("_BITACORA_PRECIOS_OK")
    if estado is not None:
        return bool(estado)
    try:
        ok = db.session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'bitacora_precios_venta' LIMIT 1"
            )
        ).scalar() is not None
    except Exception:
        ok = False
    app.config["_BITACORA_PRECIOS_OK"] = bool(ok)
    return bool(ok)


def registrar_bitacora_precio(producto_id, precio_anterior, precio_nuevo, costo_referencia, margen_objetivo, usuario, motivo):
    if not _bitacora_precios_disponible():
        return
    try:
        db.session.add(
            BitacoraPrecioVenta(
                producto_id=producto_id,
                precio_anterior=float(precio_anterior or 0),
                precio_nuevo=float(precio_nuevo or 0),
                costo_referencia=float(costo_referencia or 0) if costo_referencia is not None else None,
                margen_objetivo=float(margen_objetivo or 0) if margen_objetivo is not None else None,
                usuario=(usuario or '')[:100] if usuario else None,
                motivo=(motivo or '')[:255] if motivo else None,
            )
        )
    except Exception:
        pass


def _unidades_disponibles():
    estado = app.config.get("_UNIDADES_OK")
    if estado is not None:
        return bool(estado)
    try:
        ok = db.session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'unidades_medida' LIMIT 1"
            )
        ).scalar() is not None
    except Exception:
        ok = False
    app.config["_UNIDADES_OK"] = bool(ok)
    return bool(ok)


def _seed_unidades_base():
    if not _unidades_disponibles():
        return
    base = [
        ("UN", "Unidad", "unidad"),
        ("KG", "Kilogramo", "peso"),
        ("M", "Metro", "longitud"),
        ("CJ", "Caja", "empaque"),
        ("SC", "Saco", "empaque"),
        ("RL", "Rollo", "empaque"),
        ("LT", "Litro", "volumen"),
    ]
    cambios = False
    for codigo, nombre, tipo in base:
        ex = UnidadMedida.query.filter_by(codigo=codigo).first()
        if not ex:
            db.session.add(UnidadMedida(codigo=codigo, nombre=nombre, tipo=tipo, activo=True))
            cambios = True
    if cambios:
        db.session.commit()


def _factor_compra_a_stock(producto):
    """
    Define cuánto stock (unidad de venta/base) ingresa por 1 unidad de compra.
    Prioriza tabla de conversiones; si no existe, usa factor_conversion del producto.
    """
    if not producto:
        return 1.0

    # Caso simple: compra y venta en la misma unidad.
    uc = (producto.unidad_compra or '').strip().upper()
    uv = (producto.unidad_venta or producto.unidad or '').strip().upper()
    if uc and uv and uc == uv:
        return 1.0

    # Si existe catálogo de conversiones, intentamos resolver por código/nombre.
    if _unidades_disponibles() and uc and uv:
        try:
            u_origen = UnidadMedida.query.filter(
                (UnidadMedida.codigo == uc) | (UnidadMedida.nombre.ilike(uc))
            ).first()
            u_destino = UnidadMedida.query.filter(
                (UnidadMedida.codigo == uv) | (UnidadMedida.nombre.ilike(uv))
            ).first()
            if u_origen and u_destino:
                conv = ConversionUnidad.query.filter_by(
                    unidad_origen_id=u_origen.id,
                    unidad_destino_id=u_destino.id,
                    activo=True,
                ).first()
                if conv and float(conv.factor or 0) > 0:
                    return float(conv.factor)
        except Exception:
            pass

    # Fallback: factor del producto (legacy).
    try:
        f = float(producto.factor_conversion or 1)
    except Exception:
        f = 1
    return f if f > 0 else 1.0


def _factor_venta_a_stock(producto):
    """
    Cuánto stock base se descuenta por 1 unidad de venta.
    Prioriza catálogo de conversiones (unidad_venta -> unidad base/legacy).
    Fallback: 1 (comportamiento actual), para no romper operación existente.
    """
    if not producto:
        return 1.0

    uv = (producto.unidad_venta or producto.unidad or '').strip().upper()
    ub = (producto.unidad or producto.unidad_venta or '').strip().upper()
    if uv and ub and uv == ub:
        return 1.0

    if _unidades_disponibles() and uv and ub:
        try:
            u_origen = UnidadMedida.query.filter(
                (UnidadMedida.codigo == uv) | (UnidadMedida.nombre.ilike(uv))
            ).first()
            u_destino = UnidadMedida.query.filter(
                (UnidadMedida.codigo == ub) | (UnidadMedida.nombre.ilike(ub))
            ).first()
            if u_origen and u_destino:
                conv = ConversionUnidad.query.filter_by(
                    unidad_origen_id=u_origen.id,
                    unidad_destino_id=u_destino.id,
                    activo=True,
                ).first()
                if conv and float(conv.factor or 0) > 0:
                    return float(conv.factor)
        except Exception:
            pass
    return 1.0


# Auditoría de inventario para control de stock físico vs sistema, con opción de ajuste automático

class AuditoriaInventario(db.Model):
    __tablename__ = 'auditorias_inventario'
    id = db.Column(db.Integer, primary_key=True)
    fecha_inicio = db.Column(db.DateTime, default=db.func.current_timestamp())
    fecha_fin = db.Column(db.DateTime, nullable=True)
    usuario_auditor = db.Column(db.String(100))
    sector_bodega = db.Column(db.String(50))
    estado = db.Column(
        db.Enum('En Proceso', 'Finalizada', 'Ajustada', name='auditorias_estado_enum'),
        default='En Proceso'
    )

class DetalleAuditoria(db.Model):
    __tablename__ = 'detalle_auditoria'
    id = db.Column(db.Integer, primary_key=True)
    auditoria_id = db.Column(db.Integer, db.ForeignKey('auditorias_inventario.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    stock_sistema = db.Column(db.Integer, nullable=False)
    stock_fisico = db.Column(db.Integer, nullable=False)
    # La diferencia la calcularemos en la lógica de Python al guardar

# Lógica interna para nivelar el stock
def aplicar_ajuste_automatico(auditoria_id):
    detalles = DetalleAuditoria.query.filter_by(auditoria_id=auditoria_id).all()
    usr = current_user.nombre if current_user.is_authenticated else 'Sistema'
    aid_bod = id_almacen_bodega()

    for d in detalles:
        producto = Producto.query.get(d.producto_id)
        if aid_bod and _tablas_inventario_almacen_existen():
            fijar_stock_almacen(producto.id, aid_bod, d.stock_fisico)
            _refrescar_stock_total_producto(producto)
        else:
            producto.stock = d.stock_fisico
        diff = abs(d.stock_fisico - d.stock_sistema)
        if diff > 0:
            registrar_movimiento_kardex(
                producto.id,
                'AJUSTE',
                diff,
                f"Ajuste por Auditoría móvil #{auditoria_id}",
                usuario=usr,
                id_almacen=aid_bod or 1,
                referencia_tipo='auditoria',
                referencia_id=auditoria_id,
                stock_saldo=d.stock_fisico,
            )

    db.session.commit()


# --- RUTAS DE NAVEGACIÓN ---
# Página de inicio, redirige a punto de venta si ya está logueado, sino muestra bienvenida
@app.route('/')
@app.route('/index')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('owner_mobile'))  # primera vista de impacto para demo
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"}), 200


@app.route('/catalogo')
def catalogo_publico():
    """Catálogo público de consulta (solo lectura)."""
    q = (request.args.get('q') or '').strip()
    categoria = (request.args.get('categoria') or '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    mostrar_precio_publico = (os.getenv("PUBLICO_MUESTRA_PRECIO", "1").strip().lower() in ("1", "true", "si", "yes", "on"))
    mostrar_stock_exacto_publico = (os.getenv("PUBLICO_MUESTRA_STOCK_EXACTO", "1").strip().lower() in ("1", "true", "si", "yes", "on"))
    whatsapp_ventas = ''.join(ch for ch in (os.getenv("WHATSAPP_VENTAS", "") or "") if ch.isdigit())
    wa_base = f"https://wa.me/{whatsapp_ventas}" if whatsapp_ventas else None

    productos = Producto.query.filter(Producto.activo == True)
    if q:
        like = f"%{q}%"
        productos = productos.filter(
            (Producto.nombre.like(like)) |
            (Producto.codigo_barra.like(like))
        )
    if categoria:
        productos = productos.filter(Producto.categoria == categoria)

    productos_pagination = productos.order_by(Producto.nombre.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    categorias = [c[0] for c in db.session.query(Producto.categoria).distinct().order_by(Producto.categoria).all() if c[0]]
    return render_template(
        'catalogo_publico.html',
        productos=productos_pagination.items,
        productos_pagination=productos_pagination,
        q=q,
        categoria=categoria,
        categorias=categorias,
        mostrar_precio_publico=mostrar_precio_publico,
        mostrar_stock_exacto_publico=mostrar_stock_exacto_publico,
        wa_base=wa_base,
    )


@app.route('/consulta-stock')
def consulta_stock_publica():
    """Consulta pública y rápida de disponibilidad de stock."""
    q = (request.args.get('q') or '').strip()
    mostrar_precio_publico = (os.getenv("PUBLICO_MUESTRA_PRECIO", "1").strip().lower() in ("1", "true", "si", "yes", "on"))
    mostrar_stock_exacto_publico = (os.getenv("PUBLICO_MUESTRA_STOCK_EXACTO", "1").strip().lower() in ("1", "true", "si", "yes", "on"))
    whatsapp_ventas = ''.join(ch for ch in (os.getenv("WHATSAPP_VENTAS", "") or "") if ch.isdigit())
    wa_base = f"https://wa.me/{whatsapp_ventas}" if whatsapp_ventas else None
    productos = []
    if q:
        like = f"%{q}%"
        productos = (
            Producto.query.filter(
                Producto.activo == True,
                (Producto.nombre.like(like)) | (Producto.codigo_barra.like(like))
            )
            .order_by(Producto.stock.desc(), Producto.nombre.asc())
            .limit(50)
            .all()
        )
    return render_template(
        'consulta_stock_publica.html',
        q=q,
        productos=productos,
        mostrar_precio_publico=mostrar_precio_publico,
        mostrar_stock_exacto_publico=mostrar_stock_exacto_publico,
        wa_base=wa_base,
    )
# --- INICIO - DASHBOARD ---........................................................................
@app.route('/inicio')
@login_required
def inicio():
  
    # KPIs principales.........................................................

    stock_activo = db.session.query(db.func.sum(Producto.stock)).filter(
        Producto.activo == True,
        Producto.stock > 0
    ).scalar() or 0

    bajo_stock = Producto.query.filter(
        Producto.stock < 5,
        Producto.activo == True
    ).count()

    ventas_hoy = db.session.query(db.func.sum(Venta.monto_total)).filter(
        db.func.date(Venta.fecha) == db.func.current_date()
    ).scalar() or 0

    transacciones = Venta.query.count()
    transacciones_hoy = Venta.query.filter(
        db.func.date(Venta.fecha) == db.func.current_date()
    ).count()

    dinero_credito = db.session.query(db.func.sum(Cliente.saldo_deudor)).scalar() or 0

    retiros_caja_hoy = db.session.query(db.func.sum(MovimientoCaja.monto)).filter(
        MovimientoCaja.tipo == "Egreso",
        db.func.date(MovimientoCaja.fecha) == db.func.current_date()
    ).scalar() or 0

    ayer = datetime.now().date() - timedelta(days=1)
    ventas_ayer = db.session.query(db.func.sum(Venta.monto_total)).filter(
        db.func.date(Venta.fecha) == ayer
    ).scalar() or 0
    transacciones_ayer = Venta.query.filter(
        db.func.date(Venta.fecha) == ayer
    ).count()
    retiros_caja_ayer = db.session.query(db.func.sum(MovimientoCaja.monto)).filter(
        MovimientoCaja.tipo == "Egreso",
        db.func.date(MovimientoCaja.fecha) == ayer
    ).scalar() or 0

    def _delta_pct(actual, previo):
        if not previo:
            return None
        return ((float(actual) - float(previo)) / float(previo)) * 100.0

    var_ventas_hoy = _delta_pct(ventas_hoy, ventas_ayer)
    var_transacciones_hoy = _delta_pct(transacciones_hoy, transacciones_ayer)
    var_retiros_hoy = _delta_pct(retiros_caja_hoy, retiros_caja_ayer)

    oc_pendientes = 0
    oc_monto_pendiente = 0.0
    if _tablas_orden_compra_existen():
        oc_estados_pend = ('Borrador', 'Enviada', 'Parcial')
        oc_fil = OrdenCompra.estado.in_(oc_estados_pend)
        oc_pendientes = OrdenCompra.query.filter(oc_fil).count()
        oc_para_monto = (
            OrdenCompra.query.options(joinedload(OrdenCompra.detalles))
            .filter(oc_fil)
            .limit(300)
            .all()
        )
        oc_monto_pendiente = sum(float(o.total_estimado or 0) for o in oc_para_monto)

    hoy = datetime.now().date()
    fecha_hoy_str = hoy.strftime("%Y-%m-%d")
    ventas_hoy_detalle = (
        Venta.query.filter(
            db.func.date(Venta.fecha) == hoy,
            or_(Venta.estado.is_(None), Venta.estado != 'Abierta')
        )
        .order_by(Venta.id.desc())
        .limit(15)
        .all()
    )

    # Datos últimos 7 días..............................................................

    datos_grafico, labels_grafico = [], []
    for i in range(6, -1, -1):
        fecha_consulta = datetime.now().date() - timedelta(days=i)
        monto_dia = db.session.query(db.func.sum(Venta.monto_total)).filter(
            db.func.date(Venta.fecha) == fecha_consulta
        ).scalar() or 0
        datos_grafico.append(float(monto_dia))
        labels_grafico.append(fecha_consulta.strftime('%d/%m'))

    # Predicción simple de quiebre (7/14 días) + compra sugerida asistida
    d30_inicio = datetime.combine(hoy - timedelta(days=30), datetime.min.time())
    d7_inicio = datetime.combine(hoy - timedelta(days=7), datetime.min.time())
    ahora = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
    mes_actual = hoy.month

    consumo_30 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d30_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )
    consumo_7 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d7_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )
    d90_inicio = datetime.combine(hoy - timedelta(days=90), datetime.min.time())
    consumo_90 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d90_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )

    riesgo_quiebre = []
    quiebre_7 = 0
    quiebre_14 = 0
    riesgo_mixto = 0
    compra_sugerida_total = 0
    compra_sugerida_skus = 0
    for p in Producto.query.filter(Producto.activo == True).all():
        c30 = float(consumo_30.get(p.id, 0) or 0)
        c7 = float(consumo_7.get(p.id, 0) or 0)
        c90 = float(consumo_90.get(p.id, 0) or 0)
        base_dia = c30 / 30.0
        t30 = c30 / 30.0
        t7 = c7 / 7.0
        ratio_tend = max(0.70, min(1.35, (t7 / t30))) if t30 > 0 else 1.0
        factor_est = _factor_estacional_categoria(p.categoria, mes_actual)
        demanda_dia = base_dia * ratio_tend * factor_est
        stock_actual = float(p.stock or 0)
        cobertura = (stock_actual / demanda_dia) if demanda_dia > 0 else 9999
        sugerido = max(0, int(round((demanda_dia * 30.0) - stock_actual)))

        if sugerido > 0:
            compra_sugerida_skus += 1
            compra_sugerida_total += sugerido
        if demanda_dia <= 0:
            continue
        if cobertura <= 7:
            quiebre_7 += 1
            riesgo_quiebre.append({
                "producto": p.nombre,
                "stock": int(round(stock_actual)),
                "cobertura": round(cobertura, 1),
                "sugerido": sugerido,
                "nivel": "CRITICO",
                "motivo": "Quiebre proyectado <= 7 días",
                "query_hint": p.codigo_barra or p.nombre,
            })
        elif cobertura <= 14:
            quiebre_14 += 1
            riesgo_quiebre.append({
                "producto": p.nombre,
                "stock": int(round(stock_actual)),
                "cobertura": round(cobertura, 1),
                "sugerido": sugerido,
                "nivel": "MEDIO",
                "motivo": "Quiebre proyectado entre 8 y 14 días",
                "query_hint": p.codigo_barra or p.nombre,
            })
        elif stock_actual < 5 and c90 > 0:
            # Riesgo mixto: regla operativa + rotación reciente, aunque la proyección corta no dispare quiebre.
            riesgo_mixto += 1
            riesgo_quiebre.append({
                "producto": p.nombre,
                "stock": int(round(stock_actual)),
                "cobertura": round(cobertura, 1) if cobertura < 9999 else 9999,
                "sugerido": sugerido,
                "nivel": "MIXTO",
                "motivo": "Stock crítico + movimiento reciente (90d)",
                "query_hint": p.codigo_barra or p.nombre,
            })

    riesgo_quiebre.sort(key=lambda x: x["cobertura"])
    top_quiebre = riesgo_quiebre[:5]

    # Gestión por excepción (acciones sugeridas del día)
    alertas_accionables = []
    if bajo_stock > 0:
        alertas_accionables.append({
            "titulo": f"Hay {bajo_stock} productos con stock crítico",
            "detalle": "Prioriza reposición para no perder ventas hoy.",
            "accion": "Revisar stock crítico",
            "url": url_for('stock_critico', **{'from': 'inicio'}),
            "nivel": "danger",
        })
    if oc_pendientes > 0:
        alertas_accionables.append({
            "titulo": f"{oc_pendientes} órdenes de compra siguen pendientes",
            "detalle": "Valida estado con proveedores para evitar quiebres.",
            "accion": "Ver órdenes pendientes",
            "url": url_for('lista_ordenes_compra', **{'from': 'inicio'}),
            "nivel": "warning",
        })
    if quiebre_7 > 0:
        alertas_accionables.append({
            "titulo": f"{quiebre_7} SKUs con riesgo de quiebre en <= 7 días",
            "detalle": "Prioriza compra sugerida para proteger continuidad de ventas.",
            "accion": "Abrir IA abastecimiento",
            "url": url_for('ia_abastecimiento', dias=30, solo_alerta=1, **{'from': 'inicio'}),
            "nivel": "danger",
        })
    if riesgo_mixto > 0:
        alertas_accionables.append({
            "titulo": f"{riesgo_mixto} SKUs en riesgo mixto",
            "detalle": "Stock crítico con rotación reciente; revisa reposición aunque el quiebre corto no sea crítico.",
            "accion": "Revisar riesgo mixto",
            "url": url_for('ia_abastecimiento', dias=30, solo_alerta=1, **{'from': 'inicio'}),
            "nivel": "warning",
        })
    if transacciones_hoy > 0 and ventas_hoy > 0:
        ticket_hoy = float(ventas_hoy) / float(transacciones_hoy)
        if ticket_hoy < 25000:
            alertas_accionables.append({
                "titulo": "Ticket promedio bajo el umbral objetivo",
                "detalle": "Revisa mix de productos y venta complementaria en caja.",
                "accion": "Ir a ventas de hoy",
                "url": url_for('mostrar_ventas', fecha_inicio=fecha_hoy_str, fecha_fin=fecha_hoy_str, **{'from': 'inicio'}),
                "nivel": "info",
            })
    if not alertas_accionables:
        alertas_accionables.append({
            "titulo": "Operación estable",
            "detalle": "No hay alertas críticas; enfócate en oportunidades de margen.",
            "accion": "Abrir BI",
            "url": url_for('business_intelligence', **{'from': 'inicio'}),
            "nivel": "success",
        })

    return render_template(
        'inicio.html',
        stock_activo=stock_activo,
        bajo_stock=bajo_stock,
        ventas_hoy=ventas_hoy,
        transacciones=transacciones,
        dinero_credito=dinero_credito,
        retiros_caja_hoy=retiros_caja_hoy,
        ventas_ayer=ventas_ayer,
        transacciones_hoy=transacciones_hoy,
        transacciones_ayer=transacciones_ayer,
        retiros_caja_ayer=retiros_caja_ayer,
        var_ventas_hoy=var_ventas_hoy,
        var_transacciones_hoy=var_transacciones_hoy,
        var_retiros_hoy=var_retiros_hoy,
        oc_pendientes=oc_pendientes,
        oc_monto_pendiente=oc_monto_pendiente,
        ventas_hoy_detalle=ventas_hoy_detalle,
        fecha_hoy_str=fecha_hoy_str,
        labels_grafico=labels_grafico,
        datos_grafico=datos_grafico,
        alertas_accionables=alertas_accionables[:3],
        quiebre_7=quiebre_7,
        quiebre_14=quiebre_14,
        riesgo_mixto=riesgo_mixto,
        compra_sugerida_total=compra_sugerida_total,
        compra_sugerida_skus=compra_sugerida_skus,
        top_quiebre=top_quiebre,
    )


@app.route('/owner-mobile')
@login_required
def owner_mobile():
    """Vista mobile-first para propietario (resumen ejecutivo de 1 minuto)."""
    hoy = datetime.now().date()
    ayer = hoy - timedelta(days=1)

    ventas_hoy = db.session.query(db.func.sum(Venta.monto_total)).filter(
        db.func.date(Venta.fecha) == hoy
    ).scalar() or 0
    ventas_ayer = db.session.query(db.func.sum(Venta.monto_total)).filter(
        db.func.date(Venta.fecha) == ayer
    ).scalar() or 0
    transacciones_hoy = Venta.query.filter(db.func.date(Venta.fecha) == hoy).count()
    bajo_stock = Producto.query.filter(Producto.stock < 5, Producto.activo == True).count()
    dinero_credito = db.session.query(db.func.sum(Cliente.saldo_deudor)).scalar() or 0
    oc_pendientes = 0
    if _tablas_orden_compra_existen():
        oc_estados_pend = ('Borrador', 'Enviada', 'Parcial')
        oc_pendientes = OrdenCompra.query.filter(OrdenCompra.estado.in_(oc_estados_pend)).count()

    var_ventas_hoy = None
    if ventas_ayer:
        var_ventas_hoy = ((float(ventas_hoy) - float(ventas_ayer)) / float(ventas_ayer)) * 100.0

    # Predicción simple de quiebre (igual lógica del inicio)
    d30_inicio = datetime.combine(hoy - timedelta(days=30), datetime.min.time())
    d7_inicio = datetime.combine(hoy - timedelta(days=7), datetime.min.time())
    ahora = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
    mes_actual = hoy.month

    consumo_30 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d30_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )
    consumo_7 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d7_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )
    d90_inicio = datetime.combine(hoy - timedelta(days=90), datetime.min.time())
    consumo_90 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d90_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )

    quiebre_7 = 0
    quiebre_14 = 0
    riesgo_mixto = 0
    compra_sugerida_total = 0
    top_quiebre = []
    for p in Producto.query.filter(Producto.activo == True).all():
        c30 = float(consumo_30.get(p.id, 0) or 0)
        c7 = float(consumo_7.get(p.id, 0) or 0)
        c90 = float(consumo_90.get(p.id, 0) or 0)
        base_dia = c30 / 30.0
        t30 = c30 / 30.0
        t7 = c7 / 7.0
        ratio_tend = max(0.70, min(1.35, (t7 / t30))) if t30 > 0 else 1.0
        factor_est = _factor_estacional_categoria(p.categoria, mes_actual)
        demanda_dia = base_dia * ratio_tend * factor_est
        stock_actual = float(p.stock or 0)
        cobertura = (stock_actual / demanda_dia) if demanda_dia > 0 else 9999
        sugerido = max(0, int(round((demanda_dia * 30.0) - stock_actual)))
        compra_sugerida_total += sugerido
        if demanda_dia <= 0:
            continue
        if cobertura <= 7:
            quiebre_7 += 1
            top_quiebre.append({"producto": p.nombre, "cobertura": round(cobertura, 1), "sugerido": sugerido, "nivel": "CRITICO", "motivo": "Quiebre <= 7 días"})
        elif cobertura <= 14:
            quiebre_14 += 1
            top_quiebre.append({"producto": p.nombre, "cobertura": round(cobertura, 1), "sugerido": sugerido, "nivel": "MEDIO", "motivo": "Quiebre 8-14 días"})
        elif stock_actual < 5 and c90 > 0:
            riesgo_mixto += 1
            top_quiebre.append({"producto": p.nombre, "cobertura": round(cobertura, 1) if cobertura < 9999 else 9999, "sugerido": sugerido, "nivel": "MIXTO", "motivo": "Stock crítico + rotación reciente"})
    top_quiebre.sort(key=lambda x: x["cobertura"])

    return render_template(
        'owner_mobile.html',
        fecha_hoy_str=hoy.strftime("%Y-%m-%d"),
        ventas_hoy=ventas_hoy,
        var_ventas_hoy=var_ventas_hoy,
        transacciones_hoy=transacciones_hoy,
        dinero_credito=dinero_credito,
        bajo_stock=bajo_stock,
        oc_pendientes=oc_pendientes,
        quiebre_7=quiebre_7,
        quiebre_14=quiebre_14,
        riesgo_mixto=riesgo_mixto,
        compra_sugerida_total=compra_sugerida_total,
        top_quiebre=top_quiebre[:3],
    )


# --- BUSINESS INTELLIGENCE --------------------------------------------------------------
@app.route('/bi')
@login_required
def business_intelligence():
    hoy = datetime.now().date()
    fi_raw = (request.args.get('fecha_inicio') or '').strip()
    ff_raw = (request.args.get('fecha_fin') or '').strip()

    try:
        fecha_inicio = datetime.strptime(fi_raw, "%Y-%m-%d").date() if fi_raw else (hoy - timedelta(days=29))
    except ValueError:
        fecha_inicio = hoy - timedelta(days=29)
    try:
        fecha_fin = datetime.strptime(ff_raw, "%Y-%m-%d").date() if ff_raw else hoy
    except ValueError:
        fecha_fin = hoy
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    dt_inicio = datetime.combine(fecha_inicio, datetime.min.time())
    dt_fin_excl = datetime.combine(fecha_fin + timedelta(days=1), datetime.min.time())

    def _kpis_rango(dt_i, dt_f):
        ventas_q = Venta.query.filter(Venta.fecha >= dt_i, Venta.fecha < dt_f)
        total_v = (
            ventas_q.filter(Venta.estado == "Pagado")
            .with_entities(db.func.sum(Venta.monto_total))
            .scalar()
            or 0
        )
        docs = ventas_q.count()
        ticket = (total_v / docs) if docs else 0
        credito = (
            ventas_q.filter(Venta.metodo_pago == "Credito")
            .with_entities(db.func.sum(Venta.monto_total))
            .scalar()
            or 0
        )
        return float(total_v), int(docs), float(ticket), float(credito)

    total_ventas, total_documentos, ticket_promedio, total_credito = _kpis_rango(dt_inicio, dt_fin_excl)

    dias_rango = max(1, (fecha_fin - fecha_inicio).days + 1)
    fecha_fin_ant = fecha_inicio - timedelta(days=1)
    fecha_inicio_ant = fecha_fin_ant - timedelta(days=dias_rango - 1)
    dt_inicio_ant = datetime.combine(fecha_inicio_ant, datetime.min.time())
    dt_fin_excl_ant = datetime.combine(fecha_fin_ant + timedelta(days=1), datetime.min.time())
    total_ventas_ant, total_docs_ant, ticket_ant, total_credito_ant = _kpis_rango(dt_inicio_ant, dt_fin_excl_ant)

    def _var_pct(actual, anterior):
        if anterior == 0:
            return None
        return ((actual - anterior) / anterior) * 100.0

    serie_dias = (
        db.session.query(db.func.date(Venta.fecha), db.func.sum(Venta.monto_total))
        .filter(Venta.fecha >= dt_inicio, Venta.fecha < dt_fin_excl)
        .group_by(db.func.date(Venta.fecha))
        .order_by(db.func.date(Venta.fecha))
        .all()
    )
    ventas_por_dia = {d.strftime("%Y-%m-%d"): float(m or 0) for d, m in serie_dias}
    labels_dias, data_dias = [], []
    cursor = fecha_inicio
    while cursor <= fecha_fin:
        iso = cursor.strftime("%Y-%m-%d")
        labels_dias.append(cursor.strftime("%d/%m"))
        data_dias.append(float(ventas_por_dia.get(iso, 0)))
        cursor += timedelta(days=1)

    metodos_rows = (
        db.session.query(db.func.coalesce(Venta.metodo_pago, "Sin definir"), db.func.sum(Venta.monto_total))
        .filter(Venta.fecha >= dt_inicio, Venta.fecha < dt_fin_excl)
        .group_by(db.func.coalesce(Venta.metodo_pago, "Sin definir"))
        .order_by(db.func.sum(Venta.monto_total).desc())
        .all()
    )
    metodos_labels = [str(r[0]) for r in metodos_rows]
    metodos_data = [float(r[1] or 0) for r in metodos_rows]

    top_productos_rows = (
        db.session.query(Producto.nombre, db.func.sum(DetalleVenta.cantidad), db.func.sum(DetalleVenta.subtotal))
        .join(DetalleVenta, DetalleVenta.id_producto == Producto.id)
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.estado == 'Pagado', Venta.fecha >= dt_inicio, Venta.fecha < dt_fin_excl)
        .group_by(Producto.nombre)
        .order_by(db.func.sum(DetalleVenta.subtotal).desc())
        .limit(8)
        .all()
    )

    ventas_vendedor_rows = (
        db.session.query(
            db.func.coalesce(Venta.usuario, "Sin vendedor").label("vendedor"),
            db.func.count(Venta.id).label("n_ventas"),
            db.func.coalesce(db.func.sum(Venta.monto_total), 0).label("monto_total"),
        )
        .filter(
            Venta.estado == 'Pagado',
            Venta.fecha >= dt_inicio,
            Venta.fecha < dt_fin_excl,
        )
        .group_by(db.func.coalesce(Venta.usuario, "Sin vendedor"))
        .order_by(db.func.coalesce(db.func.sum(Venta.monto_total), 0).desc())
        .all()
    )
    ventas_vendedor = []
    for vendedor, n_ventas, monto_total_v in ventas_vendedor_rows:
        n = int(n_ventas or 0)
        m = float(monto_total_v or 0)
        ticket_v = (m / n) if n else 0.0
        ventas_vendedor.append({
            'vendedor': str(vendedor or 'Sin vendedor'),
            'n_ventas': n,
            'monto_total': m,
            'ticket_promedio': ticket_v,
        })

    ultimas_ventas = (
        Venta.query.filter(Venta.fecha >= dt_inicio, Venta.fecha < dt_fin_excl)
        .order_by(Venta.id.desc())
        .limit(12)
        .all()
    )

    # --- Reportes desde detalle de ventas (solo Pagado, mismo rango de fechas) ---
    agg_prod_rows = (
        db.session.query(
            Producto.id,
            Producto.nombre,
            db.func.coalesce(Producto.categoria, 'Sin categoría').label('cat'),
            db.func.sum(DetalleVenta.cantidad).label('qty'),
            db.func.sum(DetalleVenta.subtotal).label('rev'),
            db.func.sum(DetalleVenta.cantidad * db.func.coalesce(Producto.precio_compra, 0)).label('cogs'),
        )
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .join(Producto, Producto.id == DetalleVenta.id_producto)
        .filter(
            Venta.estado == 'Pagado',
            Venta.fecha >= dt_inicio,
            Venta.fecha < dt_fin_excl,
        )
        .group_by(Producto.id, Producto.nombre, Producto.categoria)
        .all()
    )

    prod_base = []
    total_qty = 0
    total_margin = 0.0
    for _pid, nombre, cat, qty, rev, cogs in agg_prod_rows:
        q = int(qty or 0)
        r = float(rev or 0)
        c = float(cogs or 0)
        mg = r - c
        prod_base.append(
            {
                'nombre': (nombre or '')[:90],
                'categoria': (cat or 'Sin categoría')[:50],
                'qty': q,
                'rev': r,
                'margin': mg,
            }
        )
        total_qty += q
        total_margin += mg

    def _abc_assign(sorted_items, key):
        """Clase A/B/C por curva acumulada 80% / 95% sobre el total."""
        tot = sum(key(x) for x in sorted_items)
        if tot <= 0:
            return []
        cum = 0.0
        out = []
        for x in sorted_items:
            cum += key(x)
            pct = (cum / tot) * 100.0
            if pct <= 80:
                clase = 'A'
            elif pct <= 95:
                clase = 'B'
            else:
                clase = 'C'
            out.append({**x, 'pct_acum': pct, 'clase': clase})
        return out

    by_qty = sorted(prod_base, key=lambda x: x['qty'], reverse=True)
    by_margin = sorted(prod_base, key=lambda x: x['margin'], reverse=True)
    by_margin_pos = [x for x in by_margin if float(x['margin']) > 0]
    abc_volumen = _abc_assign(by_qty, lambda x: float(x['qty']))[:45]
    abc_margen = _abc_assign(by_margin_pos, lambda x: float(x['margin']))[:45] if by_margin_pos else []

    def _count_skus_hasta_pct(sorted_items, key, pct_objetivo):
        tot = sum(key(x) for x in sorted_items)
        if tot <= 0:
            return 0, 0.0
        cum = 0.0
        n = 0
        for x in sorted_items:
            cum += key(x)
            n += 1
            if cum / tot >= (pct_objetivo / 100.0):
                return n, (cum / tot) * 100.0
        return n, (cum / tot) * 100.0 if tot else 0.0

    n80_q, _ = _count_skus_hasta_pct(by_qty, lambda x: float(x['qty']), 80)
    n80_m, _ = _count_skus_hasta_pct(by_margin_pos, lambda x: float(x['margin']), 80)
    n_skus_activos = len(prod_base)
    abc_skus_margin_neg = sum(1 for x in prod_base if float(x['margin']) < 0)

    cat_mix = db.func.coalesce(Producto.categoria, 'Sin categoría')
    met_mix = db.func.coalesce(Venta.metodo_pago, 'Sin definir')
    mix_rows = (
        db.session.query(
            cat_mix.label('cat'),
            met_mix.label('met'),
            db.func.sum(DetalleVenta.subtotal).label('monto'),
        )
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .join(Producto, Producto.id == DetalleVenta.id_producto)
        .filter(
            Venta.estado == 'Pagado',
            Venta.fecha >= dt_inicio,
            Venta.fecha < dt_fin_excl,
        )
        .group_by(cat_mix, met_mix)
        .all()
    )

    mix_mat = defaultdict(lambda: defaultdict(float))
    cats_mix = set()
    meths_mix = set()
    for cat, met, monto in mix_rows:
        m = float(monto or 0)
        mix_mat[cat][met] += m
        cats_mix.add(cat)
        meths_mix.add(met)
    cats_sorted = sorted(cats_mix)
    meth_totals = {m: sum(mix_mat[c][m] for c in cats_sorted) for m in meths_mix}
    meths_sorted = sorted(meths_mix, key=lambda mm: -meth_totals.get(mm, 0))
    mix_mat_plain = {c: {m: float(mix_mat[c][m]) for m in meths_sorted} for c in cats_sorted}
    mix_row_totals = {c: sum(mix_mat_plain[c][m] for m in meths_sorted) for c in cats_sorted}
    mix_grand_total = sum(meth_totals.values())

    hora_rows = (
        db.session.query(
            db.func.extract('hour', Venta.fecha).label('hr'),
            db.func.count(Venta.id),
            db.func.coalesce(db.func.sum(Venta.monto_total), 0),
        )
        .filter(
            Venta.estado == 'Pagado',
            Venta.fecha >= dt_inicio,
            Venta.fecha < dt_fin_excl,
        )
        .group_by(db.func.extract('hour', Venta.fecha))
        .order_by(db.func.extract('hour', Venta.fecha))
        .all()
    )
    hora_map = {int(r[0]): (int(r[1] or 0), float(r[2] or 0)) for r in hora_rows if r[0] is not None}
    bi_horas_labels = [f'{h:02d}:00' for h in range(24)]
    bi_horas_docs = [hora_map.get(h, (0, 0))[0] for h in range(24)]
    bi_horas_montos = [hora_map.get(h, (0, 0))[1] for h in range(24)]

    dia_rows = (
        db.session.query(
            db.func.extract('dow', Venta.fecha).label('wd'),
            db.func.count(Venta.id),
            db.func.coalesce(db.func.sum(Venta.monto_total), 0),
        )
        .filter(
            Venta.estado == 'Pagado',
            Venta.fecha >= dt_inicio,
            Venta.fecha < dt_fin_excl,
        )
        .group_by(db.func.extract('dow', Venta.fecha))
        .order_by(db.func.extract('dow', Venta.fecha))
        .all()
    )
    dia_map = {
        ((int(r[0]) + 6) % 7): (int(r[1] or 0), float(r[2] or 0))
        for r in dia_rows
        if r[0] is not None
    }
    bi_dia_labels = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    bi_dia_docs = [dia_map.get(d, (0, 0))[0] for d in range(7)]
    bi_dia_montos = [dia_map.get(d, (0, 0))[1] for d in range(7)]

    return render_template(
        "bi_reportes.html",
        fecha_inicio=fecha_inicio.strftime("%Y-%m-%d"),
        fecha_fin=fecha_fin.strftime("%Y-%m-%d"),
        hoy_str=hoy.strftime("%Y-%m-%d"),
        hace_7_str=(hoy - timedelta(days=6)).strftime("%Y-%m-%d"),
        hace_30_str=(hoy - timedelta(days=29)).strftime("%Y-%m-%d"),
        fecha_inicio_ant=fecha_inicio_ant.strftime("%Y-%m-%d"),
        fecha_fin_ant=fecha_fin_ant.strftime("%Y-%m-%d"),
        total_ventas=total_ventas,
        total_documentos=total_documentos,
        ticket_promedio=ticket_promedio,
        total_credito=total_credito,
        var_total_ventas=_var_pct(total_ventas, total_ventas_ant),
        var_total_documentos=_var_pct(total_documentos, total_docs_ant),
        var_ticket_promedio=_var_pct(ticket_promedio, ticket_ant),
        var_total_credito=_var_pct(total_credito, total_credito_ant),
        labels_dias=labels_dias,
        data_dias=data_dias,
        metodos_labels=metodos_labels,
        metodos_data=metodos_data,
        top_productos=top_productos_rows,
        ventas_vendedor=ventas_vendedor,
        ultimas_ventas=ultimas_ventas,
        abc_volumen=abc_volumen,
        abc_margen=abc_margen,
        abc_n_skus=n_skus_activos,
        abc_n80_qty=n80_q,
        abc_n80_margin=n80_m,
        abc_total_qty=total_qty,
        abc_total_margin=total_margin,
        abc_skus_margin_neg=abc_skus_margin_neg,
        mix_categorias=cats_sorted,
        mix_metodos=meths_sorted,
        mix_mat_plain=mix_mat_plain,
        mix_row_totals=mix_row_totals,
        mix_grand_total=mix_grand_total,
        meth_totals=meth_totals,
        bi_horas_labels=bi_horas_labels,
        bi_horas_docs=bi_horas_docs,
        bi_horas_montos=bi_horas_montos,
        bi_dia_labels=bi_dia_labels,
        bi_dia_docs=bi_dia_docs,
        bi_dia_montos=bi_dia_montos,
    )


def _contexto_panel_dueno_pitch():
    """Escenario ferretería ficticio (no BD): panel único tipo «lo que se muestra al propietario»."""
    hoy = datetime.now().date()
    hoy_str = hoy.strftime('%Y-%m-%d')
    hace_7_str = (hoy - timedelta(days=6)).strftime('%Y-%m-%d')
    hace_30_str = (hoy - timedelta(days=29)).strftime('%Y-%m-%d')
    fecha_fin_ej = hoy.strftime('%d/%m/%Y')
    fecha_ini_ej = (hoy - timedelta(days=29)).strftime('%d/%m/%Y')
    fecha_act_ini = (hoy - timedelta(days=29)).strftime('%d/%m/%Y')
    fecha_act_fin = hoy.strftime('%d/%m/%Y')
    fecha_ant_ini = (hoy - timedelta(days=59)).strftime('%d/%m/%Y')
    fecha_ant_fin = (hoy - timedelta(days=30)).strftime('%d/%m/%Y')

    total_cobrado = 43_280_000.0
    n_docs = 742
    ticket_promedio = total_cobrado / n_docs if n_docs else 0.0
    credito_monto = 5_640_000.0

    base = 1_050_000
    labels_dias = []
    data_dias = []
    for i in range(14):
        dia = hoy - timedelta(days=13 - i)
        labels_dias.append(dia.strftime('%d/%m'))
        jitter = (i % 4 - 1) * 118_000
        weekend = 220_000 if dia.weekday() >= 5 else 0
        data_dias.append(float(base + i * 195_000 + jitter + weekend))

    cat_labels = [
        'Herramientas',
        'Gasfitería',
        'Pinturas',
        'Electricidad',
        'Hogar',
        'Construcción',
        'Ferretería',
    ]
    cat_data = [9_820_000.0, 7_450_000.0, 6_980_000.0, 6_420_000.0, 5_620_000.0, 4_580_000.0, 3_940_000.0]

    top_prod = [
        ('CLAVO TECHO HELICOIDAL ZINC 2.1/2 C/GOLILLA (100 PZ)', 3_842_000.0),
        ('CODO PVC CELESTE 90° 110MM - PN10', 3_268_000.0),
        ('AMPOLLETA LED A60 CLASICA 9W/6400K E-27 LUZ FRIA', 2_965_000.0),
        ('TORNILLO AUTOP TAP FAST GALV 9-15 X 2.1/2" C 5/16', 2_541_000.0),
        ('ACRILINA CRUDA G-25 4GL (SOQUINA)', 2_387_000.0),
        ('MOTOR GASOLINA MOD TF55FX 5,5 HP, 163CC PART. MANUAL', 2_156_000.0),
        ('PERNO HEXAGONAL G2 UNC NG 1/2 X 5" (25)', 1_982_000.0),
        ('MALLA CUADRADA TIPO 5014 1.50 X 25 MTS', 1_894_000.0),
    ]

    raw = [
        ('Herramientas', 10_450_000.0, 9_020_000.0),
        ('Gasfitería', 8_920_000.0, 8_150_000.0),
        ('Pinturas', 8_150_000.0, 7_680_000.0),
        ('Electricidad', 7_410_000.0, 6_890_000.0),
        ('Hogar', 5_280_000.0, 5_010_000.0),
        ('Construcción', 4_560_000.0, 5_120_000.0),
        ('Ferretería', 5_890_000.0, 5_240_000.0),
    ]

    radar_filas = []
    total_act = sum(a for _, a, _ in raw)
    total_ant = sum(b for _, _, b in raw)
    for cat, act, ant in raw:
        if ant > 0:
            var_pct = ((act - ant) / ant) * 100.0
        elif act > 0:
            var_pct = None
        else:
            var_pct = 0.0
        share = (act / total_act * 100.0) if total_act > 0 else 0.0
        radar_filas.append({'cat': cat, 'actual': act, 'anterior': ant, 'var_pct': var_pct, 'share_pct': share})

    pie_labels = [r['cat'][:28] + ('…' if len(r['cat']) > 28 else '') for r in radar_filas]
    pie_data = [r['actual'] for r in radar_filas]
    var_total_pct = ((total_act - total_ant) / total_ant * 100.0) if total_ant > 0 else 0.0

    # Narrativa «Salud patrimonial» — simulación en CLP coherente con ferretería chilena mediana (no lee BD).
    ultra_sku_muestra = 100
    ultra_activos_estanteria_clp = 286_450_000
    ultra_refs_perdida = 47
    ultra_fuga_proyectada_clp = 12_780_000
    ultra_cemento_precio_venta_clp = 8_290
    ultra_cemento_costo_reposicion_clp = 9_640
    ultra_ranking_rentabilidad = [
        {
            'cat': 'Electricidad · cables y accesorios',
            'pct_utilidad_real': 31,
            'pct_inventario': 11,
            'diag': 'Concentrás utilidad real con poca superficie de inventario: motor del negocio.',
        },
        {
            'cat': 'Pinturas · aplicación',
            'pct_utilidad_real': 24,
            'pct_inventario': 16,
            'diag': 'Este mes puede ser tu «vaca lechera» si los precios están al día; vigilar líneas con costo logístico rezagado.',
        },
        {
            'cat': 'Gasfitería · tuberías y conexiones',
            'pct_utilidad_real': 21,
            'pct_inventario': 23,
            'diag': 'Equilibrio aceptable; vigilar PVC y fierro con lista que sube seguido.',
        },
        {
            'cat': 'Herramientas · discos y corte',
            'pct_utilidad_real': 13,
            'pct_inventario': 18,
            'diag': 'Depende de pocas referencias fuerte; riesgo de quiebre en lo premium.',
        },
        {
            'cat': 'Hogar · herrajes y seguridad',
            'pct_utilidad_real': 10,
            'pct_inventario': 12,
            'diag': 'Ticket medio estable; ojo con stock viejo de temporada.',
        },
        {
            'cat': 'Ferretería · fijaciones',
            'pct_utilidad_real': 11,
            'pct_inventario': 14,
            'diag': 'Muchas líneas de bajo margen unitario; el volumen compensa si no hay obsolescencia.',
        },
    ]
    ultra_dias_inventario = [
        {'familia': 'Ferretería · tornillos y surtidos caja', 'dias': 1280, 'estado': 'exceso', 'nota': 'Cobertura plurianual — capital quieto en pasillo fondo.'},
        {'familia': 'Herramientas · rotomartillo uso profesional', 'dias': 0, 'estado': 'quiebre', 'nota': 'Sin unidad en sala; el cliente se va con ticket alto a otro lado.'},
        {'familia': 'Construcción · sacos 25 kg y morteros', 'dias': 41, 'estado': 'tension', 'nota': 'Se mueve, pero el precio de venta puede llevar meses sin seguir al proveedor.'},
        {'familia': 'Electricidad · canalización y rollo', 'dias': 198, 'estado': 'alerta', 'nota': 'Por sobre política de meses; revisar compras duplicadas por sucursal.'},
    ]
    ultra_mapa_calor_pasillos = [
        {'nombre': 'Pasillo norte · electricidad y luminarias', 'intensidad': 91, 'rol': 'motor'},
        {'nombre': 'Mostrador caja · alta rotación', 'intensidad': 96, 'rol': 'motor'},
        {'nombre': 'Pasillo centro · gasfitería PVC', 'intensidad': 76, 'rol': 'motor'},
        {'nombre': 'Pasillo sur · pinturas y químicos', 'intensidad': 44, 'rol': 'polvo'},
        {'nombre': 'Fondo · ferretería y fijaciones', 'intensidad': 31, 'rol': 'polvo'},
        {'nombre': 'Bodega · aceros y techumbre', 'intensidad': 19, 'rol': 'polvo'},
    ]

    # Chile · narrativa «dinero recuperable» (simulación verosímil en pesos).
    pitch_tienda_demo = 'FERRETERÍA SANTO DOMINGO — datos simulados'
    pitch_efectivo_estantes_clp = 286_450_000
    pitch_fuga_inflacion_mes_clp = 4_180_000
    pitch_vaca_categoria = 'Pinturas · aplicación'
    pitch_vaca_utilidad_limpia_clp = 9_850_000
    pitch_ancla_producto = 'Malla cuadrada galvanizada 5014 × 1,50 × 25 m'
    pitch_ancla_meses_cobertura = 11
    ultra_dinero_durmiente_filas = [
        {
            'zona': 'Pasillo sur fondo · Ferretería / Fijaciones',
            'regla': 'Sin movimiento > 6 meses (ejemplo)',
            'capital_polvo_clp': 4_280_000,
            'dto_sugerido_pct': 18,
            'flujo_si_liquidas_clp': 3_509_600,
            'porque_clic': 'No es “stock luego”: es plata para sueldos o comprar lo que sí rota.',
        },
        {
            'zona': 'Bodega · tinetas y complementos pintura',
            'regla': '> 180 días sin venta',
            'capital_polvo_clp': 2_140_000,
            'dto_sugerido_pct': 15,
            'flujo_si_liquidas_clp': 1_819_000,
            'porque_clic': 'Capital congelado en unidades que nadie pidió; convertilo en efectivo.',
        },
    ]
    ultra_semaforo_umbral_margen_pct = 15
    ultra_semaforo_filas = [
        {
            'ref': 'CODO PVC CELESTE 90° 40MM - PN10 IMP A02',
            'costo_ant': 502,
            'costo_ultimo': 718,
            'pv': 649,
            'margen_sobre_costo_hoy_pct': round((649 - 718) / 718 * 100.0, 1),
            'estado': 'rojo',
        },
        {
            'ref': 'CABLE PUENTE BATERIA PRETUL (TRUPER) 2,5 MTS. # CAP-2510P',
            'costo_ant': 8395,
            'costo_ultimo': 9820,
            'pv': 11890,
            'margen_sobre_costo_hoy_pct': round((11890 - 9820) / 9820 * 100.0, 1),
            'estado': 'verde',
        },
        {
            'ref': 'MANGUERA SALIDA LAVADORA UNIVERSAL',
            'costo_ant': 1395,
            'costo_ultimo': 1688,
            'pv': 1749,
            'margen_sobre_costo_hoy_pct': round((1749 - 1688) / 1688 * 100.0, 1),
            'estado': 'rojo',
        },
        {
            'ref': 'CANDADO DE HIERRO, COLOR LATON, 40MM, CORTO, CAJA, BASIC',
            'costo_ant': 1421,
            'costo_ultimo': 1645,
            'pv': 1849,
            'margen_sobre_costo_hoy_pct': round((1849 - 1645) / 1645 * 100.0, 1),
            'estado': 'amarillo',
        },
        {
            'ref': 'ACRILINA CRUDA G-25 4GL (SOQUINA)',
            'costo_ant': 20222,
            'costo_ultimo': 23680,
            'pv': 25190,
            'margen_sobre_costo_hoy_pct': round((25190 - 23680) / 23680 * 100.0, 1),
            'estado': 'rojo',
        },
    ]
    ultra_m2_zonas = [
        {
            'nombre': 'Zona VIP · Herramientas eléctricas + electricidad',
            'pct_m2': 10,
            'pct_utilidad': 50,
            'rol': 'vip',
            'nota': 'Poca superficie, mucha utilidad neta: acá pagás el arriendo.',
        },
        {
            'nombre': 'Motor · Gasfitería',
            'pct_m2': 22,
            'pct_utilidad': 28,
            'rol': 'motor',
            'nota': 'Rotación y margen razonable; ojo con PVC y fierro con costo saltando.',
        },
        {
            'nombre': 'Mixto · Pinturas / aplicación',
            'pct_m2': 14,
            'pct_utilidad': 13,
            'rol': 'mixto',
            'nota': 'Podés ser “vaca lechera” en algunos meses si los costos están al día.',
        },
        {
            'nombre': 'Zona parásito · Construcción voluminosos (cemento, sacos, malla)',
            'pct_m2': 40,
            'pct_utilidad': 4,
            'rol': 'parasito',
            'nota': 'Mucho metro cuadrado y logística; tras gastos dejarías menos del 5% de utilidad neta.',
        },
    ]
    pitch_whatsapp_roadmap = (
        'Algoritmo de alerta de precios: avisar por WhatsApp cuando el proveedor suba costo '
        'y tu precio de venta quede rezagado. Roadmap Ultra Premium.'
    )

    return dict(
        hoy_str=hoy_str,
        hace_7_str=hace_7_str,
        hace_30_str=hace_30_str,
        fecha_ini_ej=fecha_ini_ej,
        fecha_fin_ej=fecha_fin_ej,
        fecha_act_ini=fecha_act_ini,
        fecha_act_fin=fecha_act_fin,
        fecha_ant_ini=fecha_ant_ini,
        fecha_ant_fin=fecha_ant_fin,
        total_cobrado=total_cobrado,
        n_docs=n_docs,
        ticket_promedio=ticket_promedio,
        credito_monto=credito_monto,
        labels_dias=labels_dias,
        data_dias=data_dias,
        cat_labels=cat_labels,
        cat_data=cat_data,
        top_prod=top_prod,
        radar_filas=radar_filas,
        pie_labels=pie_labels,
        pie_data=pie_data,
        total_act=total_act,
        total_ant=total_ant,
        var_total_pct=var_total_pct,
        ultra_sku_muestra=ultra_sku_muestra,
        ultra_activos_estanteria_clp=ultra_activos_estanteria_clp,
        ultra_refs_perdida=ultra_refs_perdida,
        ultra_fuga_proyectada_clp=ultra_fuga_proyectada_clp,
        ultra_cemento_precio_venta_clp=ultra_cemento_precio_venta_clp,
        ultra_cemento_costo_reposicion_clp=ultra_cemento_costo_reposicion_clp,
        ultra_ranking_rentabilidad=ultra_ranking_rentabilidad,
        ultra_dias_inventario=ultra_dias_inventario,
        ultra_mapa_calor_pasillos=ultra_mapa_calor_pasillos,
        pitch_tienda_demo=pitch_tienda_demo,
        pitch_efectivo_estantes_clp=pitch_efectivo_estantes_clp,
        pitch_fuga_inflacion_mes_clp=pitch_fuga_inflacion_mes_clp,
        pitch_vaca_categoria=pitch_vaca_categoria,
        pitch_vaca_utilidad_limpia_clp=pitch_vaca_utilidad_limpia_clp,
        pitch_ancla_producto=pitch_ancla_producto,
        pitch_ancla_meses_cobertura=pitch_ancla_meses_cobertura,
        ultra_dinero_durmiente_filas=ultra_dinero_durmiente_filas,
        ultra_semaforo_umbral_margen_pct=ultra_semaforo_umbral_margen_pct,
        ultra_semaforo_filas=ultra_semaforo_filas,
        ultra_m2_zonas=ultra_m2_zonas,
        pitch_whatsapp_roadmap=pitch_whatsapp_roadmap,
    )


def _contexto_alertas_precio_premium_demo():
    """Demo Ultra Premium de alertas de precio, priorizadas por dinero en riesgo (CLP)."""
    hoy = datetime.now().date()
    hace_30 = hoy - timedelta(days=29)

    filas = [
        {
            'producto': 'FIERRO ESTRIADO 10 MM X 12 M',
            'categoria': 'Construcción',
            'costo_actual': 6200,
            'precio_hoy': 6150,
            'margen_real_pct': -0.8,
            'perdida_estimada': 450000,
            'precio_sugerido': 7400,
            'estado': 'critico',
        },
        {
            'producto': 'SACO CEMENTO ESPECIAL (25 KG)',
            'categoria': 'Construcción',
            'costo_actual': 4850,
            'precio_hoy': 5100,
            'margen_real_pct': 4.9,
            'perdida_estimada': 120000,
            'precio_sugerido': 5600,
            'estado': 'critico',
        },
        {
            'producto': 'CODO PVC CELESTE 90° 40MM - PN10 IMP A02',
            'categoria': 'Gasfitería',
            'costo_actual': 718,
            'precio_hoy': 649,
            'margen_real_pct': -9.6,
            'perdida_estimada': 98500,
            'precio_sugerido': 890,
            'estado': 'critico',
        },
        {
            'producto': 'ACRILINA CRUDA G-25 4GL (SOQUINA)',
            'categoria': 'Pinturas',
            'costo_actual': 23680,
            'precio_hoy': 25190,
            'margen_real_pct': 6.0,
            'perdida_estimada': 45000,
            'precio_sugerido': 29500,
            'estado': 'alerta',
        },
        {
            'producto': 'MANGUERA SALIDA LAVADORA UNIVERSAL',
            'categoria': 'Gasfitería',
            'costo_actual': 1688,
            'precio_hoy': 1749,
            'margen_real_pct': 3.5,
            'perdida_estimada': 32500,
            'precio_sugerido': 2190,
            'estado': 'alerta',
        },
        {
            'producto': 'CANDADO HIERRO LATÓN 40MM CORTO BASIC',
            'categoria': 'Hogar',
            'costo_actual': 1645,
            'precio_hoy': 1849,
            'margen_real_pct': 11.0,
            'perdida_estimada': 16000,
            'precio_sugerido': 2190,
            'estado': 'alerta',
        },
    ]
    filas = sorted(filas, key=lambda x: x['perdida_estimada'], reverse=True)
    dinero_en_riesgo = sum(f['perdida_estimada'] for f in filas)
    productos_criticos = sum(1 for f in filas if f['margen_real_pct'] < 0 or f['estado'] == 'critico')
    oportunidad_recuperacion = sum(max(0, f['precio_sugerido'] - f['precio_hoy']) * 120 for f in filas)
    utilidad_sin_accion = 9860000
    utilidad_con_accion = utilidad_sin_accion + oportunidad_recuperacion

    return dict(
        hoy_str=hoy.strftime('%Y-%m-%d'),
        hace_30_str=hace_30.strftime('%Y-%m-%d'),
        dinero_en_riesgo=dinero_en_riesgo,
        productos_criticos=productos_criticos,
        oportunidad_recuperacion=oportunidad_recuperacion,
        utilidad_sin_accion=utilidad_sin_accion,
        utilidad_con_accion=utilidad_con_accion,
        filas_alerta=filas,
        categorias_riesgo_labels=[f['categoria'] for f in filas[:5]],
        categorias_riesgo_data=[f['perdida_estimada'] for f in filas[:5]],
    )


@app.route('/bi/panel-dueno')
@app.route('/gerencia/informes-dueno')
@permisos_required('panel_gerencia', 'gestionar_usuarios')
def panel_dueno():
    """
    Panel ejecutivo de gerencia: simulación comercial (ej. Ferretería Santo Domingo) + enlaces a BI y operación con datos reales.
    Rutas: /gerencia/informes-dueno y /bi/panel-dueno.
    """
    return render_template('bi_panel_dueno_completo.html', **_contexto_panel_dueno_pitch())


@app.route('/bi/demo/dueno')
@permisos_required('panel_gerencia', 'gestionar_usuarios')
def bi_dueno_demo():
    """Compatibilidad: antes página aparte; ahora ancla al panel unificado."""
    return redirect(url_for('panel_dueno') + '#sec-impacto-clp')


@app.route('/bi/demo/radar-mercado')
@permisos_required('panel_gerencia', 'gestionar_usuarios')
def bi_radar_mercado_demo():
    """Compatibilidad: antes página aparte; ahora ancla al panel unificado."""
    return redirect(url_for('panel_dueno') + '#sec-radar')


@app.route('/bi/demo/alertas-precio-premium')
@permisos_required('panel_gerencia', 'gestionar_usuarios')
def bi_alertas_precio_premium_demo():
    """Centro demo de alertas inteligentes de precios, ordenado por dinero en riesgo."""
    return render_template('bi_alertas_precio_premium_demo.html', **_contexto_alertas_precio_premium_demo())


@app.route('/gerencia/simulador-margen')
@permisos_required('panel_gerencia')
def simulador_margen():
    """
    Simulación gerencial: impacto en margen bruto ante cambios % en precio de venta y costo,
    con opción de elasticidad simple sobre las cantidades vendidas (histórico estado Pagado).
    """
    hoy = datetime.now().date()
    fi_raw = (request.args.get('fecha_inicio') or '').strip()
    ff_raw = (request.args.get('fecha_fin') or '').strip()
    try:
        fecha_inicio = datetime.strptime(fi_raw, "%Y-%m-%d").date() if fi_raw else (hoy - timedelta(days=29))
    except ValueError:
        fecha_inicio = hoy - timedelta(days=29)
    try:
        fecha_fin = datetime.strptime(ff_raw, "%Y-%m-%d").date() if ff_raw else hoy
    except ValueError:
        fecha_fin = hoy
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    def _parse_float(name, default):
        try:
            return float(request.args.get(name, default))
        except (TypeError, ValueError):
            return float(default)

    d_precio = max(-99.0, min(400.0, _parse_float('d_precio', 0)))
    d_costo = max(-99.0, min(400.0, _parse_float('d_costo', 0)))
    elasticidad = max(-5.0, min(5.0, _parse_float('elasticidad', 0)))
    categoria_filtro = (request.args.get('categoria') or '').strip()

    dt_i = datetime.combine(fecha_inicio, datetime.min.time())
    dt_f_excl = datetime.combine(fecha_fin + timedelta(days=1), datetime.min.time())

    base_q = (
        db.session.query(
            DetalleVenta.id_producto,
            db.func.sum(DetalleVenta.cantidad),
            db.func.sum(DetalleVenta.subtotal),
        )
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .join(Producto, Producto.id == DetalleVenta.id_producto)
        .filter(
            Venta.estado == 'Pagado',
            Venta.fecha >= dt_i,
            Venta.fecha < dt_f_excl,
        )
    )
    if categoria_filtro:
        base_q = base_q.filter(Producto.categoria == categoria_filtro)

    agg_rows = base_q.group_by(DetalleVenta.id_producto).all()

    factor_qty = 1.0 + (elasticidad * d_precio / 100.0)
    factor_qty_invalido = factor_qty < 0

    prod_ids = [r[0] for r in agg_rows]
    prods_map = {p.id: p for p in Producto.query.filter(Producto.id.in_(prod_ids)).all()} if prod_ids else {}

    filas = []
    ventas_base = cogs_base = 0.0
    ventas_sim = cogs_sim = 0.0
    sin_costo = 0

    for pid, qty_raw, rev_raw in agg_rows:
        qty = int(qty_raw or 0)
        rev = float(rev_raw or 0)
        if qty <= 0:
            continue
        p_obj = prods_map.get(pid)
        if not p_obj:
            continue
        cost = float(p_obj.precio_compra or 0)
        if cost <= 0:
            sin_costo += 1
        p_hist = rev / qty
        mb = rev - qty * cost
        ventas_base += rev
        cogs_base += qty * cost

        q_sim = qty * factor_qty
        if factor_qty_invalido:
            q_sim = 0.0
        elif q_sim < 0:
            q_sim = 0.0

        p_sim = p_hist * (1 + d_precio / 100.0)
        c_sim = cost * (1 + d_costo / 100.0)
        rs = q_sim * p_sim
        cs = q_sim * c_sim
        ms = rs - cs
        ventas_sim += rs
        cogs_sim += cs

        filas.append(
            {
                'nombre': (p_obj.nombre or '')[:80],
                'categoria': (p_obj.categoria or '—')[:40],
                'qty': qty,
                'p_hist': p_hist,
                'cost': cost,
                'mb': mb,
                'ms': ms,
                'delta': ms - mb,
            }
        )

    filas.sort(key=lambda x: abs(x['delta']), reverse=True)

    margen_base = ventas_base - cogs_base
    margen_sim = ventas_sim - cogs_sim
    pct_m_base = (margen_base / ventas_base * 100.0) if ventas_base > 0 else None
    pct_m_sim = (margen_sim / ventas_sim * 100.0) if ventas_sim > 0 else None

    categorias_sel = _categorias_filtro_lista()

    return render_template(
        'simulador_margen.html',
        fecha_inicio=fecha_inicio.strftime("%Y-%m-%d"),
        fecha_fin=fecha_fin.strftime("%Y-%m-%d"),
        hoy_str=hoy.strftime("%Y-%m-%d"),
        hace_7_str=(hoy - timedelta(days=6)).strftime("%Y-%m-%d"),
        hace_30_str=(hoy - timedelta(days=29)).strftime("%Y-%m-%d"),
        d_precio=d_precio,
        d_costo=d_costo,
        elasticidad=elasticidad,
        categoria_filtro=categoria_filtro,
        categorias_sel=categorias_sel,
        ventas_base=ventas_base,
        cogs_base=cogs_base,
        margen_base=margen_base,
        pct_m_base=pct_m_base,
        ventas_sim=ventas_sim,
        cogs_sim=cogs_sim,
        margen_sim=margen_sim,
        pct_m_sim=pct_m_sim,
        delta_margen=margen_sim - margen_base,
        delta_ventas=ventas_sim - ventas_base,
        delta_pct_puntos=(pct_m_sim - pct_m_base) if (pct_m_base is not None and pct_m_sim is not None) else None,
        filas=filas[:40],
        n_skus=len(filas),
        sin_costo=sin_costo,
        factor_qty=factor_qty,
        factor_qty_invalido=factor_qty_invalido,
    )


# --- REVERT-BUNDLE: centro de ayuda + permiso panel_gerencia (simulador). Eliminar este bloque y plantillas/ayuda/* para deshacer. ---
@app.route('/ayuda')
@login_required
def centro_ayuda():
    """Guías en lenguaje simple para tableros gerenciales (no modifica datos)."""
    _seed_permisos_catalogo_si_vacio()
    return render_template('ayuda/index.html')


def _factor_estacional_categoria(categoria, mes):
    cat = (categoria or "").strip().lower()
    # Heurística inicial (ajustable): pinturas suben en verano; techumbre/construcción en invierno.
    if "pint" in cat:
        return 1.20 if mes in (11, 12, 1, 2) else 0.95
    if "constru" in cat or "tech" in cat:
        return 1.15 if mes in (5, 6, 7, 8) else 1.00
    if "electric" in cat:
        return 1.05
    return 1.00


@app.route('/ia_abastecimiento')
@login_required
def ia_abastecimiento():
    """
    Predicción de demanda y sugerencia de compra.
    Modelo MVP:
    - base: promedio diario últimos 30 días
    - tendencia: ratio últimos 7 días vs 30 días
    - estacionalidad: factor por categoría + mes
    """
    dias_horizonte = request.args.get('dias', 30, type=int)
    dias_horizonte = max(7, min(dias_horizonte, 90))
    solo_alerta = request.args.get('solo_alerta') == '1'
    q = (request.args.get('q') or '').strip()

    hoy = datetime.now().date()
    d30_inicio = datetime.combine(hoy - timedelta(days=30), datetime.min.time())
    d7_inicio = datetime.combine(hoy - timedelta(days=7), datetime.min.time())
    ahora = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
    mes_actual = hoy.month

    productos_query = Producto.query.filter_by(activo=True)
    if q:
        like = f"%{q}%"
        productos_query = productos_query.filter(
            (Producto.nombre.like(like)) | (Producto.codigo_barra.like(like))
        )
    productos = productos_query.order_by(Producto.nombre.asc()).all()

    consumo_30 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d30_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )
    consumo_7 = dict(
        db.session.query(DetalleVenta.id_producto, db.func.sum(DetalleVenta.cantidad))
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(Venta.fecha >= d7_inicio, Venta.fecha < ahora, Venta.estado != "Abierta")
        .group_by(DetalleVenta.id_producto)
        .all()
    )

    sugerencias = []
    for p in productos:
        c30 = float(consumo_30.get(p.id, 0) or 0)
        c7 = float(consumo_7.get(p.id, 0) or 0)
        base_dia = c30 / 30.0
        t30 = c30 / 30.0
        t7 = c7 / 7.0
        if t30 > 0:
            ratio_tend = max(0.70, min(1.35, t7 / t30))
        else:
            ratio_tend = 1.0
        factor_est = _factor_estacional_categoria(p.categoria, mes_actual)

        demanda_proyectada = base_dia * ratio_tend * factor_est * dias_horizonte
        stock_actual = float(p.stock or 0)
        sugerido = max(0, int(round(demanda_proyectada - stock_actual)))
        cobertura_dias = (stock_actual / (base_dia * ratio_tend * factor_est)) if (base_dia * ratio_tend * factor_est) > 0 else 9999

        nivel = "OK"
        if sugerido > 0 and cobertura_dias <= 10:
            nivel = "CRITICO"
        elif sugerido > 0 and cobertura_dias <= 20:
            nivel = "MEDIO"

        fila = {
            "producto": p,
            "consumo_30": c30,
            "consumo_7": c7,
            "base_dia": base_dia,
            "factor_tendencia": ratio_tend,
            "factor_estacional": factor_est,
            "demanda_proyectada": demanda_proyectada,
            "stock_actual": stock_actual,
            "sugerido": sugerido,
            "cobertura_dias": cobertura_dias,
            "nivel": nivel,
        }
        if (not solo_alerta) or sugerido > 0:
            sugerencias.append(fila)

    sugerencias.sort(key=lambda x: (x["sugerido"], -x["consumo_30"]), reverse=True)

    return render_template(
        "ia_abastecimiento.html",
        sugerencias=sugerencias,
        dias_horizonte=dias_horizonte,
        solo_alerta=solo_alerta,
        q=q,
        total_sugerido=sum(x["sugerido"] for x in sugerencias),
        total_productos=len(sugerencias),
    )


@app.route('/bi/export.csv')
@login_required
def export_bi_csv():
    fi_raw = (request.args.get('fecha_inicio') or '').strip()
    ff_raw = (request.args.get('fecha_fin') or '').strip()
    hoy = datetime.now().date()
    try:
        fecha_inicio = datetime.strptime(fi_raw, "%Y-%m-%d").date() if fi_raw else (hoy - timedelta(days=29))
    except ValueError:
        fecha_inicio = hoy - timedelta(days=29)
    try:
        fecha_fin = datetime.strptime(ff_raw, "%Y-%m-%d").date() if ff_raw else hoy
    except ValueError:
        fecha_fin = hoy
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    dt_inicio = datetime.combine(fecha_inicio, datetime.min.time())
    dt_fin_excl = datetime.combine(fecha_fin + timedelta(days=1), datetime.min.time())
    ventas = (
        Venta.query.filter(Venta.fecha >= dt_inicio, Venta.fecha < dt_fin_excl)
        .order_by(Venta.fecha.asc(), Venta.id.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "fecha", "metodo_pago", "estado", "monto_total", "cliente", "usuario"])
    for v in ventas:
        writer.writerow([
            v.id,
            v.fecha.strftime("%Y-%m-%d %H:%M:%S") if v.fecha else "",
            v.metodo_pago or "",
            v.estado or "",
            f"{float(v.monto_total or 0):.2f}",
            v.cliente.nombre if v.cliente else "",
            v.usuario or "",
        ])

    nombre = f"bi_ventas_{fecha_inicio.strftime('%Y%m%d')}_{fecha_fin.strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@app.route('/bi/export_vendedores.csv')
@login_required
def export_bi_vendedores_csv():
    fi_raw = (request.args.get('fecha_inicio') or '').strip()
    ff_raw = (request.args.get('fecha_fin') or '').strip()
    hoy = datetime.now().date()
    try:
        fecha_inicio = datetime.strptime(fi_raw, "%Y-%m-%d").date() if fi_raw else (hoy - timedelta(days=29))
    except ValueError:
        fecha_inicio = hoy - timedelta(days=29)
    try:
        fecha_fin = datetime.strptime(ff_raw, "%Y-%m-%d").date() if ff_raw else hoy
    except ValueError:
        fecha_fin = hoy
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    dt_inicio = datetime.combine(fecha_inicio, datetime.min.time())
    dt_fin_excl = datetime.combine(fecha_fin + timedelta(days=1), datetime.min.time())

    filas = (
        db.session.query(
            db.func.coalesce(Venta.usuario, "Sin vendedor").label("vendedor"),
            db.func.count(Venta.id).label("n_ventas"),
            db.func.coalesce(db.func.sum(Venta.monto_total), 0).label("monto_total"),
        )
        .filter(
            Venta.estado == 'Pagado',
            Venta.fecha >= dt_inicio,
            Venta.fecha < dt_fin_excl,
        )
        .group_by(db.func.coalesce(Venta.usuario, "Sin vendedor"))
        .order_by(db.func.coalesce(db.func.sum(Venta.monto_total), 0).desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["vendedor", "ventas_pagadas", "monto_total", "ticket_promedio"])
    for vendedor, n_ventas, monto_total in filas:
        n = int(n_ventas or 0)
        m = float(monto_total or 0)
        ticket = (m / n) if n else 0.0
        writer.writerow([vendedor or "Sin vendedor", n, f"{m:.2f}", f"{ticket:.2f}"])

    nombre = f"bi_ventas_vendedor_{fecha_inicio.strftime('%Y%m%d')}_{fecha_fin.strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


# --- PRODUCTOS ------------------------------------------------------------------------
def _normalizar_encabezado_carga(nombre_columna):
    """Unifica encabezados CSV/Excel (ej. 'Precio Venta' -> 'precio_venta')."""
    s = str(nombre_columna).strip().lower().replace(' ', '_').replace('-', '_')
    while '__' in s:
        s = s.replace('__', '_')
    return s


def _precio_sugerido_redondeado(costo, margen_obj, terminacion):
    try:
        costo = float(costo or 0)
        margen_obj = float(margen_obj or 0.30)
    except Exception:
        return 0.0
    margen_obj = min(max(margen_obj, 0.01), 0.90)
    if costo <= 0:
        return 0.0
    base = costo / (1 - margen_obj)
    entero = int(round(base))
    term = int(terminacion or 0)
    if term == 90:
        red = (entero // 100) * 100 + 90
        if red < base:
            red += 100
        return float(red)
    if term == 990:
        red = (entero // 1000) * 1000 + 990
        if red < base:
            red += 1000
        return float(red)
    return float(entero)


def _float_param(value, default):
    """Parse float (query/form); acepta coma decimal, ej. 0,3."""
    if value is None:
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value).strip()
    if not s:
        return default
    s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return default


def _parse_clp_monto(value):
    """
    Monto en pesos chilenos desde input humano.
    Acepta: 35990, 35.990, 35,990 (miles con punto o coma), espacios.
    """
    if value is None:
        return None
    t = str(value).strip()
    if not t:
        return None
    t = t.replace(' ', '').replace('$', '')
    if ',' in t and '.' in t:
        if t.rindex(',') > t.rindex('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        parts = t.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2 and parts[1].isdigit():
            t = parts[0].replace('.', '') + '.' + parts[1]
        else:
            t = t.replace(',', '')
    else:
        t = t.replace('.', '')
    try:
        v = float(t)
        return v if v >= 0 else None
    except ValueError:
        return None


@app.route('/productos/api/catalogo_subs')
@login_required
def api_catalogo_subs_por_categoria():
    cat = (request.args.get('categoria') or '').strip()
    return jsonify(_catalogo_sub_opciones_filtro(cat))


@app.route('/productos')
@login_required
def mostrar_productos():
    query = (request.args.get('q') or '').strip()
    codigo_barra = (request.args.get('codigo_barra') or '').strip()
    categoria = (request.args.get('categoria') or '').strip()
    subcategoria = (request.args.get('subcategoria') or '').strip()
    sub_id = request.args.get('sub_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    per_page = max(5, min(per_page, 100))

    productos = Producto.query
    if query:
        productos = productos.filter(
            (Producto.nombre.like(f"%{query}%")) |
            (Producto.codigo_barra.like(f"%{query}%"))
        )
    if codigo_barra:
        productos = productos.filter(Producto.codigo_barra.like(f"%{codigo_barra}%"))
    # sub_id ya define la hoja del maestro; no combinar con categoria texto (evita vaciar resultados + búsqueda q).
    if sub_id and _catalogo_ui_disponible():
        productos = productos.filter(Producto.subcategoria_catalogo_id == sub_id)
    else:
        if categoria:
            productos = productos.filter_by(categoria=categoria)
        if subcategoria:
            productos = productos.filter_by(subcategoria=subcategoria)

    categorias = _categorias_filtro_lista()
    subcategorias = _subcategorias_filtro_legacy(categoria)
    catalogo_sub_opciones = _catalogo_sub_opciones_filtro(categoria) if categoria else []
    mostrar_filtro_sub_id = bool(_catalogo_ui_disponible() and categoria)

    productos_pagination = productos.order_by(Producto.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    _adjuntar_stock_ui(productos_pagination.items)
    return render_template(
        'productos.html',
        productos=productos_pagination.items,
        productos_pagination=productos_pagination,
        query=query,
        categoria=categoria,
        subcategoria=subcategoria,
        sub_id=sub_id,
        codigo_barra=codigo_barra,
        categorias=categorias,
        subcategorias=subcategorias,
        catalogo_sub_opciones=catalogo_sub_opciones,
        mostrar_filtro_sub_id=mostrar_filtro_sub_id,
        catalogo_registro_tree=_catalogo_arbol_registro(),
        catalogo_maestro_disponible=_catalogo_ui_disponible(),
        subcategorias_todas_legacy=_subcategorias_filtro_legacy(''),
        puede_editar_stock_admin=_usuario_puede_ajustar_stock(),
    )


@app.route('/precios/revision')
@permisos_required('revision_precios')
def revision_precios():
    q = (request.args.get('q') or '').strip()
    categoria = (request.args.get('categoria') or '').strip()
    subcategoria = (request.args.get('subcategoria') or '').strip()
    margen_obj = _float_param(request.args.get('margen_obj'), 0.30)
    terminacion = request.args.get('terminacion', 90, type=int)
    solo_alerta = request.args.get('solo_alerta', '1') == '1'

    productos_q = Producto.query.filter(Producto.activo == True)
    if q:
        like = f"%{q}%"
        productos_q = productos_q.filter(
            or_(
                Producto.nombre.like(like),
                Producto.codigo_barra.like(like),
                and_(Producto.codigo_interno.isnot(None), Producto.codigo_interno.like(like)),
            )
        )
    if categoria:
        productos_q = productos_q.filter(Producto.categoria == categoria)
    if subcategoria:
        productos_q = productos_q.filter(Producto.subcategoria == subcategoria)

    productos = productos_q.order_by(Producto.nombre.asc()).limit(1500).all()
    filas = []
    for p in productos:
        costo = float(p.precio_compra or 0)
        precio_lista = float(p.precio_venta or 0)
        precio_may = float(p.precio_mayoreo or 0)
        venta_ef = precio_efectivo_pos_producto(p)
        sugerido = _precio_sugerido_redondeado(costo, margen_obj, terminacion)
        margen_actual = ((venta_ef - costo) / venta_ef) if venta_ef > 0 and costo >= 0 else None
        requiere = sugerido > (venta_ef + 0.01)
        if solo_alerta and not requiere:
            continue
        codigo = (p.codigo_barra or "").strip() or (p.codigo_interno or "").strip() or "—"
        filas.append({
            "id": p.id,
            "codigo": codigo,
            "nombre": p.nombre,
            "categoria": p.categoria or "—",
            "subcategoria": p.subcategoria or "—",
            "costo": costo,
            "venta": venta_ef,
            "precio_lista": precio_lista,
            "precio_mayoreo": precio_may,
            "sugerido": sugerido,
            "margen_actual": margen_actual,
            "requiere": requiere,
        })

    categorias = [c[0] for c in db.session.query(Producto.categoria).filter(Producto.categoria.isnot(None), Producto.categoria != '').distinct().order_by(Producto.categoria.asc()).all()]
    sub_q = db.session.query(Producto.subcategoria).filter(Producto.subcategoria.isnot(None), Producto.subcategoria != '')
    if categoria:
        sub_q = sub_q.filter(Producto.categoria == categoria)
    subcategorias = [s[0] for s in sub_q.distinct().order_by(Producto.subcategoria.asc()).all()]

    cambios_recientes = []
    if _bitacora_precios_disponible():
        cambios_recientes = (
            BitacoraPrecioVenta.query
            .options(joinedload(BitacoraPrecioVenta.producto))
            .order_by(BitacoraPrecioVenta.id.desc())
            .limit(25)
            .all()
        )

    return render_template(
        'revision_precios.html',
        filas=filas,
        q=q,
        categoria=categoria,
        subcategoria=subcategoria,
        margen_obj=margen_obj,
        terminacion=terminacion,
        solo_alerta=solo_alerta,
        categorias=categorias,
        subcategorias=subcategorias,
        cambios_recientes=cambios_recientes,
    )


@app.route('/precios/revision/aplicar/<int:producto_id>', methods=['POST'])
@permisos_required('revision_precios')
def aplicar_precio_sugerido(producto_id):
    p = Producto.query.get_or_404(producto_id)
    margen_obj = _float_param(request.form.get('margen_obj'), 0.30)
    terminacion = request.form.get('terminacion', 90, type=int)
    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash("Debes indicar un motivo del cambio de precio.", "warning")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))

    sugerido = _precio_sugerido_redondeado(p.precio_compra or 0, margen_obj, terminacion)
    venta_ef = precio_efectivo_pos_producto(p)
    if sugerido <= 0:
        flash("No hay precio sugerido válido (revisar costo).", "warning")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))
    if sugerido <= venta_ef + 0.01:
        flash("El precio sugerido no supera el precio efectivo actual en POS.", "info")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))

    precio_anterior = venta_ef
    p.precio_venta = sugerido
    pm = float(p.precio_mayoreo or 0)
    if pm > sugerido:
        p.precio_mayoreo = sugerido
    elif pm <= 0:
        p.precio_mayoreo = sugerido
    registrar_bitacora_precio(
        producto_id=p.id,
        precio_anterior=precio_anterior,
        precio_nuevo=sugerido,
        costo_referencia=p.precio_compra or 0,
        margen_objetivo=margen_obj,
        usuario=(current_user.nombre if current_user.is_authenticated else None),
        motivo=motivo,
    )
    db.session.commit()
    flash(f"Precio actualizado para {p.nombre}.", "success")
    return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))


@app.route('/precios/revision/aplicar_masivo', methods=['POST'])
@permisos_required('revision_precios')
def aplicar_precio_sugerido_masivo():
    q = (request.form.get('q') or '').strip()
    categoria = (request.form.get('categoria') or '').strip()
    subcategoria = (request.form.get('subcategoria') or '').strip()
    margen_obj = _float_param(request.form.get('margen_obj'), 0.30)
    terminacion = request.form.get('terminacion', 90, type=int)

    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash("Debes indicar un motivo para la actualización masiva.", "warning")
        return redirect(url_for('revision_precios', q=q, categoria=categoria, subcategoria=subcategoria, margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))

    productos_q = Producto.query.filter(Producto.activo == True)
    if q:
        like = f"%{q}%"
        productos_q = productos_q.filter(
            or_(
                Producto.nombre.like(like),
                Producto.codigo_barra.like(like),
                and_(Producto.codigo_interno.isnot(None), Producto.codigo_interno.like(like)),
            )
        )
    if categoria:
        productos_q = productos_q.filter(Producto.categoria == categoria)
    if subcategoria:
        productos_q = productos_q.filter(Producto.subcategoria == subcategoria)

    aplicados = 0
    for p in productos_q.all():
        sugerido = _precio_sugerido_redondeado(p.precio_compra or 0, margen_obj, terminacion)
        venta_ef = precio_efectivo_pos_producto(p)
        if sugerido <= 0 or sugerido <= venta_ef + 0.01:
            continue
        precio_anterior = venta_ef
        p.precio_venta = sugerido
        pm = float(p.precio_mayoreo or 0)
        if pm > sugerido:
            p.precio_mayoreo = sugerido
        elif pm <= 0:
            p.precio_mayoreo = sugerido
        registrar_bitacora_precio(
            producto_id=p.id,
            precio_anterior=precio_anterior,
            precio_nuevo=sugerido,
            costo_referencia=p.precio_compra or 0,
            margen_objetivo=margen_obj,
            usuario=(current_user.nombre if current_user.is_authenticated else None),
            motivo=motivo,
        )
        aplicados += 1
    db.session.commit()
    flash(f"Actualización masiva completada. Productos ajustados: {aplicados}.", "success")
    return redirect(url_for('revision_precios', q=q, categoria=categoria, subcategoria=subcategoria, margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))


@app.route('/precios/revision/editar/<int:producto_id>', methods=['POST'])
@permisos_required('revision_precios')
def editar_precio_manual_revision(producto_id):
    """Ajuste manual de precio lista y mayoreo desde el listado (montos en pesos chilenos)."""
    p = Producto.query.get_or_404(producto_id)
    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash("Indica un motivo del cambio de precio.", "warning")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=_float_param(request.form.get('margen_obj'), 0.30), terminacion=request.form.get('terminacion', 90, type=int), solo_alerta=request.form.get('solo_alerta', '1')))

    n_lista = _parse_clp_monto(request.form.get('precio_venta'))
    n_may_raw = (request.form.get('precio_mayoreo') or '').strip()
    n_may = _parse_clp_monto(n_may_raw) if n_may_raw else None

    if n_lista is None:
        flash("Precio lista (CLP) no válido.", "danger")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=_float_param(request.form.get('margen_obj'), 0.30), terminacion=request.form.get('terminacion', 90, type=int), solo_alerta=request.form.get('solo_alerta', '1')))

    if n_lista <= 0:
        flash("El precio lista debe ser mayor a cero.", "warning")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=_float_param(request.form.get('margen_obj'), 0.30), terminacion=request.form.get('terminacion', 90, type=int), solo_alerta=request.form.get('solo_alerta', '1')))

    if n_may is not None and n_may < 0:
        flash("Precio mayoreo no válido.", "danger")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=_float_param(request.form.get('margen_obj'), 0.30), terminacion=request.form.get('terminacion', 90, type=int), solo_alerta=request.form.get('solo_alerta', '1')))

    antes_pv = float(p.precio_venta or 0)
    antes_pm = float(p.precio_mayoreo or 0)
    precio_anterior = precio_efectivo_pos_producto(p)

    p.precio_venta = float(n_lista)
    if n_may is not None:
        p.precio_mayoreo = float(n_may)
    else:
        if antes_pm > float(p.precio_venta or 0):
            p.precio_mayoreo = float(p.precio_venta or 0)

    despues_pv = float(p.precio_venta or 0)
    despues_pm = float(p.precio_mayoreo or 0)
    if abs(antes_pv - despues_pv) < 0.01 and abs(antes_pm - despues_pm) < 0.01:
        db.session.rollback()
        flash("No hay cambios respecto al precio actual.", "info")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=_float_param(request.form.get('margen_obj'), 0.30), terminacion=request.form.get('terminacion', 90, type=int), solo_alerta=request.form.get('solo_alerta', '1')))

    nuevo_ef = precio_efectivo_pos_producto(p)

    registrar_bitacora_precio(
        producto_id=p.id,
        precio_anterior=precio_anterior,
        precio_nuevo=float(nuevo_ef),
        costo_referencia=p.precio_compra or 0,
        margen_objetivo=None,
        usuario=(current_user.nombre if current_user.is_authenticated else None),
        motivo=motivo,
    )
    db.session.commit()
    flash(f"Precios actualizados (CLP) para {p.nombre}.", "success")
    margen_obj = _float_param(request.form.get('margen_obj'), 0.30)
    terminacion = request.form.get('terminacion', 90, type=int)
    return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))

# filtros rápidos para productos........................................................................

@app.route('/productos/filtro/<string:tipo>')
@login_required
def filtrar_productos(tipo):
    if tipo == "sin_stock":
        productos = Producto.query.all()
    elif tipo == "activos":
        productos = Producto.query.filter_by(activo=True).all()
    elif tipo == "venta":
        productos = Producto.query.filter(
            Producto.precio_venta > 0,
            Producto.activo == True
        ).all()
    else:
        productos = Producto.query.all()
    _adjuntar_stock_ui(productos)
    if tipo == "sin_stock":
        productos = [p for p in productos if int((p.stock_ui or {}).get('tienda', p.stock or 0) or 0) <= 0]
    elif tipo == "venta":
        productos = [p for p in productos if int((p.stock_ui or {}).get('tienda', p.stock or 0) or 0) > 0]
    categorias = _categorias_filtro_lista()
    subcategorias = _subcategorias_filtro_legacy('')
    return render_template(
        'productos.html',
        productos=productos,
        query='',
        categoria='',
        subcategoria='',
        sub_id=None,
        codigo_barra='',
        categorias=categorias,
        subcategorias=subcategorias,
        catalogo_sub_opciones=[],
        mostrar_filtro_sub_id=False,
        catalogo_registro_tree=_catalogo_arbol_registro(),
        catalogo_maestro_disponible=_catalogo_ui_disponible(),
        subcategorias_todas_legacy=subcategorias,
        puede_editar_stock_admin=_usuario_puede_ajustar_stock(),
    )


@app.route('/stock/critico')
@login_required
def stock_critico():
    umbral = request.args.get('umbral', 5, type=int)
    umbral = max(1, min(umbral, 200))
    q = (request.args.get('q') or '').strip()

    productos_q = Producto.query.filter(Producto.activo == True, Producto.stock <= umbral)
    if q:
        like = f"%{q}%"
        productos_q = productos_q.filter(
            (Producto.nombre.like(like)) |
            (Producto.codigo_barra.like(like))
        )
    productos = productos_q.order_by(Producto.stock.asc(), Producto.nombre.asc()).limit(1500).all()
    return render_template(
        'stock_critico.html',
        productos=productos,
        umbral=umbral,
        q=q,
        oc_tablas_ok=_tablas_orden_compra_existen(),
    )


@app.route('/inventario/dashboard-premium')
@login_required
def inventario_dashboard_premium():
    """Vista conceptual aislada para explorar un dashboard premium de stock."""
    return render_template('stock_dashboard_premium.html')


def _inventario_salud_payload(q, min_bodega):
    """
    Desajuste: productos.stock vs suma de stock_por_almacen en almacenes activos.
    Reposición: tienda=0 y bodega>=min_bodega (requiere TIENDA y BODEGA resueltos).
    """
    q = (q or '').strip()
    try:
        min_bodega = max(1, int(min_bodega))
    except (TypeError, ValueError):
        min_bodega = 1

    nom_tienda = 'Tienda'
    nom_bodega = 'Bodega'
    aid_t = id_almacen_tienda()
    aid_b = id_almacen_bodega()
    if aid_t:
        at = db.session.get(Almacen, aid_t)
        if at:
            nom_tienda = ((at.nombre or at.codigo or nom_tienda).strip()) or nom_tienda
    if aid_b:
        ab = db.session.get(Almacen, aid_b)
        if ab:
            nom_bodega = ((ab.nombre or ab.codigo or nom_bodega).strip()) or nom_bodega

    puede_reposicion_lista = bool(
        aid_t and aid_b and int(aid_t) != int(aid_b) and _tablas_inventario_almacen_existen()
    )

    vacio = {
        'q': q,
        'min_bodega': min_bodega,
        'n_desajuste': 0,
        'rows_des': [],
        'puede_reposicion_lista': puede_reposicion_lista,
        'detalle_tienda_bodega': puede_reposicion_lista,
        'nom_tienda': nom_tienda,
        'nom_bodega': nom_bodega,
        'n_reposicion': 0,
        'rows_rep': [],
    }

    if not _tablas_inventario_almacen_existen():
        vacio['puede_reposicion_lista'] = False
        return vacio

    suma_sq = (
        db.session.query(
            StockPorAlmacen.id_producto.label('pid'),
            func.coalesce(func.sum(StockPorAlmacen.cantidad), 0).label('suma'),
        )
        .join(Almacen, Almacen.id == StockPorAlmacen.id_almacen)
        .filter(Almacen.activo.is_(True))
        .group_by(StockPorAlmacen.id_producto)
        .subquery()
    )

    pq = (
        db.session.query(Producto, func.coalesce(suma_sq.c.suma, 0).label('suma_dep'))
        .outerjoin(suma_sq, suma_sq.c.pid == Producto.id)
        .filter(Producto.activo.is_(True))
    )
    if q:
        like = f"%{q}%"
        filtros_busqueda = [
            Producto.nombre.like(like),
            Producto.codigo_barra.like(like),
        ]
        filtros_busqueda.append(and_(Producto.codigo_interno.isnot(None), Producto.codigo_interno.like(like)))
        filtros_busqueda.append(and_(Producto.codigo_chilemat.isnot(None), Producto.codigo_chilemat.like(like)))
        pq = pq.filter(or_(*filtros_busqueda))

    batch = pq.order_by(Producto.id.asc()).limit(12000).all()

    rows_des = []
    rows_rep = []
    for p, suma_dep in batch:
        suma_dep = int(suma_dep or 0)
        sm = int(p.stock or 0)
        if sm != suma_dep:
            fila_des = {
                'nombre': p.nombre,
                'codigo_barra': ((p.codigo_barra or '').strip()) or None,
                'codigo_interno': ((p.codigo_interno or '').strip()) or None,
                'stock_maestro': sm,
                'suma_almacenes': suma_dep,
            }
            if puede_reposicion_lista:
                fila_des['qty_tienda'] = int(stock_producto_en_almacen(p.id, aid_t) or 0)
                fila_des['qty_bodega'] = int(stock_producto_en_almacen(p.id, aid_b) or 0)
            rows_des.append(fila_des)

        if puede_reposicion_lista:
            qt = int(stock_producto_en_almacen(p.id, aid_t) or 0)
            qb = int(stock_producto_en_almacen(p.id, aid_b) or 0)
            if qt == 0 and qb >= min_bodega:
                rows_rep.append(
                    {
                        'nombre': p.nombre,
                        'codigo_barra': ((p.codigo_barra or '').strip()) or None,
                        'codigo_interno': ((p.codigo_interno or '').strip()) or None,
                        'qty_tienda': qt,
                        'qty_bodega': qb,
                    }
                )

    rows_des.sort(key=lambda r: abs(int(r['stock_maestro']) - int(r['suma_almacenes'])), reverse=True)
    rows_rep.sort(key=lambda r: int(r['qty_bodega']), reverse=True)

    return {
        'q': q,
        'min_bodega': min_bodega,
        'n_desajuste': len(rows_des),
        'rows_des': rows_des,
        'puede_reposicion_lista': puede_reposicion_lista,
        'detalle_tienda_bodega': puede_reposicion_lista,
        'nom_tienda': nom_tienda,
        'nom_bodega': nom_bodega,
        'n_reposicion': len(rows_rep),
        'rows_rep': rows_rep,
    }


@app.route('/inventario/salud')
@permisos_required('enrolamiento_inventario', 'admin_inventario')
def inventario_salud():
    """Stock maestro vs suma por depósitos activos; candidatos bodega→tienda."""
    q = (request.args.get('q') or '').strip()
    try:
        min_bodega = int(request.args.get('min_bodega') or 1)
    except (TypeError, ValueError):
        min_bodega = 1
    min_bodega = max(1, min_bodega)

    export = (request.args.get('export') or '').strip().lower()
    pl = _inventario_salud_payload(q, min_bodega)

    if export == 'desajuste':
        si = io.StringIO()
        w = csv.writer(si)
        hdr = ['codigo_barra', 'codigo_interno', 'nombre', 'stock_maestro', 'suma_depositos', 'delta']
        if pl.get('detalle_tienda_bodega'):
            hdr.extend(['stock_almacen_tienda', 'stock_almacen_bodega'])
        w.writerow(hdr)
        for r in pl['rows_des']:
            sm = int(r['stock_maestro'] or 0)
            sa = int(r['suma_almacenes'] or 0)
            row = [
                r['codigo_barra'] or '',
                r['codigo_interno'] or '',
                r['nombre'] or '',
                sm,
                sa,
                sm - sa,
            ]
            if pl.get('detalle_tienda_bodega'):
                row.extend([int(r.get('qty_tienda') or 0), int(r.get('qty_bodega') or 0)])
            w.writerow(row)
        return Response(
            si.getvalue().encode('utf-8-sig'),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=salud_inventario_desajustes.csv'},
        )

    if export == 'reposicion':
        si = io.StringIO()
        w = csv.writer(si)
        w.writerow(['codigo_barra', 'codigo_interno', 'nombre', pl['nom_tienda'], pl['nom_bodega']])
        for r in pl['rows_rep']:
            w.writerow(
                [
                    r['codigo_barra'] or '',
                    r['codigo_interno'] or '',
                    r['nombre'] or '',
                    int(r['qty_tienda'] or 0),
                    int(r['qty_bodega'] or 0),
                ]
            )
        return Response(
            si.getvalue().encode('utf-8-sig'),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=salud_inventario_reposicion.csv'},
        )

    return render_template(
        'inventario_salud.html',
        q=pl['q'],
        min_bodega=pl['min_bodega'],
        n_desajuste=pl['n_desajuste'],
        rows_des=pl['rows_des'],
        puede_reposicion_lista=pl['puede_reposicion_lista'],
        detalle_tienda_bodega=pl.get('detalle_tienda_bodega', False),
        nom_tienda=pl['nom_tienda'],
        nom_bodega=pl['nom_bodega'],
        n_reposicion=pl['n_reposicion'],
        rows_rep=pl['rows_rep'],
    )


@app.route('/api/enrolamiento/sesion', methods=['POST'])
@login_required
def api_enrol_sesion():
    if not _usuario_enrol_autorizado():
        return jsonify(ok=False, error='forbidden', mensaje='No autorizado.'), 403
    if not _tablas_enrolamiento_existen():
        return jsonify(
            ok=False,
            mensaje='Faltan tablas de enrolamiento. Ejecutá sql/2026_05_06_enrolamiento_inventario.sql en la base.',
        ), 503
    data = request.get_json(silent=True) or {}
    raw_aid = data.get('id_almacen')
    id_almacen = None
    if raw_aid is not None and str(raw_aid).strip() != '':
        try:
            id_almacen = int(raw_aid)
        except (TypeError, ValueError):
            return jsonify(ok=False, mensaje='Almacén inválido.'), 400
        alm_chk = Almacen.query.filter_by(id=id_almacen, activo=True).first()
        if not alm_chk:
            return jsonify(ok=False, mensaje='Almacén no encontrado o inactivo.'), 400
    nombre_usuario = (getattr(current_user, 'nombre', None) or getattr(current_user, 'correo', None) or '')[:80]
    s = EnrolamientoTomaSesion(usuario=nombre_usuario, id_almacen=id_almacen)
    db.session.add(s)
    db.session.commit()
    almacen_nombre = ''
    almacen_rol = ''
    if id_almacen:
        alm = Almacen.query.get(id_almacen)
        if alm:
            almacen_nombre = (alm.nombre or alm.codigo or '').strip()
            almacen_rol = _enrol_resumen_almacen_codigo(alm)
    return jsonify(sesion_id=s.id, id_almacen=id_almacen, almacen_nombre=almacen_nombre, almacen_rol=almacen_rol)


@app.route('/api/enrolamiento/procesar_escaneo', methods=['POST'])
@login_required
def api_enrol_procesar_escaneo():
    if not _usuario_enrol_autorizado():
        return jsonify(ok=False, mensaje='No autorizado.'), 403
    if not _tablas_enrolamiento_existen():
        return jsonify(ok=False, mensaje='Tablas de enrolamiento no instaladas.'), 503
    data = request.get_json(silent=True) or {}
    try:
        sesion_id = int(data.get('sesion_id'))
    except (TypeError, ValueError):
        return jsonify(ok=False, mensaje='Sesión inválida.'), 400
    codigo = data.get('codigo')
    ses = _enrol_sesion_get_or_404(sesion_id)
    if not ses:
        return jsonify(ok=False, mensaje='Sesión no encontrada.'), 404
    p = _enrol_buscar_producto_por_codigo(codigo)
    if p:
        return jsonify(
            caso='A',
            producto=_enrol_serializar_producto(p, ses.id, ses.id_almacen),
        )
    return jsonify(caso='B', codigo_pendiente=_enrol_normalizar_codigo(codigo))


@app.route('/api/enrolamiento/buscar_maestro')
@login_required
def api_enrol_buscar_maestro():
    if not _usuario_enrol_autorizado():
        return jsonify(ok=False, mensaje='No autorizado.'), 403
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify(ok=True, items=[])
    like = f"%{q}%"
    filtros = [
        Producto.nombre.like(like),
        Producto.codigo_barra.like(like),
    ]
    filtros.append(and_(Producto.codigo_interno.isnot(None), Producto.codigo_interno.like(like)))
    filtros.append(and_(Producto.codigo_chilemat.isnot(None), Producto.codigo_chilemat.like(like)))
    items_q = (
        Producto.query.filter(or_(*filtros))
        .order_by(Producto.nombre.asc())
        .limit(40)
    )
    items = []
    for it in items_q:
        items.append({
            'id': it.id,
            'nombre': it.nombre,
            'codigo_chilemat': (it.codigo_chilemat or '').strip(),
            'codigo_interno': (it.codigo_interno or '').strip(),
            'imagen_url': (it.imagen_url or '').strip(),
        })
    return jsonify(ok=True, items=items)


@app.route('/api/enrolamiento/vincular', methods=['POST'])
@login_required
def api_enrol_vincular():
    if not _usuario_enrol_autorizado():
        return jsonify(ok=False, mensaje='No autorizado.'), 403
    if not _tablas_enrolamiento_existen():
        return jsonify(ok=False, mensaje='Tablas de enrolamiento no instaladas.'), 503
    data = request.get_json(silent=True) or {}
    try:
        sesion_id = int(data.get('sesion_id'))
        producto_id = int(data.get('producto_id'))
    except (TypeError, ValueError):
        return jsonify(ok=False, mensaje='Datos incompletos.'), 400
    ses = _enrol_sesion_get_or_404(sesion_id)
    if not ses:
        return jsonify(ok=False, mensaje='Sesión no encontrada.'), 404
    p = Producto.query.get(producto_id)
    if not p:
        return jsonify(ok=False, mensaje='Producto no encontrado.'), 404
    cb = _enrol_normalizar_codigo(data.get('codigo_barras'))
    if cb and _enrol_codigo_barra_ocupado(cb, excluir_producto_id=p.id):
        return jsonify(ok=False, error='barras_duplicado', mensaje='El código de barras ya está en otro producto.'), 409
    if cb:
        p.codigo_barra = cb[:50]
    try:
        cant = int(data.get('cantidad_inicial', 0))
    except (TypeError, ValueError):
        cant = 0
    cant = max(0, cant)
    mult = _tablas_inventario_almacen_existen()
    aid = _enrol_destino_almacen(ses, data.get('id_almacen_destino'))
    try:
        if mult:
            if cant and not aid:
                return jsonify(ok=False, mensaje='No hay almacén destino para sumar stock.'), 400
            if cant and aid:
                _, err = ajustar_stock_almacen(p.id, aid, cant)
                if err:
                    db.session.rollback()
                    return jsonify(ok=False, mensaje=err), 400
                _refrescar_stock_total_producto(p)
        else:
            p.stock = int(p.stock or 0) + cant
        if cant:
            _enrol_linea_conteo_sumar(ses.id, p.id, cant)
        db.session.commit()
    except SQLAlchemyError as ex:
        db.session.rollback()
        return jsonify(ok=False, mensaje=str(ex)), 400
    return jsonify(producto=_enrol_serializar_producto(p, ses.id, ses.id_almacen))


@app.route('/api/enrolamiento/alta_manual', methods=['POST'])
@login_required
def api_enrol_alta_manual():
    if not _usuario_enrol_autorizado():
        return jsonify(ok=False, mensaje='No autorizado.'), 403
    if not _tablas_enrolamiento_existen():
        return jsonify(ok=False, mensaje='Tablas de enrolamiento no instaladas.'), 503
    data = request.get_json(silent=True) or {}
    try:
        sesion_id = int(data.get('sesion_id'))
    except (TypeError, ValueError):
        return jsonify(ok=False, mensaje='Sesión inválida.'), 400
    ses = _enrol_sesion_get_or_404(sesion_id)
    if not ses:
        return jsonify(ok=False, mensaje='Sesión no encontrada.'), 404
    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return jsonify(ok=False, mensaje='El nombre es obligatorio.'), 400
    try:
        pv = float(str(data.get('precio_venta')).replace(',', '.'))
    except (TypeError, ValueError):
        pv = 0.0
    if pv <= 0:
        return jsonify(ok=False, mensaje='Precio de venta debe ser mayor que cero.'), 400
    try:
        pc = float(str(data.get('precio_compra', 0)).replace(',', '.'))
    except (TypeError, ValueError):
        pc = 0.0
    try:
        pm = float(str(data.get('precio_mayoreo', 0)).replace(',', '.'))
    except (TypeError, ValueError):
        pm = 0.0
    pc = max(0.0, pc)
    pm = max(0.0, pm)
    cb = _enrol_normalizar_codigo(data.get('codigo_barras'))
    if cb and _enrol_codigo_barra_ocupado(cb):
        return jsonify(ok=False, error='barras_duplicado', mensaje='El código de barras ya existe.'), 409
    try:
        cantidad_inicial = int(data.get('cantidad_inicial', 0))
    except (TypeError, ValueError):
        cantidad_inicial = 0
    cantidad_inicial = max(0, cantidad_inicial)

    p = Producto(
        nombre=nombre[:100],
        codigo_barra=cb[:50] if cb else None,
        codigo_chilemat=((data.get('codigo_chilemat') or '').strip()[:80] or None),
        precio_compra=pc,
        precio_venta=pv,
        precio_mayoreo=pm,
        stock=0,
        activo=True,
        unidad='Unidad',
        unidad_venta='Unidad',
        unidad_compra='Unidad',
    )
    sub_raw = data.get('subcategoria_catalogo_id')
    cat_raw = data.get('categoria_catalogo_id')
    if sub_raw:
        try:
            _sincronizar_producto_desde_subcatalogo(p, int(sub_raw))
        except (TypeError, ValueError):
            pass
    elif cat_raw:
        try:
            cc = CatalogoCategoria.query.get(int(cat_raw))
            if cc:
                p.categoria = (cc.nombre or '')[:50]
        except (TypeError, ValueError):
            pass
    else:
        cat_txt = (data.get('categoria') or '').strip()
        if cat_txt:
            p.categoria = cat_txt[:50]

    mult = _tablas_inventario_almacen_existen()
    aid = _enrol_destino_almacen(ses, data.get('id_almacen_destino'))
    try:
        db.session.add(p)
        db.session.flush()
        if mult:
            if cantidad_inicial and not aid:
                db.session.rollback()
                return jsonify(ok=False, mensaje='No hay almacén destino para el stock inicial.'), 400
            if cantidad_inicial and aid:
                _, err = ajustar_stock_almacen(p.id, aid, cantidad_inicial)
                if err:
                    db.session.rollback()
                    return jsonify(ok=False, mensaje=err), 400
                _refrescar_stock_total_producto(p)
        else:
            p.stock = cantidad_inicial
        if cantidad_inicial:
            _enrol_linea_conteo_sumar(ses.id, p.id, cantidad_inicial)
        db.session.commit()
    except SQLAlchemyError as ex:
        db.session.rollback()
        return jsonify(ok=False, mensaje=str(ex)), 400
    return jsonify(producto=_enrol_serializar_producto(p, ses.id, ses.id_almacen))


@app.route('/api/enrolamiento/entrada_stock', methods=['POST'])
@login_required
def api_enrol_entrada_stock():
    if not _usuario_enrol_autorizado():
        return jsonify(ok=False, mensaje='No autorizado.'), 403
    if not _tablas_enrolamiento_existen():
        return jsonify(ok=False, mensaje='Tablas de enrolamiento no instaladas.'), 503
    data = request.get_json(silent=True) or {}
    try:
        sesion_id = int(data.get('sesion_id'))
        producto_id = int(data.get('producto_id'))
        cantidad = int(data.get('cantidad'))
    except (TypeError, ValueError):
        return jsonify(ok=False, mensaje='Datos incompletos.'), 400
    if cantidad < 1:
        return jsonify(ok=False, mensaje='La cantidad debe ser al menos 1.'), 400
    ses = _enrol_sesion_get_or_404(sesion_id)
    if not ses:
        return jsonify(ok=False, mensaje='Sesión no encontrada.'), 404
    p = Producto.query.get(producto_id)
    if not p:
        return jsonify(ok=False, mensaje='Producto no encontrado.'), 404

    act_precios = bool(data.get('actualizar_precios'))
    if act_precios:
        if data.get('precio_venta') not in (None, ''):
            try:
                pv = float(str(data.get('precio_venta')).replace(',', '.'))
                if pv > 0:
                    p.precio_venta = pv
            except (TypeError, ValueError):
                pass
        if data.get('precio_compra') not in (None, ''):
            try:
                p.precio_compra = max(0.0, float(str(data.get('precio_compra')).replace(',', '.')))
            except (TypeError, ValueError):
                pass
        if data.get('precio_mayoreo') not in (None, ''):
            try:
                p.precio_mayoreo = max(0.0, float(str(data.get('precio_mayoreo')).replace(',', '.')))
            except (TypeError, ValueError):
                pass

    mult = _tablas_inventario_almacen_existen()
    aid = _enrol_destino_almacen(ses, data.get('id_almacen_destino'))
    try:
        if mult:
            if not aid:
                return jsonify(ok=False, mensaje='No hay almacén destino.'), 400
            _, err = ajustar_stock_almacen(p.id, aid, cantidad)
            if err:
                db.session.rollback()
                return jsonify(ok=False, mensaje=err), 400
            _refrescar_stock_total_producto(p)
        else:
            p.stock = int(p.stock or 0) + cantidad
        _enrol_linea_conteo_sumar(ses.id, p.id, cantidad)
        db.session.commit()
    except SQLAlchemyError as ex:
        db.session.rollback()
        return jsonify(ok=False, mensaje=str(ex)), 400
    return jsonify(producto=_enrol_serializar_producto(p, ses.id, ses.id_almacen))


@app.route('/api/enrolamiento/traslado', methods=['POST'])
@login_required
def api_enrol_traslado():
    if not _usuario_enrol_autorizado():
        return jsonify(ok=False, mensaje='No autorizado.'), 403
    if not _tablas_enrolamiento_existen():
        return jsonify(ok=False, mensaje='Tablas de enrolamiento no instaladas.'), 503
    if not _tablas_inventario_almacen_existen():
        return jsonify(ok=False, mensaje='Traslados requieren inventario por almacén.'), 400
    data = request.get_json(silent=True) or {}
    try:
        sesion_id = int(data.get('sesion_id'))
        producto_id = int(data.get('producto_id'))
        cantidad = int(data.get('cantidad'))
        io = int(data.get('id_almacen_origen'))
        idt = int(data.get('id_almacen_destino'))
    except (TypeError, ValueError):
        return jsonify(ok=False, mensaje='Datos incompletos.'), 400
    if cantidad < 1:
        return jsonify(ok=False, mensaje='Cantidad inválida.'), 400
    if io == idt:
        return jsonify(ok=False, mensaje='Origen y destino deben ser distintos.'), 400
    ses = _enrol_sesion_get_or_404(sesion_id)
    if not ses:
        return jsonify(ok=False, mensaje='Sesión no encontrada.'), 404
    p = Producto.query.get(producto_id)
    if not p:
        return jsonify(ok=False, mensaje='Producto no encontrado.'), 404
    for aid in (io, idt):
        if not Almacen.query.filter_by(id=aid, activo=True).first():
            return jsonify(ok=False, mensaje='Almacén inválido.'), 400
    try:
        _, err = ajustar_stock_almacen(p.id, io, -cantidad)
        if err:
            db.session.rollback()
            return jsonify(ok=False, mensaje=err), 400
        _, err2 = ajustar_stock_almacen(p.id, idt, cantidad)
        if err2:
            db.session.rollback()
            return jsonify(ok=False, mensaje=err2), 400
        _refrescar_stock_total_producto(p)
        db.session.commit()
    except SQLAlchemyError as ex:
        db.session.rollback()
        return jsonify(ok=False, mensaje=str(ex)), 400
    return jsonify(producto=_enrol_serializar_producto(p, ses.id, ses.id_almacen))


@app.route('/inventario/enrolamiento')
@permisos_required('enrolamiento_inventario', 'admin_inventario')
def inventario_enrolamiento():
    if not _tablas_enrolamiento_existen():
        flash(
            'Faltan las tablas de enrolamiento. Ejecutá en MySQL el script sql/2026_05_06_enrolamiento_inventario.sql '
            '(y las migraciones de almacenes si aún no las aplicaste).',
            'danger',
        )
        return redirect(url_for('index'))
    almacenes_ui = _enrol_almacenes_ui()
    if not almacenes_ui:
        flash('No hay almacenes activos. Creá al menos uno en Administración → Almacenes.', 'warning')
    enrol_cat_padres = None
    enrol_cat_nombres = _categorias_filtro_lista()
    if _catalogo_ui_disponible():
        enrol_cat_padres = [
            {'id': c.id, 'nombre': c.nombre}
            for c in CatalogoCategoria.query.filter_by(activo=True)
            .order_by(CatalogoCategoria.orden.asc(), CatalogoCategoria.nombre.asc())
            .all()
        ]
    id_almacen_default = None
    tid = id_almacen_tienda()
    if tid and any(a['id'] == tid for a in almacenes_ui):
        id_almacen_default = tid
    elif almacenes_ui:
        id_almacen_default = almacenes_ui[0]['id']
    return render_template(
        'inventario_enrolamiento.html',
        almacenes_ui=almacenes_ui,
        puede_traslado_almacenes=_enrol_permite_traslado_ui(),
        id_almacen_default=id_almacen_default,
        enrol_cat_padres=enrol_cat_padres,
        enrol_cat_nombres=enrol_cat_nombres,
    )


@app.route('/toggle_producto/<int:id>', methods=['POST'])
@login_required
def toggle_producto(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = not producto.activo
    db.session.commit()
    return redirect(url_for('mostrar_productos'))


@app.route('/productos/<int:id>/editar_stock', methods=['POST'])
@login_required
def editar_stock_producto(id):
    if not _usuario_puede_ajustar_stock():
        flash("No tienes permisos para ajustar stock desde esta pantalla.", "danger")
        return redirect(request.referrer or url_for('mostrar_productos'))

    producto = Producto.query.get_or_404(id)
    stock_nuevo_raw = (request.form.get('stock') or '').strip()
    try:
        stock_nuevo = int(stock_nuevo_raw)
    except (TypeError, ValueError):
        flash("Stock inválido. Debe ingresar un número entero.", "warning")
        return redirect(request.referrer or url_for('mostrar_productos'))

    if stock_nuevo < 0:
        flash("El stock no puede ser negativo.", "warning")
        return redirect(request.referrer or url_for('mostrar_productos'))

    if _tablas_inventario_almacen_existen():
        aid_tienda = id_almacen_tienda()
        if aid_tienda:
            fijar_stock_almacen(producto.id, aid_tienda, stock_nuevo)
            _refrescar_stock_total_producto(producto)
        else:
            producto.stock = stock_nuevo
    else:
        producto.stock = stock_nuevo

    db.session.commit()
    flash(f"Stock actualizado para «{producto.nombre}»: {stock_nuevo}.", "success")
    return redirect(request.referrer or url_for('mostrar_productos'))


@app.route('/productos/stock_masivo', methods=['POST'])
@login_required
def actualizar_stock_masivo_productos():
    if not _usuario_puede_ajustar_stock():
        flash("No tienes permisos para ejecutar ajustes masivos de stock.", "danger")
        return redirect(request.referrer or url_for('mostrar_productos'))

    stock_objetivo_raw = (request.form.get('stock_objetivo') or '').strip()
    try:
        stock_objetivo = int(stock_objetivo_raw)
    except (TypeError, ValueError):
        flash("Stock objetivo inválido. Debe ser un número entero.", "warning")
        return redirect(request.referrer or url_for('mostrar_productos'))

    if stock_objetivo < 0:
        flash("El stock objetivo no puede ser negativo.", "warning")
        return redirect(request.referrer or url_for('mostrar_productos'))

    confirmacion = (request.form.get('confirmacion') or '').strip().upper()
    if confirmacion != 'CONFIRMAR':
        flash("Confirmación inválida. Escriba CONFIRMAR para aplicar el ajuste masivo.", "warning")
        return redirect(request.referrer or url_for('mostrar_productos'))

    alcance = (request.form.get('alcance') or 'todos').strip().lower()
    productos_q = Producto.query
    if alcance == 'filtrados':
        q = (request.form.get('q') or '').strip()
        codigo_barra = (request.form.get('codigo_barra') or '').strip()
        categoria = (request.form.get('categoria') or '').strip()
        subcategoria = (request.form.get('subcategoria') or '').strip()
        sub_id = request.form.get('sub_id', type=int)

        if q:
            productos_q = productos_q.filter(
                (Producto.nombre.like(f"%{q}%")) |
                (Producto.codigo_barra.like(f"%{q}%"))
            )
        if codigo_barra:
            productos_q = productos_q.filter(Producto.codigo_barra.like(f"%{codigo_barra}%"))
        if sub_id and _catalogo_ui_disponible():
            productos_q = productos_q.filter(Producto.subcategoria_catalogo_id == sub_id)
        else:
            if categoria:
                productos_q = productos_q.filter_by(categoria=categoria)
            if subcategoria:
                productos_q = productos_q.filter_by(subcategoria=subcategoria)

    productos = productos_q.all()
    if not productos:
        flash("No hay productos para aplicar el ajuste masivo.", "warning")
        return redirect(request.referrer or url_for('mostrar_productos'))

    usa_almacenes = _tablas_inventario_almacen_existen()
    for p in productos:
        p.stock = stock_objetivo
        if usa_almacenes:
            aplicar_stock_desde_catalogo_a_tienda(p)
    db.session.commit()

    msg_scope = "filtrados" if alcance == 'filtrados' else "todos"
    flash(
        f"Ajuste masivo aplicado: {len(productos)} producto(s) en stock {stock_objetivo} ({msg_scope}).",
        "success",
    )
    return redirect(request.referrer or url_for('mostrar_productos'))

#guardar nuevo producto desde formulario........................................................................

@app.route('/guardar_producto', methods=['POST'])
@login_required
def guardar_producto():
    unidad_compra = (request.form.get('unidad_compra') or '').strip()
    unidad_venta = (request.form.get('unidad_venta') or '').strip()
    unidad_legacy = (request.form.get('unidad') or '').strip()
    try:
        factor = float(request.form.get('factor_conversion', 1) or 1)
    except (TypeError, ValueError):
        factor = 1
    factor = factor if factor > 0 else 1

    sub_cat_id = request.form.get('subcategoria_catalogo_id', type=int)
    if _catalogo_arbol_registro() and not sub_cat_id:
        flash('Elija categoría, familia e ítem del maestro (tres desplegables) antes de guardar.', 'warning')
        return redirect(url_for('mostrar_productos'))

    nuevo_p = Producto(
        nombre=request.form['nombre'],
        codigo_barra=request.form['codigo'],
        precio_compra=request.form['p_compra'],
        precio_venta=request.form['p_venta'],
        precio_mayoreo=request.form.get('p_mayoreo'),
        unidad=unidad_venta or unidad_legacy or "Unidad",
        unidad_compra=unidad_compra or unidad_venta or unidad_legacy or "Unidad",
        unidad_venta=unidad_venta or unidad_legacy or "Unidad",
        factor_conversion=factor,
        stock=request.form['stock'],
        categoria=(request.form.get('categoria') or '').strip() or None,
        subcategoria=(request.form.get('subcategoria') or '').strip() or None,
        ubicacion_pasillo=(request.form.get('ubicacion_pasillo') or '').strip() or None,
        ubicacion_estante=(request.form.get('ubicacion_estante') or '').strip() or None,
        ubicacion_nivel=(request.form.get('ubicacion_nivel') or '').strip() or None,
        activo=True
    )
    if sub_cat_id:
        _sincronizar_producto_desde_subcatalogo(nuevo_p, sub_cat_id)
    db.session.add(nuevo_p)
    db.session.flush()
    aplicar_stock_desde_catalogo_a_tienda(nuevo_p)
    db.session.commit()
    return redirect(url_for('mostrar_productos'))
#..............................................................................................
@app.route('/cargar_productos', methods=['POST'])
@login_required
def cargar_productos():
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        flash("Debe seleccionar un archivo.", "warning")
        return redirect(url_for('mostrar_productos'))

    fn = (archivo.filename or '').lower()
    if not (fn.endswith('.csv') or fn.endswith('.xlsx') or fn.endswith('.xlsm')):
        flash("Formato inválido. Suba un .csv o un Excel .xlsx.", "warning")
        return redirect(url_for('mostrar_productos'))

    contenido = archivo.read()
    if len(contenido) > 5 * 1024 * 1024:
        flash("El archivo excede 5MB. Divídalo en bloques.", "warning")
        return redirect(url_for('mostrar_productos'))

    creados = 0
    actualizados = 0
    omitidos = 0
    duplicados_archivo = 0
    precios_sugeridos = 0
    cache_por_codigo = {}

    keymap = {}
    filas = []

    if fn.endswith('.xlsx') or fn.endswith('.xlsm'):
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(contenido), engine='openpyxl')
        except Exception as e:
            flash(
                f"No se pudo leer el Excel (.xlsx). Si usó formato .xls antiguo, guarde como .xlsx en Excel. Detalle: {e}",
                "danger",
            )
            return redirect(url_for('mostrar_productos'))
        df.columns = [_normalizar_encabezado_carga(c) for c in df.columns]
        for c in df.columns:
            keymap[c] = c
        for _, r in df.iterrows():
            fila = {}
            for col in df.columns:
                v = r[col]
                if pd.isna(v):
                    fila[col] = ''
                elif isinstance(v, float) and v == int(v):
                    fila[col] = int(v)
                else:
                    fila[col] = v
            filas.append(fila)
    else:
        texto_csv = None
        for enc in ("utf-8-sig", "latin-1"):
            try:
                texto_csv = contenido.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if texto_csv is None:
            flash("No se pudo leer el CSV. Use UTF-8 o Latin-1.", "danger")
            return redirect(url_for('mostrar_productos'))

        reader = csv.DictReader(io.StringIO(texto_csv))
        for h in reader.fieldnames or []:
            if h and str(h).strip():
                orig = str(h).strip()
                keymap[_normalizar_encabezado_carga(orig)] = orig
        filas = list(reader)

    def _csv_has(logical_name):
        return _normalizar_encabezado_carga(logical_name) in keymap

    def _csv_cell(row, logical_name):
        k = keymap.get(_normalizar_encabezado_carga(logical_name))
        if k is None:
            return None
        return row.get(k)

    def _to_float(v, default=0.0):
        try:
            if v is None or str(v).strip() == '':
                return float(default)
            return float(str(v).replace(',', '.'))
        except Exception:
            return float(default)

    def _to_int(v, default=0):
        try:
            if v is None or str(v).strip() == '':
                return int(default)
            return int(float(str(v).replace(',', '.')))
        except Exception:
            return int(default)

    def _clip(v, max_len):
        s = (v or '')
        s = str(s).strip()
        return s[:max_len]

    def _margen_default():
        try:
            return float(os.getenv('CARGA_CSV_MARGEN_DEFAULT', '0.30'))
        except ValueError:
            return 0.30

    def _aplicar_precio_venta_sugerido(prod_row, es_nuevo, row_data):
        nonlocal precios_sugeridos
        costo = float(prod_row.precio_compra or 0)
        mg = _margen_default()
        if _csv_has('margen_venta'):
            mg = _to_float(_csv_cell(row_data, 'margen_venta'), mg)
        term = 90
        if _csv_has('terminacion'):
            term = _to_int(_csv_cell(row_data, 'terminacion'), 90)
        if costo <= 0:
            if es_nuevo:
                prod_row.precio_venta = 0.0
            return
        prod_row.precio_venta = _precio_sugerido_redondeado(costo, mg, term)
        precios_sugeridos += 1

    for row in filas:
        codigo = _clip(_csv_cell(row, 'codigo_barra') or _csv_cell(row, 'codigo') or '', 50)
        nombre = _clip(_csv_cell(row, 'nombre') or '', 100)
        if not codigo or not nombre:
            omitidos += 1
            continue

        if codigo in cache_por_codigo:
            prod = cache_por_codigo[codigo]
            es_nuevo = False
            duplicados_archivo += 1
        else:
            with db.session.no_autoflush:
                prod = Producto.query.filter_by(codigo_barra=codigo).first()
            es_nuevo = prod is None
            if es_nuevo:
                prod = Producto(codigo_barra=codigo, activo=True)
                db.session.add(prod)
            cache_por_codigo[codigo] = prod

        prod.nombre = nombre

        if _csv_has('precio_compra'):
            prod.precio_compra = _to_float(_csv_cell(row, 'precio_compra'), 0)

        pv_cell = _csv_cell(row, 'precio_venta')
        if pv_cell is not None:
            if str(pv_cell).strip() != '':
                prod.precio_venta = _to_float(pv_cell, 0)
            else:
                _aplicar_precio_venta_sugerido(prod, es_nuevo, row)
        elif es_nuevo:
            _aplicar_precio_venta_sugerido(prod, True, row)

        if _csv_has('precio_mayoreo'):
            prod.precio_mayoreo = _to_float(_csv_cell(row, 'precio_mayoreo'), 0)

        if _csv_has('unidad_venta') or _csv_has('unidad') or _csv_has('unidad_compra'):
            prod.unidad = _clip(
                _csv_cell(row, 'unidad_venta') or _csv_cell(row, 'unidad') or "Unidad",
                20,
            )
            prod.unidad_compra = _clip(
                _csv_cell(row, 'unidad_compra')
                or _csv_cell(row, 'unidad_venta')
                or _csv_cell(row, 'unidad')
                or "Unidad",
                20,
            )
            prod.unidad_venta = _clip(
                _csv_cell(row, 'unidad_venta') or _csv_cell(row, 'unidad') or "Unidad",
                20,
            )
        elif es_nuevo:
            prod.unidad = _clip("Unidad", 20)
            prod.unidad_compra = _clip("Unidad", 20)
            prod.unidad_venta = _clip("Unidad", 20)

        if _csv_has('factor_conversion'):
            prod.factor_conversion = _to_float(_csv_cell(row, 'factor_conversion'), 1) or 1
        elif es_nuevo:
            prod.factor_conversion = 1.0

        if _csv_has('stock'):
            prod.stock = _to_int(_csv_cell(row, 'stock'), 0)
            aplicar_stock_desde_catalogo_a_tienda(prod)

        if _csv_has('categoria'):
            prod.categoria = _clip(_csv_cell(row, 'categoria'), 50) or None
        elif es_nuevo:
            prod.categoria = None
        if _csv_has('subcategoria'):
            prod.subcategoria = _clip(_csv_cell(row, 'subcategoria'), 50) or None
        elif es_nuevo:
            prod.subcategoria = None
        if _csv_has('ubicacion_pasillo'):
            prod.ubicacion_pasillo = _clip(_csv_cell(row, 'ubicacion_pasillo'), 12) or None
        if _csv_has('ubicacion_estante'):
            prod.ubicacion_estante = _clip(_csv_cell(row, 'ubicacion_estante'), 12) or None
        if _csv_has('ubicacion_nivel'):
            prod.ubicacion_nivel = _clip(_csv_cell(row, 'ubicacion_nivel'), 12) or None

        prod.activo = True

        if es_nuevo:
            creados += 1
        else:
            actualizados += 1
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error en carga masiva: {str(e)}", "danger")
        return redirect(url_for('mostrar_productos'))
    msg = (
        f"Carga completada. Creados: {creados} | Actualizados: {actualizados} | "
        f"Omitidos: {omitidos} | Duplicados en archivo: {duplicados_archivo}."
    )
    if precios_sugeridos:
        msg += f" Precio venta sugerido aplicado: {precios_sugeridos} filas."
    flash(msg, "success")
    return redirect(url_for('mostrar_productos'))

@app.route('/productos/exportar_excel')
@login_required
def exportar_productos_excel():
    """Descarga catálogo en Excel (.xlsx) para editar y volver a subir en Carga masiva."""
    q = (request.args.get('q') or '').strip()
    codigo_barra = (request.args.get('codigo_barra') or '').strip()
    categoria = (request.args.get('categoria') or '').strip()
    subcategoria = (request.args.get('subcategoria') or '').strip()
    sub_id = request.args.get('sub_id', type=int)

    productos_q = Producto.query
    if q:
        productos_q = productos_q.filter(
            (Producto.nombre.like(f"%{q}%")) |
            (Producto.codigo_barra.like(f"%{q}%"))
        )
    if codigo_barra:
        productos_q = productos_q.filter(Producto.codigo_barra.like(f"%{codigo_barra}%"))
    if sub_id and _catalogo_ui_disponible():
        productos_q = productos_q.filter(Producto.subcategoria_catalogo_id == sub_id)
    else:
        if categoria:
            productos_q = productos_q.filter_by(categoria=categoria)
        if subcategoria:
            productos_q = productos_q.filter_by(subcategoria=subcategoria)

    productos = productos_q.order_by(Producto.nombre.asc()).all()
    import pandas as pd

    rows = []
    for p in productos:
        rows.append({
            'nombre': p.nombre or '',
            'codigo_barra': p.codigo_barra or '',
            'precio_compra': float(p.precio_compra or 0),
            'precio_venta': float(p.precio_venta or 0),
            'precio_mayoreo': float(p.precio_mayoreo or 0),
            'margen_venta': '',
            'terminacion': '',
            'unidad_compra': p.unidad_compra or '',
            'unidad_venta': p.unidad_venta or p.unidad or '',
            'factor_conversion': float(p.factor_conversion or 1),
            'stock': int(p.stock or 0),
            'categoria': p.categoria or '',
            'subcategoria': p.subcategoria or '',
            'ubicacion_pasillo': p.ubicacion_pasillo or '',
            'ubicacion_estante': p.ubicacion_estante or '',
            'ubicacion_nivel': p.ubicacion_nivel or '',
        })
    df = pd.DataFrame(rows)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Productos')
    bio.seek(0)
    return send_file(
        bio,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='productos_ferreteria.xlsx',
    )


@app.route('/descargar_plantilla_productos')
def descargar_plantilla_productos():
    # precio_venta vacío + precio_compra > 0 → precio venta sugerido (misma lógica que Revisión de precios).
    # terminacion: 0 redondeo entero, 90 termina en …90, 990 en …990.
    contenido = (
        "nombre,codigo_barra,precio_compra,precio_venta,precio_mayoreo,margen_venta,terminacion,"
        "unidad_compra,unidad_venta,factor_conversion,stock,categoria,subcategoria,"
        "ubicacion_pasillo,ubicacion_estante,ubicacion_nivel\n"
    )
    contenido += "Tornillo Zincado 1in,123456,12000,180,160,0.30,90,Caja,Unidad,100,3500,Herramientas,Tornillos,P02,E04,N1\n"
    contenido += "Producto precio sugerido,999888,5000,,,0.35,90,Pieza,Unidad,1,100,Herramientas,Varios,P01,E01,N1\n"
    return Response(
        contenido,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=plantilla_productos.csv"}
    )
# --- PROVEEDORES ---....................................................................
@app.route('/proveedores')
@login_required
def mostrar_proveedores():
    q = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = max(10, min(per_page, 100))

    proveedores_query = Proveedor.query
    if q:
        like = f"%{q}%"
        proveedores_query = proveedores_query.filter(
            (Proveedor.nombre.like(like)) |
            (Proveedor.contacto.like(like)) |
            (Proveedor.telefono.like(like)) |
            (Proveedor.email.like(like))
        )

    proveedores_pagination = proveedores_query.order_by(Proveedor.nombre.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    proveedores = proveedores_pagination.items
    canales_map = obtener_canales_proveedor()

    total_proveedores = Proveedor.query.count()
    proveedores_con_telefono = Proveedor.query.filter(Proveedor.telefono.isnot(None), Proveedor.telefono != '').count()
    proveedores_con_email = Proveedor.query.filter(Proveedor.email.isnot(None), Proveedor.email != '').count()

    return render_template(
        'provedores.html',
        proveedores=proveedores,
        canales_compra_map=canales_map,
        canales_compra_validos=CANALES_COMPRA_VALIDOS,
        proveedores_pagination=proveedores_pagination,
        q=q,
        per_page=per_page,
        total_proveedores=total_proveedores,
        proveedores_con_telefono=proveedores_con_telefono,
        proveedores_con_email=proveedores_con_email
    )
# proceso de guardar nuevo proveedor desde formulario........................................................................
@app.route('/guardar_proveedor', methods=['POST'])
@login_required
def guardar_proveedor():
    nombre = (request.form.get('nombre') or '').strip()
    contacto = (request.form.get('contacto') or '').strip()
    telefono = (request.form.get('telefono') or '').strip()
    email = (request.form.get('email') or '').strip()
    canal_compra = (request.form.get('canal_compra') or 'manual').strip().lower()

    if not nombre:
        flash("El nombre del proveedor es obligatorio.", "warning")
        return redirect(url_for('mostrar_proveedores'))

    nuevo_prov = Proveedor(
        nombre=nombre,
        contacto=contacto or None,
        telefono=telefono or None,
        email=email or None
    )
    db.session.add(nuevo_prov)
    db.session.commit()
    guardar_canal_compra_proveedor(nuevo_prov.id, canal_compra)
    flash("Proveedor registrado correctamente.", "success")
    return redirect(url_for('mostrar_proveedores'))


@app.route('/editar_proveedor/<int:id>', methods=['POST'])
@login_required
def editar_proveedor(id):
    prov = Proveedor.query.get_or_404(id)
    nombre = (request.form.get('nombre') or '').strip()
    contacto = (request.form.get('contacto') or '').strip()
    telefono = (request.form.get('telefono') or '').strip()
    email = (request.form.get('email') or '').strip()
    canal_compra = (request.form.get('canal_compra') or 'manual').strip().lower()

    if not nombre:
        flash("El nombre del proveedor es obligatorio.", "warning")
        return redirect(url_for('mostrar_proveedores'))

    prov.nombre = nombre
    prov.contacto = contacto or None
    prov.telefono = telefono or None
    prov.email = email or None
    db.session.commit()
    guardar_canal_compra_proveedor(prov.id, canal_compra)
    flash("Proveedor actualizado correctamente.", "success")
    return redirect(url_for('mostrar_proveedores'))


@app.route('/eliminar_proveedor/<int:id>', methods=['POST'])
@login_required
def eliminar_proveedor(id):
    prov = Proveedor.query.get_or_404(id)
    try:
        db.session.delete(prov)
        db.session.commit()
        eliminar_canal_compra_proveedor(id)
        flash("Proveedor eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo eliminar proveedor: {str(e)}", "danger")
    return redirect(url_for('mostrar_proveedores'))

# --- MODULO DE VENTAS  ---........................................................................
@app.route('/ventas')
@login_required
@caja_requerida
def mostrar_ventas():
    fecha_inicio = request.args.get('fecha_inicio', '').strip()
    fecha_fin = request.args.get('fecha_fin', '').strip()
    estado = request.args.get('estado', '').strip()
    metodo_pago = request.args.get('metodo_pago', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 30, type=int)
    per_page = max(10, min(per_page, 100))

    ventas_query = Venta.query
    if estado:
        ventas_query = ventas_query.filter(Venta.estado == estado)
    if metodo_pago:
        ventas_query = ventas_query.filter(Venta.metodo_pago == metodo_pago)
    if fecha_inicio:
        try:
            fi = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            ventas_query = ventas_query.filter(Venta.fecha >= fi)
        except ValueError:
            pass
    if fecha_fin:
        try:
            ff = datetime.strptime(fecha_fin, "%Y-%m-%d") + timedelta(days=1)
            ventas_query = ventas_query.filter(Venta.fecha < ff)
        except ValueError:
            pass

    total_dia = ventas_query.filter(Venta.estado == "Pagado").with_entities(db.func.sum(Venta.monto_total)).scalar() or 0
    monto_en_vuelo = ventas_query.filter(Venta.estado == "Pendiente").with_entities(db.func.sum(Venta.monto_total)).scalar() or 0
    cant_tickets = ventas_query.count()
    art_rotados = (
        db.session.query(db.func.sum(DetalleVenta.cantidad))
        .join(Venta, DetalleVenta.id_venta == Venta.id)
        .scalar() or 0
    )
    promedio = (total_dia + monto_en_vuelo) / cant_tickets if cant_tickets > 0 else 0

    ventas_pagination = ventas_query.order_by(Venta.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    ventas = ventas_pagination.items
    productos = Producto.query.filter_by(activo=True).all()
    pendientes = ventas_query.filter(Venta.estado == 'Pendiente').count()

    return render_template('gestion_ventas.html', 
                           total_dia=total_dia,
                           monto_en_vuelo=monto_en_vuelo,
                           ventas_pendientes_count=pendientes,
                           ticket_promedio=promedio,
                           total_articulos=art_rotados,
                           ventas=ventas,
                           productos=productos,
                           ventas_pagination=ventas_pagination)

# proceso de guardar venta desde formulario de ventas
@app.route('/guardar_venta', methods=['POST'])
@login_required
@caja_requerida
def guardar_venta():
    # 1. Obtenemos la caja
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    
    # 2. Capturamos método de pago y cliente
    metodo_seleccionado = request.form.get('metodo_pago', 'Efectivo')
    cliente_id = request.form.get('cliente_id') # Asegúrate de enviar este ID desde el HTML
    
    if not caja:
        flash("No hay caja abierta para registrar ventas.", "danger")
        return redirect(url_for('abrir_caja'))

    # Pre-calculamos y validamos líneas de venta
    ids = request.form.getlist('id_producto[]')
    cantidades = request.form.getlist('cantidad[]')
    precios = request.form.getlist('precio_unitario[]')
    lineas_validas = []

    for pid, c, p in zip(ids, cantidades, precios):
        if not pid or not c or not p:
            continue
        try:
            producto_id = int(pid)
            cantidad = int(c)
            precio = float(p)
        except (TypeError, ValueError):
            flash("Hay productos con cantidades o precios inválidos.", "danger")
            return redirect(url_for('punto_venta'))
        if cantidad <= 0 or precio < 0:
            flash("Las cantidades deben ser mayores a 0 y los precios no negativos.", "warning")
            return redirect(url_for('punto_venta'))
        lineas_validas.append((producto_id, cantidad, precio))

    if not lineas_validas:
        flash("Debe agregar al menos un producto válido a la venta.", "warning")
        return redirect(url_for('punto_venta'))

    total_proyectado = sum(cantidad * precio for _, cantidad, precio in lineas_validas)

    # --- LÓGICA DE CRÉDITO PREMIUM ---
    cliente = None
    if metodo_seleccionado == "Credito":
        if not cliente_id:
            flash("Error: Seleccione un cliente para ventas a crédito.", "danger")
            return redirect(url_for('punto_venta'))
        
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            flash("Error: Cliente no encontrado.", "danger")
            return redirect(url_for('punto_venta'))

        # Validamos si tiene cupo (Límite - Saldo actual)
        if (cliente.saldo_deudor + total_proyectado) > cliente.limite_credito:
            cupo = cliente.limite_credito - cliente.saldo_deudor
            flash(f"CRÉDITO DENEGADO: El cliente excede su límite. Cupo disponible: ${cupo:,.0f}", "warning")
            return redirect(url_for('punto_venta'))
        
        # Aumentamos la deuda del cliente inmediatamente
        cliente.saldo_deudor += total_proyectado
    # ---------------------------------

    nueva_venta = Venta(
        usuario=current_user.nombre, 
        caja_id=caja.id,
        cliente_id=cliente_id if cliente_id else None,
        monto_total=total_proyectado,
        estado="Pagado" if metodo_seleccionado != "Credito" else "Pendiente",
        metodo_pago=metodo_seleccionado
    )

    db.session.add(nueva_venta)
    db.session.flush()

    # 3. Validamos stock y registramos detalles
    for producto_id, cant, prec in lineas_validas:
        subtotal = cant * prec
        prod = Producto.query.get(producto_id)
        if not prod:
            db.session.rollback()
            flash("Uno de los productos seleccionados no existe.", "danger")
            return redirect(url_for('punto_venta'))
        factor_venta_stock = _factor_venta_a_stock(prod)
        consumo_stock = int(round(cant * factor_venta_stock))
        if consumo_stock <= 0:
            db.session.rollback()
            flash(f"Conversión inválida para {prod.nombre}.", "warning")
            return redirect(url_for('punto_venta'))
        disp = stock_disponible_venta_tienda(prod)
        if disp < consumo_stock:
            db.session.rollback()
            flash(
                f"Stock insuficiente para {prod.nombre}. "
                f"Requiere {consumo_stock} u. base en tienda y hay {disp}.",
                "warning",
            )
            return redirect(url_for('punto_venta'))
        
        detalle = DetalleVenta(
            id_venta=nueva_venta.id, 
            id_producto=producto_id,
            cantidad=cant, 
            precio_unitario=prec,
            subtotal=subtotal
        )
        db.session.add(detalle)
        err_st = descontar_stock_venta_tienda(prod, consumo_stock)
        if err_st:
            db.session.rollback()
            flash(f"No se pudo descontar stock para {prod.nombre}: {err_st}", "danger")
            return redirect(url_for('punto_venta'))
        registrar_movimiento_kardex(
            prod.id,
            'SALIDA',
            consumo_stock,
            f"Venta directa #{nueva_venta.id} ({metodo_seleccionado})"
            f" ({cant} {prod.unidad_venta_final} -> {consumo_stock} stock)",
            usuario=current_user.nombre,
            id_almacen=id_almacen_tienda() or 1,
            referencia_tipo='venta',
            referencia_id=nueva_venta.id,
            stock_saldo=None,
        )

    try:
        db.session.commit()
        msg = f"Venta #{nueva_venta.id} registrada."
        if metodo_seleccionado == "Credito":
            msg += f" Cargado a cuenta de {cliente.nombre}."
        flash(msg, "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al registrar venta: {str(e)}", "danger")

    return redirect(url_for('mostrar_ventas'))


def _reparar_precios_cero_lineas_venta_abierta(venta):
    """
    Líneas POS con precio_unitario 0 pero el catálogo ya tiene precio (venta o mayoreo).
    Actualiza y recalcula total.
    """
    if not venta or getattr(venta, 'estado', None) != 'Abierta':
        return False
    detalles = list(venta.detalles or [])
    if not detalles:
        return False
    arreglados = 0
    for d in detalles:
        prod = d.producto
        if not prod:
            continue
        pu_lin = float(d.precio_unitario or 0)
        pu_cat = precio_efectivo_pos_producto(prod)
        if pu_lin <= 0 and pu_cat > 0:
            cant = float(d.cantidad or 1)
            desc = float(d.descuento or 0)
            d.precio_unitario = pu_cat
            d.subtotal = (pu_cat * cant) * (1 - desc / 100.0)
            arreglados += 1
    if not arreglados:
        return False
    venta.recalcular_total()
    db.session.commit()
    flash(
        f"Se actualizó el precio en {arreglados} línea(s) que estaban en $0 según precio venta/mayoreo del catálogo.",
        "info",
    )
    return True


def _nombre_usuario_pos_actual():
    nom = (getattr(current_user, 'nombre', None) or '').strip()
    return nom or "POS"


def _venta_abierta_por_caja_y_usuario(caja_id, usuario_nombre):
    return (
        Venta.query.filter_by(estado="Abierta", caja_id=caja_id, usuario=usuario_nombre)
        .order_by(Venta.id.desc())
        .first()
    )


def _venta_validar_stock_tienda(venta):
    """
    Revisa si una venta puede cobrarse/descontarse en TIENDA.
    Retorna lista de mensajes de faltantes (vacía si todo ok).
    """
    faltantes = []
    if not venta:
        return faltantes
    try:
        detalles = list(venta.detalles or [])
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("No se pudo cargar detalle de venta %s para validar stock: %s", getattr(venta, 'id', None), ex)
        return ["No se pudo validar stock del vale (revise detalle)."]
    for d in detalles:
        try:
            producto = d.producto or Producto.query.get(d.id_producto)
            if not producto:
                faltantes.append("Producto no encontrado en línea de venta.")
                continue
            factor_venta_stock = _factor_venta_a_stock(producto)
            consumo_stock = int(round((d.cantidad or 0) * factor_venta_stock))
            disp = stock_disponible_venta_tienda(producto)
            if consumo_stock <= 0:
                faltantes.append(f"{producto.nombre}: conversión inválida.")
                continue
            if disp < consumo_stock:
                faltantes.append(
                    f"{producto.nombre} (disponible tienda: {disp}, requerido: {consumo_stock})"
                )
        except Exception as ex:
            db.session.rollback()
            app.logger.exception("No se pudo validar stock de línea %s: %s", getattr(d, 'id', None), ex)
            faltantes.append("No se pudo validar una línea del vale.")
    return faltantes


def _asegurar_columnas_ventas_legacy():
    """Asegura columnas agregadas en `ventas` para bases legacy (MySQL/Postgres)."""
    if app.config.get('_VENTAS_LEGACY_OK'):
        return True
    try:
        insp = sa_inspect(db.engine)
        if 'ventas' not in set(insp.get_table_names()):
            app.config['_VENTAS_LEGACY_OK'] = True
            return True
        cols = {c['name'] for c in insp.get_columns('ventas')}
        cambios = False
        if 'punto_retiro' not in cols:
            db.session.execute(text(
                "ALTER TABLE ventas ADD COLUMN punto_retiro VARCHAR(30) DEFAULT 'Bodega'"
            ))
            db.session.execute(text(
                "UPDATE ventas SET punto_retiro = 'Bodega' "
                "WHERE punto_retiro IS NULL OR punto_retiro = ''"
            ))
            cambios = True
        if 'vuelto' not in cols:
            db.session.execute(text("ALTER TABLE ventas ADD COLUMN vuelto NUMERIC(14,2) NULL"))
            cambios = True
        if 'saldo_favor_usado' not in cols:
            db.session.execute(text("ALTER TABLE ventas ADD COLUMN saldo_favor_usado NUMERIC(14,2) DEFAULT 0"))
            cambios = True
        if 'prioridad' not in cols:
            db.session.execute(text("ALTER TABLE ventas ADD COLUMN prioridad INTEGER NULL"))
            cambios = True
        if 'motivo_anulacion' not in cols:
            db.session.execute(text("ALTER TABLE ventas ADD COLUMN motivo_anulacion VARCHAR(500) NULL"))
            cambios = True
        if 'fecha_anulacion' not in cols:
            db.session.execute(text("ALTER TABLE ventas ADD COLUMN fecha_anulacion TIMESTAMP NULL"))
            cambios = True
        if 'usuario_anulacion' not in cols:
            db.session.execute(text("ALTER TABLE ventas ADD COLUMN usuario_anulacion VARCHAR(80) NULL"))
            cambios = True
        if cambios:
            db.session.commit()
        app.config['_VENTAS_LEGACY_OK'] = True
        return True
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("No se pudo asegurar columnas legacy de ventas: %s", ex)
        return False


def _asegurar_columnas_productos_legacy():
    """Asegura columnas agregadas en `productos` para bases legacy."""
    if app.config.get('_PRODUCTOS_LEGACY_OK'):
        return True
    try:
        insp = sa_inspect(db.engine)
        if 'productos' not in set(insp.get_table_names()):
            app.config['_PRODUCTOS_LEGACY_OK'] = True
            return True
        cols = {c['name'] for c in insp.get_columns('productos')}
        cambios = False
        if 'codigo_chilemat' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN codigo_chilemat VARCHAR(80) NULL"))
            cambios = True
        if 'codigo_interno' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN codigo_interno VARCHAR(32) NULL"))
            cambios = True
        if 'imagen_url' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN imagen_url VARCHAR(500) NULL"))
            cambios = True
        if 'unidad_compra' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN unidad_compra VARCHAR(20) NULL"))
            cambios = True
        if 'unidad_venta' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN unidad_venta VARCHAR(20) NULL"))
            cambios = True
        if 'factor_conversion' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN factor_conversion NUMERIC(12,4) NULL"))
            cambios = True
        if 'subcategoria_catalogo_id' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN subcategoria_catalogo_id INTEGER NULL"))
            cambios = True
        if 'ubicacion_pasillo' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN ubicacion_pasillo VARCHAR(12) NULL"))
            cambios = True
        if 'ubicacion_estante' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN ubicacion_estante VARCHAR(12) NULL"))
            cambios = True
        if 'ubicacion_nivel' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN ubicacion_nivel VARCHAR(12) NULL"))
            cambios = True
        if 'activo' not in cols:
            db.session.execute(text("ALTER TABLE productos ADD COLUMN activo BOOLEAN DEFAULT TRUE"))
            cambios = True
        if cambios:
            db.session.commit()
        app.config['_PRODUCTOS_LEGACY_OK'] = True
        return True
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("No se pudo asegurar columnas legacy de productos: %s", ex)
        return False


def _asegurar_columnas_detalle_ventas_legacy():
    """Asegura columnas agregadas en `detalle_ventas` para bases legacy."""
    if app.config.get('_DETALLE_VENTAS_LEGACY_OK'):
        return True
    try:
        insp = sa_inspect(db.engine)
        if 'detalle_ventas' not in set(insp.get_table_names()):
            app.config['_DETALLE_VENTAS_LEGACY_OK'] = True
            return True
        cols = {c['name'] for c in insp.get_columns('detalle_ventas')}
        cambios = False
        if 'precio_unitario' not in cols:
            db.session.execute(text("ALTER TABLE detalle_ventas ADD COLUMN precio_unitario NUMERIC(14,2) NOT NULL DEFAULT 0"))
            cambios = True
        if 'descuento' not in cols:
            db.session.execute(text("ALTER TABLE detalle_ventas ADD COLUMN descuento NUMERIC(8,2) NULL"))
            cambios = True
        if 'subtotal' not in cols:
            db.session.execute(text("ALTER TABLE detalle_ventas ADD COLUMN subtotal NUMERIC(14,2) NULL"))
            cambios = True
        if cambios:
            db.session.commit()
        app.config['_DETALLE_VENTAS_LEGACY_OK'] = True
        return True
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("No se pudo asegurar columnas legacy de detalle_ventas: %s", ex)
        return False


def _asegurar_columnas_caja_cuadratura():
    """Asegura columnas de cuadratura/cierre en `caja` para bases legacy."""
    if app.config.get('_CAJA_CUADRATURA_OK'):
        return True
    try:
        insp = sa_inspect(db.engine)
        if 'caja' not in set(insp.get_table_names()):
            app.config['_CAJA_CUADRATURA_OK'] = True
            return True

        cols = {c['name'] for c in insp.get_columns('caja')}
        cambios = False
        if 'monto_teorico_cierre' not in cols:
            db.session.execute(text("ALTER TABLE caja ADD COLUMN monto_teorico_cierre NUMERIC(14,2) NULL"))
            cambios = True
        if 'monto_contado_cierre' not in cols:
            db.session.execute(text("ALTER TABLE caja ADD COLUMN monto_contado_cierre NUMERIC(14,2) NULL"))
            cambios = True
        if 'diferencia_cierre' not in cols:
            db.session.execute(text("ALTER TABLE caja ADD COLUMN diferencia_cierre NUMERIC(14,2) NULL"))
            cambios = True
        if 'observacion_cierre' not in cols:
            db.session.execute(text("ALTER TABLE caja ADD COLUMN observacion_cierre VARCHAR(255) NULL"))
            cambios = True
        if 'supervisor_cierre' not in cols:
            db.session.execute(text("ALTER TABLE caja ADD COLUMN supervisor_cierre VARCHAR(80) NULL"))
            cambios = True

        if cambios:
            db.session.commit()
        app.config['_CAJA_CUADRATURA_OK'] = True
        return True
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("No se pudo asegurar columnas de cuadratura de caja: %s", ex)
        return False


def _redondear_montos_ventas_pendientes():
    """Limpia montos_total con decimales en vales pendientes (legado).

    El cálculo nuevo redondea siempre, pero ventas creadas antes de este fix
    pueden tener .48 u otros decimales que rompen el input HTML del cobro
    en caja. Esta tarea idempotente redondea solo los pendientes.
    """
    if app.config.get('_REDONDEO_VENTAS_OK'):
        return True
    try:
        insp = sa_inspect(db.engine)
        if 'ventas' not in set(insp.get_table_names()):
            app.config['_REDONDEO_VENTAS_OK'] = True
            return True
        db.session.execute(text(
            "UPDATE ventas SET monto_total = ROUND(monto_total) "
            "WHERE estado = 'Pendiente' AND monto_total IS NOT NULL"
        ))
        db.session.commit()
        app.config['_REDONDEO_VENTAS_OK'] = True
        return True
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("No se pudo redondear montos pendientes: %s", ex)
        return False


# proceso de punto de venta, creación de venta abierta y manejo de vales pendientes........................................
@app.route('/punto_venta')
@login_required      # Verifica que el usuario esté logueado
@caja_requerida     # <--- ESTA ES LA LÍNEA QUE FALTA
@permisos_required('pos_emitir_vale')
def punto_venta():
    if not _asegurar_columnas_caja_cuadratura():
        flash("No se pudo preparar la tabla de caja (cuadratura). Revise permisos de BD.", "danger")
        return redirect(url_for('mostrar_ventas'))
    if not _asegurar_columnas_ventas_legacy():
        flash("No se pudo preparar la tabla de ventas (campos legacy). Revise permisos de BD.", "danger")
        return redirect(url_for('mostrar_ventas'))

    # Buscar la última caja abierta
    caja = obtener_caja_activa()
    if not caja:
        flash("No hay caja abierta. Debe abrir la caja antes de usar el punto de venta.")
        return redirect(url_for('mostrar_ventas'))

    vendedor_actual = _nombre_usuario_pos_actual()
    # Cada vendedor trabaja su vale abierto dentro de la misma caja.
    venta = _venta_abierta_por_caja_y_usuario(caja.id, vendedor_actual)
    if not venta:
        venta = Venta(
            usuario=vendedor_actual,
            estado="Abierta",
            monto_total=0,
            caja_id=caja.id,
            fecha=db.func.current_timestamp()
        )
        db.session.add(venta)
        db.session.commit()

    _reparar_precios_cero_lineas_venta_abierta(venta)

    # Vales pendientes
    vales_pendientes = Venta.query.filter_by(estado="Pendiente").all()

    # Si la venta tiene cliente asociado
    cliente = venta.cliente if venta and venta.cliente_id else None

    detalles = venta.detalles or []
    factores_stock = {}
    consumos_stock = {}
    for d in detalles:
        f = _factor_venta_a_stock(d.producto)
        factores_stock[d.id] = f
        consumos_stock[d.id] = int(round((d.cantidad or 0) * f))

    pids = [d.id_producto for d in detalles if d.id_producto]
    stock_tienda = stock_tienda_por_producto_ids(pids)

    # Renderizar la plantilla con los datos
    return render_template(
        'punto_venta.html',
        venta=venta,
        detalles=detalles,
        vales_pendientes=vales_pendientes,
        cliente=cliente,
        factores_stock=factores_stock,
        consumos_stock=consumos_stock,
        stock_tienda=stock_tienda,
    )


# proceso de agregar productos a venta abierta desde punto de venta........................................

@app.route('/agregar_producto_venta', methods=['POST'])
@login_required
@caja_requerida
@permisos_required('pos_emitir_vale')
def agregar_producto_venta():
    try:
        codigo = (request.form.get('codigo') or '').strip()
        producto_id_raw = request.form.get('producto_id')
        caja = obtener_caja_activa()
        if not caja:
            flash("No hay caja abierta para operar en Punto de Venta.", "warning")
            return redirect(url_for('abrir_caja'))

        producto = None
        if producto_id_raw:
            try:
                producto = Producto.query.get(int(producto_id_raw))
            except (TypeError, ValueError):
                producto = None
        if not producto and codigo:
            cnorm = codigo.strip().upper()
            producto = (
                Producto.query.filter(db.func.upper(db.func.trim(Producto.codigo_barra)) == cnorm)
                .first()
            )
        if not producto and codigo:
            cnorm = codigo.strip().upper()
            producto = (
                Producto.query.filter(
                    Producto.codigo_interno.isnot(None),
                    db.func.upper(db.func.trim(Producto.codigo_interno)) == cnorm,
                )
                .first()
            )
        if not producto and codigo:
            cnorm = codigo.strip().upper()
            producto = (
                Producto.query.filter(
                    Producto.codigo_chilemat.isnot(None),
                    db.func.upper(db.func.trim(Producto.codigo_chilemat)) == cnorm,
                )
                .first()
            )
        if not producto:
            flash(f"Producto no encontrado ({codigo or 'sin código'}).", "warning")
            return redirect(url_for('punto_venta'))

        if stock_disponible_venta_tienda(producto) <= 0:
            flash(f"Sin stock disponible en tienda para {producto.nombre}.", "warning")
            return redirect(url_for('punto_venta'))

        db.session.refresh(producto)
        pu_ef = precio_efectivo_pos_producto(producto)
        if pu_ef <= 0:
            flash(
                f"El producto «{producto.nombre}» no tiene precio de venta ni mayoreo configurado.",
                "warning",
            )
            return redirect(url_for('punto_venta'))

        vendedor_actual = _nombre_usuario_pos_actual()
        venta = _venta_abierta_por_caja_y_usuario(caja.id, vendedor_actual)
        if not venta:
            venta = Venta(
                usuario=vendedor_actual,
                estado="Abierta",
                monto_total=0,
                caja_id=caja.id,
                fecha=db.func.current_timestamp()
            )
            db.session.add(venta)
            db.session.flush()

        cantidad = 1
        precio_unitario = pu_ef
        desc = 0.0
        detalle = DetalleVenta(
            id_venta=venta.id,
            id_producto=producto.id,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            descuento=desc,
            subtotal=precio_unitario * cantidad * (1 - desc / 100.0),
        )
        db.session.add(detalle)
        db.session.flush()
        venta.recalcular_total()
        db.session.commit()
        return redirect(url_for('punto_venta'))
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("No se pudo agregar producto al vale: %s", ex)
        flash(f"No se pudo agregar el producto al vale: {ex}", "danger")
        return redirect(url_for('punto_venta'))

# proceso de eliminar producto de venta abierta desde punto de venta........................................

@app.route('/eliminar_detalle/<int:id>', methods=['POST'])
@login_required
@caja_requerida
@permisos_required('pos_emitir_vale')
def eliminar_detalle(id):
    detalle = DetalleVenta.query.get_or_404(id)
    venta = detalle.venta
    db.session.delete(detalle)
    venta.recalcular_total()
    db.session.commit()
    return redirect(url_for('punto_venta'))

#eliminar venta abierta o pendiente desde pantalla de ventas........................................................................

@app.route('/eliminar_venta/<int:id>', methods=['POST'])
@login_required
@caja_requerida
def eliminar_venta(id):
    venta = Venta.query.get_or_404(id)
    try:
        db.session.delete(venta)
        db.session.commit()
        flash(f"Venta N°{venta.id} eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar la venta: {str(e)}", "danger")
    return redirect(url_for('mostrar_ventas'))


# proceso de finalización de venta, validación de cliente y emisión de vale................................

@app.route('/finalizar_venta', methods=['POST'])
@login_required
@caja_requerida
@permisos_required('pos_emitir_vale')
def finalizar_venta():
    caja = obtener_caja_activa()
    if not caja:
        flash("No hay caja abierta para emitir vale.", "warning")
        return redirect(url_for('abrir_caja'))

    vendedor_actual = _nombre_usuario_pos_actual()
    # Cada vendedor finaliza su propio vale abierto.
    venta = _venta_abierta_por_caja_y_usuario(caja.id, vendedor_actual)
    if not venta or venta.monto_total == 0:
        flash("Error: La venta está vacía.", "danger")
        return redirect(url_for('punto_venta'))
    # Persistencia explícita para reportes por vendedor.
    venta.usuario = vendedor_actual
    faltantes = _venta_validar_stock_tienda(venta)
    if faltantes:
        flash(
            "No se puede emitir el vale: falta stock en tienda para "
            + "; ".join(faltantes[:3]),
            "warning",
        )
        return redirect(url_for('punto_venta'))

    nombre = request.form.get('cliente_nombre')
    direccion = request.form.get('cliente_direccion')
    giro = request.form.get('cliente_giro')
    telefono = request.form.get('cliente_telefono')
    correo = request.form.get('cliente_correo')
    comuna = request.form.get('cliente_comuna')
    ciudad = request.form.get('cliente_ciudad')
    es_cliente_final = request.form.get('cliente_final') == '1'

    if es_cliente_final:
        cliente = obtener_o_crear_cliente_final()
    else:
        rut = request.form.get('cliente_rut')
        if not rut or not validar_rut(rut):
            flash("Error: RUT inválido.", "danger")
            return redirect(url_for('punto_venta'))

        cliente = Cliente.query.filter_by(rut=rut).first()

        if cliente:
            cliente.direccion = direccion or cliente.direccion
            cliente.giro = giro or cliente.giro
            cliente.telefono = telefono or cliente.telefono
            cliente.correo = correo or cliente.correo
            cliente.comuna = comuna or cliente.comuna
            cliente.ciudad = ciudad or cliente.ciudad

            if nombre and nombre != cliente.nombre:
                flash("El cliente ya existe, no puedes cambiar el nombre.", "warning")
                return redirect(url_for('punto_venta'))
        else:
            if not nombre:
                flash("Error: Nombre es obligatorio para nuevo cliente.", "danger")
                return redirect(url_for('punto_venta'))
            cliente = Cliente(
                nombre=nombre,
                rut=rut,
                giro=giro,
                direccion=direccion,
                telefono=telefono,
                correo=correo,
                comuna=comuna,
                ciudad=ciudad,
            )
            db.session.add(cliente)

    db.session.commit()

    # Marcar la venta como pendiente y asignar prioridad
    pendientes = Venta.query.filter_by(estado="Pendiente").count()
    punto_retiro = (request.form.get('punto_retiro') or '').strip()
    puntos_validos = {'Bodega', 'Tienda', 'Despacho'}
    if (not punto_retiro) or punto_retiro == '__PENDIENTE__' or punto_retiro not in puntos_validos:
        flash("Debe seleccionar dónde retirará el cliente (Bodega, Tienda o Despacho).", "warning")
        return redirect(url_for('punto_venta'))
    venta.prioridad = pendientes + 1
    venta.cliente_id = cliente.id
    venta.estado = "Pendiente"
    venta.punto_retiro = punto_retiro
    db.session.commit()

    # Mensaje de confirmación
    flash(f"Vale N°{venta.id} emitido para {cliente.nombre}. Turno {venta.prioridad}.", "info")

    detalles_picking = sorted(list(venta.detalles), key=lambda d: clave_ubicacion_producto(d.producto))

    # Renderizar ticket
    return render_template('ticket_vale.html',
                           venta=venta,
                           detalles=venta.detalles,
                           detalles_picking=detalles_picking,
                           cliente=cliente)

#edición de venta para vales pendientes desde pantalla de ventas........................................

@app.route('/editar_venta/<int:id>', methods=['GET', 'POST'])
@login_required
@caja_requerida
def editar_venta(id):
    venta = Venta.query.get_or_404(id)
    if (venta.estado or '').strip() == 'Anulada':
        flash('No se puede editar un vale anulado.', 'warning')
        return redirect(url_for('mostrar_ventas'))
    productos = Producto.query.all()
    if request.method == 'POST':
        venta.usuario = request.form['usuario']
        # eliminar detalles anteriores
        for d in venta.detalles:
            db.session.delete(d)
        ids = request.form.getlist('id_producto[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio_unitario[]')
        total = 0
        for i in range(len(ids)):
            id_producto = int(ids[i])
            cantidad = int(cantidades[i])
            precio_unitario = float(precios[i])
            subtotal = cantidad * precio_unitario
            total += subtotal
            detalle = DetalleVenta(
                id_venta=venta.id,
                id_producto=id_producto,
                cantidad=cantidad,
                precio_unitario=precio_unitario
            )
            db.session.add(detalle)
        venta.total = total
        db.session.commit()
        flash("Venta actualizada correctamente.", "success")
        return redirect(url_for('mostrar_ventas'))
    return render_template('editar_venta.html', venta=venta, productos=productos)


@app.route('/pos/usuarios_autorizar_descuento')
@login_required
@caja_requerida
def pos_usuarios_autorizar_descuento():
    """Lista usuarios activos que pueden autorizar aumento de descuento en POS (autocompletado)."""
    q = (request.args.get('q') or '').strip().lower()
    items = []
    for u in Usuario.query.order_by(Usuario.nombre).all():
        if not usuario_esta_activo(u):
            continue
        if not usuario_obj_tiene_permiso(u, 'autorizar_descuento_pos'):
            continue
        nombre = (u.nombre or '').strip()
        correo = (u.correo or '').strip()
        if q and q not in nombre.lower() and q not in correo.lower():
            continue
        items.append({'nombre': nombre, 'correo': correo})
    return jsonify({'usuarios': items[:50]})


# proceso de actualización de cantidad y descuento en venta abierta desde punto de venta........................................
@app.route('/actualizar_item', methods=['POST'])
@login_required
@caja_requerida
@permisos_required('pos_emitir_vale')
def actualizar_item():
    detalle_id = request.form.get('actualizar')
    solo_cantidad = request.form.get('solo_cantidad') == '1'
    try:
        cantidad = int(request.form.get(f'cantidad_{detalle_id}', 1))
        descuento = float(request.form.get(f'descuento_{detalle_id}', 0))
    except (TypeError, ValueError):
        flash("Cantidad o descuento inválido.", "warning")
        return redirect(url_for('punto_venta'))

    if cantidad <= 0:
        flash("La cantidad debe ser mayor a 0.", "warning")
        return redirect(url_for('punto_venta'))

    caja_activa = obtener_caja_activa()
    detalle = DetalleVenta.query.get(detalle_id)
    if not detalle:
        return redirect(url_for('punto_venta'))

    if not detalle.venta or detalle.venta.estado != "Abierta" or detalle.venta.caja_id != (caja_activa.id if caja_activa else None):
        flash("No puede modificar ítems fuera de la venta activa del turno.", "warning")
        return redirect(url_for('punto_venta'))

    desc_anterior = float(detalle.descuento or 0)
    if solo_cantidad:
        descuento = desc_anterior
    if descuento < 0:
        flash("El descuento no puede ser negativo.", "warning")
        return redirect(url_for('punto_venta'))
    if descuento > 100:
        flash("El descuento no puede ser mayor al 100%.", "warning")
        return redirect(url_for('punto_venta'))

    aumenta_desc = descuento > desc_anterior + 1e-6
    desc_con_credencial_supervisor = False
    if aumenta_desc and not usuario_tiene_permiso('autorizar_descuento_pos'):
        ident_raw = (
            request.form.get('supervisor_identificador')
            or request.form.get('supervisor_correo')
            or ''
        ).strip()
        pwd = request.form.get('supervisor_clave') or ''
        if not ident_raw or not pwd:
            flash(
                "Para aumentar el descuento el supervisor debe ingresar su usuario (o correo) y contraseña.",
                "warning",
            )
            return redirect(url_for('punto_venta'))
        sup, err_lookup = resolver_usuario_por_identificador_pos(ident_raw)
        if err_lookup == 'ambiguous_email_local':
            flash(
                "Varios correos coinciden con ese texto; el supervisor debe usar el correo completo.",
                "warning",
            )
            return redirect(url_for('punto_venta'))
        if err_lookup == 'ambiguous_nombre':
            flash(
                "Hay más de un usuario con ese nombre; use la parte antes del @ del correo o el correo completo.",
                "warning",
            )
            return redirect(url_for('punto_venta'))
        if (
            not sup
            or err_lookup == 'not_found'
            or not sup.check_password(pwd)
            or not usuario_esta_activo(sup)
            or not usuario_obj_tiene_permiso(sup, 'autorizar_descuento_pos')
        ):
            flash(
                "Autorización inválida: usuario no encontrado, sin permiso o contraseña incorrecta.",
                "danger",
            )
            return redirect(url_for('punto_venta'))
        desc_con_credencial_supervisor = True

    if detalle.producto:
        f_prev = _factor_venta_a_stock(detalle.producto)
        cons_prev = int(round((detalle.cantidad or 0) * f_prev))
        cons_new = int(round(cantidad * f_prev))
        disp_t = stock_disponible_venta_tienda(detalle.producto)
        if disp_t + cons_prev < cons_new:
            max_u = int((disp_t + cons_prev) / f_prev) if f_prev else disp_t + detalle.cantidad
            flash(f"Stock insuficiente en tienda. Cantidad máxima aproximada: {max_u}.", "warning")
            return redirect(url_for('punto_venta'))

    detalle.cantidad = cantidad
    detalle.descuento = descuento
    detalle.subtotal = (detalle.precio_unitario * cantidad) * (1 - (descuento / 100))
    db.session.commit()
    detalle.venta.recalcular_total()
    db.session.commit()

    if desc_con_credencial_supervisor:
        flash("Descuento aplicado con autorización de supervisor.", "success")

    return redirect(url_for('punto_venta'))


def _asegurar_tablas_cambios():
    """Asegura que las tablas y columnas del módulo de cambios existan.

    - Las tablas se crean a través de los modelos SQLAlchemy (db.create_all() en init_db).
      Aquí solo respaldamos el caso de bases que se actualizan sin re-ejecutar init_db.
    - Las columnas nuevas (ALTER TABLE) se agregan en sintaxis ANSI portable
      (sirve tanto para MySQL como para Postgres/Neon).
    """
    if app.config.get('_CAMBIOS_TABLAS_OK'):
        return True
    try:
        insp = sa_inspect(db.engine)
        tablas = set(insp.get_table_names())
        tablas_modelos = ['cambios_operacion', 'cambios_detalle',
                          'clientes_saldos_favor', 'movimientos_saldo_favor']
        if any(t not in tablas for t in tablas_modelos):
            db.create_all()
            insp = sa_inspect(db.engine)
            tablas = set(insp.get_table_names())

        if 'cambios_operacion' in tablas:
            cols_cambio = {c['name'] for c in insp.get_columns('cambios_operacion')}
            if 'venta_origen_id' not in cols_cambio:
                db.session.execute(text(
                    "ALTER TABLE cambios_operacion ADD COLUMN venta_origen_id INTEGER NULL"
                ))
                db.session.commit()
        app.config['_CAMBIOS_TABLAS_OK'] = True
        return True
    except Exception:
        db.session.rollback()
        return False


def _producto_por_codigo_pos(codigo):
    c = (codigo or '').strip().upper()
    if not c:
        return None
    p = Producto.query.filter(db.func.upper(db.func.trim(Producto.codigo_barra)) == c).first()
    if p:
        return p
    return (
        Producto.query.filter(
            Producto.codigo_interno.isnot(None),
            db.func.upper(db.func.trim(Producto.codigo_interno)) == c,
        ).first()
    )


def _parse_lineas_cambio(raw_txt):
    rows = []
    for idx, raw in enumerate((raw_txt or '').splitlines(), start=1):
        line = (raw or '').strip()
        if not line:
            continue
        parts = [p.strip() for p in line.replace(';', ',').split(',') if p.strip() != '']
        if len(parts) < 2:
            raise ValueError(f"Línea {idx}: use formato codigo,cantidad[,precio].")
        codigo = parts[0]
        try:
            cantidad = int(parts[1])
        except (TypeError, ValueError):
            raise ValueError(f"Línea {idx}: cantidad inválida.")
        if cantidad <= 0:
            raise ValueError(f"Línea {idx}: cantidad debe ser mayor a 0.")
        precio_manual = None
        if len(parts) >= 3:
            try:
                precio_manual = float(str(parts[2]).replace('.', '').replace(',', '.'))
            except (TypeError, ValueError):
                raise ValueError(f"Línea {idx}: precio inválido.")
            if precio_manual < 0:
                raise ValueError(f"Línea {idx}: precio no puede ser negativo.")
        rows.append({'codigo': codigo, 'cantidad': cantidad, 'precio_manual': precio_manual})
    return rows


def _saldo_favor_actual(cliente_id):
    if not cliente_id:
        return 0.0
    row = ClienteSaldoFavor.query.filter_by(cliente_id=cliente_id).first()
    return float(row.saldo or 0) if row else 0.0


def _aplicar_mov_saldo_favor(cliente_id, cambio_id, tipo, monto, observacion):
    if not cliente_id or float(monto or 0) <= 0:
        return 0.0
    reg = ClienteSaldoFavor.query.filter_by(cliente_id=cliente_id).first()
    if not reg:
        reg = ClienteSaldoFavor(cliente_id=cliente_id, saldo=0)
        db.session.add(reg)
        db.session.flush()
    actual = float(reg.saldo or 0)
    if tipo == 'CREDITO':
        nuevo = actual + float(monto)
    else:
        nuevo = max(0.0, actual - float(monto))
    reg.saldo = nuevo
    db.session.add(
        MovimientoSaldoFavor(
            cliente_id=cliente_id,
            cambio_id=cambio_id,
            tipo=tipo,
            monto=float(monto),
            saldo_resultante=nuevo,
            observacion=(observacion or '')[:255] if observacion else None,
        )
    )
    return nuevo


# CAJA vales pendientes
@app.route('/caja/vales_pendientes')
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def caja_pendientes():
    _redondear_montos_ventas_pendientes()
    db.session.rollback()
    hoy = datetime.now().date()
    dt_ini_hoy = datetime.combine(hoy, datetime.min.time())
    dt_fin_hoy = datetime.combine(hoy + timedelta(days=1), datetime.min.time())

    caja_apertura = obtener_caja_activa()
    cid = caja_apertura.id if caja_apertura else None
    monto_apertura = caja_apertura.monto_inicial if caja_apertura else 0

    # Documentos cobrados hoy en esta caja (alineado al turno actual)
    q_pagado_hoy = Venta.query.filter(
        Venta.estado == "Pagado",
        Venta.fecha >= dt_ini_hoy,
        Venta.fecha < dt_fin_hoy,
    )
    if cid is not None:
        q_pagado_hoy = q_pagado_hoy.filter(Venta.caja_id == cid)
    tickets_emitidos = q_pagado_hoy.count()

    monto_vendido = (
        db.session.query(db.func.coalesce(db.func.sum(Venta.monto_total), 0))
        .filter(
            Venta.estado == "Pagado",
            Venta.fecha >= dt_ini_hoy,
            Venta.fecha < dt_fin_hoy,
        )
    )
    if cid is not None:
        monto_vendido = monto_vendido.filter(Venta.caja_id == cid)
    monto_vendido = float(monto_vendido.scalar() or 0)

    # Cola para cobrar en esta pantalla (mismo filtro que la tabla de vales)
    vales = (
        Venta.query.filter(
            Venta.estado == "Pendiente",
            Venta.metodo_pago.is_(None),
        )
        .order_by(Venta.fecha.desc())
        .all()
    )
    db.session.rollback()
    for v in vales:
        falt = _venta_validar_stock_tienda(v)
        v.stock_cobrable = len(falt) == 0
        v.stock_alerta = "; ".join(falt[:2]) if falt else ""
        v.saldo_favor_disponible = _saldo_favor_actual(v.cliente_id) if v.cliente_id else 0.0
    db.session.rollback()
    monto_pendiente = float(
        db.session.query(db.func.coalesce(db.func.sum(Venta.monto_total), 0))
        .filter(Venta.estado == "Pendiente", Venta.metodo_pago.is_(None))
        .scalar()
        or 0
    )

    q_vuelto = db.session.query(db.func.coalesce(db.func.sum(Venta.vuelto), 0)).filter(
        Venta.fecha >= dt_ini_hoy,
        Venta.fecha < dt_fin_hoy,
        Venta.estado == "Pagado",
    )
    if cid is not None:
        q_vuelto = q_vuelto.filter(Venta.caja_id == cid)
    vuelto_entregado = float(q_vuelto.scalar() or 0)

    # Créditos registrados hoy para control operativo de caja
    creditos_hoy = (
        Venta.query.filter(
            Venta.fecha >= dt_ini_hoy,
            Venta.fecha < dt_fin_hoy,
            Venta.metodo_pago == "Credito",
        )
        .order_by(Venta.fecha.desc())
        .limit(15)
        .all()
    )

    return render_template(
        'caja_pendientes.html',
        tickets_emitidos=tickets_emitidos,
        monto_apertura=monto_apertura,
        monto_vendido=monto_vendido,
        monto_pendiente=monto_pendiente,
        vuelto_entregado=vuelto_entregado,
        vales=vales,
        creditos_hoy=creditos_hoy
    )


@app.route('/caja/cambios', methods=['GET', 'POST'])
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def caja_cambios():
    if not _asegurar_tablas_cambios():
        flash("No se pudo preparar tablas de cambios/saldos. Revise permisos de BD.", "danger")
        return redirect(url_for('caja_pendientes'))

    cliente_id = request.form.get('cliente_id', type=int) if request.method == 'POST' else request.args.get('cliente_id', type=int)
    cliente = Cliente.query.get(cliente_id) if cliente_id else None

    if request.method == 'POST':
        caja_activa = obtener_caja_activa()
        if not caja_activa:
            flash("Debe tener caja abierta para registrar cambios.", "warning")
            return redirect(url_for('abrir_caja'))

        try:
            devueltos = _parse_lineas_cambio(request.form.get('lineas_devueltas'))
            entregados = _parse_lineas_cambio(request.form.get('lineas_entregadas'))
        except ValueError as ex:
            flash(str(ex), "warning")
            return redirect(url_for('caja_cambios', cliente_id=cliente_id or None))

        if not devueltos:
            flash("Debe ingresar al menos una línea devuelta.", "warning")
            return redirect(url_for('caja_cambios', cliente_id=cliente_id or None))

        observacion = (request.form.get('observacion') or '').strip()[:500]
        try:
            monto_pagado = float(request.form.get('monto_pagado') or 0)
            monto_devuelto = float(request.form.get('monto_devuelto_efectivo') or 0)
        except (TypeError, ValueError):
            flash("Monto pagado/devuelto inválido.", "warning")
            return redirect(url_for('caja_cambios', cliente_id=cliente_id or None))
        if monto_pagado < 0 or monto_devuelto < 0:
            flash("Los montos no pueden ser negativos.", "warning")
            return redirect(url_for('caja_cambios', cliente_id=cliente_id or None))

        try:
            usar_saldo = float(request.form.get('usar_saldo_favor') or 0)
        except (TypeError, ValueError):
            usar_saldo = 0
        usar_saldo = max(0.0, usar_saldo)

        detalle_devueltos = []
        detalle_entregados = []
        total_devuelto = 0.0
        total_entregado = 0.0
        aid_tienda = id_almacen_tienda() or 1

        try:
            for row in devueltos:
                p = _producto_por_codigo_pos(row['codigo'])
                if not p:
                    raise ValueError(f"No existe producto devuelto con código: {row['codigo']}")
                precio = row['precio_manual']
                if precio is None:
                    precio = precio_efectivo_pos_producto(p)
                if precio <= 0:
                    raise ValueError(f"Producto devuelto sin precio válido: {p.nombre}")
                subtotal = float(precio) * int(row['cantidad'])
                detalle_devueltos.append((p, int(row['cantidad']), float(precio), subtotal))
                total_devuelto += subtotal

            for row in entregados:
                p = _producto_por_codigo_pos(row['codigo'])
                if not p:
                    raise ValueError(f"No existe producto entregado con código: {row['codigo']}")
                precio = row['precio_manual']
                if precio is None:
                    precio = precio_efectivo_pos_producto(p)
                if precio <= 0:
                    raise ValueError(f"Producto entregado sin precio válido: {p.nombre}")
                qty = int(row['cantidad'])
                disp = stock_disponible_venta_tienda(p)
                if disp < qty:
                    raise ValueError(f"Stock insuficiente en tienda para {p.nombre}. Disponible: {disp}.")
                subtotal = float(precio) * qty
                detalle_entregados.append((p, qty, float(precio), subtotal))
                total_entregado += subtotal

            saldo_actual = _saldo_favor_actual(cliente.id) if cliente else 0.0
            saldo_usado = min(saldo_actual, usar_saldo)
            neto = float(total_entregado - total_devuelto - saldo_usado)
            if neto > 0 and monto_pagado + 1e-6 < neto:
                raise ValueError(f"Faltan ${neto - monto_pagado:,.0f} por pagar para cerrar el cambio.")
            if neto <= 0:
                if monto_pagado > 0:
                    raise ValueError("No corresponde monto pagado cuando hay saldo a favor/compensación.")
                saldo_resultante = abs(neto) - monto_devuelto
                if saldo_resultante > 0 and not cliente:
                    raise ValueError("Para dejar saldo a favor debe seleccionar cliente.")
                if saldo_resultante < -1e-6:
                    raise ValueError("Monto devuelto en efectivo excede la diferencia a favor del cliente.")
            else:
                if monto_devuelto > 0:
                    raise ValueError("No corresponde devolución en efectivo cuando el neto es por pagar.")

            venta_origen_id = request.form.get('venta_origen_id', type=int)
            if venta_origen_id:
                if not Venta.query.get(venta_origen_id):
                    venta_origen_id = None

            cambio = CambioOperacion(
                cliente_id=cliente.id if cliente else None,
                caja_id=caja_activa.id,
                usuario_id=current_user.id if current_user.is_authenticated else None,
                venta_origen_id=venta_origen_id,
                total_devuelto=total_devuelto,
                total_entregado=total_entregado,
                saldo_usado=saldo_usado,
                monto_pagado=monto_pagado,
                monto_devuelto_efectivo=monto_devuelto,
                saldo_generado=max(0.0, abs(neto) - monto_devuelto) if neto <= 0 else 0.0,
                observacion=observacion or None,
            )
            db.session.add(cambio)
            db.session.flush()

            for p, qty, precio, subtotal in detalle_devueltos:
                db.session.add(CambioDetalle(
                    cambio_id=cambio.id, producto_id=p.id, tipo='DEVUELTO',
                    cantidad=qty, precio_unitario=precio, subtotal=subtotal
                ))
                if _tablas_inventario_almacen_existen():
                    _, err = ajustar_stock_almacen(p.id, aid_tienda, qty, allow_negative=False)
                    if err:
                        raise ValueError(f"{p.nombre}: {err}")
                else:
                    p.stock = int((p.stock or 0) + qty)
                _refrescar_stock_total_producto(p)
                registrar_movimiento_kardex(
                    p.id, 'ENTRADA', qty, f"Cambio #{cambio.id} (producto devuelto)",
                    usuario=current_user.nombre, id_almacen=aid_tienda,
                    referencia_tipo='cambio', referencia_id=cambio.id
                )

            for p, qty, precio, subtotal in detalle_entregados:
                db.session.add(CambioDetalle(
                    cambio_id=cambio.id, producto_id=p.id, tipo='ENTREGADO',
                    cantidad=qty, precio_unitario=precio, subtotal=subtotal
                ))
                if _tablas_inventario_almacen_existen():
                    _, err = ajustar_stock_almacen(p.id, aid_tienda, -qty, allow_negative=False)
                    if err:
                        raise ValueError(f"{p.nombre}: {err}")
                else:
                    if int(p.stock or 0) < qty:
                        raise ValueError(f"Stock insuficiente para {p.nombre}.")
                    p.stock = int((p.stock or 0) - qty)
                _refrescar_stock_total_producto(p)
                registrar_movimiento_kardex(
                    p.id, 'SALIDA', qty, f"Cambio #{cambio.id} (producto entregado)",
                    usuario=current_user.nombre, id_almacen=aid_tienda,
                    referencia_tipo='cambio', referencia_id=cambio.id
                )

            if cliente and saldo_usado > 0:
                _aplicar_mov_saldo_favor(cliente.id, cambio.id, 'DEBITO', saldo_usado, f'Uso en cambio #{cambio.id}')
            if cliente and neto <= 0:
                saldo_nuevo = max(0.0, abs(neto) - monto_devuelto)
                if saldo_nuevo > 0:
                    _aplicar_mov_saldo_favor(cliente.id, cambio.id, 'CREDITO', saldo_nuevo, f'Saldo generado cambio #{cambio.id}')

            db.session.commit()
            if neto > 0:
                flash(f"Cambio #{cambio.id} registrado. Diferencia pagada: ${monto_pagado:,.0f}.", "success")
            else:
                msg = f"Cambio #{cambio.id} registrado."
                if cliente and cambio.saldo_generado > 0:
                    msg += f" Saldo a favor generado: ${cambio.saldo_generado:,.0f}."
                elif monto_devuelto > 0:
                    msg += f" Devuelto en efectivo: ${monto_devuelto:,.0f}."
                flash(msg, "success")
            return redirect(
                url_for(
                    'caja_cambios',
                    cliente_id=cliente.id if cliente else None,
                    ultimo_cambio=cambio.id,
                )
            )
        except Exception as ex:
            db.session.rollback()
            flash(f"No se pudo registrar el cambio: {ex}", "danger")
            return redirect(url_for('caja_cambios', cliente_id=cliente.id if cliente else None))

    clientes = Cliente.query.order_by(Cliente.nombre.asc()).all()
    recientes = CambioOperacion.query.order_by(CambioOperacion.id.desc()).limit(20).all()
    saldo_actual = _saldo_favor_actual(cliente.id) if cliente else 0.0
    ultimo_cambio = request.args.get('ultimo_cambio', type=int)
    cambio_reciente = CambioOperacion.query.get(ultimo_cambio) if ultimo_cambio else None
    return render_template(
        'caja_cambios.html',
        clientes=clientes,
        cliente_sel=cliente,
        saldo_actual=saldo_actual,
        recientes=recientes,
        cambio_reciente=cambio_reciente,
    )


@app.route('/api/cambios/producto/<codigo>')
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def api_cambios_producto(codigo):
    p = _producto_por_codigo_pos(codigo)
    if not p:
        return jsonify(ok=False, mensaje='Producto no encontrado.'), 404
    precio = float(precio_efectivo_pos_producto(p) or 0)
    stock_t = stock_disponible_venta_tienda(p)
    return jsonify(
        ok=True,
        producto={
            'id': p.id,
            'codigo_barra': (p.codigo_barra or '').strip(),
            'codigo_interno': (p.codigo_interno or '').strip(),
            'nombre': p.nombre,
            'precio': precio,
            'stock_tienda': int(stock_t if stock_t is not None else (p.stock or 0)),
        }
    )


def _devoluciones_previas_por_producto(venta_id):
    rows = (
        db.session.query(CambioDetalle.producto_id, db.func.coalesce(db.func.sum(CambioDetalle.cantidad), 0))
        .join(CambioOperacion, CambioOperacion.id == CambioDetalle.cambio_id)
        .filter(
            CambioOperacion.venta_origen_id == venta_id,
            CambioDetalle.tipo == 'DEVUELTO',
        )
        .group_by(CambioDetalle.producto_id)
        .all()
    )
    return {int(pid): int(qty or 0) for pid, qty in rows}


def _venta_a_dict_para_cambio(v):
    devueltas_restantes = _devoluciones_previas_por_producto(v.id)
    detalles = []
    for d in (v.detalles or []):
        prod = d.producto
        producto_id = int(d.id_producto)
        cantidad_vendida = int(d.cantidad or 0)
        ya_devuelta_disponible = int(devueltas_restantes.get(producto_id, 0) or 0)
        ya_devuelta_linea = min(cantidad_vendida, ya_devuelta_disponible)
        cantidad_pendiente = max(0, cantidad_vendida - ya_devuelta_linea)
        devueltas_restantes[producto_id] = max(0, ya_devuelta_disponible - ya_devuelta_linea)
        if cantidad_pendiente <= 0:
            continue
        detalles.append({
            'producto_id': producto_id,
            'codigo_barra': ((prod.codigo_barra or '').strip() if prod else ''),
            'codigo_interno': ((prod.codigo_interno or '').strip() if prod else ''),
            'nombre': (prod.nombre if prod else f"Producto #{producto_id}"),
            'cantidad': cantidad_pendiente,
            'cantidad_original': cantidad_vendida,
            'cantidad_ya_devuelta': ya_devuelta_linea,
            'precio_unitario': float(d.precio_unitario or 0),
            'descuento': float(d.descuento or 0),
            'subtotal': float(d.subtotal or 0),
        })
    cambios_previos = CambioOperacion.query.filter_by(venta_origen_id=v.id).count()
    return {
        'id': v.id,
        'fecha': v.fecha.strftime('%d/%m/%Y %H:%M') if v.fecha else None,
        'estado': v.estado or '',
        'monto_total': float(v.monto_total or 0),
        'cliente_id': v.cliente_id,
        'cliente_nombre': v.cliente.nombre if v.cliente else None,
        'cliente_rut': (v.cliente.rut if v.cliente else None),
        'tiene_devoluciones_previas': cambios_previos > 0,
        'devolucion_completa': cambios_previos > 0 and not detalles,
        'detalles': detalles,
    }


def _parse_folio_vale(q):
    """Acepta 'VL000123', 'VL123', '123' y devuelve int o None."""
    if not q:
        return None
    s = q.strip().upper()
    if s.startswith('VL'):
        s = s[2:]
    s = s.lstrip('0') or '0'
    try:
        return int(s)
    except ValueError:
        return None


@app.route('/api/cambios/buscar_venta')
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def api_cambios_buscar_venta():
    """Busca venta original para precargar líneas en cambio.

    Reglas de búsqueda:
      - Si el texto contiene letras/dígito verificador típico de RUT, busca cliente y devuelve sus últimas ventas.
      - Si el texto es numérico (con o sin prefijo 'VL'), busca por folio de venta.
      - Si no encuentra nada, retorna ok=False con mensaje claro.
    """
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify(ok=False, mensaje='Indique folio o RUT a buscar.'), 400

    qup = q.upper()

    if qup.startswith('VL'):
        folio = _parse_folio_vale(q)
        if folio is None:
            return jsonify(ok=False, mensaje=f'Folio inválido: {q}'), 400
        v = Venta.query.get(folio)
        if not v:
            return jsonify(ok=False, mensaje=f'No existe vale con folio #{folio}.'), 404
        return jsonify(ok=True, modo='venta', venta=_venta_a_dict_para_cambio(v))

    if q.isdigit():
        folio = int(q.lstrip('0') or '0')
        if folio > 0:
            v = Venta.query.get(folio)
            if v:
                return jsonify(ok=True, modo='venta', venta=_venta_a_dict_para_cambio(v))

    rut_limpio = q.replace('.', '').replace('-', '').replace(' ', '').upper()
    if validar_rut(q):
        rut_db_normalizado = q.replace('.', '').upper()
        if '-' not in rut_db_normalizado and len(rut_db_normalizado) >= 2:
            rut_db_normalizado = rut_db_normalizado[:-1] + '-' + rut_db_normalizado[-1]
        cliente = (
            Cliente.query.filter(
                or_(
                    Cliente.rut == q,
                    Cliente.rut == rut_db_normalizado,
                    db.func.replace(db.func.replace(Cliente.rut, '.', ''), '-', '') == rut_limpio,
                )
            ).first()
        )
        if not cliente:
            return jsonify(ok=False, mensaje=f'No se encontró cliente con RUT {q}.'), 404
        ventas = (
            Venta.query.filter(Venta.cliente_id == cliente.id)
            .order_by(Venta.fecha.desc(), Venta.id.desc())
            .limit(15)
            .all()
        )
        return jsonify(
            ok=True,
            modo='lista',
            cliente={
                'id': cliente.id,
                'nombre': cliente.nombre,
                'rut': cliente.rut or '',
            },
            ventas=[
                {
                    'id': v.id,
                    'fecha': v.fecha.strftime('%d/%m/%Y %H:%M') if v.fecha else '',
                    'estado': v.estado or '',
                    'monto_total': float(v.monto_total or 0),
                }
                for v in ventas
            ],
        )

    return jsonify(ok=False, mensaje='Sin resultados. Pruebe folio (ej. 1234 o VL001234) o RUT del cliente.'), 404


@app.route('/api/cambios/venta/<int:id>')
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def api_cambios_venta_detalle(id):
    v = Venta.query.get_or_404(id)
    return jsonify(ok=True, venta=_venta_a_dict_para_cambio(v))


@app.route('/caja/cambios/<int:id>/ticket')
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def ticket_cambio(id):
    cambio = CambioOperacion.query.get_or_404(id)
    devueltos = [d for d in (cambio.detalles or []) if (d.tipo or '').upper() == 'DEVUELTO']
    entregados = [d for d in (cambio.detalles or []) if (d.tipo or '').upper() == 'ENTREGADO']
    neto = float((cambio.total_entregado or 0) - (cambio.total_devuelto or 0) - (cambio.saldo_usado or 0))
    return render_template(
        'ticket_cambio.html',
        cambio=cambio,
        devueltos=devueltos,
        entregados=entregados,
        neto=neto,
        auto_print=(request.args.get('auto_print') == '1'),
    )


@app.route('/caja/cambios/historial')
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def caja_cambios_historial():
    if not _asegurar_tablas_cambios():
        flash("No se pudo preparar tablas de cambios/saldos. Revise permisos de BD.", "danger")
        return redirect(url_for('caja_pendientes'))

    q_cliente_id = request.args.get('cliente_id', type=int)
    q_vendedor = (request.args.get('vendedor') or '').strip()
    q_desde = (request.args.get('desde') or '').strip()
    q_hasta = (request.args.get('hasta') or '').strip()

    q = CambioOperacion.query

    if q_cliente_id:
        q = q.filter(CambioOperacion.cliente_id == q_cliente_id)

    if q_vendedor:
        like_v = f"%{q_vendedor}%"
        q = q.outerjoin(Usuario, CambioOperacion.usuario_id == Usuario.id).filter(
            or_(Usuario.nombre.like(like_v), Usuario.correo.like(like_v))
        )

    try:
        if q_desde:
            desde_dt = datetime.strptime(q_desde, '%Y-%m-%d')
            q = q.filter(CambioOperacion.fecha >= desde_dt)
    except ValueError:
        flash("La fecha 'desde' no es válida.", "warning")

    try:
        if q_hasta:
            hasta_dt = datetime.strptime(q_hasta, '%Y-%m-%d') + timedelta(days=1)
            q = q.filter(CambioOperacion.fecha < hasta_dt)
    except ValueError:
        flash("La fecha 'hasta' no es válida.", "warning")

    limite = 500
    cambios = q.order_by(CambioOperacion.fecha.desc(), CambioOperacion.id.desc()).limit(limite).all()

    total_cambios = len(cambios)
    sum_devuelto = sum(float(c.total_devuelto or 0) for c in cambios)
    sum_entregado = sum(float(c.total_entregado or 0) for c in cambios)
    sum_saldo_usado = sum(float(c.saldo_usado or 0) for c in cambios)
    sum_pagado = sum(float(c.monto_pagado or 0) for c in cambios)
    sum_devuelto_efectivo = sum(float(c.monto_devuelto_efectivo or 0) for c in cambios)
    sum_saldo_generado = sum(float(c.saldo_generado or 0) for c in cambios)
    neto_rango = sum_entregado - sum_devuelto - sum_saldo_usado

    clientes = Cliente.query.order_by(Cliente.nombre.asc()).all()

    return render_template(
        'caja_cambios_historial.html',
        cambios=cambios,
        total_cambios=total_cambios,
        sum_devuelto=sum_devuelto,
        sum_entregado=sum_entregado,
        sum_saldo_usado=sum_saldo_usado,
        sum_pagado=sum_pagado,
        sum_devuelto_efectivo=sum_devuelto_efectivo,
        sum_saldo_generado=sum_saldo_generado,
        neto_rango=neto_rango,
        clientes=clientes,
        q_cliente_id=q_cliente_id,
        q_vendedor=q_vendedor,
        q_desde=q_desde,
        q_hasta=q_hasta,
        limite=limite,
    )


@app.route('/caja/saldos-favor')
@login_required
@permisos_required('caja_cobrar_vale', 'gestionar_usuarios')
def caja_saldos_favor():
    """Clientes con saldo a favor vigente por devoluciones/cambios."""
    if not _asegurar_tablas_cambios():
        flash("No se pudo preparar tablas de saldos a favor. Revise permisos de BD.", "danger")
        return redirect(url_for('caja_pendientes'))

    q = (request.args.get('q') or '').strip()
    consulta = (
        ClienteSaldoFavor.query
        .join(Cliente, Cliente.id == ClienteSaldoFavor.cliente_id)
        .filter(ClienteSaldoFavor.saldo > 0)
    )
    if q:
        like_q = f"%{q}%"
        consulta = consulta.filter(or_(Cliente.nombre.like(like_q), Cliente.rut.like(like_q)))

    saldos = (
        consulta
        .order_by(ClienteSaldoFavor.saldo.desc(), Cliente.nombre.asc())
        .limit(500)
        .all()
    )
    total_saldo = sum(float(s.saldo or 0) for s in saldos)
    clientes_con_saldo = len(saldos)
    ultimos_movs = {}
    if saldos:
        ids = [s.cliente_id for s in saldos]
        movimientos = (
            MovimientoSaldoFavor.query
            .filter(MovimientoSaldoFavor.cliente_id.in_(ids))
            .order_by(MovimientoSaldoFavor.fecha.desc(), MovimientoSaldoFavor.id.desc())
            .all()
        )
        for mov in movimientos:
            ultimos_movs.setdefault(mov.cliente_id, mov)

    return render_template(
        'caja_saldos_favor.html',
        saldos=saldos,
        ultimos_movs=ultimos_movs,
        total_saldo=total_saldo,
        clientes_con_saldo=clientes_con_saldo,
        busqueda=q,
        limite=500,
    )


@app.route('/caja/vales/<int:id>/anular', methods=['POST'])
@login_required
@caja_requerida
@permisos_required('anular_vale_caja')
def anular_vale_caja(id):
    """Vale emitido y no cobrado: cliente no retorna. No descuenta stock (aún no pasó por cobro)."""
    venta = Venta.query.get_or_404(id)
    if venta.estado != 'Pendiente' or venta.metodo_pago is not None:
        flash('Solo se pueden anular vales pendientes de cobro (sin método de pago).', 'warning')
        return redirect(url_for('caja_pendientes'))
    motivo = (request.form.get('motivo') or '').strip()[:500]
    venta.estado = 'Anulada'
    venta.motivo_anulacion = motivo or None
    venta.fecha_anulacion = datetime.now()
    venta.usuario_anulacion = (current_user.nombre or '')[:80] if current_user.is_authenticated else None
    try:
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        err = str(ex).lower()
        if 'unknown column' in err or 'motivo_anulacion' in err:
            flash(
                'Ejecutá en MySQL la migración sql/2026_05_04_ventas_anulacion_vale.sql y vuelve a intentar.',
                'danger',
            )
        else:
            flash(f'No se pudo anular el vale: {ex}', 'danger')
        return redirect(url_for('caja_pendientes'))
    flash(f'Vale #{venta.id} anulado. No descontó stock (no estaba cobrado).', 'success')
    return redirect(url_for('caja_pendientes'))


@app.route('/procesar_cobro_caja/<int:id>', methods=['POST'])
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def procesar_cobro_caja(id):
    db.session.rollback()
    venta = Venta.query.options(joinedload(Venta.detalles)).get_or_404(id)
    caja_activa = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    metodo = request.form.get('metodo_pago')
    tipo_doc = request.form.get('tipo_documento', 'Boleta')
    if venta.estado == 'Anulada':
        flash(f"El vale #{venta.id} está anulado y no puede cobrarse.", "warning")
        return redirect(url_for('caja_pendientes'))
    if venta.estado != 'Pendiente':
        flash(f"El documento #{venta.id} no está en cola de cobro.", "warning")
        return redirect(url_for('caja_pendientes'))
    if venta.metodo_pago is not None:
        flash(f"El vale #{venta.id} ya fue procesado anteriormente.", "info")
        return redirect(url_for('caja_pendientes'))
    faltantes_stock = _venta_validar_stock_tienda(venta)
    if faltantes_stock:
        flash(
            "No se puede cobrar el vale por stock insuficiente en tienda: "
            + "; ".join(faltantes_stock[:3]),
            "warning",
        )
        return redirect(url_for('caja_pendientes'))

    try:
        monto_recibido = float(request.form.get('monto_recibido') or 0)
        usar_saldo_favor = float(request.form.get('usar_saldo_favor') or 0)
    except (TypeError, ValueError):
        flash("Monto recibido inválido.", "warning")
        return redirect(url_for('caja_pendientes'))
    if monto_recibido < 0 or usar_saldo_favor < 0:
        flash("Los montos no pueden ser negativos.", "warning")
        return redirect(url_for('caja_pendientes'))
    saldo_cliente_actual = _saldo_favor_actual(venta.cliente_id) if venta.cliente_id else 0.0
    saldo_favor_usado = min(float(usar_saldo_favor or 0), saldo_cliente_actual, float(venta.monto_total or 0))
    total_a_pagar = max(0.0, float(venta.monto_total or 0) - saldo_favor_usado)

    try:
        # Preparamos y validamos todas las líneas antes de mutar venta/stock.
        lineas_stock = []
        for d in list(venta.detalles or []):
            producto = Producto.query.get(d.id_producto)
            if not producto:
                raise ValueError(f"Producto no encontrado en línea #{d.id}.")
            factor_venta_stock = _factor_venta_a_stock(producto)
            consumo_stock = int(round((d.cantidad or 0) * factor_venta_stock))
            if consumo_stock <= 0:
                raise ValueError(f"Conversión inválida para {producto.nombre}.")
            disp = stock_disponible_venta_tienda(producto)
            if disp < consumo_stock:
                raise ValueError(f"Stock insuficiente para {producto.nombre}.")
            lineas_stock.append({
                'detalle_id': d.id,
                'producto_id': producto.id,
                'cantidad_venta': d.cantidad or 0,
                'consumo_stock': consumo_stock,
            })

        # Partimos la transacción real desde un estado limpio. Esto evita que
        # un SELECT/validación previa deje Postgres en InFailedSqlTransaction.
        db.session.rollback()
        venta = Venta.query.options(joinedload(Venta.detalles)).get_or_404(id)
        caja_activa = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()

        venta.metodo_pago = metodo
        venta.tipo_documento = tipo_doc
        venta.caja_id = caja_activa.id
        venta.fecha = datetime.now()
        venta.desglosar_iva()

        if metodo == "Credito":
            venta.estado = "Pendiente"
            venta.monto_recibido = 0
            venta.vuelto = 0
            venta.saldo_favor_usado = 0
            if venta.cliente:
                venta.cliente.saldo_deudor = (venta.cliente.saldo_deudor or 0) + venta.monto_total
        else:
            if saldo_favor_usado > 0:
                if not venta.cliente_id:
                    flash("Para usar saldo a favor el vale debe tener cliente identificado.", "warning")
                    return redirect(url_for('caja_pendientes'))
                saldo_cliente_actual = _saldo_favor_actual(venta.cliente_id)
                saldo_favor_usado = min(saldo_favor_usado, saldo_cliente_actual, float(venta.monto_total or 0))
                total_a_pagar = max(0.0, float(venta.monto_total or 0) - saldo_favor_usado)
            if monto_recibido < total_a_pagar:
                flash("El monto recibido no puede ser menor al total pendiente después de saldo a favor.", "warning")
                return redirect(url_for('caja_pendientes'))
            venta.estado = "Pagado"
            venta.monto_recibido = monto_recibido
            venta.vuelto = monto_recibido - total_a_pagar
            venta.saldo_favor_usado = saldo_favor_usado
            if saldo_favor_usado > 0:
                _aplicar_mov_saldo_favor(
                    venta.cliente_id,
                    None,
                    'DEBITO',
                    saldo_favor_usado,
                    f'Uso en venta #{venta.id}',
                )

        for linea in lineas_stock:
            producto = Producto.query.get(linea['producto_id'])
            if not producto:
                raise ValueError(f"Producto no encontrado en línea #{linea['detalle_id']}.")
            consumo_stock = linea['consumo_stock']
            err_st = descontar_stock_venta_tienda(producto, consumo_stock)
            if err_st:
                raise ValueError(f"{producto.nombre}: {err_st}")
            registrar_movimiento_kardex(
                producto.id,
                'SALIDA',
                consumo_stock,
                f"Cobro vale/venta #{venta.id} ({metodo})"
                f" ({linea['cantidad_venta']} {producto.unidad_venta_final} -> {consumo_stock} stock)",
                usuario=current_user.nombre,
                id_almacen=id_almacen_tienda() or 1,
                referencia_tipo='venta',
                referencia_id=venta.id,
                stock_saldo=None,
            )

        db.session.commit()
        
        if metodo == "Credito":
            flash(f"Vale #{venta.id} registrado a crédito para {venta.cliente.nombre if venta.cliente else 'cliente'}.", "success")
            return redirect(url_for('caja_pendientes', ultima_venta=venta.id))
        else:
            flash(f"¡Venta #{venta.id} finalizada! Vuelto: ${venta.vuelto:,.0f}", "success")
            return redirect(
                url_for(
                    'ver_ticket_cobro',
                    id=venta.id,
                    vuelto=f"{float(venta.vuelto or 0):.2f}",
                    auto_print='1',
                )
            )

    except Exception as e: # <--- Ahora este except sí tiene su try
        db.session.rollback()
        flash(f"Error crítico al procesar pago: {str(e)}", "danger")
        return redirect(url_for('caja_pendientes'))


@app.route('/caja/vale_retiro/<int:id>')
@login_required
@caja_requerida
@permisos_required('caja_cobrar_vale')
def ver_ticket_cobro(id):
    venta = Venta.query.get_or_404(id)
    if venta.estado != 'Pagado':
        flash("El vale de retiro solo está disponible para ventas pagadas.", "warning")
        return redirect(url_for('caja_pendientes'))
    return render_template(
        'ticket_cobro.html',
        venta=venta,
        detalles=venta.detalles or [],
        cajero_nombre=(current_user.nombre or '').strip() if current_user.is_authenticated else '',
        auto_print=(request.args.get('auto_print') == '1'),
        vuelto=float((request.args.get('vuelto') or venta.vuelto or 0)),
    )

# busca productos por código o nombre para agregar en venta........................................
@app.route('/buscar_producto')
@login_required
@caja_requerida
def buscar_producto():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({"results": []})
    if not _asegurar_columnas_productos_legacy():
        return jsonify({"results": []})

    raw_sv = request.args.get('solo_vendibles')
    if raw_sv is not None and str(raw_sv).strip() != '':
        solo_vendibles = str(raw_sv).strip().lower() in ('1', 'true', 'si', 'yes', 'on')
    else:
        # POS envía origen=pos; si falta el flag (JS viejo, proxy), filtrar por defecto
        solo_vendibles = request.args.get('origen', '').strip().lower() == 'pos'

    like = f"%{q}%"
    fetch_limit = 100 if solo_vendibles else 20
    try:
        insp = sa_inspect(db.engine)
        cols = {c['name'] for c in insp.get_columns('productos')}
        if not {'id', 'nombre'}.issubset(cols):
            return jsonify({"results": []})

        campos = ['id', 'nombre']
        for c in ('codigo_barra', 'codigo_interno', 'codigo_chilemat', 'precio_venta', 'precio_mayoreo', 'stock'):
            if c in cols:
                campos.append(c)

        filtros = ["LOWER(nombre) LIKE LOWER(:like)"]
        for c in ('codigo_barra', 'codigo_interno', 'codigo_chilemat'):
            if c in cols:
                filtros.append(f"LOWER({c}) LIKE LOWER(:like)")

        where_parts = [f"({' OR '.join(filtros)})"]
        if 'activo' in cols:
            where_parts.insert(0, "(activo IS NULL OR activo = TRUE)")
        if solo_vendibles:
            precio_exprs = []
            if 'precio_venta' in cols:
                precio_exprs.append("COALESCE(precio_venta, 0)")
            if 'precio_mayoreo' in cols:
                precio_exprs.append("COALESCE(precio_mayoreo, 0)")
            if precio_exprs:
                where_parts.append(f"(({') + ('.join(precio_exprs)}) > 0)")
            if 'stock' in cols:
                where_parts.append("COALESCE(stock, 0) > 0")

        sql = (
            f"SELECT {', '.join(campos)} "
            f"FROM productos "
            f"WHERE {' AND '.join(where_parts)} "
            f"ORDER BY nombre ASC "
            f"LIMIT :lim"
        )
        productos = db.session.execute(text(sql), {"like": like, "lim": fetch_limit}).mappings().all()
    except Exception as ex:
        db.session.rollback()
        app.logger.exception("buscar_producto falló; devolviendo lista vacía para no romper Select2: %s", ex)
        return jsonify({"results": []})

    results = []
    for p in productos:
        codigo = (
            (p.get('codigo_barra') or '').strip()
            or (p.get('codigo_interno') or '').strip()
            or (p.get('codigo_chilemat') or '').strip()
        )
        if not codigo:
            continue
        results.append({
            "id": codigo,
            "producto_id": int(p.get('id')),
            "text": f"{(p.get('nombre') or '').strip()} ({codigo})",
        })
        if len(results) >= 20:
            break

    return jsonify({"results": results})

# proceso de apertura de caja desde pantalla de caja........................................................................

@app.route('/abrir_caja', methods=['GET', 'POST'])
@login_required
@permisos_required('caja_abrir')
def abrir_caja():
    caja_activa = obtener_caja_activa()
    if caja_activa:
        flash(f"Ya existe una caja abierta (N°{caja_activa.id}). Debe cerrarla antes de abrir otra.", "info")
        return redirect(url_for('punto_venta'))

    if request.method == 'POST':
        monto_inicial = float(request.form['monto_inicial'])
        caja = Caja(monto_inicial=monto_inicial, usuario_apertura="Admin")
        db.session.add(caja)
        db.session.commit()
        flash("Caja abierta con monto inicial: ${}".format(monto_inicial))
        return redirect(url_for('punto_venta'))
    return render_template('abrir_caja.html')

# proceso de registrar movimientos de caja desde pantalla de caja........................................................................

@app.route('/movimiento_caja', methods=['GET', 'POST'])
@login_required
@permisos_required('caja_movimientos')
def movimiento_caja():
    if request.method == 'POST':
        q_redirect = {}
        if request.form.get('filtro_q_tipo'):
            q_redirect['tipo'] = request.form.get('filtro_q_tipo')
        if request.form.get('filtro_q_hoy'):
            q_redirect['hoy'] = request.form.get('filtro_q_hoy')
    else:
        q_redirect = request.args.to_dict(flat=True)

    if request.method == 'POST':
        caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
        if not caja:
            flash("No hay caja abierta para registrar movimientos.", "warning")
            return redirect(url_for('abrir_caja'))
        tipo = request.form['tipo']
        concepto = request.form['concepto']
        responsable = (request.form.get('responsable_retiro') or '').strip()
        if tipo == "Egreso":
            if not responsable:
                flash("Debe indicar el responsable del retiro.", "warning")
                return redirect(url_for('movimiento_caja', **q_redirect))
        movimiento = MovimientoCaja(
            caja_id=caja.id,
            tipo=tipo,
            concepto=concepto,
            monto=float(request.form['monto']),
            responsable_retiro=responsable if tipo == "Egreso" else None,
            usuario_registro=current_user.nombre if current_user.is_authenticated else None
        )
        db.session.add(movimiento)
        db.session.commit()
        flash("Movimiento registrado correctamente", "success")
        return redirect(url_for('movimiento_caja', **q_redirect))

    # Si es GET, mostrar la lista premium con filtros opcionales
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    movimientos = caja.movimientos if caja else []
    filtro_tipo = request.args.get('tipo', '').strip()
    solo_hoy = request.args.get('hoy', '0') == '1'

    if filtro_tipo in ('Ingreso', 'Egreso'):
        movimientos = [m for m in movimientos if m.tipo == filtro_tipo]
    if solo_hoy:
        fecha_hoy = datetime.now().date()
        movimientos = [m for m in movimientos if m.fecha and m.fecha.date() == fecha_hoy]

    # Campos de presentación (compatibilidad con registros antiguos en concepto)
    for m in movimientos:
        resp = (getattr(m, "responsable_retiro", None) or "").strip()
        conc = m.concepto or ""
        if not resp and m.tipo == "Egreso" and conc.startswith("[RESP:"):
            cierre = conc.find("]")
            if cierre != -1:
                resp = conc[6:cierre].strip() or "No definido"
                conc = conc[cierre + 1:].strip()
            else:
                resp = "No definido"
        m.responsable = resp if resp else "-"
        m.concepto_limpio = conc
        m.registrado_por = (getattr(m, "usuario_registro", None) or "").strip() or "-"

    movimientos = sorted(movimientos, key=lambda m: m.fecha or datetime.min, reverse=True)
    return render_template(
        'movimiento_caja.html',
        movimientos=movimientos,
        filtro_tipo=filtro_tipo,
        solo_hoy=solo_hoy,
        q_redirect=q_redirect
    )

# mostrar movimientos de caja...............................................................
@app.route('/cerrar_caja', methods=['GET', 'POST'])
@login_required
@permisos_required('caja_cerrar')
def cerrar_caja():
    # 1. Buscamos la caja activa
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    
    if not caja:
        flash("No hay ninguna caja abierta para cerrar.", "info")
        return redirect(url_for('index'))

    vales_pendientes_cierre = (
        Venta.query.filter(
            Venta.caja_id == caja.id,
            Venta.estado == "Pendiente",
            or_(Venta.metodo_pago.is_(None), Venta.metodo_pago == ""),
        )
        .order_by(Venta.fecha.asc(), Venta.id.asc())
        .all()
    )
    tickets_abiertos_cierre = (
        Venta.query.filter(
            Venta.caja_id == caja.id,
            Venta.estado == "Abierta",
        )
        .order_by(Venta.fecha.asc(), Venta.id.asc())
        .all()
    )

    # 2. Cálculos de VENTAS del turno
    # Defensa ante datos demo/importados: consideramos solo movimientos desde la apertura.
    apertura_turno = caja.fecha_apertura or datetime.min
    ahora_turno = datetime.now()
    ventas = (
        Venta.query.filter(
            Venta.caja_id == caja.id,
            or_(Venta.fecha.is_(None), and_(Venta.fecha >= apertura_turno, Venta.fecha <= ahora_turno)),
        )
        .all()
    )

    def _metodo_pago(v):
        return (v.metodo_pago or "").strip()

    def _monto_cobrado_por_medio(v):
        return max(0.0, float(v.monto_total or 0) - float(getattr(v, 'saldo_favor_usado', 0) or 0))

    total_efectivo = sum(_monto_cobrado_por_medio(v) for v in ventas if _metodo_pago(v) == "Efectivo") or 0
    total_debito = sum(_monto_cobrado_por_medio(v) for v in ventas if _metodo_pago(v) == "Debito") or 0
    total_transferencia = sum(_monto_cobrado_por_medio(v) for v in ventas if _metodo_pago(v) == "Transferencia") or 0
    total_fiado = sum(v.monto_total for v in ventas if _metodo_pago(v).lower() == "credito") or 0

    ventas_turno = [v for v in ventas if v.estado != "Abierta"]
    ventas_turno.sort(key=lambda x: x.fecha or datetime.min, reverse=True)
    
    # 3. Cálculos de ABONOS (Dinero de deudas cobrado hoy)
    # Importante: Esto suma dinero real a la caja
    abonos_hoy = (
        AbonoCredito.query.filter(
            AbonoCredito.caja_id == caja.id,
            or_(AbonoCredito.fecha.is_(None), and_(AbonoCredito.fecha >= apertura_turno, AbonoCredito.fecha <= ahora_turno)),
        )
        .all()
    )
    total_abonos_efectivo = sum(a.monto_abono for a in abonos_hoy if a.metodo_pago == "Efectivo") or 0
    total_abonos_otros = sum(a.monto_abono for a in abonos_hoy if a.metodo_pago != "Efectivo") or 0

    # Cambios/devoluciones del turno: solo el efectivo pagado/devuelto afecta gaveta.
    cambios_turno = (
        CambioOperacion.query.filter(
            CambioOperacion.caja_id == caja.id,
            or_(CambioOperacion.fecha.is_(None), and_(CambioOperacion.fecha >= apertura_turno, CambioOperacion.fecha <= ahora_turno)),
        )
        .order_by(CambioOperacion.fecha.desc())
        .all()
    )
    cambios_efectivo_recibido = sum(float(c.monto_pagado or 0) for c in cambios_turno) or 0
    cambios_efectivo_devuelto = sum(float(c.monto_devuelto_efectivo or 0) for c in cambios_turno) or 0
    cambios_saldo_generado = sum(float(c.saldo_generado or 0) for c in cambios_turno) or 0
    cambios_saldo_usado = sum(float(c.saldo_usado or 0) for c in cambios_turno) or 0
    
    # 4. Movimientos manuales de Caja (Ingresos/Egresos)
    ingresos_manuales = sum(m.monto for m in caja.movimientos if m.tipo == "Ingreso") or 0
    egresos = sum(m.monto for m in caja.movimientos if m.tipo == "Egreso") or 0
    
    # 5. MONTO TEÓRICO EN GAVETA (Lo que Ana debe entregar en billetes/monedas)
    # Inicial + Ventas Efec + Abonos Efec + pagos por cambios + Ingresos Manuales - devoluciones efectivo - Gastos
    monto_teorico = (
        caja.monto_inicial
        + total_efectivo
        + total_abonos_efectivo
        + cambios_efectivo_recibido
        + ingresos_manuales
    ) - cambios_efectivo_devuelto - egresos
    
    # 6. GRAN TOTAL DE MOVIMIENTOS (Productividad total)
    gran_total_dia = total_efectivo + total_debito + total_transferencia + total_fiado + total_abonos_efectivo + total_abonos_otros

    umbral_diferencia = float((os.getenv('CIERRE_DIFERENCIA_UMBRAL') or '2000').strip() or '2000')

    if request.method == 'POST':
        if vales_pendientes_cierre or tickets_abiertos_cierre:
            total_bloqueo = len(vales_pendientes_cierre) + len(tickets_abiertos_cierre)
            flash(
                f"No se puede cerrar caja: hay {total_bloqueo} documento(s) en vuelo "
                f"({len(vales_pendientes_cierre)} pendiente(s) sin método y {len(tickets_abiertos_cierre)} abierto(s)). "
                "Debes resolverlos antes de cerrar.",
                "warning",
            )
            return redirect(url_for('caja_pendientes'))
        monto_contado_raw = (request.form.get('monto_contado') or '').strip()
        if not monto_contado_raw:
            flash("Debe ingresar el efectivo contado para realizar la cuadratura.", "warning")
            return redirect(url_for('cerrar_caja'))
        try:
            monto_contado = float(monto_contado_raw.replace(',', '.'))
        except ValueError:
            flash("El efectivo contado ingresado no es válido.", "danger")
            return redirect(url_for('cerrar_caja'))
        diferencia_cuadratura = monto_contado - monto_teorico
        observacion_cierre = (request.form.get('observacion_cierre') or '').strip()
        supervisor_nombre = None

        if abs(diferencia_cuadratura) >= umbral_diferencia:
            ident_raw = (request.form.get('supervisor_identificador') or '').strip()
            pwd = request.form.get('supervisor_clave') or ''
            if not ident_raw or not pwd:
                flash(
                    f"La diferencia supera el umbral (${umbral_diferencia:,.0f}). "
                    "Debe autorizar un supervisor con credenciales.",
                    "warning",
                )
                return redirect(url_for('cerrar_caja'))
            sup, err_lookup = resolver_usuario_por_identificador_pos(ident_raw)
            if err_lookup == 'ambiguous_email_local':
                flash("Varios correos coinciden; use el correo completo del supervisor.", "warning")
                return redirect(url_for('cerrar_caja'))
            if err_lookup == 'ambiguous_nombre':
                flash("Hay más de un usuario con ese nombre; use usuario/correo único.", "warning")
                return redirect(url_for('cerrar_caja'))
            if (
                not sup
                or err_lookup == 'not_found'
                or not sup.check_password(pwd)
                or not usuario_esta_activo(sup)
                or not usuario_obj_tiene_permiso(sup, 'gestionar_usuarios')
            ):
                flash("Autorización de supervisor inválida.", "danger")
                return redirect(url_for('cerrar_caja'))
            supervisor_nombre = (sup.nombre or sup.correo or '').strip()[:80]

        # Procesamos el cierre oficial
        caja.fecha_cierre = datetime.now()
        caja.monto_final = monto_contado
        caja.monto_teorico_cierre = monto_teorico
        caja.monto_contado_cierre = monto_contado
        caja.diferencia_cierre = diferencia_cuadratura
        caja.observacion_cierre = observacion_cierre[:255] if observacion_cierre else None
        caja.supervisor_cierre = supervisor_nombre
        caja.estado = "Cerrada"
        caja.usuario_cierre = current_user.nombre
        
        try:
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            err = str(ex).lower()
            if 'unknown column' in err or 'monto_teorico_cierre' in err:
                flash(
                    'Faltan columnas de cuadratura en la tabla caja. Ejecutá la migración sql/2026_05_06_caja_cuadratura_historial.sql.',
                    'danger',
                )
            else:
                flash(f'No se pudo cerrar caja: {ex}', 'danger')
            return redirect(url_for('cerrar_caja'))
        
        # Redirigimos al ticket con toda la info
        return render_template('ticket_cierre.html', 
                               caja=caja, 
                               total_efectivo=total_efectivo,
                               total_debito=total_debito,
                               total_transferencia=total_transferencia,
                               total_abonos=(total_abonos_efectivo + total_abonos_otros),
                               total_fiado=total_fiado,
                               cambios_efectivo_recibido=cambios_efectivo_recibido,
                               cambios_efectivo_devuelto=cambios_efectivo_devuelto,
                               cambios_saldo_generado=cambios_saldo_generado,
                               cambios_saldo_usado=cambios_saldo_usado,
                               cambios_turno=cambios_turno,
                               ingresos=ingresos_manuales, 
                               egresos=egresos,
                               monto_teorico=monto_teorico,
                               monto_contado=monto_contado,
                               diferencia_cuadratura=diferencia_cuadratura,
                               umbral_diferencia=umbral_diferencia,
                               gran_total_ventas=gran_total_dia,
                               ventas_turno=ventas_turno)

    # Si es GET, mostramos la pantalla de confirmación
    return render_template('confirmar_cierre.html', 
                           caja=caja, 
                           vales_pendientes_cierre=vales_pendientes_cierre,
                           tickets_abiertos_cierre=tickets_abiertos_cierre,
                           total_efectivo=total_efectivo,
                           total_debito=total_debito,
                           total_transferencia=total_transferencia,
                           total_fiado=total_fiado,
                           cambios_efectivo_recibido=cambios_efectivo_recibido,
                           cambios_efectivo_devuelto=cambios_efectivo_devuelto,
                           cambios_saldo_generado=cambios_saldo_generado,
                           cambios_saldo_usado=cambios_saldo_usado,
                           cambios_turno=cambios_turno,
                           ingresos=ingresos_manuales,
                           egresos=egresos,
                           monto_teorico=monto_teorico,
                           umbral_diferencia=umbral_diferencia,
                           gran_total_ventas=gran_total_dia,
                           ventas_count=len(ventas),
                           ventas_turno=ventas_turno)


def _resumen_caja_cerrada(caja):
    """Recalcula el desglose operativo de una caja cerrada para auditoría/reimpresión."""
    ventas = Venta.query.filter_by(caja_id=caja.id).all()

    def _metodo_pago(v):
        return (v.metodo_pago or "").strip()

    def _monto_cobrado_por_medio(v):
        return max(0.0, float(v.monto_total or 0) - float(getattr(v, 'saldo_favor_usado', 0) or 0))

    total_efectivo = sum(_monto_cobrado_por_medio(v) for v in ventas if _metodo_pago(v) == "Efectivo") or 0
    total_debito = sum(_monto_cobrado_por_medio(v) for v in ventas if _metodo_pago(v) == "Debito") or 0
    total_transferencia = sum(_monto_cobrado_por_medio(v) for v in ventas if _metodo_pago(v) == "Transferencia") or 0
    total_fiado = sum(float(v.monto_total or 0) for v in ventas if _metodo_pago(v).lower() == "credito") or 0
    ventas_turno = [v for v in ventas if v.estado != "Abierta"]
    ventas_turno.sort(key=lambda x: x.fecha or datetime.min, reverse=True)

    abonos_hoy = AbonoCredito.query.filter_by(caja_id=caja.id).all()
    total_abonos_efectivo = sum(float(a.monto_abono or 0) for a in abonos_hoy if a.metodo_pago == "Efectivo") or 0
    total_abonos_otros = sum(float(a.monto_abono or 0) for a in abonos_hoy if a.metodo_pago != "Efectivo") or 0

    cambios_turno = CambioOperacion.query.filter_by(caja_id=caja.id).order_by(CambioOperacion.fecha.desc()).all()
    cambios_efectivo_recibido = sum(float(c.monto_pagado or 0) for c in cambios_turno) or 0
    cambios_efectivo_devuelto = sum(float(c.monto_devuelto_efectivo or 0) for c in cambios_turno) or 0
    cambios_saldo_generado = sum(float(c.saldo_generado or 0) for c in cambios_turno) or 0
    cambios_saldo_usado = sum(float(c.saldo_usado or 0) for c in cambios_turno) or 0

    ingresos = sum(float(m.monto or 0) for m in caja.movimientos if m.tipo == "Ingreso") or 0
    egresos = sum(float(m.monto or 0) for m in caja.movimientos if m.tipo == "Egreso") or 0
    monto_teorico = float(caja.monto_teorico_cierre or 0)
    if not monto_teorico:
        monto_teorico = (
            float(caja.monto_inicial or 0)
            + total_efectivo
            + total_abonos_efectivo
            + cambios_efectivo_recibido
            + ingresos
        ) - cambios_efectivo_devuelto - egresos

    return dict(
        total_efectivo=total_efectivo,
        total_debito=total_debito,
        total_transferencia=total_transferencia,
        total_abonos=total_abonos_efectivo + total_abonos_otros,
        total_fiado=total_fiado,
        cambios_efectivo_recibido=cambios_efectivo_recibido,
        cambios_efectivo_devuelto=cambios_efectivo_devuelto,
        cambios_saldo_generado=cambios_saldo_generado,
        cambios_saldo_usado=cambios_saldo_usado,
        cambios_turno=cambios_turno,
        ingresos=ingresos,
        egresos=egresos,
        monto_teorico=monto_teorico,
        monto_contado=float(caja.monto_contado_cierre or caja.monto_final or 0),
        diferencia_cuadratura=float(caja.diferencia_cierre or 0),
        gran_total_ventas=total_efectivo + total_debito + total_transferencia + total_fiado + total_abonos_efectivo + total_abonos_otros,
        ventas_turno=ventas_turno,
    )


@app.route('/caja/historial_cierres')
@login_required
@permisos_required('gestionar_usuarios')
def caja_historial_cierres():
    q_usuario = (request.args.get('usuario') or '').strip()
    q_desde = (request.args.get('desde') or '').strip()
    q_hasta = (request.args.get('hasta') or '').strip()

    q = Caja.query.filter(Caja.estado == "Cerrada").order_by(Caja.fecha_cierre.desc(), Caja.id.desc())

    if q_usuario:
        like_u = f"%{q_usuario}%"
        q = q.filter(or_(Caja.usuario_cierre.like(like_u), Caja.usuario_apertura.like(like_u)))

    desde_dt = None
    hasta_dt = None
    try:
        if q_desde:
            desde_dt = datetime.strptime(q_desde, '%Y-%m-%d')
            q = q.filter(Caja.fecha_cierre >= desde_dt)
    except ValueError:
        flash("La fecha 'desde' no es válida.", "warning")

    try:
        if q_hasta:
            hasta_dt = datetime.strptime(q_hasta, '%Y-%m-%d') + timedelta(days=1)
            q = q.filter(Caja.fecha_cierre < hasta_dt)
    except ValueError:
        flash("La fecha 'hasta' no es válida.", "warning")

    cierres = q.limit(300).all()
    total_cierres = len(cierres)
    total_diferencia = sum(float(c.diferencia_cierre or 0) for c in cierres)
    total_teorico = sum(float(c.monto_teorico_cierre or 0) for c in cierres)
    total_contado = sum(float(c.monto_contado_cierre or c.monto_final or 0) for c in cierres)
    diferencia_faltante = sum(float(c.diferencia_cierre or 0) for c in cierres if float(c.diferencia_cierre or 0) < 0)
    diferencia_sobrante = sum(float(c.diferencia_cierre or 0) for c in cierres if float(c.diferencia_cierre or 0) > 0)
    cierres_con_diferencia = sum(1 for c in cierres if abs(float(c.diferencia_cierre or 0)) >= 0.0001)
    cierres_exactos = sum(1 for c in cierres if abs(float(c.diferencia_cierre or 0)) < 0.0001)
    pct_exactitud = (cierres_exactos * 100.0 / total_cierres) if total_cierres else 0.0
    hoy = datetime.now().date()
    mes_actual_inicio = hoy.replace(day=1).strftime('%Y-%m-%d')

    return render_template(
        'caja_historial_cierres.html',
        cierres=cierres,
        total_cierres=total_cierres,
        total_diferencia=total_diferencia,
        total_teorico=total_teorico,
        total_contado=total_contado,
        diferencia_faltante=diferencia_faltante,
        diferencia_sobrante=diferencia_sobrante,
        cierres_con_diferencia=cierres_con_diferencia,
        cierres_exactos=cierres_exactos,
        pct_exactitud=pct_exactitud,
        q_usuario=q_usuario,
        q_desde=q_desde,
        q_hasta=q_hasta,
        mes_actual_inicio=mes_actual_inicio,
        hoy=hoy.strftime('%Y-%m-%d'),
    )


@app.route('/caja/historial_cierres/<int:id>/ticket')
@login_required
@permisos_required('gestionar_usuarios', 'caja_cerrar')
def ticket_cierre_historico(id):
    caja = Caja.query.get_or_404(id)
    if caja.estado != "Cerrada":
        flash("Solo se puede reimprimir el ticket de una caja cerrada.", "warning")
        return redirect(url_for('caja_historial_cierres'))
    resumen = _resumen_caja_cerrada(caja)
    return render_template(
        'ticket_cierre.html',
        caja=caja,
        umbral_diferencia=float((os.getenv('CIERRE_DIFERENCIA_UMBRAL') or '2000').strip() or '2000'),
        **resumen,
    )

# editar usuario....................................................................................

@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    roles = Rol.query.all()

    if request.method == 'POST':
        usuario.nombre = request.form['nombre']
        usuario.correo = request.form['correo']
        usuario.rol_id = request.form['rol_id']

        # Si quieres permitir cambiar contraseña:
        if request.form['password']:
            usuario.set_password(request.form['password'])

        db.session.commit()
        flash("Usuario actualizado correctamente.", "success")
        return redirect(url_for('usuarios'))

    return render_template('editar_usuario.html', usuario=usuario, roles=roles)

# eliminar usuario.................................................................................

@app.route('/eliminar_usuario/<int:id>', methods=['POST'])
@permisos_required('gestionar_usuarios')
def eliminar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash("Usuario eliminado correctamente.", "success")
    return redirect(url_for('usuarios'))

#.......consulta cliente..........................................................................

def _rut_sin_formato(rut: str) -> str:
    """RUT comparable: solo dígitos + dígito verificador (K mayúscula)."""
    return (rut or '').replace('.', '').replace('-', '').replace(' ', '').upper().strip()


def _rut_variantes_busqueda(rut_raw: str):
    """Cadenas de RUT a probar contra Cliente.rut (evita SQL REPLACE anidado que falla en algunos MySQL)."""
    key = _rut_sin_formato(rut_raw)
    out = {rut_raw.strip(), key}
    if len(key) >= 2:
        cuerpo, dv = key[:-1], key[-1]
        out.add(f"{cuerpo}-{dv}")
        if dv == 'K':
            out.add(f"{cuerpo}-k")
        if cuerpo.isdigit():
            try:
                n = int(cuerpo)
                out.add(f"{n:,}".replace(",", ".") + "-" + dv)
                if dv == 'K':
                    out.add(f"{n:,}".replace(",", ".") + "-k")
            except ValueError:
                pass
    return [x for x in out if x]


@app.route('/consultar_cliente')
@login_required
def consultar_cliente():
    """Busca cliente por RUT tolerando distinto formato guardado en BD (con/sin puntos)."""
    try:
        rut_raw = (request.args.get('rut') or '').strip()
        if not rut_raw:
            return jsonify({'existe': False, 'error': 'sin_rut'}), 400
        key = _rut_sin_formato(rut_raw)
        if len(key) < 8:
            return jsonify({'existe': False, 'error': 'rut_corto'}), 400

        variantes = _rut_variantes_busqueda(rut_raw)
        cliente = Cliente.query.filter(Cliente.rut.in_(variantes)).first()

        if cliente:
            saldo_favor = _saldo_favor_actual(cliente.id)
            return jsonify({
                'existe': True,
                'cliente': {
                    'nombre': cliente.nombre,
                    'direccion': cliente.direccion,
                    'giro': cliente.giro,
                    'telefono': cliente.telefono,
                    'correo': cliente.correo,
                    'comuna': cliente.comuna,
                    'ciudad': cliente.ciudad,
                    'saldo_favor': saldo_favor,
                },
            })
        return jsonify({'existe': False})
    except Exception as ex:
        return jsonify({'existe': False, 'error': 'servidor', 'mensaje': str(ex)}), 500

# --- PROCESO DE LOGIN Y LOGOUT ---......................................................
def _login_pagina_recuperacion():
    """HTML mínimo sin Jinja por si falla render_template o el contexto en /login."""
    cfg = _config_empresa_default()
    nombre = html.escape(str(cfg.get('nombre_comercial') or 'ERP'))
    base = (request.host_url or '').rstrip('/')
    limpiar = f'{base}/login?descartar_sesion=1'
    action = html.escape(f'{base}/login')
    limpiar_esc = html.escape(limpiar)
    body = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Acceso ERP</title>
<style>
body {{ font-family: system-ui,sans-serif; max-width: 480px; margin: 2rem auto; padding: 0 1rem; }}
a.btn {{ display: inline-block; padding: .5rem .75rem; background: #0d6efd; color: #fff; text-decoration: none;
  border-radius: 6px; margin: .5rem 0; }}
form label {{ display: block; margin-top: .75rem; }}
input {{ width: 100%; box-sizing: border-box; padding: .4rem; }}
button {{ margin-top: 1rem; padding: .6rem 1rem; width: 100%; background: #198754; color: #fff; border: 0;
  border-radius: 6px; font-weight: bold; cursor: pointer; }}
.note {{ background: #fff3cd; border: 1px solid #ffc107; padding: .75rem; border-radius: 6px; margin: 1rem 0;
  font-size: .9rem; }}
</style></head><body>
<p><strong>{nombre}</strong> — acceso al ERP</p>
<div class="note">Si esta página apareció en lugar del diseño normal, hubo un error al cargar el login.
  Prueba <a href="{limpiar_esc}">descartar sesión (enlace)</a> o una ventana privada del navegador.</div>
<form method="post" action="{action}">
<label>Correo<input type="email" name="correo" required autocomplete="username"></label>
<label>Contraseña<input type="password" name="password" required autocomplete="current-password"></label>
<button type="submit">Ingresar</button>
</form>
<p style="font-size:.85rem;color:#555">Mira la consola donde ejecutas <code>python app.py</code> para el detalle técnico.</p>
</body></html>"""
    return Response(body, mimetype='text/html; charset=utf-8')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.args.get('descartar_sesion') == '1':
        session.clear()
        flash('Sesión descartada. Intenta iniciar sesión de nuevo.', 'info')
        return redirect(url_for('login'))

    try:
        try:
            autenticado = current_user.is_authenticated
        except Exception:
            session.clear()
            autenticado = False
        if autenticado:
            return redirect(url_for('owner_mobile'))

        if request.method == 'POST':
            _seed_permisos_catalogo_si_vacio()
            correo = request.form.get('correo')
            password = request.form.get('password')
            try:
                usuario = Usuario.query.filter_by(correo=correo).first()
            except SQLAlchemyError as err:
                app.logger.error('Error de base de datos en POST /login: %s', err)
                flash(
                    'No se pudo conectar a la base de datos. Revisa que MySQL esté en marcha, que '
                    'SQLALCHEMY_DATABASE_URI en env_qa.txt o .env.qa sea correcta (host, puerto, usuario y nombre de base) '
                    'y ejecuta chequear_bd_windows.bat para validar la conexión y el esquema.',
                    'danger',
                )
                return redirect(url_for('login'))

            if usuario and usuario.check_password(password):
                if not usuario_esta_activo(usuario):
                    flash("Tu cuenta está desactivada. Contacta al administrador.", "warning")
                    return redirect(url_for('login'))
                login_user(usuario)
                if usuario_requiere_cambio_clave(usuario):
                    flash("Por seguridad, cambia tu contraseña temporal.", "warning")
                    return redirect(url_for('cambiar_password'))
                flash(f"Bienvenido al sistema, {usuario.nombre}", "success")
                next_url = (request.args.get('next') or '').strip()
                if next_url.startswith('/') and not next_url.startswith('//'):
                    return redirect(next_url)
                return redirect(url_for('owner_mobile'))
            else:
                flash("Correo o contraseña incorrectos. Intente de nuevo.", "danger")

        return render_template('login.html')
    except Exception:
        app.logger.exception('Error no controlado en /login')
        return _login_pagina_recuperacion()


@app.route('/cambiar_password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        actual = request.form.get('password_actual', '')
        nueva = request.form.get('password_nueva', '')
        confirmar = request.form.get('password_confirmar', '')

        if not current_user.check_password(actual):
            flash("La contraseña actual no es correcta.", "danger")
            return redirect(url_for('cambiar_password'))
        if len(nueva or '') < 8:
            flash("La nueva contraseña debe tener al menos 8 caracteres.", "warning")
            return redirect(url_for('cambiar_password'))
        if nueva != confirmar:
            flash("La confirmación de contraseña no coincide.", "warning")
            return redirect(url_for('cambiar_password'))

        current_user.set_password(nueva)
        if usuario_requiere_cambio_clave(current_user):
            current_user.perfil = 'ACTIVO'
        db.session.commit()
        flash("Contraseña actualizada correctamente.", "success")
        return redirect(url_for('index'))

    return render_template('cambiar_password.html')

# PROCESO DE LOGOUT.................................................................
@app.route('/logout')
def logout():
    if not current_user.is_authenticated:
        return redirect(url_for('index'))
    caja_abierta = obtener_caja_activa()
    if caja_abierta:
        return render_template('confirmar_logout_caja.html', caja=caja_abierta)
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for('index'))


@app.route('/logout/forzar', methods=['POST'])
@login_required
def logout_forzar():
    """Cierra sesión aunque la caja siga abierta (tras confirmación explícita del usuario)."""
    logout_user()
    session.clear()
    flash("Sesión cerrada. Recuerde revisar el estado de la caja si quedó abierta.", "warning")
    return redirect(url_for('index'))


# --- gestión de usuarios ---........................................................

@app.route('/usuarios', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def usuarios():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        password = request.form['password']
        rol_id = request.form['rol_id']

        nuevo_usuario = Usuario(
            nombre=nombre,
            correo=correo,
            rol_id=rol_id,
            perfil='FORZAR_CLAVE',
        )
        nuevo_usuario.set_password(password)

        db.session.add(nuevo_usuario)
        db.session.commit()

        flash("Usuario creado correctamente.", "success")
        return redirect(url_for('usuarios'))

    usuarios = Usuario.query.all()
    roles = Rol.query.all()
    return render_template('usuarios.html', usuarios=usuarios, roles=roles)


@app.route('/usuarios/<int:id>/toggle_estado', methods=['POST'])
@permisos_required('gestionar_usuarios')
def toggle_estado_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if current_user.is_authenticated and current_user.id == usuario.id:
        flash("No puedes desactivar tu propio usuario.", "warning")
        return redirect(url_for('usuarios'))

    estado_actual = (usuario.perfil or 'ACTIVO').strip().upper()
    usuario.perfil = 'INACTIVO' if estado_actual != 'INACTIVO' else 'ACTIVO'
    db.session.commit()
    flash(f"Usuario {usuario.nombre} ahora está {usuario.perfil}.", "success")
    return redirect(url_for('usuarios'))


@app.route('/admin/empresa', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def admin_empresa():
    cfg = obtener_config_empresa()
    if request.method == 'POST':
        data = {
            "nombre_comercial": request.form.get('nombre_comercial', ''),
            "razon_social": request.form.get('razon_social', ''),
            "eslogan": request.form.get('eslogan', ''),
            "telefono": request.form.get('telefono', ''),
            "correo": request.form.get('correo', ''),
            "direccion": request.form.get('direccion', ''),
            "mod_ventas": "1" if request.form.get('mod_ventas') == '1' else "0",
            "mod_caja": "1" if request.form.get('mod_caja') == '1' else "0",
            "mod_inventario": "1" if request.form.get('mod_inventario') == '1' else "0",
            "mod_bi": "1" if request.form.get('mod_bi') == '1' else "0",
            "mod_ia": "1" if request.form.get('mod_ia') == '1' else "0",
        }
        if not (data["nombre_comercial"] or '').strip():
            flash("El nombre comercial es obligatorio.", "warning")
            return redirect(url_for('admin_empresa'))
        cfg = guardar_config_empresa(data)
        flash("Datos de empresa actualizados correctamente.", "success")
    return render_template('admin_empresa.html', empresa=cfg)


@app.route('/admin/almacenes', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def admin_almacenes():
    """CRUD de almacenes (inventario multi-bodega). Códigos TIENDA/BODEGA resuelven POS y recepciones."""
    if not _tablas_inventario_almacen_existen():
        flash(
            'Las tablas de almacenes no existen. Ejecute la migración sql/2026_04_30_stock_por_almacen.sql',
            'warning',
        )
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        act = (request.form.get('action') or '').strip()
        try:
            if act == 'crear':
                codigo = (request.form.get('codigo') or '').strip().upper()[:20]
                nombre = (request.form.get('nombre') or '').strip()[:100]
                if not codigo or not nombre:
                    flash('Código y nombre son obligatorios.', 'warning')
                elif Almacen.query.filter(
                    db.func.upper(db.func.trim(Almacen.codigo)) == codigo
                ).first():
                    flash('Ya existe un almacén con ese código.', 'warning')
                else:
                    db.session.add(Almacen(codigo=codigo, nombre=nombre, activo=True))
                    db.session.commit()
                    _invalidar_cache_ids_almacen()
                    flash('Almacén creado.', 'success')
            elif act == 'editar':
                aid = request.form.get('id', type=int)
                a = Almacen.query.get(aid) if aid else None
                if not a:
                    flash('Almacén no encontrado.', 'warning')
                else:
                    codigo = (request.form.get('codigo') or '').strip().upper()[:20]
                    nombre = (request.form.get('nombre') or '').strip()[:100]
                    if not codigo or not nombre:
                        flash('Código y nombre son obligatorios.', 'warning')
                    else:
                        otra = (
                            Almacen.query.filter(
                                db.func.upper(db.func.trim(Almacen.codigo)) == codigo,
                                Almacen.id != a.id,
                            ).first()
                        )
                        if otra:
                            flash('Otro almacén ya usa ese código.', 'warning')
                        else:
                            a.codigo = codigo
                            a.nombre = nombre
                            a.activo = bool(request.form.get('activo'))
                            db.session.commit()
                            _invalidar_cache_ids_almacen()
                            flash('Almacén actualizado.', 'success')
            elif act == 'toggle':
                aid = request.form.get('id', type=int)
                a = Almacen.query.get(aid) if aid else None
                if a:
                    a.activo = not bool(a.activo)
                    db.session.commit()
                    _invalidar_cache_ids_almacen()
                    flash('Estado del almacén actualizado.', 'success')
            elif act == 'eliminar':
                aid = request.form.get('id', type=int)
                a = Almacen.query.get(aid) if aid else None
                if not a:
                    flash('Almacén no encontrado.', 'warning')
                elif StockPorAlmacen.query.filter_by(id_almacen=a.id).first():
                    flash(
                        'No se puede eliminar: hay stock por producto en este almacén. Traslade o ajuste primero.',
                        'warning',
                    )
                else:
                    hay_k = False
                    try:
                        if sa_inspect(db.engine).has_table('movimientos_inventario'):
                            hay_k = bool(
                                db.session.execute(
                                    text('SELECT 1 FROM movimientos_inventario WHERE id_almacen = :x LIMIT 1'),
                                    {'x': int(a.id)},
                                ).scalar()
                            )
                    except Exception:
                        hay_k = False
                    if hay_k:
                        flash(
                            'No se puede eliminar: existen movimientos de kardex asociados. Desactive el almacén.',
                            'warning',
                        )
                    else:
                        db.session.delete(a)
                        db.session.commit()
                        _invalidar_cache_ids_almacen()
                        flash('Almacén eliminado.', 'success')
            else:
                flash('Acción no reconocida.', 'warning')
        except Exception as ex:
            db.session.rollback()
            flash(f'Error al guardar: {ex}', 'danger')
        return redirect(url_for('admin_almacenes'))

    almacenes = Almacen.query.order_by(Almacen.codigo.asc()).all()
    conteos = {}
    for row in db.session.execute(
        text(
            'SELECT id_almacen, COUNT(*) AS n FROM stock_por_almacen '
            'WHERE cantidad <> 0 GROUP BY id_almacen'
        )
    ).fetchall():
        conteos[int(row[0])] = int(row[1])

    return render_template(
        'admin_almacenes.html',
        almacenes=almacenes,
        conteos_stock_no_cero=conteos,
        codigo_tienda_esperado=_codigo_almacen_tienda(),
        codigo_bodega_esperado=_codigo_almacen_bodega(),
        id_tienda_resuelto=id_almacen_tienda(),
        id_bodega_resuelto=id_almacen_bodega(),
    )


@app.route('/admin/clientes', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def admin_clientes():
    """Mantenedor de clientes (crédito, datos de contacto)."""
    if request.method == 'POST':
        act = (request.form.get('action') or '').strip()
        try:
            if act == 'crear':
                rut = (request.form.get('rut') or '').strip()
                nombre = (request.form.get('nombre') or '').strip()[:100]
                if not nombre or not rut:
                    flash('RUT y nombre son obligatorios.', 'warning')
                elif not validar_rut(rut):
                    flash('RUT inválido.', 'warning')
                elif Cliente.query.filter_by(rut=rut).first():
                    flash('Ya existe un cliente con ese RUT.', 'warning')
                else:
                    lim = request.form.get('limite_credito', type=float)
                    if lim is None or lim < 0:
                        lim = 500000.0
                    db.session.add(
                        Cliente(
                            rut=rut,
                            nombre=nombre,
                            giro=(request.form.get('giro') or '').strip()[:100] or None,
                            direccion=(request.form.get('direccion') or '').strip()[:200] or None,
                            telefono=(request.form.get('telefono') or '').strip()[:20] or None,
                            correo=(request.form.get('correo') or '').strip()[:100] or None,
                            comuna=(request.form.get('comuna') or '').strip()[:80] or None,
                            ciudad=(request.form.get('ciudad') or '').strip()[:80] or None,
                            limite_credito=float(lim),
                            estado_credito=(request.form.get('estado_credito') or 'Activo').strip()[:20] or 'Activo',
                            saldo_deudor=0.0,
                        )
                    )
                    db.session.commit()
                    flash('Cliente creado.', 'success')
            elif act == 'editar':
                cid = request.form.get('id', type=int)
                c = Cliente.query.get(cid) if cid else None
                if not c:
                    flash('Cliente no encontrado.', 'warning')
                else:
                    rut = (request.form.get('rut') or '').strip()
                    nombre = (request.form.get('nombre') or '').strip()[:100]
                    if not nombre or not rut:
                        flash('RUT y nombre son obligatorios.', 'warning')
                    elif not validar_rut(rut):
                        flash('RUT inválido.', 'warning')
                    elif _cliente_es_sistema_final(c) and rut != (c.rut or '').strip():
                        flash(
                            'No puede cambiarse el RUT del cliente genérico de vales; ajuste POS_RUT_CLIENTE_FINAL si necesita otro identificador.',
                            'warning',
                        )
                    else:
                        otra = Cliente.query.filter(Cliente.rut == rut, Cliente.id != c.id).first()
                        if otra:
                            flash('Otro cliente ya usa ese RUT.', 'warning')
                        else:
                            c.rut = rut
                            c.nombre = nombre
                            c.giro = (request.form.get('giro') or '').strip()[:100] or None
                            c.direccion = (request.form.get('direccion') or '').strip()[:200] or None
                            c.telefono = (request.form.get('telefono') or '').strip()[:20] or None
                            c.correo = (request.form.get('correo') or '').strip()[:100] or None
                            c.comuna = (request.form.get('comuna') or '').strip()[:80] or None
                            c.ciudad = (request.form.get('ciudad') or '').strip()[:80] or None
                            lim = request.form.get('limite_credito', type=float)
                            if lim is not None and lim >= 0:
                                c.limite_credito = float(lim)
                            ec = (request.form.get('estado_credito') or '').strip()[:20]
                            if ec in ('Activo', 'Bloqueado'):
                                c.estado_credito = ec
                            saldo = request.form.get('saldo_deudor', type=float)
                            if saldo is not None and saldo >= 0:
                                c.saldo_deudor = float(saldo)
                            db.session.commit()
                            flash('Cliente actualizado.', 'success')
            elif act == 'eliminar':
                cid = request.form.get('id', type=int)
                c = Cliente.query.get(cid) if cid else None
                if not c:
                    flash('Cliente no encontrado.', 'warning')
                elif _cliente_es_sistema_final(c):
                    flash('No se puede eliminar el cliente genérico del POS (vales sin identificación).', 'warning')
                elif Venta.query.filter_by(cliente_id=c.id).first():
                    flash('No se puede eliminar: hay ventas asociadas.', 'warning')
                elif AbonoCredito.query.filter_by(cliente_id=c.id).first():
                    flash('No se puede eliminar: hay abonos de crédito registrados.', 'warning')
                else:
                    db.session.delete(c)
                    db.session.commit()
                    flash('Cliente eliminado.', 'success')
            else:
                flash('Acción no reconocida.', 'warning')
        except Exception as ex:
            db.session.rollback()
            flash(f'Error al guardar: {ex}', 'danger')
        return redirect(url_for('admin_clientes', q=request.args.get('q') or None))

    q = (request.args.get('q') or '').strip()
    edit_id = request.args.get('edit', type=int)
    edit_cliente = Cliente.query.get(edit_id) if edit_id else None
    qc = Cliente.query
    if q:
        qc = qc.filter(
            or_(
                Cliente.nombre.contains(q),
                Cliente.rut.contains(q),
                db.func.coalesce(Cliente.correo, '').contains(q),
            )
        )
    clientes = qc.order_by(Cliente.nombre.asc()).limit(250).all()
    return render_template(
        'admin_clientes.html',
        clientes=clientes,
        busqueda=q,
        edit_cliente=edit_cliente,
        rut_cliente_final=_rut_cliente_final_normalizado(),
    )


@app.route('/admin/roles-permisos', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def admin_roles_permisos():
    """Asignación de permisos por rol (matriz simple)."""
    _seed_permisos_catalogo_si_vacio()

    if request.method == 'POST':
        act = (request.form.get('action') or '').strip()
        if act != 'guardar_rol':
            flash('Acción no reconocida.', 'warning')
            return redirect(url_for('admin_roles_permisos'))
        rid = request.form.get('rol_id', type=int)
        rol = Rol.query.get(rid) if rid else None
        if not rol:
            flash('Rol no encontrado.', 'warning')
            return redirect(url_for('admin_roles_permisos'))
        ids_raw = request.form.getlist('permiso_id')
        ids_int = []
        for x in ids_raw:
            try:
                ids_int.append(int(x))
            except (TypeError, ValueError):
                pass
        perm_gestionar = Permiso.query.filter_by(nombre='gestionar_usuarios').first()
        if (
            perm_gestionar
            and current_user.rol_id == rol.id
            and current_user.rol
            and not _rol_es_administrador_por_nombre(current_user.rol)
            and perm_gestionar.id not in ids_int
        ):
            flash(
                'No puede quitarse a su propio rol el permiso «gestionar_usuarios» mientras use ese rol.',
                'danger',
            )
            return redirect(url_for('admin_roles_permisos'))
        try:
            RolPermiso.query.filter_by(rol_id=rol.id).delete(synchronize_session=False)
            for pid in ids_int:
                if Permiso.query.get(pid):
                    db.session.add(RolPermiso(rol_id=rol.id, permiso_id=pid))
            db.session.commit()
            flash(f'Permisos actualizados para el rol «{rol.nombre}».', 'success')
            if current_user.rol_id == rol.id:
                flash('Cierre sesión y vuelva a entrar para que los cambios apliquen a su usuario.', 'info')
        except Exception as ex:
            db.session.rollback()
            flash(f'Error al guardar: {ex}', 'danger')
        return redirect(url_for('admin_roles_permisos'))

    roles = Rol.query.options(joinedload(Rol.rol_permisos).joinedload(RolPermiso.permiso)).order_by(Rol.nombre.asc()).all()
    permisos = Permiso.query.order_by(Permiso.nombre.asc()).all()
    rol_permiso_ids = {}
    for r in roles:
        rol_permiso_ids[r.id] = {rp.permiso_id for rp in (r.rol_permisos or []) if rp.permiso_id}
    return render_template(
        'admin_roles_permisos.html',
        roles=roles,
        permisos=permisos,
        rol_permiso_ids=rol_permiso_ids,
    )


@app.route('/admin/unidades', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def admin_unidades():
    if not _unidades_disponibles():
        flash("La tabla de unidades no existe. Ejecuta la migración sql/2026_05_01_unidades_medida_conversiones.sql", "warning")
        return redirect(url_for('inicio'))

    _seed_unidades_base()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'unidad':
            codigo = (request.form.get('codigo') or '').strip().upper()[:10]
            nombre = (request.form.get('nombre') or '').strip()[:50]
            tipo = (request.form.get('tipo') or 'unidad').strip()[:20]
            if not codigo or not nombre:
                flash("Código y nombre de unidad son obligatorios.", "warning")
            elif UnidadMedida.query.filter_by(codigo=codigo).first():
                flash("Ya existe una unidad con ese código.", "warning")
            else:
                db.session.add(UnidadMedida(codigo=codigo, nombre=nombre, tipo=tipo, activo=True))
                db.session.commit()
                flash("Unidad creada correctamente.", "success")
        elif action == 'conversion':
            origen_id = request.form.get('unidad_origen_id', type=int)
            destino_id = request.form.get('unidad_destino_id', type=int)
            factor = request.form.get('factor', type=float) or 0
            if not origen_id or not destino_id or factor <= 0:
                flash("Datos de conversión inválidos.", "warning")
            elif origen_id == destino_id:
                flash("La unidad origen y destino no pueden ser iguales.", "warning")
            else:
                ex = ConversionUnidad.query.filter_by(unidad_origen_id=origen_id, unidad_destino_id=destino_id).first()
                if ex:
                    ex.factor = factor
                    ex.activo = True
                    flash("Conversión actualizada.", "success")
                else:
                    db.session.add(
                        ConversionUnidad(
                            unidad_origen_id=origen_id,
                            unidad_destino_id=destino_id,
                            factor=factor,
                            activo=True,
                        )
                    )
                    flash("Conversión creada.", "success")
                db.session.commit()
        return redirect(url_for('admin_unidades'))

    unidades = UnidadMedida.query.order_by(UnidadMedida.codigo.asc()).all()
    conversiones = ConversionUnidad.query.order_by(ConversionUnidad.id.desc()).all()
    return render_template('admin_unidades.html', unidades=unidades, conversiones=conversiones)


@app.route('/admin/catalogo', methods=['GET', 'POST'])
@permisos_required('gestionar_usuarios')
def admin_catalogo():
    """Mantenedor: categoría → subcategoría 1 (nivel2) → subcategoría 2 (hoja) + asignación a productos sin FK."""
    if not _tablas_catalogo_producto_existen():
        flash(
            'Las tablas del catálogo no existen. Ejecute sql/2026_05_02_catalogo_categorias.sql y '
            'sql/2026_05_02_catalogo_subcategoria_nivel2.sql',
            'warning',
        )
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        act = (request.form.get('action') or '').strip()
        try:
            if act == 'crear_categoria':
                nombre = (request.form.get('nombre') or '').strip()[:80]
                orden = request.form.get('orden', type=int) or 0
                if not nombre:
                    flash('El nombre de la categoría es obligatorio.', 'warning')
                elif CatalogoCategoria.query.filter_by(nombre=nombre).first():
                    flash('Ya existe una categoría con ese nombre.', 'warning')
                else:
                    db.session.add(CatalogoCategoria(nombre=nombre, orden=orden, activo=True))
                    db.session.commit()
                    flash('Categoría creada.', 'success')
            elif act == 'editar_categoria':
                cid = request.form.get('id', type=int)
                cat = CatalogoCategoria.query.get(cid) if cid else None
                if not cat:
                    flash('Categoría no encontrada.', 'warning')
                else:
                    nombre = (request.form.get('nombre') or '').strip()[:80]
                    if not nombre:
                        flash('Nombre obligatorio.', 'warning')
                    else:
                        otra = CatalogoCategoria.query.filter(
                            CatalogoCategoria.nombre == nombre,
                            CatalogoCategoria.id != cat.id,
                        ).first()
                        if otra:
                            flash('Otra categoría ya usa ese nombre.', 'warning')
                        else:
                            cat.nombre = nombre
                            cat.orden = request.form.get('orden', type=int) or 0
                            cat.activo = bool(request.form.get('activo'))
                            db.session.commit()
                            flash('Categoría actualizada.', 'success')
            elif act == 'toggle_categoria':
                cid = request.form.get('id', type=int)
                cat = CatalogoCategoria.query.get(cid) if cid else None
                if cat:
                    cat.activo = not bool(cat.activo)
                    db.session.commit()
                    flash('Estado de categoría actualizado.', 'success')
            elif act == 'crear_sub':
                cid = request.form.get('categoria_id', type=int)
                n2 = (request.form.get('nivel2') or '').strip()[:80]
                leaf = (request.form.get('nombre_hoja') or '').strip()[:80]
                orden = request.form.get('orden', type=int) or 0
                cat = CatalogoCategoria.query.get(cid) if cid else None
                if not cat:
                    flash('Seleccione una categoría válida.', 'warning')
                elif not leaf:
                    flash('El nombre de la hoja (subcategoría 2) es obligatorio.', 'warning')
                else:
                    db.session.add(
                        CatalogoSubcategoria(
                            categoria_id=cat.id,
                            nivel2=n2,
                            nombre=leaf,
                            orden=orden,
                            activo=True,
                        )
                    )
                    db.session.commit()
                    flash('Subcategorías creadas bajo la categoría.', 'success')
            elif act == 'renombrar_nivel2':
                cid = request.form.get('categoria_id', type=int)
                n2_actual = (request.form.get('nivel2_actual') or '').strip()[:80]
                n2_nuevo = (request.form.get('nivel2_nuevo') or '').strip()[:80]
                cat = CatalogoCategoria.query.get(cid) if cid else None
                if not cat:
                    flash('Categoría inválida para renombrar familia.', 'warning')
                elif not n2_actual:
                    flash('Debe indicar la familia (Subcategoría 1) actual.', 'warning')
                elif not n2_nuevo:
                    flash('Debe indicar el nuevo nombre de la familia.', 'warning')
                else:
                    filas = (
                        CatalogoSubcategoria.query
                        .filter_by(categoria_id=cat.id, nivel2=n2_actual)
                        .all()
                    )
                    if not filas:
                        flash('No se encontraron hojas para esa familia.', 'warning')
                    else:
                        for s in filas:
                            s.nivel2 = n2_nuevo
                        db.session.commit()
                        flash(f'Familia actualizada en {len(filas)} hoja(s).', 'success')
            elif act == 'editar_sub':
                sid = request.form.get('id', type=int)
                sub = CatalogoSubcategoria.query.get(sid) if sid else None
                if not sub:
                    flash('Registro no encontrado.', 'warning')
                else:
                    n2 = (request.form.get('nivel2') or '').strip()[:80]
                    leaf = (request.form.get('nombre_hoja') or '').strip()[:80]
                    if not leaf:
                        flash('Nombre de hoja obligatorio.', 'warning')
                    else:
                        sub.nivel2 = n2
                        sub.nombre = leaf
                        sub.orden = request.form.get('orden', type=int) or 0
                        sub.activo = bool(request.form.get('activo'))
                        db.session.commit()
                        flash('Subcategoría actualizada.', 'success')
            elif act == 'toggle_sub':
                sid = request.form.get('id', type=int)
                sub = CatalogoSubcategoria.query.get(sid) if sid else None
                if sub:
                    sub.activo = not bool(sub.activo)
                    db.session.commit()
                    flash('Estado de la hoja actualizado.', 'success')
            elif act == 'eliminar_sub':
                sid = request.form.get('id', type=int)
                sub = CatalogoSubcategoria.query.get(sid) if sid else None
                if not sub:
                    flash('Registro no encontrado.', 'warning')
                elif Producto.query.filter_by(subcategoria_catalogo_id=sub.id).first():
                    flash('No se puede eliminar: hay productos asignados a esta hoja. Desactívela o reasigne productos.', 'warning')
                else:
                    db.session.delete(sub)
                    db.session.commit()
                    flash('Hoja del catálogo eliminada.', 'success')
            elif act == 'asignar_producto':
                pid = request.form.get('producto_id', type=int)
                sid = request.form.get('subcategoria_catalogo_id', type=int)
                p = Producto.query.get(pid) if pid else None
                if not p or not sid:
                    flash('Datos incompletos.', 'warning')
                else:
                    _sincronizar_producto_desde_subcatalogo(p, sid)
                    db.session.commit()
                    flash(f'Producto «{p.nombre}» clasificado en el catálogo.', 'success')
            elif act == 'asignar_masivo':
                sid = request.form.get('subcategoria_catalogo_id', type=int)
                ids = []
                for x in request.form.getlist('producto_ids'):
                    try:
                        ids.append(int(x))
                    except (TypeError, ValueError):
                        pass
                ids = ids[:150]
                if not sid or not ids:
                    flash('Seleccione al menos un producto y una hoja del catálogo.', 'warning')
                elif not CatalogoSubcategoria.query.get(sid):
                    flash('Hoja de catálogo inválida.', 'warning')
                else:
                    n = 0
                    for pid in ids:
                        p = Producto.query.get(pid)
                        if p and p.subcategoria_catalogo_id is None:
                            _sincronizar_producto_desde_subcatalogo(p, sid)
                            n += 1
                    db.session.commit()
                    flash(f'Productos clasificados: {n} (solo los que no tenían catálogo).', 'success')
            else:
                flash('Acción no reconocida.', 'warning')
        except Exception as ex:
            db.session.rollback()
            flash(f'Error al guardar: {ex}', 'danger')

        cid = request.form.get('redirect_cat_id', type=int)
        return redirect(url_for('admin_catalogo', cat_id=cid) if cid else url_for('admin_catalogo'))

    cat_filtro = request.args.get('cat_id', type=int)
    categorias = (
        CatalogoCategoria.query.order_by(CatalogoCategoria.orden.asc(), CatalogoCategoria.nombre.asc()).all()
    )
    subs_q = (
        CatalogoSubcategoria.query.options(joinedload(CatalogoSubcategoria.categoria))
        .join(CatalogoCategoria, CatalogoCategoria.id == CatalogoSubcategoria.categoria_id)
        .order_by(
            CatalogoCategoria.orden,
            CatalogoCategoria.nombre,
            CatalogoSubcategoria.nivel2,
            CatalogoSubcategoria.orden,
            CatalogoSubcategoria.nombre,
        )
    )
    if cat_filtro:
        subs_q = subs_q.filter(CatalogoSubcategoria.categoria_id == cat_filtro)
    subcategorias = subs_q.limit(800).all()

    sin_catalogo = (
        Producto.query.filter(Producto.subcategoria_catalogo_id.is_(None), Producto.activo.isnot(False))
        .order_by(Producto.nombre.asc())
        .limit(200)
        .all()
    )
    opciones_hojas = _opciones_hojas_catalogo_para_select()
    # Árbol jerárquico para visualización y mantenimiento por dependencia:
    # categoría (nivel 1) -> familia/nivel2 (nivel 2) -> hojas (nivel 3).
    hojas_all = (
        CatalogoSubcategoria.query.options(joinedload(CatalogoSubcategoria.categoria))
        .join(CatalogoCategoria, CatalogoCategoria.id == CatalogoSubcategoria.categoria_id)
        .order_by(
            CatalogoCategoria.orden.asc(),
            CatalogoCategoria.nombre.asc(),
            CatalogoSubcategoria.nivel2.asc(),
            CatalogoSubcategoria.orden.asc(),
            CatalogoSubcategoria.nombre.asc(),
        )
        .all()
    )
    jerarquia_catalogo = []
    por_cat = {}
    for c in categorias:
        node = {"cat": c, "familias": []}
        por_cat[c.id] = node
        jerarquia_catalogo.append(node)
    for s in hojas_all:
        nodo_cat = por_cat.get(s.categoria_id)
        if not nodo_cat:
            continue
        fam_name = (s.nivel2 or '').strip() or 'Sin familia'
        fam = next((f for f in nodo_cat["familias"] if f["nombre"] == fam_name), None)
        if fam is None:
            fam = {"nombre": fam_name, "hojas": []}
            nodo_cat["familias"].append(fam)
        fam["hojas"].append(s)

    return render_template(
        'admin_catalogo.html',
        categorias=categorias,
        subcategorias=subcategorias,
        cat_filtro=cat_filtro,
        sin_catalogo=sin_catalogo,
        opciones_hojas=opciones_hojas,
        jerarquia_catalogo=jerarquia_catalogo,
    )


# API para el Escáner Móvil.............................................................
@app.route('/api/buscar_producto/<codigo>')
@login_required
def api_buscar_producto(codigo):
    # Busca por código de barras
    producto = Producto.query.filter_by(codigo_barra=codigo).first()
    
    if producto:
        aid_t = id_almacen_tienda()
        aid_b = id_almacen_bodega()
        st_t = stock_producto_en_almacen(producto.id, aid_t) if aid_t and _tablas_inventario_almacen_existen() else None
        st_b = stock_producto_en_almacen(producto.id, aid_b) if aid_b and _tablas_inventario_almacen_existen() else None
        return jsonify({
            "status": "success",
            "id": producto.id,
            "nombre": producto.nombre,
            "stock": producto.stock,
            "stock_total": producto.stock,
            "stock_tienda": st_t if st_t is not None else stock_disponible_venta_tienda(producto),
            "stock_bodega": st_b if st_b is not None else None,
        })
    
    return jsonify({"status": "error", "message": "No existe"}), 404
@app.route('/finalizar_auditoria/<int:auditoria_id>', methods=['POST'])
@login_required

# Esta ruta se llama desde el botón "Finalizar Auditoría" en la pantalla de auditorías. Solo alguien con el permiso 'admin_inventario' puede acceder a esta función, que procesa los resultados de la auditoría, ajusta el stock maestro y registra los movimientos en el Kardex.
@permisos_required('admin_inventario') # Solo alguien con rango puede ajustar
def finalizar_auditoria(auditoria_id):
    auditoria = AuditoriaInventario.query.get_or_404(auditoria_id)
    detalles = DetalleAuditoria.query.filter_by(auditoria_id=auditoria_id).all()
    aid_bod = id_almacen_bodega()

    for d in detalles:
        # 1. Identificar el producto
        producto = Producto.query.get(d.producto_id)
        
        # 2. Calcular la diferencia (Fisico - Sistema)
        diferencia = d.stock_fisico - d.stock_sistema
        
        if diferencia != 0:
            if aid_bod and _tablas_inventario_almacen_existen():
                fijar_stock_almacen(producto.id, aid_bod, d.stock_fisico)
                _refrescar_stock_total_producto(producto)
            else:
                producto.stock = d.stock_fisico
            registrar_movimiento_kardex(
                producto.id,
                'AJUSTE',
                abs(diferencia),
                f"Ajuste por Auditoría #{auditoria_id}",
                usuario=current_user.nombre,
                id_almacen=aid_bod or 1,
                referencia_tipo='auditoria',
                referencia_id=auditoria_id,
                stock_saldo=d.stock_fisico,
            )

    # 5. Marcar auditoría como finalizada
    auditoria.estado = 'Ajustada'
    auditoria.fecha_fin = datetime.now()
    db.session.commit()
    
    flash("Inventario ajustado y Kardex actualizado correctamente.", "success")
    return redirect(url_for('ver_auditorias'))

def _carpeta_docs_recepcion():
    carpeta = os.path.join(app.root_path, 'static', 'uploads', 'recepciones')
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _ruta_doc_recepcion(recepcion_id):
    carpeta = _carpeta_docs_recepcion()
    pref = f"recepcion_{int(recepcion_id)}_"
    for nom in os.listdir(carpeta):
        if nom.startswith(pref):
            return nom
    return None


def _guardar_doc_recepcion(recepcion_id, archivo):
    if not archivo or not getattr(archivo, 'filename', None):
        return None
    nombre = secure_filename(archivo.filename or '')
    if not nombre:
        return None
    carpeta = _carpeta_docs_recepcion()
    # Reemplaza archivo previo de la misma recepción
    prev = _ruta_doc_recepcion(recepcion_id)
    if prev:
        try:
            os.remove(os.path.join(carpeta, prev))
        except OSError:
            pass
    final = f"recepcion_{int(recepcion_id)}_{nombre}"
    archivo.save(os.path.join(carpeta, final))
    return final


def _optimizar_imagen_factura_ia(raw_bytes):
    """Reduce tamaño para API de visión (JPEG base64)."""
    from PIL import Image

    im = Image.open(io.BytesIO(raw_bytes))
    if im.mode not in ('RGB', 'L'):
        im = im.convert('RGB')
    im.thumbnail((2048, 2048))
    buf = io.BytesIO()
    im.save(buf, format='JPEG', quality=82, optimize=True)
    return buf.getvalue()


def _pdf_factura_a_imagenes_jpeg(path, max_pages=2):
    """Primera(s) página(s) de PDF a bytes JPEG."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None, 'PyMuPDF no instalado. Ejecute: pip install PyMuPDF'
    out = []
    try:
        doc = fitz.open(path)
        for i in range(min(len(doc), max_pages)):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
            png = pix.tobytes('png')
            out.append(_optimizar_imagen_factura_ia(png))
        doc.close()
    except Exception as ex:
        return None, str(ex)
    return out, None


def _json_desde_texto_modelo(texto):
    t = (texto or '').strip()
    if t.startswith('```'):
        t = re.sub(r'^```(?:json)?\s*', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\s*```$', '', t)
    return json.loads(t)


def _openai_extraer_items_factura(data_urls_jpeg, api_key):
    """
    data_urls_jpeg: lista de data:image/jpeg;base64,...
    Devuelve lista de dicts: codigo_proveedor, descripcion, cantidad, precio_unitario
    """
    model = (os.getenv('OPENAI_VISION_MODEL') or 'gpt-4o-mini').strip()
    detail = (os.getenv('OPENAI_VISION_DETAIL') or 'low').strip().lower()
    if detail not in ('low', 'high', 'auto'):
        detail = 'low'
    instrucciones = (
        'Eres un asistente para ferretería en Chile. Lee la factura o guía de despacho en la(s) imagen(es) '
        'y extrae SOLO las líneas de productos mercadería (excluye totales, IVA, texto legal, envío vacío). '
        'Responde con un JSON válido (sin markdown) con esta forma exacta:\n'
        '{"items":[{"codigo_proveedor": string o null, "descripcion": string, "cantidad": number, '
        '"precio_unitario": number o null}]}\n'
        'cantidad = unidades facturadas (entero o decimal que redondearemos). precio_unitario = precio neto '
        'por unidad si aparece; si solo hay subtotal de línea, calcula precio_unitario = subtotal/cantidad.'
    )
    content = [{'type': 'text', 'text': instrucciones}]
    for url in data_urls_jpeg:
        content.append({'type': 'image_url', 'image_url': {'url': url, 'detail': detail}})

    payload = {
        'model': model,
        'temperature': 0.1,
        'max_tokens': 4096,
        'messages': [{'role': 'user', 'content': content}],
        'response_format': {'type': 'json_object'},
    }
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_txt = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'OpenAI HTTP {e.code}: {err_txt[:500]}') from e
    except urllib.error.URLError as e:
        raise RuntimeError(f'Error de red: {e}') from e

    try:
        msg = body['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError('Respuesta OpenAI inesperada') from e

    data = _json_desde_texto_modelo(msg)
    items = data.get('items') or []
    if not isinstance(items, list):
        return []
    limpio = []
    for it in items[:60]:
        if not isinstance(it, dict):
            continue
        limpio.append(
            {
                'codigo_proveedor': (it.get('codigo_proveedor') or it.get('codigo') or None),
                'descripcion': (it.get('descripcion') or it.get('descripcion_producto') or '')[:500],
                'cantidad': it.get('cantidad'),
                'precio_unitario': it.get('precio_unitario'),
            }
        )
    return limpio


def _matchear_producto_linea_factura(codigo_factura, descripcion):
    """Empareja una línea de factura con Producto (código de barra / nombre)."""
    cod = (str(codigo_factura) if codigo_factura is not None else '').strip()
    if cod:
        p = (
            Producto.query.filter(Producto.activo.isnot(False))
            .filter(db.func.upper(db.func.trim(Producto.codigo_barra)) == cod.upper())
            .first()
        )
        if p:
            return p, 'codigo'
        p = (
            Producto.query.filter(Producto.activo.isnot(False))
            .filter(Producto.codigo_barra == cod)
            .first()
        )
        if p:
            return p, 'codigo'
    desc = (descripcion or '').strip()
    if not desc:
        return None, None
    like = f'%{desc[:100]}%'
    p = (
        Producto.query.filter(Producto.activo.isnot(False))
        .filter(Producto.nombre.ilike(like))
        .order_by(db.func.length(Producto.nombre).asc())
        .first()
    )
    if p:
        return p, 'nombre'
    for w in desc.split():
        w = w.strip('.,;:()[]')
        if len(w) < 4:
            continue
        like_w = f'%{w}%'
        p = (
            Producto.query.filter(Producto.activo.isnot(False))
            .filter(Producto.nombre.ilike(like_w))
            .order_by(Producto.id.asc())
            .first()
        )
        if p:
            return p, 'nombre_parcial'
    return None, None


def _aplicar_linea_recepcion(
    recepcion,
    producto_id,
    cantidad_documento,
    cantidad_fisica,
    usuario_nombre,
    costo_unitario=None,
    autorizar_margen_bajo=False,
):
    """Suma stock y registra kardex; retorna (error|None, alerta_costo|None)."""
    if recepcion.estado not in ('Pendiente', 'Incompleta'):
        return "Esta recepción ya no admite líneas.", None
    try:
        cant_fis = int(cantidad_fisica)
        cant_doc = int(cantidad_documento)
    except (TypeError, ValueError):
        return "Cantidades inválidas.", None
    if cant_fis <= 0:
        return "La cantidad recibida debe ser mayor a cero.", None
    if cant_doc < 0:
        return "La cantidad según documento no puede ser negativa.", None

    producto = Producto.query.get(producto_id)
    if not producto:
        return "Producto no encontrado.", None

    factor_compra_stock = _factor_compra_a_stock(producto)
    ingreso_stock = int(round(cant_fis * factor_compra_stock))
    if ingreso_stock <= 0:
        return "El factor de conversión genera ingreso de stock inválido.", None

    alerta = None
    try:
        costo_nuevo = float(costo_unitario) if costo_unitario is not None and str(costo_unitario).strip() != '' else None
    except (TypeError, ValueError):
        costo_nuevo = None
    if costo_nuevo is not None and costo_nuevo > 0:
        costo_anterior = float(producto.precio_compra or 0)
        precio_venta_actual = float(producto.precio_venta or 0)
        min_margen = float(os.getenv("MARGEN_MINIMO_RECEPCION", "0.18"))
        margen_proyectado = ((precio_venta_actual - costo_nuevo) / costo_nuevo) if precio_venta_actual > 0 else None

        if (
            margen_proyectado is not None
            and margen_proyectado < min_margen
            and not autorizar_margen_bajo
        ):
            pct_actual = f"{(margen_proyectado * 100):.1f}%"
            pct_min = f"{(min_margen * 100):.1f}%"
            return (
                f"Margen proyectado bajo para {producto.nombre} ({pct_actual}, mínimo {pct_min}). "
                f"Marque 'Autorizar recepción con margen bajo' o ajuste precio de venta.",
                None,
            )

    det = DetalleRecepcion.query.filter_by(
        recepcion_id=recepcion.id, producto_id=producto_id
    ).first()
    if det:
        det.cantidad_recibida += cant_fis
        det.cantidad_documento = max(det.cantidad_documento, cant_doc)
    else:
        det = DetalleRecepcion(
            recepcion_id=recepcion.id,
            producto_id=producto_id,
            cantidad_documento=cant_doc,
            cantidad_recibida=cant_fis,
        )
        db.session.add(det)

    aid_bod = id_almacen_bodega()
    if aid_bod and _tablas_inventario_almacen_existen():
        _, err_stock = ajustar_stock_almacen(producto.id, aid_bod, ingreso_stock)
        if err_stock:
            return err_stock, None
        _refrescar_stock_total_producto(producto)
    else:
        producto.stock = (producto.stock or 0) + ingreso_stock

    if recepcion.estado == 'Pendiente':
        recepcion.estado = 'Incompleta'

    if costo_nuevo is not None and costo_nuevo > 0:
        costo_anterior = float(producto.precio_compra or 0)
        precio_venta_actual = float(producto.precio_venta or 0)
        min_margen = float(os.getenv("MARGEN_MINIMO_RECEPCION", "0.18"))
        margen_proyectado = ((precio_venta_actual - costo_nuevo) / costo_nuevo) if precio_venta_actual > 0 else None

        producto.precio_compra = costo_nuevo
        if costo_anterior > 0 and costo_nuevo > costo_anterior:
            pct_margen = ((precio_venta_actual - costo_anterior) / costo_anterior) if costo_anterior else 0
            precio_sugerido = round(costo_nuevo * (1 + max(pct_margen, 0)), 0)
            alerta = (
                f"{producto.nombre}: costo subió de ${costo_anterior:,.0f} a ${costo_nuevo:,.0f}. "
                f"Revise precio de venta actual ${precio_venta_actual:,.0f}; sugerido >= ${precio_sugerido:,.0f}."
            )
        elif costo_anterior <= 0:
            alerta = f"{producto.nombre}: se registró costo de compra ${costo_nuevo:,.0f} (sin referencia anterior)."

        registrar_bitacora_costo(
            producto_id=producto.id,
            proveedor_id=recepcion.proveedor_id,
            recepcion_id=recepcion.id,
            costo_anterior=costo_anterior,
            costo_nuevo=costo_nuevo,
            precio_venta_referencia=precio_venta_actual,
            usuario=usuario_nombre,
            observacion="Recepción con costo unitario informado",
        )

    if factor_compra_stock != 1:
        msg_conv = (
            f"Conversión aplicada: {cant_fis} {producto.unidad_compra or 'compra'}"
            f" = {ingreso_stock} {producto.unidad_venta_final}."
        )
        alerta = f"{alerta} {msg_conv}" if alerta else msg_conv

    registrar_movimiento_kardex(
        producto.id,
        'ENTRADA',
        ingreso_stock,
        f"Recepción #{recepcion.id} — Doc. {recepcion.documento_tipo} {recepcion.documento_numero}"
        f" ({cant_fis} {producto.unidad_compra or producto.unidad_venta_final} -> {ingreso_stock} {producto.unidad_venta_final})",
        usuario=usuario_nombre,
        id_almacen=aid_bod or 1,
        referencia_tipo='recepcion',
        referencia_id=recepcion.id,
        stock_saldo=None,
    )
    return None, alerta


# API para registrar cada ítem recibido durante proceso de recepción de mercadería
@app.route('/api/registrar_item_recepcion', methods=['POST'])
@login_required
def registrar_item_recepcion():
    data = request.json or {}
    try:
        rid = int(data.get('recepcion_id'))
        pid = int(data.get('producto_id'))
        cant_doc = int(data.get('cantidad_esperada', 0))
        cant_fis = int(data.get('cantidad_fisica', 0))
        costo_unitario = data.get('costo_unitario')
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400

    recepcion = RecepcionCompra.query.get(rid)
    if not recepcion:
        return jsonify({"status": "error", "message": "Recepción no encontrada"}), 404

    err, alerta = _aplicar_linea_recepcion(
        recepcion, pid, cant_doc, cant_fis, current_user.nombre, costo_unitario=costo_unitario
    )
    if err:
        db.session.rollback()
        return jsonify({"status": "error", "message": err}), 400

    db.session.commit()
    return jsonify({"status": "success", "alerta": alerta})
# API para guardar conteo de inventario desde escáner móvil durante auditoría
@app.route('/api/guardar_conteo_inventario', methods=['POST'])
@login_required
def guardar_conteo_inventario():
    data = request.json
    
    # Obtener stock actual del sistema para comparar después
    producto = Producto.query.get(data['producto_id'])
    aid_bod = id_almacen_bodega()
    if aid_bod and _tablas_inventario_almacen_existen():
        sis = stock_producto_en_almacen(producto.id, aid_bod)
        if sis is None:
            sis = int(producto.stock or 0)
    else:
        sis = int(producto.stock or 0)
    
    # Registrar el hallazgo del bodeguero
    nuevo_detalle = DetalleAuditoria(
        auditoria_id=data['auditoria_id'],
        producto_id=data['producto_id'],
        stock_sistema=sis,
        stock_fisico=data['cantidad_fisica'] # Lo que el bodeguero contó
    )
    
    db.session.add(nuevo_detalle)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "Conteo registrado"})


@app.route('/ver_auditorias')
@login_required
def ver_auditorias():
    """Listado mínimo de auditorías; el ajuste masivo redirige al kardex."""
    auditorias = AuditoriaInventario.query.order_by(AuditoriaInventario.id.desc()).limit(50).all()
    return render_template('auditorias_lista.html', auditorias=auditorias)


@app.route('/kardex')
@login_required
def kardex():
    pid = request.args.get('producto_id', type=int)
    tipo = (request.args.get('tipo') or '').strip()
    qtext = (request.args.get('q') or '').strip()
    fecha_inicio = (request.args.get('fecha_inicio') or '').strip()
    fecha_fin = (request.args.get('fecha_fin') or '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 40

    consulta = MovimientoInventario.query.options(
        joinedload(MovimientoInventario.producto)
    ).order_by(MovimientoInventario.fecha.desc(), MovimientoInventario.id.desc())

    if pid:
        consulta = consulta.filter(MovimientoInventario.id_producto == pid)
    if tipo in ('ENTRADA', 'SALIDA', 'AJUSTE'):
        consulta = consulta.filter(MovimientoInventario.tipo_movimiento == tipo)
    if qtext:
        like = f"%{qtext}%"
        consulta = consulta.join(Producto, Producto.id == MovimientoInventario.id_producto).filter(
            or_(
                Producto.nombre.like(like),
                Producto.codigo_barra.like(like),
                MovimientoInventario.motivo.like(like),
            )
        )
    if fecha_inicio:
        try:
            fi = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            consulta = consulta.filter(MovimientoInventario.fecha >= fi)
        except ValueError:
            pass
    if fecha_fin:
        try:
            ff = datetime.strptime(fecha_fin, '%Y-%m-%d') + timedelta(days=1)
            consulta = consulta.filter(MovimientoInventario.fecha < ff)
        except ValueError:
            pass

    pagination = consulta.paginate(page=page, per_page=per_page, error_out=False)
    productos_sel = Producto.query.filter_by(activo=True).order_by(Producto.nombre).limit(800).all()
    return render_template(
        'kardex.html',
        movimientos=pagination.items,
        pagination=pagination,
        productos_sel=productos_sel,
        filtros={
            'producto_id': pid,
            'tipo': tipo,
            'q': qtext,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
        },
    )


_OC_ESTADOS_VALIDOS = ('Borrador', 'Enviada', 'Parcial', 'Cerrada', 'Anulada')


@app.route('/compras/ordenes')
@login_required
def lista_ordenes_compra():
    if not _tablas_orden_compra_existen():
        flash('Ejecute la migración sql/2026_05_03_ordenes_compra.sql en la base de datos.', 'warning')
        return redirect(url_for('inicio'))
    ordenes = (
        OrdenCompra.query.options(
            joinedload(OrdenCompra.proveedor),
            joinedload(OrdenCompra.detalles),
        )
        .order_by(OrdenCompra.id.desc())
        .limit(500)
        .all()
    )
    return render_template('ordenes_compra_lista.html', ordenes=ordenes)


@app.route('/compras/ordenes/nueva', methods=['GET', 'POST'])
@login_required
def orden_compra_nueva():
    if not _tablas_orden_compra_existen():
        flash('Ejecute la migración sql/2026_05_03_ordenes_compra.sql', 'warning')
        return redirect(url_for('inicio'))
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    canales_compra_map = obtener_canales_proveedor()
    producto_sugerido_id = request.values.get('producto_id_sugerido', type=int) or request.values.get('producto_id', type=int)
    producto_sugerido = Producto.query.get(producto_sugerido_id) if producto_sugerido_id else None

    sugerencias_payload_raw = (request.values.get('sugerencias_payload') or '').strip()
    sugerencias_multi = []
    if sugerencias_payload_raw:
        try:
            raw_items = json.loads(sugerencias_payload_raw)
            if isinstance(raw_items, list):
                ids = [int(it.get('id')) for it in raw_items if isinstance(it, dict) and str(it.get('id', '')).isdigit()]
                productos_map = {p.id: p for p in Producto.query.filter(Producto.id.in_(ids)).all()} if ids else {}
                for it in raw_items:
                    if not isinstance(it, dict):
                        continue
                    pid = int(it.get('id')) if str(it.get('id', '')).isdigit() else None
                    if not pid or pid not in productos_map:
                        continue
                    try:
                        qty = float(it.get('qty') or 0)
                    except (TypeError, ValueError):
                        qty = 0
                    qty = max(0.0, qty)
                    if qty <= 0:
                        continue
                    sugerencias_multi.append({
                        "producto": productos_map[pid],
                        "cantidad": qty,
                    })
        except Exception:
            sugerencias_multi = []
    proveedor_sugerido_id = None
    if sugerencias_multi and _tablas_orden_compra_existen():
        try:
            ids_productos_ia = [s["producto"].id for s in sugerencias_multi if s.get("producto")]
            if ids_productos_ia:
                filas_prov = (
                    db.session.query(OrdenCompra.proveedor_id, db.func.count(DetalleOrdenCompra.id))
                    .join(DetalleOrdenCompra, DetalleOrdenCompra.orden_compra_id == OrdenCompra.id)
                    .filter(
                        OrdenCompra.proveedor_id.isnot(None),
                        OrdenCompra.estado != 'Anulada',
                        DetalleOrdenCompra.producto_id.in_(ids_productos_ia),
                    )
                    .group_by(OrdenCompra.proveedor_id)
                    .order_by(db.func.count(DetalleOrdenCompra.id).desc(), OrdenCompra.proveedor_id.asc())
                    .all()
                )
                if filas_prov:
                    proveedor_sugerido_id = int(filas_prov[0][0])
        except Exception:
            proveedor_sugerido_id = None

    if request.method == 'POST':
        prov_id = request.form.get('proveedor_id', type=int)
        numero = (request.form.get('numero') or '').strip()[:50]
        if not prov_id or not numero:
            flash('Proveedor y número de OC son obligatorios.', 'warning')
            return render_template(
                'orden_compra_form.html',
                proveedores=proveedores,
                canales_compra_map=canales_compra_map,
                oc=None,
                estados=_OC_ESTADOS_VALIDOS,
                hoy=datetime.now().strftime('%Y-%m-%d'),
                producto_sugerido=producto_sugerido,
                sugerencias_multi=sugerencias_multi,
                sugerencias_payload=sugerencias_payload_raw,
                proveedor_sugerido_id=proveedor_sugerido_id,
            )
        if OrdenCompra.query.filter_by(proveedor_id=prov_id, numero=numero).first():
            flash('Ya existe una orden con ese número para el proveedor.', 'warning')
            return render_template(
                'orden_compra_form.html',
                proveedores=proveedores,
                canales_compra_map=canales_compra_map,
                oc=None,
                estados=_OC_ESTADOS_VALIDOS,
                hoy=datetime.now().strftime('%Y-%m-%d'),
                producto_sugerido=producto_sugerido,
                sugerencias_multi=sugerencias_multi,
                sugerencias_payload=sugerencias_payload_raw,
                proveedor_sugerido_id=proveedor_sugerido_id,
            )
        try:
            fecha_e = datetime.strptime((request.form.get('fecha_emision') or '').strip(), '%Y-%m-%d').date()
        except ValueError:
            fecha_e = datetime.now().date()
        estado = (request.form.get('estado') or 'Borrador').strip()
        if estado not in _OC_ESTADOS_VALIDOS:
            estado = 'Borrador'
        oc = OrdenCompra(
            proveedor_id=prov_id,
            numero=numero,
            fecha_emision=fecha_e,
            estado=estado,
            observacion=(request.form.get('observacion') or '').strip()[:500] or None,
            usuario_creador=(current_user.nombre if current_user.is_authenticated else None),
        )
        if sugerencias_multi:
            marca_ia = f"[IA] Selección asistida ({len(sugerencias_multi)} SKU) {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            obs_prev = (oc.observacion or '').strip()
            if obs_prev:
                oc.observacion = f"{obs_prev} | {marca_ia}"[:500]
            else:
                oc.observacion = marca_ia[:500]
        db.session.add(oc)
        db.session.flush()
        if producto_sugerido:
            db.session.add(
                DetalleOrdenCompra(
                    orden_compra_id=oc.id,
                    producto_id=producto_sugerido.id,
                    cantidad=1,
                    precio_unitario=float(producto_sugerido.precio_compra or 0),
                )
            )
        for s in sugerencias_multi:
            p = s["producto"]
            db.session.add(
                DetalleOrdenCompra(
                    orden_compra_id=oc.id,
                    producto_id=p.id,
                    cantidad=max(1.0, float(s["cantidad"])),
                    precio_unitario=float(p.precio_compra or 0),
                )
            )
        db.session.commit()
        if sugerencias_multi:
            flash(f'Orden de compra creada con {len(sugerencias_multi)} línea(s) sugerida(s) por IA.', 'success')
        else:
            flash('Orden de compra creada. Agregue líneas de productos.', 'success')
        return redirect(url_for('orden_compra_editar', oid=oc.id))
    return render_template(
        'orden_compra_form.html',
        proveedores=proveedores,
        canales_compra_map=canales_compra_map,
        oc=None,
        estados=_OC_ESTADOS_VALIDOS,
        hoy=datetime.now().strftime('%Y-%m-%d'),
        producto_sugerido=producto_sugerido,
        sugerencias_multi=sugerencias_multi,
        sugerencias_payload=sugerencias_payload_raw,
        proveedor_sugerido_id=proveedor_sugerido_id,
    )


@app.route('/compras/ordenes/<int:oid>', methods=['GET', 'POST'])
@login_required
def orden_compra_editar(oid):
    if not _tablas_orden_compra_existen():
        flash('Ejecute la migración sql/2026_05_03_ordenes_compra.sql', 'warning')
        return redirect(url_for('inicio'))
    oc = (
        OrdenCompra.query.options(
            joinedload(OrdenCompra.proveedor),
            joinedload(OrdenCompra.detalles).joinedload(DetalleOrdenCompra.producto),
        ).get_or_404(oid)
    )
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    canales_compra_map = obtener_canales_proveedor()
    canal_oc = canal_compra_proveedor(oc.proveedor_id) if oc.proveedor_id else "manual"
    if request.method == 'POST':
        act = (request.form.get('action') or '').strip()
        try:
            if act == 'guardar_cabecera':
                prov_id = request.form.get('proveedor_id', type=int)
                numero = (request.form.get('numero') or '').strip()[:50]
                if not prov_id or not numero:
                    flash('Proveedor y número son obligatorios.', 'warning')
                else:
                    dup = (
                        OrdenCompra.query.filter(
                            OrdenCompra.proveedor_id == prov_id,
                            OrdenCompra.numero == numero,
                            OrdenCompra.id != oc.id,
                        ).first()
                    )
                    if dup:
                        flash('Otra orden ya usa ese número para el proveedor.', 'warning')
                    else:
                        try:
                            fecha_e = datetime.strptime((request.form.get('fecha_emision') or '').strip(), '%Y-%m-%d').date()
                        except ValueError:
                            fecha_e = oc.fecha_emision
                        estado = (request.form.get('estado') or oc.estado).strip()
                        if estado not in _OC_ESTADOS_VALIDOS:
                            estado = oc.estado
                        oc.proveedor_id = prov_id
                        oc.numero = numero
                        oc.fecha_emision = fecha_e
                        oc.estado = estado
                        oc.observacion = (request.form.get('observacion') or '').strip()[:500] or None
                        db.session.commit()
                        flash('Cabecera actualizada.', 'success')
            elif act == 'add_line':
                pid = request.form.get('producto_id', type=int)
                try:
                    cant = float(request.form.get('cantidad', 0) or 0)
                    pu = float(request.form.get('precio_unitario', 0) or 0)
                except (TypeError, ValueError):
                    flash('Cantidad o precio inválidos.', 'warning')
                    return redirect(url_for('orden_compra_editar', oid=oid))
                if not pid or cant <= 0:
                    flash('Seleccione producto y cantidad mayor a cero.', 'warning')
                elif not Producto.query.get(pid):
                    flash('Producto no encontrado.', 'warning')
                else:
                    db.session.add(
                        DetalleOrdenCompra(
                            orden_compra_id=oc.id,
                            producto_id=pid,
                            cantidad=cant,
                            precio_unitario=max(0.0, pu),
                        )
                    )
                    db.session.commit()
                    flash('Línea agregada.', 'success')
            elif act == 'eliminar_linea':
                did = request.form.get('detalle_id', type=int)
                det = DetalleOrdenCompra.query.get(did) if did else None
                if det and det.orden_compra_id == oc.id:
                    db.session.delete(det)
                    db.session.commit()
                    flash('Línea eliminada.', 'success')
            else:
                flash('Acción no reconocida.', 'warning')
        except Exception as ex:
            db.session.rollback()
            flash(f'Error: {ex}', 'danger')
        return redirect(url_for('orden_compra_editar', oid=oid))
    total_estimado = sum(
        (float(d.cantidad or 0) * float(d.precio_unitario or 0)) for d in (oc.detalles or [])
    )
    return render_template(
        'orden_compra_form.html',
        proveedores=proveedores,
        canales_compra_map=canales_compra_map,
        canal_oc=canal_oc,
        oc=oc,
        estados=_OC_ESTADOS_VALIDOS,
        total_estimado=total_estimado,
        hoy=datetime.now().strftime('%Y-%m-%d'),
    )


@app.route('/recepciones')
@login_required
def lista_recepciones():
    recepciones = (
        RecepcionCompra.query.options(joinedload(RecepcionCompra.proveedor))
        .order_by(RecepcionCompra.id.desc())
        .limit(120)
        .all()
    )
    return render_template('recepciones_lista.html', recepciones=recepciones)


@app.route('/recepciones/tablet')
@login_required
def recepcion_tablet():
    proveedores = Proveedor.query.order_by(Proveedor.nombre.asc()).all()
    recepciones_activas = (
        RecepcionCompra.query.filter(RecepcionCompra.estado.in_(["Pendiente", "Incompleta"]))
        .order_by(RecepcionCompra.id.desc())
        .limit(30)
        .all()
    )
    return render_template(
        'movil_recepcion.html',
        proveedores=proveedores,
        recepciones_activas=recepciones_activas
    )


@app.route('/api/recepciones/iniciar', methods=['POST'])
@login_required
def api_iniciar_recepcion():
    data = request.json or {}
    try:
        proveedor_id = int(data.get('proveedor_id', 0))
    except (TypeError, ValueError):
        proveedor_id = 0
    doc_tipo = (data.get('documento_tipo') or 'Factura').strip()
    doc_num = (data.get('documento_numero') or '').strip()

    if not proveedor_id:
        return jsonify({"status": "error", "message": "Proveedor obligatorio"}), 400
    if doc_tipo not in ('Factura', 'Guia de Despacho'):
        doc_tipo = 'Factura'
    if not doc_num:
        return jsonify({"status": "error", "message": "Número de documento obligatorio"}), 400

    rec = RecepcionCompra(
        proveedor_id=proveedor_id,
        documento_tipo=doc_tipo,
        documento_numero=doc_num,
        usuario_bodega=current_user.nombre,
        estado='Pendiente',
    )
    db.session.add(rec)
    db.session.commit()
    return jsonify({"status": "success", "recepcion_id": rec.id})


@app.route('/api/recepciones/<int:rid>/resumen')
@login_required
def api_resumen_recepcion(rid):
    rec = RecepcionCompra.query.options(
        joinedload(RecepcionCompra.detalles).joinedload(DetalleRecepcion.producto)
    ).get_or_404(rid)
    items = []
    for d in rec.detalles:
        items.append({
            "producto": d.producto.nombre if d.producto else f"ID {d.producto_id}",
            "codigo": d.producto.codigo_barra if d.producto else "",
            "cantidad_documento": d.cantidad_documento,
            "cantidad_recibida": d.cantidad_recibida,
        })
    return jsonify({
        "status": "success",
        "recepcion_id": rec.id,
        "estado": rec.estado,
        "documento": f"{rec.documento_tipo} {rec.documento_numero}",
        "items": items,
    })


@app.route('/recepciones/costos')
@login_required
def reporte_costos_recepcion():
    if not _bitacora_costos_disponible():
        flash("Aún no existe la tabla de bitácora de costos. Ejecute migración SQL para habilitar este reporte.", "warning")
        return render_template('recepcion_costos.html', registros=[])
    registros = (
        BitacoraCostoCompra.query.options(
            joinedload(BitacoraCostoCompra.producto),
            joinedload(BitacoraCostoCompra.proveedor),
        )
        .order_by(BitacoraCostoCompra.id.desc())
        .limit(300)
        .all()
    )
    return render_template('recepcion_costos.html', registros=registros)


@app.route('/recepciones/nueva', methods=['GET', 'POST'])
@login_required
def nueva_recepcion():
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    ordenes_oc = []
    if _tablas_orden_compra_existen():
        ordenes_oc = (
            OrdenCompra.query.filter(OrdenCompra.estado.in_(['Borrador', 'Enviada', 'Parcial']))
            .options(joinedload(OrdenCompra.proveedor))
            .order_by(OrdenCompra.id.desc())
            .limit(200)
            .all()
        )
    if request.method == 'POST':
        try:
            prov_id = int(request.form.get('proveedor_id', 0))
        except (TypeError, ValueError):
            prov_id = 0
        doc_tipo = request.form.get('documento_tipo', 'Factura')
        doc_num = (request.form.get('documento_numero') or '').strip()
        oc_id = request.form.get('orden_compra_id', type=int) or None
        if not prov_id:
            flash('Seleccione proveedor.', 'warning')
            return render_template(
                'recepcion_nueva.html',
                proveedores=proveedores,
                ordenes_oc=ordenes_oc,
                oc_tablas_ok=_tablas_orden_compra_existen(),
            )
        if doc_tipo not in ('Factura', 'Guia de Despacho'):
            doc_tipo = 'Factura'
        if not doc_num:
            flash('Indique número de factura o guía.', 'warning')
            return render_template(
                'recepcion_nueva.html',
                proveedores=proveedores,
                ordenes_oc=ordenes_oc,
                oc_tablas_ok=_tablas_orden_compra_existen(),
            )
        rec = RecepcionCompra(
            proveedor_id=prov_id,
            documento_tipo=doc_tipo,
            documento_numero=doc_num,
            usuario_bodega=current_user.nombre,
            estado='Pendiente',
        )
        if _tablas_orden_compra_existen() and oc_id:
            oc = OrdenCompra.query.get(oc_id)
            if oc and oc.proveedor_id == prov_id:
                rec.orden_compra_id = oc_id
            elif oc_id:
                flash('La orden de compra no coincide con el proveedor; recepción sin vínculo a OC.', 'warning')
        db.session.add(rec)
        db.session.commit()
        _guardar_doc_recepcion(rec.id, request.files.get('documento_archivo'))
        flash('Recepción creada. Agregue productos y cantidades recibidas.', 'success')
        return redirect(url_for('detalle_recepcion', rid=rec.id))
    return render_template(
        'recepcion_nueva.html',
        proveedores=proveedores,
        ordenes_oc=ordenes_oc,
        oc_tablas_ok=_tablas_orden_compra_existen(),
    )


@app.route('/recepciones/<int:rid>', methods=['GET', 'POST'])
@login_required
def detalle_recepcion(rid):
    rec = RecepcionCompra.query.options(
        joinedload(RecepcionCompra.proveedor),
        joinedload(RecepcionCompra.orden_compra),
        joinedload(RecepcionCompra.detalles).joinedload(DetalleRecepcion.producto),
    ).get_or_404(rid)

    if request.method == 'POST' and rec.estado in ('Pendiente', 'Incompleta'):
        action = request.form.get('action')
        if action == 'asociar_oc' and _tablas_orden_compra_existen():
            oc_id = request.form.get('orden_compra_id', type=int)
            if oc_id:
                oc = OrdenCompra.query.get(oc_id)
                if oc and oc.proveedor_id == rec.proveedor_id:
                    rec.orden_compra_id = oc_id
                    db.session.commit()
                    flash('Orden de compra vinculada a esta recepción.', 'success')
                else:
                    flash('La orden debe ser del mismo proveedor que la recepción.', 'warning')
            else:
                rec.orden_compra_id = None
                db.session.commit()
                flash('Se quitó el vínculo con la orden de compra.', 'info')
            return redirect(url_for('detalle_recepcion', rid=rid))
        if action == 'add_line':
            try:
                pid = int(request.form.get('producto_id', 0))
                cant_doc = int(request.form.get('cantidad_documento', 0))
                cant_fis = int(request.form.get('cantidad_recibida', 0))
            except (TypeError, ValueError):
                flash('Datos de línea inválidos.', 'warning')
                return redirect(url_for('detalle_recepcion', rid=rid))
            costo_unit = request.form.get('costo_unitario')
            autorizar_margen_bajo = request.form.get('autorizar_margen_bajo') == '1'
            err, alerta = _aplicar_linea_recepcion(
                rec,
                pid,
                cant_doc,
                cant_fis,
                current_user.nombre,
                costo_unitario=costo_unit,
                autorizar_margen_bajo=autorizar_margen_bajo,
            )
            if err:
                db.session.rollback()
                flash(err, 'danger')
            else:
                db.session.commit()
                flash('Línea registrada y stock actualizado.', 'success')
                if alerta:
                    flash(f"Alerta de costos: {alerta}", 'warning')
            return redirect(url_for('detalle_recepcion', rid=rid))
        if action == 'finalizar':
            ids_nuevos = []
            for d in rec.detalles:
                p = d.producto
                if p and not (p.codigo_barra or '').strip():
                    p.codigo_barra = f"INT-{p.id:06d}"
                    ids_nuevos.append(str(p.id))
            rec.estado = 'Finalizada'
            db.session.commit()
            flash('Recepción finalizada.', 'success')
            if ids_nuevos:
                return redirect(url_for('imprimir_etiquetas_recepcion', rid=rid, ids=",".join(ids_nuevos)))
            return redirect(url_for('lista_recepciones'))

    tiene_documento = _ruta_doc_recepcion(rec.id) is not None
    ia_factura_habilitada = bool((os.getenv('OPENAI_API_KEY') or '').strip())
    ordenes_mismo_prov = []
    if _tablas_orden_compra_existen():
        ordenes_mismo_prov = (
            OrdenCompra.query.filter(
                OrdenCompra.proveedor_id == rec.proveedor_id,
                OrdenCompra.estado.in_(['Borrador', 'Enviada', 'Parcial']),
            )
            .order_by(OrdenCompra.id.desc())
            .limit(80)
            .all()
        )
    return render_template(
        'recepcion_detalle.html',
        recepcion=rec,
        tiene_documento=tiene_documento,
        ia_factura_habilitada=ia_factura_habilitada,
        ordenes_mismo_prov=ordenes_mismo_prov,
        oc_tablas_ok=_tablas_orden_compra_existen(),
    )


@app.route('/recepciones/<int:rid>/ia-factura/analizar', methods=['POST'])
@login_required
def api_ia_factura_analizar(rid):
    """Analiza PDF/imagen adjunta con visión OpenAI y sugiere líneas con emparejamiento al catálogo."""
    rec = RecepcionCompra.query.get_or_404(rid)
    if rec.estado not in ('Pendiente', 'Incompleta'):
        return jsonify(ok=False, message='La recepción no admite líneas.'), 400
    api_key = (os.getenv('OPENAI_API_KEY') or '').strip()
    if not api_key:
        return jsonify(ok=False, sin_api_key=True, message='Configure OPENAI_API_KEY en el servidor.'), 503
    nom = _ruta_doc_recepcion(rid)
    if not nom:
        return jsonify(ok=False, message='No hay documento adjunto en esta recepción.'), 400
    path = os.path.join(_carpeta_docs_recepcion(), nom)
    if not os.path.isfile(path):
        return jsonify(ok=False, message='Archivo adjunto no encontrado.'), 404
    ext = os.path.splitext(nom)[1].lower()
    data_urls = []
    if ext == '.pdf':
        jpegs, err = _pdf_factura_a_imagenes_jpeg(path, max_pages=int(os.getenv('IA_FACTURA_PDF_PAGINAS', '2')))
        if err:
            return jsonify(ok=False, message=err), 400
        for jb in jpegs:
            b64 = base64.b64encode(jb).decode('ascii')
            data_urls.append(f'data:image/jpeg;base64,{b64}')
    elif ext in ('.png', '.jpg', '.jpeg', '.webp'):
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            raw = _optimizar_imagen_factura_ia(raw)
            b64 = base64.b64encode(raw).decode('ascii')
            data_urls.append(f'data:image/jpeg;base64,{b64}')
        except Exception as ex:
            return jsonify(ok=False, message=str(ex)), 400
    else:
        return jsonify(ok=False, message='Formato no soportado para IA (PDF, JPG, PNG, WEBP).'), 400
    try:
        lineas = _openai_extraer_items_factura(data_urls, api_key)
    except Exception as ex:
        return jsonify(ok=False, message=str(ex)), 502
    out = []
    for row in lineas:
        cod = row.get('codigo_proveedor')
        desc = row.get('descripcion') or ''
        try:
            cant = float(row.get('cantidad') or 0)
        except (TypeError, ValueError):
            cant = 0
        cant_i = int(round(cant))
        if cant_i <= 0:
            continue
        precio = row.get('precio_unitario')
        try:
            precio_f = float(precio) if precio not in (None, '') else None
        except (TypeError, ValueError):
            precio_f = None
        if precio_f is not None and precio_f <= 0:
            precio_f = None
        p, how = _matchear_producto_linea_factura(cod, desc)
        out.append(
            {
                'descripcion_factura': desc,
                'codigo_factura': cod,
                'cantidad_documento': cant_i,
                'cantidad_recibida': cant_i,
                'precio_unitario': precio_f,
                'producto_id': p.id if p else None,
                'producto_nombre': p.nombre if p else None,
                'producto_codigo': (p.codigo_barra or '').strip() if p else None,
                'match': how,
            }
        )
    return jsonify(ok=True, items=out, total=len(out))


@app.route('/recepciones/<int:rid>/ia-factura/aplicar', methods=['POST'])
@login_required
def api_ia_factura_aplicar(rid):
    """Aplica líneas confirmadas (JSON) con la misma lógica que registrar línea manual."""
    rec = RecepcionCompra.query.get_or_404(rid)
    if rec.estado not in ('Pendiente', 'Incompleta'):
        return jsonify(ok=False, message='La recepción no admite líneas.'), 400
    data = request.get_json(silent=True) or {}
    items = data.get('items')
    if not isinstance(items, list) or not items:
        return jsonify(ok=False, message='Lista de ítems vacía.'), 400
    autorizar = bool(data.get('autorizar_margen_bajo'))
    ok_n = 0
    errores = []
    alertas = []
    for it in items[:50]:
        if not isinstance(it, dict):
            continue
        if not it.get('aplicar'):
            continue
        try:
            pid = int(it.get('producto_id'))
        except (TypeError, ValueError):
            errores.append({'error': 'producto_id inválido', 'item': it.get('descripcion_factura')})
            continue
        try:
            cdoc = int(it.get('cantidad_documento', 0))
            cfis = int(it.get('cantidad_recibida', 0))
        except (TypeError, ValueError):
            errores.append({'producto_id': pid, 'error': 'Cantidades inválidas'})
            continue
        costo = it.get('costo_unitario')
        err, alerta = _aplicar_linea_recepcion(
            rec,
            pid,
            cdoc,
            cfis,
            current_user.nombre,
            costo_unitario=costo,
            autorizar_margen_bajo=autorizar,
        )
        if err:
            errores.append({'producto_id': pid, 'error': err})
            db.session.rollback()
            continue
        try:
            db.session.commit()
            ok_n += 1
            if alerta:
                alertas.append(alerta)
        except Exception as ex:
            db.session.rollback()
            errores.append({'producto_id': pid, 'error': str(ex)})
    return jsonify(ok=True, aplicados=ok_n, errores=errores, alertas=alertas)


@app.route('/recepciones/<int:rid>/documento')
@login_required
def ver_documento_recepcion(rid):
    rec = RecepcionCompra.query.get_or_404(rid)
    nombre = _ruta_doc_recepcion(rec.id)
    if not nombre:
        flash("Esta recepción no tiene documento adjunto.", "warning")
        return redirect(url_for('detalle_recepcion', rid=rid))
    return send_from_directory(_carpeta_docs_recepcion(), nombre, as_attachment=False)


@app.route('/recepciones/<int:rid>/etiquetas')
@login_required
def imprimir_etiquetas_recepcion(rid):
    rec = RecepcionCompra.query.options(
        joinedload(RecepcionCompra.detalles).joinedload(DetalleRecepcion.producto),
        joinedload(RecepcionCompra.proveedor),
    ).get_or_404(rid)
    ids_raw = (request.args.get('ids') or '').strip()
    ids_set = {int(x) for x in ids_raw.split(',') if x.strip().isdigit()} if ids_raw else set()
    productos = []
    for d in rec.detalles:
        p = d.producto
        if not p:
            continue
        if ids_set and p.id not in ids_set:
            continue
        productos.append(p)
    if not productos:
        flash("No hay etiquetas pendientes para esta recepción.", "info")
        return redirect(url_for('detalle_recepcion', rid=rid))
    return render_template('recepcion_etiquetas.html', recepcion=rec, productos=productos, auto_print=True)


@app.route('/ver_documento/<int:id>')
@login_required
def ver_documento(id):
    # 1. Buscamos la venta en la base de datos
    venta = Venta.query.get_or_404(id)
    
    # 2. Si es Factura, nos aseguramos de que tenga el IVA desglosado
    if venta.tipo_documento == 'Factura' or venta.tipo_documento == '33':
        venta.desglosar_iva() # Usamos la función que creamos en el modelo
        
    # 3. Renderizamos la plantilla pasando los datos de la venta
    return render_template('documento_tributario.html', venta=venta)
# Ruta para descargar el documento tributario en PDF. Similar a 'ver_documento' pero convierte el HTML a PDF usando pdfkit.

@app.route('/descargar_pdf/<int:id>')
@login_required
def descargar_pdf(id):
    # 1. Buscamos la venta y calculamos impuestos
    venta = Venta.query.get_or_404(id)
    venta.desglosar_iva()

    # 2. GENERAMOS EL QR LOCALMENTE (Para evitar errores de red)
    datos_qr = f"Ferreteria-Santo-Domingo|Folio:{venta.id}|Total:{venta.monto_total}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(datos_qr)
    qr.make(fit=True)
    
    img_qr = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img_qr.save(buffered, format="PNG")
    # Convertimos la imagen a texto (base64) para inyectarla en el HTML
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    # 3. Renderizamos el HTML pasando la variable del QR
    html = render_template('documento_tributario.html', venta=venta, qr_code=qr_base64)

    # 4. Configuración de wkhtmltopdf para Windows
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

    # 5. Opciones del PDF (Ajustadas para velocidad y sin red)
    options = {
        'page-size': 'Letter',
        'encoding': "UTF-8",
        'margin-top': '0.5in',
        'margin-right': '0.5in',
        'margin-bottom': '0.5in',
        'margin-left': '0.5in',
        'quiet': '', 
        'enable-local-file-access': None,
        'no-outline': None
    }

    # 6. Generación del archivo
    try:
        pdf = pdfkit.from_string(html, False, options=options, configuration=config)
        
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Factura_FSD_{id}.pdf'
        return response
    except Exception as e:
        return f"Error crítico al generar PDF: {str(e)}"


def _parse_fecha_cartola_txt(txt):
    if not txt or not str(txt).strip():
        return None
    try:
        return datetime.strptime(str(txt).strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _cartola_credito_context(cliente_id, fecha_desde_txt, fecha_hasta_txt, orden):
    """Movimientos de crédito (ventas Credito + abonos) para cartola / PDF / boucher."""
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        return None
    desde_d = _parse_fecha_cartola_txt(fecha_desde_txt)
    hasta_d = _parse_fecha_cartola_txt(fecha_hasta_txt)
    orden = (orden or 'desc').strip().lower()
    if orden not in ('asc', 'desc'):
        orden = 'desc'

    ventas_credito = (
        Venta.query.filter(
            Venta.cliente_id == cliente_id,
            Venta.metodo_pago == 'Credito',
            or_(Venta.estado.is_(None), Venta.estado != 'Anulada'),
        )
        .order_by(Venta.fecha.asc(), Venta.id.asc())
        .all()
    )
    abonos_all = (
        AbonoCredito.query.filter_by(cliente_id=cliente_id)
        .order_by(AbonoCredito.fecha.asc(), AbonoCredito.id.asc())
        .all()
    )

    events = []
    for v in ventas_credito:
        dt = v.fecha or datetime.min
        doc = (v.tipo_documento or 'Vale').strip()
        folio = v.nro_documento
        detalle = f'Venta al crédito ({doc})'
        if folio:
            detalle = f'{detalle} — Folio {folio}'
        events.append(
            (
                dt,
                0,
                v.id,
                'cargo',
                float(v.monto_total or 0),
                f'{doc} #{v.id}',
                detalle,
            )
        )
    for a in abonos_all:
        dt = a.fecha or datetime.min
        mp = (a.metodo_pago or '').strip()
        detalle = (a.comentario or 'Abono a cuenta').strip() or 'Abono a cuenta'
        if mp:
            detalle = f'{detalle} [{mp}]'
        events.append(
            (
                dt,
                1,
                a.id,
                'abono',
                float(a.monto_abono or 0),
                f'Abono #{a.id}',
                detalle,
            )
        )

    events.sort(key=lambda t: (t[0], t[1], t[2]))

    def _fecha_dia(dt):
        return dt.date() if hasattr(dt, 'date') else dt

    opening = 0.0
    for (dt, _tie, _eid, tipo, monto, _ref, _det) in events:
        fd = _fecha_dia(dt)
        if desde_d and fd < desde_d:
            opening += monto if tipo == 'cargo' else -monto

    bal = opening
    mov_chrono = []
    total_cargos = 0.0
    total_abonos = 0.0
    for (dt, _tie, _eid, tipo, monto, ref, detalle) in events:
        fd = _fecha_dia(dt)
        if desde_d and fd < desde_d:
            continue
        if hasta_d and fd > hasta_d:
            continue
        if tipo == 'cargo':
            bal += monto
            total_cargos += monto
        else:
            bal -= monto
            total_abonos += monto
        mov_chrono.append(
            {
                'fecha': dt,
                'tipo': tipo,
                'ref': ref,
                'detalle': detalle,
                'monto': monto,
                'saldo_corriente': bal,
                'saldo_visual': bal,
            }
        )

    movimientos = list(reversed(mov_chrono)) if orden == 'desc' else mov_chrono
    saldo_reconstruido = bal
    saldo_actual = float(cliente.saldo_deudor or 0)
    diferencia_saldo = saldo_reconstruido - saldo_actual

    return {
        'cliente': cliente,
        'movimientos': movimientos,
        'fecha_desde_txt': (fecha_desde_txt or '').strip() or '',
        'fecha_hasta_txt': (fecha_hasta_txt or '').strip() or '',
        'orden': orden,
        'total_cargos': total_cargos,
        'total_abonos': total_abonos,
        'saldo_reconstruido': saldo_reconstruido,
        'saldo_actual': saldo_actual,
        'diferencia_saldo': diferencia_saldo,
        'generado_en': datetime.now(),
    }


@app.route('/creditos')
@login_required
@caja_requerida
def modulo_creditos():
    clientes = Cliente.query.filter(Cliente.saldo_deudor > 0).order_by(Cliente.nombre.asc()).all()
    ultimos_abonos = AbonoCredito.query.order_by(AbonoCredito.fecha.desc()).limit(20).all()
    return render_template('modulo_creditos.html', clientes=clientes, ultimos_abonos=ultimos_abonos)


@app.route('/creditos/estado_cuenta/<int:cliente_id>')
@login_required
@caja_requerida
def estado_cuenta_credito(cliente_id):
    ctx = _cartola_credito_context(
        cliente_id,
        request.args.get('desde'),
        request.args.get('hasta'),
        request.args.get('orden', 'desc'),
    )
    if ctx is None:
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('modulo_creditos'))
    return render_template('estado_cuenta_credito.html', **ctx)


@app.route('/creditos/estado_cuenta/<int:cliente_id>/pdf')
@login_required
@caja_requerida
def estado_cuenta_credito_pdf(cliente_id):
    ctx = _cartola_credito_context(
        cliente_id,
        request.args.get('desde'),
        request.args.get('hasta'),
        request.args.get('orden', 'desc'),
    )
    if ctx is None:
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('modulo_creditos'))
    html = render_template('estado_cuenta_credito_pdf.html', **ctx)
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    options = {
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'margin-top': '0.5in',
        'margin-right': '0.5in',
        'margin-bottom': '0.5in',
        'margin-left': '0.5in',
        'quiet': '',
        'enable-local-file-access': None,
    }
    try:
        pdf = pdfkit.from_string(html, False, options=options, configuration=config)
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Cartola_credito_cliente_{cliente_id}.pdf'
        return response
    except Exception as e:
        flash(f'No se pudo generar el PDF: {e}', 'danger')
        return redirect(url_for('estado_cuenta_credito', cliente_id=cliente_id))


@app.route('/creditos/estado_cuenta/<int:cliente_id>/boucher')
@login_required
@caja_requerida
def estado_cuenta_credito_boucher(cliente_id):
    ctx = _cartola_credito_context(
        cliente_id,
        request.args.get('desde'),
        request.args.get('hasta'),
        request.args.get('orden', 'desc'),
    )
    if ctx is None:
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('modulo_creditos'))
    ctx['mostrar_control_interno'] = True
    ctx['saldo_maestro'] = ctx['saldo_actual']
    return render_template('estado_cuenta_credito_boucher.html', **ctx)


@app.route('/registrar_abono', methods=['POST'])
@login_required
@caja_requerida
def registrar_abono():
    cliente_id = request.form.get('cliente_id')
    metodo_pago = request.form.get('metodo_pago', 'Efectivo')
    try:
        monto_abono = float(request.form.get('monto_abono', 0))
    except (TypeError, ValueError):
        flash("Monto de abono inválido.", "warning")
        return redirect(url_for('modulo_creditos'))

    if monto_abono <= 0:
        flash("El monto de abono debe ser mayor a 0.", "warning")
        return redirect(url_for('modulo_creditos'))

    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        flash("Cliente no encontrado.", "danger")
        return redirect(url_for('modulo_creditos'))

    saldo_anterior = cliente.saldo_deudor or 0
    if saldo_anterior <= 0:
        flash("El cliente no registra deuda pendiente.", "info")
        return redirect(url_for('modulo_creditos'))

    caja_activa = obtener_caja_activa()
    if not caja_activa:
        flash("Debe existir una caja abierta para registrar abonos.", "warning")
        return redirect(url_for('abrir_caja'))

    monto_aplicado = min(monto_abono, saldo_anterior)
    nuevo_saldo = saldo_anterior - monto_aplicado
    cliente.saldo_deudor = nuevo_saldo
    if nuevo_saldo <= 0:
        cliente.estado_credito = "Activo"

    abono = AbonoCredito(
        cliente_id=cliente.id,
        monto_abono=monto_aplicado,
        saldo_anterior=saldo_anterior,
        nuevo_saldo=nuevo_saldo,
        metodo_pago=metodo_pago,
        caja_id=caja_activa.id,
        usuario_id=current_user.id,
        comentario=f"Abono registrado por {current_user.nombre}"
    )
    db.session.add(abono)
    db.session.commit()

    if monto_abono > monto_aplicado:
        excedente = monto_abono - monto_aplicado
        flash(
            f"Abono aplicado: ${monto_aplicado:,.0f}. El excedente ${excedente:,.0f} no se aplicó porque la deuda fue cubierta.",
            "info"
        )
    else:
        flash(f"Abono registrado para {cliente.nombre}. Nuevo saldo: ${nuevo_saldo:,.0f}.", "success")

    return render_template(
        'ticket_abono.html',
        abono=abono,
        cliente=cliente,
        caja=caja_activa,
        cajero_nombre=current_user.nombre if current_user.is_authenticated else None,
        auto_print=True
    )


@app.route('/ticket_abono/<int:id>')
@login_required
def ver_ticket_abono(id):
    """Comprobante de abono (reimpresión desde historial)."""
    abono = AbonoCredito.query.get_or_404(id)
    cliente = abono.cliente
    if not cliente:
        flash("Cliente asociado al abono no encontrado.", "danger")
        return redirect(url_for('modulo_creditos'))
    caja = Caja.query.get(abono.caja_id) if abono.caja_id else None
    usr = Usuario.query.get(abono.usuario_id) if abono.usuario_id else None
    cajero_nombre = usr.nombre if usr else "—"
    auto_print = request.args.get("print") == "1"
    return render_template(
        'ticket_abono.html',
        abono=abono,
        cliente=cliente,
        caja=caja,
        cajero_nombre=cajero_nombre,
        auto_print=auto_print
    )


# 8. ABONOS: Registro de pagos a deudas de clientes
class AbonoCredito(db.Model):
    __tablename__ = 'abonos_credito'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    monto_abono = db.Column(db.Float, nullable=False)
    saldo_anterior = db.Column(db.Float)
    nuevo_saldo = db.Column(db.Float)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    metodo_pago = db.Column(db.String(20)) # Efectivo, Debito, etc.
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id')) # Para el cierre de caja
    usuario_id = db.Column(db.Integer) # Quién recibió el pago
    comentario = db.Column(db.Text)

# --- cierre del archivo ---
if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    host = (os.getenv('FLASK_RUN_HOST') or '0.0.0.0').strip() or '0.0.0.0'
    port = int((os.getenv('FLASK_RUN_PORT') or '5000').strip() or '5000')
    app.run(host=host, port=port, debug=debug_mode)
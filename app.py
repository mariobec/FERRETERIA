# --- IMPORTS ---
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import csv
import os
import json
from functools import wraps
from flask_login import current_user, login_required, UserMixin, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
# Busca esta línea y asegúrate de que incluya "text"
from sqlalchemy import text, or_
from sqlalchemy.orm import joinedload
import qrcode
import io
import base64
import pdfkit
from flask import make_response, render_template
# --- CONFIGURACIÓN DE LA APP ---
app = Flask(__name__)
db_uri = (os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI') or '').strip()
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
if not db_uri:
    db_uri = 'mysql+pymysql://mbecerra:clave_segura@localhost/ferreteria'
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clave_secreta_segura')
# En desarrollo, recargar plantillas al guardar (sin depender de debug=True).
# Desactivar explícitamente con FLASK_TEMPLATE_RELOAD=0 si no lo deseas.
if os.getenv('FLASK_TEMPLATE_RELOAD', '1') != '0':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
db = SQLAlchemy(app)

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
    cfg = _config_empresa_default()
    cfg.update({k: (str(v).strip() if v is not None else "") for k, v in data.items() if k in cfg})
    with open(_ruta_config_empresa(), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def usuario_tiene_permiso(nombre_permiso):
    if not current_user.is_authenticated or not getattr(current_user, 'rol', None):
        return False
    rol_nombre = (current_user.rol.nombre or '').strip().lower()
    if rol_nombre in ('admin', 'administrador', 'superadmin', 'super admin'):
        return True
    return any((rp.permiso and rp.permiso.nombre == nombre_permiso) for rp in (current_user.rol.rol_permisos or []))


def usuario_esta_activo(usuario):
    """Compatibilidad: usamos 'perfil' como estado ACTIVO/INACTIVO."""
    return (getattr(usuario, 'perfil', None) or 'ACTIVO').strip().upper() != 'INACTIVO'


def usuario_requiere_cambio_clave(usuario):
    perfil = (getattr(usuario, 'perfil', None) or '').strip().upper()
    return perfil in ('FORZAR_CLAVE', 'ACTIVO_FORZAR_CLAVE')


@app.context_processor
def inject_company_context():
    return {
        'empresa_cfg': obtener_config_empresa(),
        'puede_administrar': usuario_tiene_permiso('gestionar_usuarios'),
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
    return Usuario.query.get(int(user_id))

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
                permisos_rol = [rp.permiso.nombre for rp in current_user.rol.rol_permisos]
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
def caja_requerida(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Buscamos si existe una caja que esté en estado 'Abierta'
        caja_activa = Caja.query.filter_by(estado='Abierta').first()
        if not caja_activa:
            flash("⚠️ ACCESO RESTRINGIDO: Debe realizar la Apertura de Caja.", "warning")
            return redirect(url_for('abrir_caja'))
        return f(*args, **kwargs)
    return decorated_function


def obtener_caja_activa():
    """Retorna la caja abierta más reciente o None."""
    return Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()


@app.before_request
def forzar_cambio_clave_si_corresponde():
    if not current_user.is_authenticated:
        return None
    ep = request.endpoint or ''
    permitidos = {'cambiar_password', 'logout', 'static'}
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

# 1. PRODUCTO: base de todo, se usa en los detalles de venta
class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    codigo_barra = db.Column(db.String(50), unique=True)
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
    ubicacion_pasillo = db.Column(db.String(12))
    ubicacion_estante = db.Column(db.String(12))
    ubicacion_nivel = db.Column(db.String(12))
    activo = db.Column(db.Boolean, default=True)

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
    prioridad = db.Column(db.Integer)

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
        self.monto_total = sum(
            (d.cantidad * d.precio_unitario) * (1 - ((d.descuento or 0) / 100))
            for d in self.detalles
        )
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
    # Si existe tabla de almacenes con FK activa, validamos/buscamos un id válido.
    almacen_id = None
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

    # Si no hay almacén válido, omitimos kardex para no bloquear cobros/ventas.
    if not almacen_id:
        return

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
        stock_saldo=int(stock_saldo) if stock_saldo is not None else None,
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

    for d in detalles:
        producto = Producto.query.get(d.producto_id)
        producto.stock = d.stock_fisico
        diff = abs(d.stock_fisico - d.stock_sistema)
        if diff > 0:
            registrar_movimiento_kardex(
                producto.id,
                'AJUSTE',
                diff,
                f"Ajuste por Auditoría móvil #{auditoria_id}",
                usuario=usr,
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
        return redirect(url_for('punto_venta'))  # si ya está logueado, va al POS
    return render_template('index.html')


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

    dinero_credito = db.session.query(db.func.sum(Cliente.saldo_deudor)).scalar() or 0

    retiros_caja_hoy = db.session.query(db.func.sum(MovimientoCaja.monto)).filter(
        MovimientoCaja.tipo == "Egreso",
        db.func.date(MovimientoCaja.fecha) == db.func.current_date()
    ).scalar() or 0

    hoy = datetime.now().date()
    fecha_hoy_str = hoy.strftime("%Y-%m-%d")
    ventas_hoy_detalle = (
        Venta.query.filter(db.func.date(Venta.fecha) == hoy)
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

    return render_template(
        'inicio.html',
        stock_activo=stock_activo,
        bajo_stock=bajo_stock,
        ventas_hoy=ventas_hoy,
        transacciones=transacciones,
        dinero_credito=dinero_credito,
        retiros_caja_hoy=retiros_caja_hoy,
        ventas_hoy_detalle=ventas_hoy_detalle,
        fecha_hoy_str=fecha_hoy_str,
        labels_grafico=labels_grafico,
        datos_grafico=datos_grafico
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
        .filter(Venta.fecha >= dt_inicio, Venta.fecha < dt_fin_excl)
        .group_by(Producto.nombre)
        .order_by(db.func.sum(DetalleVenta.subtotal).desc())
        .limit(8)
        .all()
    )

    ultimas_ventas = (
        Venta.query.filter(Venta.fecha >= dt_inicio, Venta.fecha < dt_fin_excl)
        .order_by(Venta.id.desc())
        .limit(12)
        .all()
    )

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
        ultimas_ventas=ultimas_ventas,
    )


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


# --- PRODUCTOS ------------------------------------------------------------------------
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


@app.route('/productos')
@login_required
def mostrar_productos():
    query = (request.args.get('q') or '').strip()
    codigo_barra = (request.args.get('codigo_barra') or '').strip()
    categoria = (request.args.get('categoria') or '').strip()
    subcategoria = (request.args.get('subcategoria') or '').strip()
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
    if categoria:
        productos = productos.filter_by(categoria=categoria)
    if subcategoria:
        productos = productos.filter_by(subcategoria=subcategoria)

    categorias = [
        c[0] for c in db.session.query(Producto.categoria)
        .filter(Producto.categoria.isnot(None), Producto.categoria != '')
        .distinct().order_by(Producto.categoria.asc()).all()
    ]
    subcategorias_q = db.session.query(Producto.subcategoria).filter(
        Producto.subcategoria.isnot(None),
        Producto.subcategoria != ''
    )
    if categoria:
        subcategorias_q = subcategorias_q.filter(Producto.categoria == categoria)
    subcategorias = [s[0] for s in subcategorias_q.distinct().order_by(Producto.subcategoria.asc()).all()]

    productos_pagination = productos.order_by(Producto.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    return render_template(
        'productos.html',
        productos=productos_pagination.items,
        productos_pagination=productos_pagination,
        query=query,
        categoria=categoria,
        subcategoria=subcategoria,
        codigo_barra=codigo_barra,
        categorias=categorias,
        subcategorias=subcategorias,
    )


@app.route('/precios/revision')
@login_required
def revision_precios():
    q = (request.args.get('q') or '').strip()
    categoria = (request.args.get('categoria') or '').strip()
    subcategoria = (request.args.get('subcategoria') or '').strip()
    margen_obj = request.args.get('margen_obj', 0.30, type=float)
    terminacion = request.args.get('terminacion', 90, type=int)
    solo_alerta = request.args.get('solo_alerta', '1') == '1'

    productos_q = Producto.query.filter(Producto.activo == True)
    if q:
        like = f"%{q}%"
        productos_q = productos_q.filter((Producto.nombre.like(like)) | (Producto.codigo_barra.like(like)))
    if categoria:
        productos_q = productos_q.filter(Producto.categoria == categoria)
    if subcategoria:
        productos_q = productos_q.filter(Producto.subcategoria == subcategoria)

    productos = productos_q.order_by(Producto.nombre.asc()).limit(1500).all()
    filas = []
    for p in productos:
        costo = float(p.precio_compra or 0)
        venta = float(p.precio_venta or 0)
        sugerido = _precio_sugerido_redondeado(costo, margen_obj, terminacion)
        margen_actual = ((venta - costo) / venta) if venta > 0 and costo > 0 else None
        requiere = sugerido > venta
        if solo_alerta and not requiere:
            continue
        filas.append({
            "id": p.id,
            "codigo": p.codigo_barra,
            "nombre": p.nombre,
            "categoria": p.categoria or "—",
            "subcategoria": p.subcategoria or "—",
            "costo": costo,
            "venta": venta,
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
@login_required
def aplicar_precio_sugerido(producto_id):
    p = Producto.query.get_or_404(producto_id)
    margen_obj = request.form.get('margen_obj', 0.30, type=float)
    terminacion = request.form.get('terminacion', 90, type=int)
    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash("Debes indicar un motivo del cambio de precio.", "warning")
        return redirect(url_for('revision_precios', q=request.form.get('q'), categoria=request.form.get('categoria'), subcategoria=request.form.get('subcategoria'), margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))

    sugerido = _precio_sugerido_redondeado(p.precio_compra or 0, margen_obj, terminacion)
    if sugerido > 0:
        precio_anterior = float(p.precio_venta or 0)
        p.precio_venta = sugerido
        p.precio_mayoreo = p.precio_mayoreo or sugerido
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
@login_required
def aplicar_precio_sugerido_masivo():
    q = (request.form.get('q') or '').strip()
    categoria = (request.form.get('categoria') or '').strip()
    subcategoria = (request.form.get('subcategoria') or '').strip()
    margen_obj = request.form.get('margen_obj', 0.30, type=float)
    terminacion = request.form.get('terminacion', 90, type=int)

    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash("Debes indicar un motivo para la actualización masiva.", "warning")
        return redirect(url_for('revision_precios', q=q, categoria=categoria, subcategoria=subcategoria, margen_obj=margen_obj, terminacion=terminacion, solo_alerta=request.form.get('solo_alerta', '1')))

    productos_q = Producto.query.filter(Producto.activo == True)
    if q:
        like = f"%{q}%"
        productos_q = productos_q.filter((Producto.nombre.like(like)) | (Producto.codigo_barra.like(like)))
    if categoria:
        productos_q = productos_q.filter(Producto.categoria == categoria)
    if subcategoria:
        productos_q = productos_q.filter(Producto.subcategoria == subcategoria)

    aplicados = 0
    for p in productos_q.all():
        sugerido = _precio_sugerido_redondeado(p.precio_compra or 0, margen_obj, terminacion)
        if sugerido > float(p.precio_venta or 0):
            precio_anterior = float(p.precio_venta or 0)
            p.precio_venta = sugerido
            p.precio_mayoreo = p.precio_mayoreo or sugerido
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

# filtros rápidos para productos........................................................................

@app.route('/productos/filtro/<string:tipo>')
@login_required
def filtrar_productos(tipo):
    if tipo == "sin_stock":
        productos = Producto.query.filter_by(stock=0).all()
    elif tipo == "activos":
        productos = Producto.query.filter_by(activo=True).all()
    elif tipo == "venta":
        productos = Producto.query.filter(
            Producto.stock > 0,
            Producto.precio_venta > 0,
            Producto.activo == True
        ).all()
    else:
        productos = Producto.query.all()
    categorias = [
        c[0] for c in db.session.query(Producto.categoria)
        .filter(Producto.categoria.isnot(None), Producto.categoria != '')
        .distinct().order_by(Producto.categoria.asc()).all()
    ]
    subcategorias = [
        s[0] for s in db.session.query(Producto.subcategoria)
        .filter(Producto.subcategoria.isnot(None), Producto.subcategoria != '')
        .distinct().order_by(Producto.subcategoria.asc()).all()
    ]
    return render_template(
        'productos.html',
        productos=productos,
        query='',
        categoria='',
        subcategoria='',
        codigo_barra='',
        categorias=categorias,
        subcategorias=subcategorias
    )

@app.route('/toggle_producto/<int:id>', methods=['POST'])
@login_required
def toggle_producto(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = not producto.activo
    db.session.commit()
    return redirect(url_for('mostrar_productos'))

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
        categoria=request.form.get('categoria'),
        subcategoria=request.form.get('subcategoria'),
        ubicacion_pasillo=(request.form.get('ubicacion_pasillo') or '').strip() or None,
        ubicacion_estante=(request.form.get('ubicacion_estante') or '').strip() or None,
        ubicacion_nivel=(request.form.get('ubicacion_nivel') or '').strip() or None,
        activo=True
    )
    db.session.add(nuevo_p)
    db.session.commit()
    return redirect(url_for('mostrar_productos'))
#..............................................................................................
@app.route('/cargar_productos', methods=['POST'])
@login_required
def cargar_productos():
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        flash("Debe seleccionar un archivo CSV.", "warning")
        return redirect(url_for('mostrar_productos'))
    if not archivo.filename.lower().endswith('.csv'):
        flash("Formato inválido. Debe subir un archivo .csv (no Excel).", "warning")
        return redirect(url_for('mostrar_productos'))

    # En producción (Render) los CSV suelen venir con codificaciones mixtas.
    # Limitamos tamaño para evitar OOM en plan free y decodificamos con fallback.
    contenido = archivo.read()
    if len(contenido) > 5 * 1024 * 1024:
        flash("El CSV excede 5MB. Divida el archivo en bloques.", "warning")
        return redirect(url_for('mostrar_productos'))
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
    creados = 0
    actualizados = 0
    omitidos = 0
    duplicados_archivo = 0
    cache_por_codigo = {}

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

    for row in reader:
        codigo = _clip(row.get('codigo_barra'), 50)
        nombre = _clip(row.get('nombre'), 100)
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
        prod.precio_compra = _to_float(row.get('precio_compra', 0), 0)
        prod.precio_venta = _to_float(row.get('precio_venta', 0), 0)
        prod.precio_mayoreo = _to_float(row.get('precio_mayoreo', 0), 0)
        prod.unidad = _clip(row.get('unidad_venta') or row.get('unidad') or "Unidad", 20)
        prod.unidad_compra = _clip(row.get('unidad_compra') or row.get('unidad_venta') or row.get('unidad') or "Unidad", 20)
        prod.unidad_venta = _clip(row.get('unidad_venta') or row.get('unidad') or "Unidad", 20)
        prod.factor_conversion = _to_float(row.get('factor_conversion', 1), 1) or 1
        prod.stock = _to_int(row.get('stock', 0), 0)
        prod.categoria = _clip(row.get('categoria'), 50) or None
        prod.subcategoria = _clip(row.get('subcategoria'), 50) or None
        prod.ubicacion_pasillo = _clip(row.get('ubicacion_pasillo'), 12) or None
        prod.ubicacion_estante = _clip(row.get('ubicacion_estante'), 12) or None
        prod.ubicacion_nivel = _clip(row.get('ubicacion_nivel'), 12) or None
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
    flash(
        f"Carga completada. Creados: {creados} | Actualizados: {actualizados} | Omitidos: {omitidos} | Duplicados en archivo: {duplicados_archivo}.",
        "success",
    )
    return redirect(url_for('mostrar_productos'))

@app.route('/descargar_plantilla_productos')
def descargar_plantilla_productos():
    contenido = "nombre,codigo_barra,precio_compra,precio_venta,precio_mayoreo,unidad_compra,unidad_venta,factor_conversion,stock,categoria,subcategoria,ubicacion_pasillo,ubicacion_estante,ubicacion_nivel\n"
    contenido += "Tornillo Zincado 1in,123456,12000,180,160,Caja,Unidad,100,3500,Herramientas,Tornillos,P02,E04,N1\n"
    contenido += "Cadena galvanizada,789012,650,1200,1100,Rollo,Metro,25,400,Construcción,Cadenas,P05,E01,N2\n"
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

    total_proveedores = Proveedor.query.count()
    proveedores_con_telefono = Proveedor.query.filter(Proveedor.telefono.isnot(None), Proveedor.telefono != '').count()
    proveedores_con_email = Proveedor.query.filter(Proveedor.email.isnot(None), Proveedor.email != '').count()

    return render_template(
        'provedores.html',
        proveedores=proveedores,
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

    if not nombre:
        flash("El nombre del proveedor es obligatorio.", "warning")
        return redirect(url_for('mostrar_proveedores'))

    prov.nombre = nombre
    prov.contacto = contacto or None
    prov.telefono = telefono or None
    prov.email = email or None
    db.session.commit()
    flash("Proveedor actualizado correctamente.", "success")
    return redirect(url_for('mostrar_proveedores'))


@app.route('/eliminar_proveedor/<int:id>', methods=['POST'])
@login_required
def eliminar_proveedor(id):
    prov = Proveedor.query.get_or_404(id)
    try:
        db.session.delete(prov)
        db.session.commit()
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
        if (prod.stock or 0) < consumo_stock:
            db.session.rollback()
            flash(
                f"Stock insuficiente para {prod.nombre}. "
                f"Requiere {consumo_stock} {prod.unidad_venta_final} y hay {prod.stock}.",
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
        prod.stock -= consumo_stock
        registrar_movimiento_kardex(
            prod.id,
            'SALIDA',
            consumo_stock,
            f"Venta directa #{nueva_venta.id} ({metodo_seleccionado})"
            f" ({cant} {prod.unidad_venta_final} -> {consumo_stock} stock)",
            usuario=current_user.nombre,
            referencia_tipo='venta',
            referencia_id=nueva_venta.id,
            stock_saldo=prod.stock,
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


# proceso de punto de venta, creación de venta abierta y manejo de vales pendientes........................................
@app.route('/punto_venta')
@login_required      # Verifica que el usuario esté logueado
@caja_requerida     # <--- ESTA ES LA LÍNEA QUE FALTA
def punto_venta():
    # Buscar la última caja abierta
    caja = obtener_caja_activa()
    if not caja:
        flash("No hay caja abierta. Debe abrir la caja antes de usar el punto de venta.")
        return redirect(url_for('mostrar_ventas'))

    # Buscar la última venta abierta del turno actual (no de otra caja)
    venta = Venta.query.filter_by(estado="Abierta", caja_id=caja.id).order_by(Venta.id.desc()).first()
    if not venta:
        venta = Venta(
            usuario="POS",
            estado="Abierta",
            monto_total=0,
            caja_id=caja.id,
            fecha=db.func.current_timestamp()
        )
        db.session.add(venta)
        db.session.commit()

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

    # Renderizar la plantilla con los datos
    return render_template(
        'punto_venta.html',
        venta=venta,
        detalles=detalles,
        vales_pendientes=vales_pendientes,
        cliente=cliente,
        factores_stock=factores_stock,
        consumos_stock=consumos_stock,
    )


# proceso de agregar productos a venta abierta desde punto de venta........................................

@app.route('/agregar_producto_venta', methods=['POST'])
@login_required
@caja_requerida
def agregar_producto_venta():
    codigo = request.form['codigo']
    caja = obtener_caja_activa()
    if not caja:
        flash("No hay caja abierta para operar en Punto de Venta.", "warning")
        return redirect(url_for('abrir_caja'))

    producto = Producto.query.filter_by(codigo_barra=codigo).first()
    if not producto:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for('punto_venta'))

    if (producto.stock or 0) <= 0:
        flash(f"Sin stock disponible para {producto.nombre}.", "warning")
        return redirect(url_for('punto_venta'))

    venta = Venta.query.filter_by(estado="Abierta", caja_id=caja.id).order_by(Venta.id.desc()).first()
    if not venta:
        venta = Venta(
            usuario="POS",
            estado="Abierta",
            monto_total=0,
            caja_id=caja.id,
            fecha=db.func.current_timestamp()
        )
        db.session.add(venta)
        db.session.flush()

    cantidad = 1
    precio_unitario = producto.precio_venta
    detalle = DetalleVenta(
        id_venta=venta.id,
        id_producto=producto.id,
        cantidad=cantidad,
        precio_unitario=precio_unitario
    )
    db.session.add(detalle)
    venta.total += cantidad * precio_unitario
    db.session.commit()
    return redirect(url_for('punto_venta'))

# proceso de eliminar producto de venta abierta desde punto de venta........................................

@app.route('/eliminar_detalle/<int:id>', methods=['POST'])
@login_required
@caja_requerida
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
def finalizar_venta():
    caja = obtener_caja_activa()
    if not caja:
        flash("No hay caja abierta para emitir vale.", "warning")
        return redirect(url_for('abrir_caja'))

    # Buscar la última venta abierta
    venta = Venta.query.filter_by(estado="Abierta", caja_id=caja.id).order_by(Venta.id.desc()).first()
    if not venta or venta.monto_total == 0:
        flash("Error: La venta está vacía.", "danger")
        return redirect(url_for('punto_venta'))

    nombre = request.form.get('cliente_nombre')
    direccion = request.form.get('cliente_direccion')
    telefono = request.form.get('cliente_telefono')
    correo = request.form.get('cliente_correo')
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
            cliente.telefono = telefono or cliente.telefono
            cliente.correo = correo or cliente.correo

            if nombre and nombre != cliente.nombre:
                flash("El cliente ya existe, no puedes cambiar el nombre.", "warning")
                return redirect(url_for('punto_venta'))
        else:
            if not nombre:
                flash("Error: Nombre es obligatorio para nuevo cliente.", "danger")
                return redirect(url_for('punto_venta'))
            cliente = Cliente(nombre=nombre, rut=rut,
                              direccion=direccion, telefono=telefono, correo=correo)
            db.session.add(cliente)

    db.session.commit()

    # Marcar la venta como pendiente y asignar prioridad
    pendientes = Venta.query.filter_by(estado="Pendiente").count()
    venta.prioridad = pendientes + 1
    venta.cliente_id = cliente.id
    venta.estado = "Pendiente"
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
def editar_venta(id):
    venta = Venta.query.get_or_404(id)
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

# proceso de actualización de cantidad y descuento en venta abierta desde punto de venta........................................
@app.route('/actualizar_item', methods=['POST'])
@login_required
@caja_requerida
def actualizar_item():
    detalle_id = request.form.get('actualizar')
    try:
        cantidad = int(request.form.get(f'cantidad_{detalle_id}', 1))
        descuento = float(request.form.get(f'descuento_{detalle_id}', 0))
    except (TypeError, ValueError):
        flash("Cantidad o descuento inválido.", "warning")
        return redirect(url_for('punto_venta'))

    if cantidad <= 0:
        flash("La cantidad debe ser mayor a 0.", "warning")
        return redirect(url_for('punto_venta'))
    if descuento < 0:
        flash("El descuento no puede ser negativo.", "warning")
        return redirect(url_for('punto_venta'))
    if descuento > 100:
        flash("El descuento no puede ser mayor al 100%.", "warning")
        return redirect(url_for('punto_venta'))

    caja_activa = obtener_caja_activa()
    detalle = DetalleVenta.query.get(detalle_id)
    if detalle:
        if not detalle.venta or detalle.venta.estado != "Abierta" or detalle.venta.caja_id != (caja_activa.id if caja_activa else None):
            flash("No puede modificar ítems fuera de la venta activa del turno.", "warning")
            return redirect(url_for('punto_venta'))
        if detalle.producto and (detalle.producto.stock + detalle.cantidad) < cantidad:
            disponible = detalle.producto.stock + detalle.cantidad
            flash(f"Stock insuficiente. Disponible máximo: {disponible}.", "warning")
            return redirect(url_for('punto_venta'))
        detalle.cantidad = cantidad
        detalle.descuento = descuento
        detalle.subtotal = (detalle.precio_unitario * cantidad) * (1 - (descuento / 100))
        db.session.commit()

        # Recalcular el total de la venta
        detalle.venta.recalcular_total()
        db.session.commit()

    return redirect(url_for('punto_venta'))


# CAJA vales pendientes
@app.route('/caja/vales_pendientes')
def caja_pendientes():
    hoy = datetime.now().date()

    # Indicadores
    tickets_emitidos = Venta.query.filter(Venta.fecha >= hoy).count()

    caja_apertura = Caja.query.filter_by(estado="Abierta").order_by(Caja.fecha_apertura.desc()).first()
    monto_apertura = caja_apertura.monto_inicial if caja_apertura else 0

    monto_vendido = db.session.query(db.func.sum(Venta.monto_total)).filter(Venta.estado == "Pagado").scalar() or 0
    monto_pendiente = db.session.query(db.func.sum(Venta.monto_total)).filter(Venta.estado == "Pendiente").scalar() or 0
    vuelto_entregado = db.session.query(db.func.sum(Venta.vuelto)).filter(Venta.fecha >= hoy).scalar() or 0

    # Vales pendientes de cobro en caja (aún sin método de pago definido)
    vales = Venta.query.filter(
        Venta.estado == "Pendiente",
        Venta.metodo_pago.is_(None)
    ).order_by(Venta.fecha.desc()).all()

    # Créditos registrados hoy para control operativo de caja
    creditos_hoy = Venta.query.filter(
        Venta.fecha >= hoy,
        Venta.metodo_pago == "Credito"
    ).order_by(Venta.fecha.desc()).limit(15).all()

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


@app.route('/procesar_cobro_caja/<int:id>', methods=['POST'])
@login_required
@caja_requerida
def procesar_cobro_caja(id):
    venta = Venta.query.get_or_404(id)
    caja_activa = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    metodo = request.form.get('metodo_pago')
    tipo_doc = request.form.get('tipo_documento', 'Boleta')
    if venta.metodo_pago is not None:
        flash(f"El vale #{venta.id} ya fue procesado anteriormente.", "info")
        return redirect(url_for('caja_pendientes'))

    try:
        monto_recibido = float(request.form.get('monto_recibido', 0))
    except (TypeError, ValueError):
        flash("Monto recibido inválido.", "warning")
        return redirect(url_for('caja_pendientes'))
    if monto_recibido < 0:
        flash("El monto recibido no puede ser negativo.", "warning")
        return redirect(url_for('caja_pendientes'))
    
    try: # <--- ESTA PALABRA ES LA QUE FALTA
        venta.metodo_pago = metodo
        venta.tipo_documento = tipo_doc
        venta.caja_id = caja_activa.id
        venta.fecha = datetime.now()
        venta.desglosar_iva()

        if metodo == "Credito":
            venta.estado = "Pendiente"
            venta.monto_recibido = 0
            venta.vuelto = 0
            if venta.cliente:
                venta.cliente.saldo_deudor = (venta.cliente.saldo_deudor or 0) + venta.monto_total
        else:
            if monto_recibido < venta.monto_total:
                flash("El monto recibido no puede ser menor al total para pagos no crédito.", "warning")
                return redirect(url_for('caja_pendientes'))
            venta.estado = "Pagado"
            venta.monto_recibido = monto_recibido
            venta.vuelto = monto_recibido - venta.monto_total

        for d in venta.detalles:
            producto = Producto.query.get(d.id_producto)
            if producto:
                factor_venta_stock = _factor_venta_a_stock(producto)
                consumo_stock = int(round((d.cantidad or 0) * factor_venta_stock))
                if consumo_stock <= 0:
                    raise ValueError(f"Conversión inválida para {producto.nombre}.")
                if (producto.stock or 0) < consumo_stock:
                    raise ValueError(f"Stock insuficiente para {producto.nombre}.")
                producto.stock -= consumo_stock
                registrar_movimiento_kardex(
                    producto.id,
                    'SALIDA',
                    consumo_stock,
                    f"Cobro vale/venta #{venta.id} ({metodo})"
                    f" ({d.cantidad} {producto.unidad_venta_final} -> {consumo_stock} stock)",
                    usuario=current_user.nombre,
                    referencia_tipo='venta',
                    referencia_id=venta.id,
                    stock_saldo=producto.stock,
                )

        db.session.commit()
        
        if metodo == "Credito":
            flash(f"Vale #{venta.id} registrado a crédito para {venta.cliente.nombre if venta.cliente else 'cliente'}.", "success")
        else:
            flash(f"¡Venta #{venta.id} finalizada! Vuelto: ${venta.vuelto:,.0f}", "success")
        return redirect(url_for('caja_pendientes', ultima_venta=venta.id))

    except Exception as e: # <--- Ahora este except sí tiene su try
        db.session.rollback()
        flash(f"Error crítico al procesar pago: {str(e)}", "danger")
        return redirect(url_for('caja_pendientes'))

# busca productos por código o nombre para agregar en venta........................................
@app.route('/buscar_producto')
def buscar_producto():
    q = request.args.get('q', '')
    productos = Producto.query.filter(
        (Producto.nombre.like(f"%{q}%")) |
        (Producto.codigo_barra.like(f"%{q}%"))
    ).limit(20).all()

    results = []
    for p in productos:
        results.append({
            "id": p.codigo_barra,
            "producto_id": p.id,
            "text": f"{p.nombre} ({p.codigo_barra})"
        })

    return {"results": results}

# proceso de apertura de caja desde pantalla de caja........................................................................

@app.route('/abrir_caja', methods=['GET', 'POST'])
@login_required
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
def cerrar_caja():
    # 1. Buscamos la caja activa
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    
    if not caja:
        flash("No hay ninguna caja abierta para cerrar.", "info")
        return redirect(url_for('index'))

    # 2. Cálculos de VENTAS del turno
    ventas = Venta.query.filter_by(caja_id=caja.id).all()

    def _metodo_pago(v):
        return (v.metodo_pago or "").strip()

    total_efectivo = sum(v.monto_total for v in ventas if _metodo_pago(v) == "Efectivo") or 0
    total_debito = sum(v.monto_total for v in ventas if _metodo_pago(v) == "Debito") or 0
    total_transferencia = sum(v.monto_total for v in ventas if _metodo_pago(v) == "Transferencia") or 0
    total_fiado = sum(v.monto_total for v in ventas if _metodo_pago(v).lower() == "credito") or 0

    ventas_turno = [v for v in ventas if v.estado != "Abierta"]
    ventas_turno.sort(key=lambda x: x.fecha or datetime.min, reverse=True)
    
    # 3. Cálculos de ABONOS (Dinero de deudas cobrado hoy)
    # Importante: Esto suma dinero real a la caja
    abonos_hoy = AbonoCredito.query.filter_by(caja_id=caja.id).all()
    total_abonos_efectivo = sum(a.monto_abono for a in abonos_hoy if a.metodo_pago == "Efectivo") or 0
    total_abonos_otros = sum(a.monto_abono for a in abonos_hoy if a.metodo_pago != "Efectivo") or 0
    
    # 4. Movimientos manuales de Caja (Ingresos/Egresos)
    ingresos_manuales = sum(m.monto for m in caja.movimientos if m.tipo == "Ingreso") or 0
    egresos = sum(m.monto for m in caja.movimientos if m.tipo == "Egreso") or 0
    
    # 5. MONTO TEÓRICO EN GAVETA (Lo que Ana debe entregar en billetes/monedas)
    # Inicial + Ventas Efec + Abonos Efec + Ingresos Manuales - Gastos
    monto_teorico = (caja.monto_inicial + total_efectivo + total_abonos_efectivo + ingresos_manuales) - egresos
    
    # 6. GRAN TOTAL DE MOVIMIENTOS (Productividad total)
    gran_total_dia = total_efectivo + total_debito + total_transferencia + total_fiado + total_abonos_efectivo + total_abonos_otros

    if request.method == 'POST':
        # Procesamos el cierre oficial
        caja.fecha_cierre = datetime.now()
        caja.monto_final = monto_teorico 
        caja.estado = "Cerrada"
        caja.usuario_cierre = current_user.nombre
        
        db.session.commit()
        
        # Redirigimos al ticket con toda la info
        return render_template('ticket_cierre.html', 
                               caja=caja, 
                               total_efectivo=total_efectivo,
                               total_debito=total_debito,
                               total_transferencia=total_transferencia,
                               total_abonos=(total_abonos_efectivo + total_abonos_otros),
                               total_fiado=total_fiado,
                               ingresos=ingresos_manuales, 
                               egresos=egresos,
                               gran_total_ventas=gran_total_dia,
                               ventas_turno=ventas_turno)

    # Si es GET, mostramos la pantalla de confirmación
    return render_template('confirmar_cierre.html', 
                           caja=caja, 
                           total_efectivo=total_efectivo,
                           total_debito=total_debito,
                           total_transferencia=total_transferencia,
                           total_fiado=total_fiado,
                           ingresos=ingresos_manuales,
                           egresos=egresos,
                           monto_teorico=monto_teorico,
                           gran_total_ventas=gran_total_dia,
                           ventas_count=len(ventas),
                           ventas_turno=ventas_turno)

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

@app.route('/consultar_cliente')
def consultar_cliente():
    rut = request.args.get('rut')
    cliente = Cliente.query.filter_by(rut=rut).first()

    if cliente:
        return jsonify({
            "existe": True,
            "cliente": {
                "nombre": cliente.nombre,
                "direccion": cliente.direccion,
                "telefono": cliente.telefono,
                "correo": cliente.correo
            }
        })
    else:
        return jsonify({"existe": False})

# --- PROCESO DE LOGIN Y LOGOUT ---......................................................
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, lo mandamos al index directamente
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')
        usuario = Usuario.query.filter_by(correo=correo).first()

        if usuario and usuario.check_password(password):
            if not usuario_esta_activo(usuario):
                flash("Tu cuenta está desactivada. Contacta al administrador.", "warning")
                return redirect(url_for('login'))
            login_user(usuario)
            if usuario_requiere_cambio_clave(usuario):
                flash("Por seguridad, cambia tu contraseña temporal.", "warning")
                return redirect(url_for('cambiar_password'))
            flash(f"Bienvenido al sistema, {usuario.nombre}", "success")
            
            # CAMBIO CLAVE: Al ir al 'index', se activa el decorador @caja_requerida
            # Si no hay caja abierta, el sistema lo mandará a 'abrir_caja'
            return redirect(url_for('index'))
        else:
            flash("Correo o contraseña incorrectos. Intente de nuevo.", "danger")

    return render_template('login.html')


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
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "info")
    # Redirige a 'index', que es la página con el fondo de ferretería
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
        }
        if not (data["nombre_comercial"] or '').strip():
            flash("El nombre comercial es obligatorio.", "warning")
            return redirect(url_for('admin_empresa'))
        cfg = guardar_config_empresa(data)
        flash("Datos de empresa actualizados correctamente.", "success")
    return render_template('admin_empresa.html', empresa=cfg)


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

# API para el Escáner Móvil.............................................................
@app.route('/api/buscar_producto/<codigo>')
@login_required
def api_buscar_producto(codigo):
    # Busca por código de barras
    producto = Producto.query.filter_by(codigo_barra=codigo).first()
    
    if producto:
        return jsonify({
            "status": "success",
            "id": producto.id,
            "nombre": producto.nombre,
            "stock": producto.stock
        })
    
    return jsonify({"status": "error", "message": "No existe"}), 404
@app.route('/finalizar_auditoria/<int:auditoria_id>', methods=['POST'])
@login_required

# Esta ruta se llama desde el botón "Finalizar Auditoría" en la pantalla de auditorías. Solo alguien con el permiso 'admin_inventario' puede acceder a esta función, que procesa los resultados de la auditoría, ajusta el stock maestro y registra los movimientos en el Kardex.
@permisos_required('admin_inventario') # Solo alguien con rango puede ajustar
def finalizar_auditoria(auditoria_id):
    auditoria = AuditoriaInventario.query.get_or_404(auditoria_id)
    detalles = DetalleAuditoria.query.filter_by(auditoria_id=auditoria_id).all()

    for d in detalles:
        # 1. Identificar el producto
        producto = Producto.query.get(d.producto_id)
        
        # 2. Calcular la diferencia (Fisico - Sistema)
        diferencia = d.stock_fisico - d.stock_sistema
        
        if diferencia != 0:
            producto.stock = d.stock_fisico
            registrar_movimiento_kardex(
                producto.id,
                'AJUSTE',
                abs(diferencia),
                f"Ajuste por Auditoría #{auditoria_id}",
                usuario=current_user.nombre,
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

    factor_compra_stock = _factor_compra_a_stock(producto)
    ingreso_stock = int(round(cant_fis * factor_compra_stock))
    if ingreso_stock <= 0:
        return "El factor de conversión genera ingreso de stock inválido.", None

    producto.stock = (producto.stock or 0) + ingreso_stock
    if recepcion.estado == 'Pendiente':
        recepcion.estado = 'Incompleta'

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
        referencia_tipo='recepcion',
        referencia_id=recepcion.id,
        stock_saldo=producto.stock,
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
    
    # Registrar el hallazgo del bodeguero
    nuevo_detalle = DetalleAuditoria(
        auditoria_id=data['auditoria_id'],
        producto_id=data['producto_id'],
        stock_sistema=producto.stock, # Lo que hay hoy
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
    if request.method == 'POST':
        try:
            prov_id = int(request.form.get('proveedor_id', 0))
        except (TypeError, ValueError):
            prov_id = 0
        doc_tipo = request.form.get('documento_tipo', 'Factura')
        doc_num = (request.form.get('documento_numero') or '').strip()
        if not prov_id:
            flash('Seleccione proveedor.', 'warning')
            return render_template('recepcion_nueva.html', proveedores=proveedores)
        if doc_tipo not in ('Factura', 'Guia de Despacho'):
            doc_tipo = 'Factura'
        if not doc_num:
            flash('Indique número de factura o guía.', 'warning')
            return render_template('recepcion_nueva.html', proveedores=proveedores)
        rec = RecepcionCompra(
            proveedor_id=prov_id,
            documento_tipo=doc_tipo,
            documento_numero=doc_num,
            usuario_bodega=current_user.nombre,
            estado='Pendiente',
        )
        db.session.add(rec)
        db.session.commit()
        _guardar_doc_recepcion(rec.id, request.files.get('documento_archivo'))
        flash('Recepción creada. Agregue productos y cantidades recibidas.', 'success')
        return redirect(url_for('detalle_recepcion', rid=rec.id))
    return render_template('recepcion_nueva.html', proveedores=proveedores)


@app.route('/recepciones/<int:rid>', methods=['GET', 'POST'])
@login_required
def detalle_recepcion(rid):
    rec = RecepcionCompra.query.options(
        joinedload(RecepcionCompra.proveedor),
        joinedload(RecepcionCompra.detalles).joinedload(DetalleRecepcion.producto),
    ).get_or_404(rid)

    if request.method == 'POST' and rec.estado in ('Pendiente', 'Incompleta'):
        action = request.form.get('action')
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
    return render_template('recepcion_detalle.html', recepcion=rec, tiene_documento=tiene_documento)


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


@app.route('/creditos')
@login_required
@caja_requerida
def modulo_creditos():
    clientes = Cliente.query.filter(Cliente.saldo_deudor > 0).order_by(Cliente.nombre.asc()).all()
    ultimos_abonos = AbonoCredito.query.order_by(AbonoCredito.fecha.desc()).limit(20).all()
    return render_template('modulo_creditos.html', clientes=clientes, ultimos_abonos=ultimos_abonos)


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
    app.run(debug=os.getenv('FLASK_DEBUG', '0') == '1')
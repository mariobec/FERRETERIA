# --- IMPORTS ---
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import csv
from io import TextIOWrapper
from functools import wraps
from flask_login import current_user, login_required, UserMixin, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
# Busca esta línea y asegúrate de que incluya "text"
from sqlalchemy import text
# --- CONFIGURACIÓN DE LA APP ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://mbecerra:clave_segura@localhost/ferreteria'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave_secreta_segura'
db = SQLAlchemy(app)


# --- LOGIN MANAGER ---.........................................................................
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # nombre de la ruta de login
login_manager.login_message = "Debes iniciar sesión para acceder a esta página."
login_manager.login_message_category = "warning"
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
    stock = db.Column(db.Integer)
    categoria = db.Column(db.String(50))
    subcategoria = db.Column(db.String(50))
    activo = db.Column(db.Boolean, default=True)

# --- VENTA ---
class Venta(db.Model):
    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    monto_total = db.Column(db.Float, nullable=False, default=0.0)
    usuario = db.Column(db.String(50))

    estado = db.Column(db.String(20), default="Pendiente")
    metodo_pago = db.Column(db.String(20), nullable=True)
    monto_recibido = db.Column(db.Float, nullable=True)
    vuelto = db.Column(db.Float, nullable=True)

    # Relación con caja
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=True)
    caja = db.relationship('Caja', back_populates='ventas')

    # Relación con cliente
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    cliente = db.relationship('Cliente', backref='ventas')

    # Campo de prioridad
    prioridad = db.Column(db.Integer)

  # Relación con detalles (usa id_venta en la tabla detalle_ventas)
    detalles = db.relationship(
        'DetalleVenta',
        backref='venta',
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Método para recalcular el total automáticamente
    def recalcular_total(self):
        self.monto_total = sum(
            (d.cantidad * d.precio_unitario) - (d.descuento or 0)
            for d in self.detalles
        )

    @property
    def total(self):
        return self.monto_total

    @total.setter
    def total(self, value):
        self.monto_total = float(value) if value else 0.0
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
    concepto = db.Column(db.String(100))
    monto = db.Column(db.Float, nullable=False)


# 6. PROVEEDOR: datos de proveedores
class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(100))
    rfc = db.Column(db.String(20))


# 7. CLIENTE: datos de clientes
class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    rut = db.Column(db.String(12), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    giro = db.Column(db.String(100))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    correo = db.Column(db.String(100))


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
# --- MODELOS PARA LOGÍSTICA Y BODEGA ---

class RecepcionCompra(db.Model):
    __tablename__ = 'recepciones_compra'
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    documento_tipo = db.Column(db.Enum('Factura', 'Guia de Despacho'), nullable=False)
    documento_numero = db.Column(db.String(50), nullable=False)
    fecha_recepcion = db.Column(db.DateTime, default=db.func.current_timestamp())
    usuario_bodega = db.Column(db.String(100))
    estado = db.Column(db.Enum('Pendiente', 'Incompleta', 'Finalizada'), default='Pendiente')
    
    detalles = db.relationship('DetalleRecepcion', backref='recepcion', lazy=True)

class DetalleRecepcion(db.Model):
    __tablename__ = 'detalle_recepcion'
    id = db.Column(db.Integer, primary_key=True)
    recepcion_id = db.Column(db.Integer, db.ForeignKey('recepciones_compra.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad_documento = db.Column(db.Integer, nullable=False)
    cantidad_recibida = db.Column(db.Integer, nullable=False)

class AuditoriaInventario(db.Model):
    __tablename__ = 'auditorias_inventario'
    id = db.Column(db.Integer, primary_key=True)
    fecha_inicio = db.Column(db.DateTime, default=db.func.current_timestamp())
    fecha_fin = db.Column(db.DateTime, nullable=True)
    usuario_auditor = db.Column(db.String(100))
    sector_bodega = db.Column(db.String(50))
    estado = db.Column(db.Enum('En Proceso', 'Finalizada', 'Ajustada'), default='En Proceso')

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
    
    for d in detalles:
        producto = Producto.query.get(d.producto_id)
        # Actualizamos el stock real al stock contado
        producto.stock = d.stock_fisico 
        
        # Registramos el movimiento en el Kardex para auditoría futura
        mov = MovimientoInventario(
            id_producto=producto.id,
            id_almacen=1,
            tipo_movimiento='AJUSTE',
            cantidad=abs(d.stock_fisico - d.stock_sistema),
            motivo=f"Ajuste por Auditoría Móvil #{auditoria_id}",
            usuario=current_user.nombre
        )
        db.session.add(mov)
    
    db.session.commit()


# --- RUTAS DE NAVEGACIÓN ---
# Página de inicio, redirige a punto de venta si ya está logueado, sino muestra bienvenida
@app.route('/')
@app.route('/index')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('punto_venta'))  # si ya está logueado, va al POS
    return render_template('index.html')
# --- INICIO - DASHBOARD ---........................................................................
@app.route('/')
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
        labels_grafico=labels_grafico,
        datos_grafico=datos_grafico
    )


# --- PRODUCTOS ------------------------------------------------------------------------
@app.route('/productos')
def mostrar_productos():
    query = request.args.get('q', '')
    categoria = request.args.get('categoria', '')
    productos = Producto.query
    if query:
        productos = productos.filter(
            (Producto.nombre.like(f"%{query}%")) |
            (Producto.codigo_barra.like(f"%{query}%"))
        )
    if categoria:
        productos = productos.filter_by(categoria=categoria)
    productos = productos.all()
    return render_template('productos.html', productos=productos)

# filtros rápidos para productos........................................................................

@app.route('/productos/filtro/<string:tipo>')
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
    return render_template('productos.html', productos=productos)

@app.route('/toggle_producto/<int:id>')
def toggle_producto(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = not producto.activo
    db.session.commit()
    return redirect(url_for('mostrar_productos'))

#guardar nuevo producto desde formulario........................................................................

@app.route('/guardar_producto', methods=['POST'])
def guardar_producto():
    nuevo_p = Producto(
        nombre=request.form['nombre'],
        codigo_barra=request.form['codigo'],
        precio_compra=request.form['p_compra'],
        precio_venta=request.form['p_venta'],
        precio_mayoreo=request.form.get('p_mayoreo'),
        unidad=request.form.get('unidad'),
        stock=request.form['stock'],
        categoria=request.form.get('categoria'),
        subcategoria=request.form.get('subcategoria'),
        activo=True
    )
    db.session.add(nuevo_p)
    db.session.commit()
    return redirect(url_for('mostrar_productos'))
#..............................................................................................
@app.route('/cargar_productos', methods=['POST'])
def cargar_productos():
    archivo = request.files['archivo']
    if not archivo:
        return "No se subió archivo", 400
    try:
        stream = TextIOWrapper(archivo.stream, encoding='utf-8')
        reader = csv.DictReader(stream)
    except UnicodeDecodeError:
        archivo.stream.seek(0)
        stream = TextIOWrapper(archivo.stream, encoding='latin-1')
        reader = csv.DictReader(stream)
    for row in reader:
        nuevo_p = Producto(
            nombre=row.get('nombre'),
            codigo_barra=row.get('codigo_barra'),
            precio_compra=float(row.get('precio_compra', 0)),
            precio_venta=float(row.get('precio_venta', 0)),
            precio_mayoreo=float(row.get('precio_mayoreo', 0)),
            unidad=row.get('unidad'),
            stock=int(row.get('stock', 0)),
            categoria=row.get('categoria'),
            subcategoria=row.get('subcategoria'),
            activo=True
        )
        db.session.add(nuevo_p)
    db.session.commit()
    return redirect(url_for('mostrar_productos'))

@app.route('/descargar_plantilla_productos')
def descargar_plantilla_productos():
    contenido = "nombre,codigo_barra,precio_compra,precio_venta,precio_mayoreo,unidad,stock,categoria,subcategoria\n"
    contenido += "Cemento Melón 25kl,123456,2500,3000,2800,Saco,100,Construcción,Cemento\n"
    contenido += "Martillo Carpintero,789012,1500,2000,1800,Pieza,50,Herramientas,Martillos\n"
    return Response(
        contenido,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=plantilla_productos.csv"}
    )
# --- PROVEEDORES ---....................................................................
@app.route('/proveedores')
def mostrar_proveedores():
    todos_prov = Proveedor.query.all()
    return render_template('proveedores.html', proveedores=todos_prov)

@app.route('/guardar_proveedor', methods=['POST'])
def guardar_proveedor():
    nuevo_prov = Proveedor(
        nombre=request.form['nombre'],
        contacto=request.form['contacto'],
        telefono=request.form['telefono'],
        email=request.form['email'],
        rfc=request.form['rfc']
    )
    db.session.add(nuevo_prov)
    db.session.commit()
    return redirect(url_for('mostrar_proveedores'))

# --- VENTAS ---........................................................................
@app.route('/ventas')
@login_required
@caja_requerida
def mostrar_ventas():
  
    # 1. Quitamos el filtro de fecha para ver si aparecen los datos
    total_dia = db.session.query(db.func.sum(Venta.monto_total)).scalar() or 0

    cant_tickets = Venta.query.count()

    # 2. Artículos totales (sin filtro de fecha)
    art_rotados = db.session.query(db.func.sum(DetalleVenta.cantidad)).scalar() or 0

    # 3. Calculamos el promedio
    promedio = total_dia / cant_tickets if cant_tickets > 0 else 0

    # 4. Traemos la lista de ventas para la tabla inferior
    ventas = Venta.query.order_by(Venta.id.desc()).all()
    productos = Producto.query.filter_by(activo=True).all()
    pendientes = Venta.query.filter_by(estado='Pendiente').count()

    return render_template('gestion_ventas.html', 
                           total_dia=total_dia,
                           ventas_pendientes_count=pendientes,
                           ticket_promedio=promedio,
                           total_articulos=art_rotados,
                           ventas=ventas,
                           productos=productos)



# proceso de guardar venta desde formulario de ventas........................................................................
@app.route('/guardar_venta', methods=['POST'])
def guardar_venta():
    usuario = request.form.get('usuario', 'S/U')
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    if not caja:
        flash("No hay caja abierta. Debe abrir una caja antes de registrar ventas.")
        return redirect(url_for('mostrar_ventas'))

    nueva_venta = Venta(usuario=usuario, caja_id=caja.id, monto_total=0)
    db.session.add(nueva_venta)
    db.session.flush()

    ids = request.form.getlist('id_producto[]')
    cantidades = request.form.getlist('cantidad[]')
    precios = request.form.getlist('precio_unitario[]')
    acumulado_total = 0

    for i in range(len(ids)):
        if not ids[i]: continue
        cant = int(cantidades[i])
        prec = float(precios[i])
        acumulado_total += (cant * prec)
        detalle = DetalleVenta(id_venta=nueva_venta.id, id_producto=int(ids[i]),
                               cantidad=cant, precio_unitario=prec)
        db.session.add(detalle)

    nueva_venta.total = acumulado_total
    db.session.commit()
    flash("Venta guardada con éxito.")
    return redirect(url_for('mostrar_ventas'))

# proceso de punto de venta, creación de venta abierta y manejo de vales pendientes........................................
@app.route('/punto_venta')
def punto_venta():
    # Buscar la última caja abierta
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    if not caja:
        flash("No hay caja abierta. Debe abrir la caja antes de usar el punto de venta.")
        return redirect(url_for('mostrar_ventas'))

    # Buscar la última venta abierta
    venta = Venta.query.filter_by(estado="Abierta").order_by(Venta.id.desc()).first()
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

    # Renderizar la plantilla con los datos
    return render_template(
        'punto_venta.html',
        venta=venta,
        detalles=venta.detalles,
        vales_pendientes=vales_pendientes,
        cliente=cliente
    )


# proceso de agregar productos a venta abierta desde punto de venta........................................

@app.route('/agregar_producto_venta', methods=['POST'])
def agregar_producto_venta():
    codigo = request.form['codigo']
    producto = Producto.query.filter_by(codigo_barra=codigo).first()
    if producto:
        cantidad = 1
        precio_unitario = producto.precio_venta
        venta = Venta.query.order_by(Venta.id.desc()).first()
        detalle = DetalleVenta(id_venta=venta.id, id_producto=producto.id,
                               cantidad=cantidad, precio_unitario=precio_unitario)
        db.session.add(detalle)
        venta.total += cantidad * precio_unitario
        db.session.commit()
    return redirect(url_for('punto_venta'))

# proceso de eliminar producto de venta abierta desde punto de venta........................................

@app.route('/eliminar_detalle/<int:id>')
def eliminar_detalle(id):
    detalle = DetalleVenta.query.get_or_404(id)
    venta = detalle.venta
    venta.total -= detalle.cantidad * detalle.precio_unitario
    db.session.delete(detalle)
    db.session.commit()
    return redirect(url_for('punto_venta'))

#eliminar venta abierta o pendiente desde pantalla de ventas........................................................................

@app.route('/eliminar_venta/<int:id>', methods=['POST','GET'])
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
def finalizar_venta():
    # Buscar la última venta abierta
    venta = Venta.query.filter_by(estado="Abierta").order_by(Venta.id.desc()).first()
    if not venta or venta.monto_total == 0:
        flash("Error: La venta está vacía.", "danger")
        return redirect(url_for('punto_venta'))

    # Datos del formulario
    rut = request.form.get('cliente_rut')
    nombre = request.form.get('cliente_nombre')
    direccion = request.form.get('cliente_direccion')
    telefono = request.form.get('cliente_telefono')
    correo = request.form.get('cliente_correo')

    # Validación de RUT................................................................
    if not rut or not validar_rut(rut):
        flash("Error: RUT inválido.", "danger")
        return redirect(url_for('punto_venta'))

    # Buscar cliente por RUT
    cliente = Cliente.query.filter_by(rut=rut).first()

    if cliente:
        # Actualizar datos opcionales
        cliente.direccion = direccion or cliente.direccion
        cliente.telefono = telefono or cliente.telefono
        cliente.correo = correo or cliente.correo

        # Bloquear modificación de nombre
        if nombre and nombre != cliente.nombre:
            flash("El cliente ya existe, no puedes cambiar el nombre.", "warning")
            return redirect(url_for('punto_venta'))
    else:
        # Nuevo cliente → nombre obligatorio................................................
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

    # Renderizar ticket
    return render_template('ticket_vale.html',
                           venta=venta,
                           detalles=venta.detalles,
                           cliente=cliente)

#edición de venta para vales pendientes desde pantalla de ventas........................................

@app.route('/editar_venta/<int:id>', methods=['GET', 'POST'])
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
def actualizar_item():
    detalle_id = request.form.get('actualizar')
    cantidad = int(request.form.get(f'cantidad_{detalle_id}', 1))
    descuento = float(request.form.get(f'descuento_{detalle_id}', 0))

    detalle = DetalleVenta.query.get(detalle_id)
    if detalle:
        detalle.cantidad = cantidad
        detalle.descuento = descuento
        detalle.subtotal = (detalle.precio_unitario * cantidad) - descuento
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

    monto_vendido = db.session.query(db.func.sum(Venta.monto_total)).filter(Venta.estado == "Pagada").scalar() or 0
    monto_pendiente = db.session.query(db.func.sum(Venta.monto_total)).filter(Venta.estado == "Pendiente").scalar() or 0
    vuelto_entregado = db.session.query(db.func.sum(Venta.vuelto)).filter(Venta.fecha >= hoy).scalar() or 0

    # Vales pendientes para la tabla
    vales = Venta.query.filter(Venta.estado == "Pendiente").order_by(Venta.fecha.desc()).all()

    return render_template(
        'caja_pendientes.html',
        tickets_emitidos=tickets_emitidos,
        monto_apertura=monto_apertura,
        monto_vendido=monto_vendido,
        monto_pendiente=monto_pendiente,
        vuelto_entregado=vuelto_entregado,
        vales=vales
    )


# proceso de Cobro en caja para vales pendientes...................................................

@app.route('/caja/cobrar/<int:id>', methods=['POST'])
def cobrar_vale(id):
    venta = Venta.query.get_or_404(id)
    caja = Caja.query.filter_by(estado="Abierta").first()
    if not caja:
        flash("Error: ¡Debes abrir la caja primero!", "danger")
        return redirect(url_for('abrir_caja'))

    if venta.estado == "Pagada":
        flash("Esta venta ya fue pagada.", "warning")
        return redirect(url_for('caja_pendientes'))

    try:
        venta.metodo_pago = request.form['metodo_pago']
        venta.monto_recibido = float(request.form['monto_recibido'])
        venta.vuelto = venta.monto_recibido - venta.total

        if venta.monto_recibido < venta.total:
            flash("Error: El monto recibido es insuficiente.", "danger")
            return redirect(url_for('caja_pendientes'))

        venta.estado = "Pagada"
        venta.caja_id = caja.id

        for d in venta.detalles:
            producto = Producto.query.get(d.id_producto)
            if producto:
                if producto.stock < d.cantidad:
                    flash(f"Advertencia: Stock insuficiente para {producto.nombre}", "warning")
                producto.stock -= d.cantidad

        db.session.commit()
        flash(f"Venta N°{venta.id} pagada. Vuelto: ${venta.vuelto}", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error al procesar el pago: {str(e)}", "danger")

    return redirect(url_for('caja_pendientes'))

# Esta función procesa el cobro de un vale pendiente desde la pantalla de caja, actualizando el estado de la venta, descontando el stock y mostrando el ticket final.

def procesar_cobro_caja(id):
    venta = Venta.query.get_or_404(id)
    metodo = request.form.get('metodo_pago')
    recibido = int(request.form.get('monto_recibido', 0))

    total = venta.monto_total
    vuelto = 0
    if metodo == "Efectivo" and recibido > total:
        vuelto = recibido - total

    # Guardar pago en la BD
    venta.estado = "Pagado"
    db.session.commit()

    flash(f"Pago registrado. Vuelto: ${vuelto:,.0f}")
    return redirect(url_for('vales_pendientes'))

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
            "text": f"{p.nombre} ({p.codigo_barra})"
        })

    return {"results": results}

# proceso de apertura de caja desde pantalla de caja........................................................................

@app.route('/abrir_caja', methods=['GET', 'POST'])
def abrir_caja():
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
def movimiento_caja():
    if request.method == 'POST':
        caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
        movimiento = MovimientoCaja(
            caja_id=caja.id,
            tipo=request.form['tipo'],
            concepto=request.form['concepto'],
            monto=float(request.form['monto'])
        )
        db.session.add(movimiento)
        db.session.commit()
        flash("Movimiento registrado correctamente", "success")
        return redirect(url_for('movimiento_caja'))  # redirige a la misma ruta

    # Si es GET, mostrar la lista premium
    movimientos = MovimientoCaja.query.order_by(MovimientoCaja.fecha.desc()).all()
    return render_template('movimiento_caja.html', movimientos=movimientos)



# mostrar movimientos de caja........................................................................

@app.route('/cerrar_caja', methods=['POST'])
def cerrar_caja():
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    if caja:
        caja.fecha_cierre = db.func.current_timestamp()
        ventas = Venta.query.filter_by(caja_id=caja.id).all()
        total_efectivo = sum(v.total for v in ventas if v.metodo_pago == "Efectivo")
        ingresos = sum(m.monto for m in caja.movimientos if m.tipo == "Ingreso")
        egresos = sum(m.monto for m in caja.movimientos if m.tipo == "Egreso")
        caja.monto_final = caja.monto_inicial + total_efectivo + ingresos - egresos
        caja.estado = "Cerrada"
        caja.usuario_cierre = "Admin"
        db.session.commit()
        return render_template('ticket_cierre.html', caja=caja, ventas=ventas,
                               total_efectivo=total_efectivo,
                               ingresos=ingresos, egresos=egresos)
    return redirect(url_for('punto_venta'))

# 2. Cambiamos estado y descontamos stock....................................................
    venta.estado = "Pagada"
    
    for d in venta.detalles:
        prod = Producto.query.get(d.id_producto)
        if prod:
            prod.stock -= d.cantidad # Aquí ocurre el descuento real

    db.session.commit()
    
    # 3. Mostramos el ticket final (es_vale=False para que diga "BOLETA").........................
    return render_template('ticket.html', venta=venta, detalles=venta.detalles, es_vale=False)


# Validar si el correo ya existe..............................................................
    if Usuario.query.filter_by(correo=correo).first():
        flash("El correo ya está registrado.", "danger")
        return redirect(url_for('usuarios'))

    nuevo_usuario = Usuario(nombre=nombre, correo=correo, rol_id=rol_id)
    nuevo_usuario.set_password(password)

    db.session.add(nuevo_usuario)
    db.session.commit()
    flash("Usuario creado correctamente.", "success")
    return redirect(url_for('usuarios'))

# editar usuario....................................................................................

@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
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

@app.route('/eliminar_usuario/<int:id>', methods=['POST', 'GET'])
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
# --- procesar cobro caja ---
@app.route('/procesar_cobro_caja/<int:id>', methods=['POST'])
def procesar_cobro_caja(id):
    venta = Venta.query.get_or_404(id)
    metodo = request.form.get('metodo_pago')
    recibido = int(request.form.get('monto_recibido', 0))

    total = venta.monto_total
    vuelto = 0
    if metodo == "Efectivo" and recibido > total:
        vuelto = recibido - total

    # Guardar pago en la BD
    venta.estado = "Pagado"
    db.session.commit()

    flash(f"Pago registrado. Vuelto: ${vuelto:,.0f}", "success")
    return redirect(url_for('caja_pendientes'))

# --- proceso de login y logout ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']
        usuario = Usuario.query.filter_by(correo=correo).first()

        if usuario and usuario.check_password(password):
            login_user(usuario)
            flash(f"Bienvenido, {usuario.nombre}", "success")
            return redirect(url_for('punto_venta'))  # redirige al POS
        else:
            flash("Credenciales inválidas", "danger")

    return render_template('login.html')

# proceso de logout..............................................................................
@app.route('/logout')
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('index'))

# --- gestión de usuarios ---
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
            rol_id=rol_id
        )
        nuevo_usuario.set_password(password)

        db.session.add(nuevo_usuario)
        db.session.commit()

        flash("Usuario creado correctamente.", "success")
        return redirect(url_for('usuarios'))

    usuarios = Usuario.query.all()
    roles = Rol.query.all()
    return render_template('usuarios.html', usuarios=usuarios, roles=roles)

# API para el Escáner Móvil
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
            # 3. Actualizar el stock maestro del producto
            producto.stock = d.stock_fisico
            
            # 4. Registrar en la tabla de Movimientos de Inventario (Kardex)
            # que ya teníamos en la Fase 1
            nuevo_mov = MovimientoInventario(
                id_producto=producto.id,
                id_almacen=1, # Por defecto Almacén Central
                tipo_movimiento='AJUSTE',
                cantidad=abs(diferencia),
                motivo=f"Ajuste por Auditoría #{auditoria_id}",
                usuario=current_user.nombre,
                fecha=datetime.now()
            )
            db.session.add(nuevo_mov)

    # 5. Marcar auditoría como finalizada
    auditoria.estado = 'Ajustada'
    auditoria.fecha_fin = datetime.now()
    db.session.commit()
    
    flash("Inventario ajustado y Kardex actualizado correctamente.", "success")
    return redirect(url_for('ver_auditorias'))

# API para registrar cada ítem recibido durante proceso de recepción de mercadería
@app.route('/api/registrar_item_recepcion', methods=['POST'])
@login_required
def registrar_item_recepcion():
    data = request.json
    # 1. Buscar producto
    producto = Producto.query.get(data['producto_id'])
    
    # 2. Registrar el detalle de la recepción
    nuevo_detalle = DetalleRecepcion(
        recepcion_id=data['recepcion_id'],
        producto_id=data['producto_id'],
        cantidad_documento=data['cantidad_esperada'],
        cantidad_recibida=data['cantidad_fisica']
    )
    db.session.add(nuevo_detalle)

    # 3. IMPACTO EN STOCK: Sumar lo recibido al maestro
    producto.stock += int(data['cantidad_fisica'])

    # 4. Generar Movimiento de Inventario (ENTRADA)
    mov = MovimientoInventario(
        id_producto=producto.id,
        id_almacen=1,
        tipo_movimiento='ENTRADA',
        cantidad=data['cantidad_fisica'],
        motivo=f"Recepción Documento: {data['num_doc']}",
        usuario=current_user.nombre
    )
    db.session.add(mov)
    
    db.session.commit()
    return jsonify({"status": "success"})
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

# --- cierre del archivo ---
if __name__ == '__main__':
    app.run(debug=True)
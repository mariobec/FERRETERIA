# --- IMPORTS ---
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import csv
from io import TextIOWrapper

# --- CONFIGURACIÓN DE LA APP ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://mbecerra:clave_segura@localhost/ferreteria'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave_secreta_segura'
db = SQLAlchemy(app)

# --- FUNCIÓN DE VALIDACIÓN DE RUT ---............................................................
def validar_rut(rut: str) -> bool:
    rut = rut.replace(".", "").replace("-", "").upper()
    if len(rut) < 8:
        return False
    cuerpo, dv = rut[:-1], rut[-1]
    try:
        reverso = map(int, reversed(cuerpo))
        factores = [2, 3, 4, 5, 6, 7]
        suma = sum(d * factores[i % 6] for i, d in enumerate(reverso))
        residuos = 11 - (suma % 11)
        dv_esperado = 'K' if residuos == 10 else '0' if residuos == 11 else str(residuos)
        return dv == dv_esperado
    except:
        return False

# --- MODELOS DE BASE DE DATOS ---
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

    ventas = db.relationship('Venta', back_populates='caja', lazy=True)
    movimientos = db.relationship('MovimientoCaja', backref='caja', lazy=True)
# --- NUEVOS MODELOS ---
class Rol(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(20), unique=True, nullable=False)
    descripcion = db.Column(db.String(100))

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)

    rol = db.relationship('Rol', backref='usuarios')

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
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

    # Relación con caja...................................................................
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=True)
    caja = db.relationship('Caja', back_populates='ventas')

    # Relación con cliente................................................................
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    cliente = db.relationship('Cliente', backref='ventas')

    # Campo de prioridad para orden de atención............................................
    prioridad = db.Column(db.Integer)

    # Relación con detalles
    detalles = db.relationship('DetalleVenta', backref='venta', lazy=True, cascade="all, delete-orphan")


    @property
    def total(self):
        return self.monto_total

    @total.setter
    def total(self, value):
        self.monto_total = float(value) if value else 0.0

class DetalleVenta(db.Model):
    __tablename__ = 'detalle_ventas'
    id = db.Column(db.Integer, primary_key=True)
    id_venta = db.Column(db.Integer, db.ForeignKey('ventas.id'))
    id_producto = db.Column(db.Integer, db.ForeignKey('productos.id'))
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    producto = db.relationship('Producto', backref='detalles_venta')

class MovimientoCaja(db.Model):
    __tablename__ = 'movimiento_caja'
    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    tipo = db.Column(db.String(20))
    concepto = db.Column(db.String(100))
    monto = db.Column(db.Float, nullable=False)

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

class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(100))
    rfc = db.Column(db.String(20))

    # ...................................................................
    # --- MAESTRO CLIENTES ---
class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    rut = db.Column(db.String(12), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    giro = db.Column(db.String(100))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    correo = db.Column(db.String(100))

    #....................................................................

# --- RUTAS DE NAVEGACIÓN ---
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
def mostrar_ventas():
    todas_ventas = Venta.query.order_by(Venta.fecha.desc()).all()
    productos = Producto.query.all()
    return render_template('ventas.html', ventas=todas_ventas, productos=productos)

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
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    if not caja:
        flash("No hay caja abierta. Debe abrir la caja antes de usar el punto de venta.")
        return redirect(url_for('mostrar_ventas'))

    venta = Venta.query.filter_by(estado="Abierta").order_by(Venta.id.desc()).first()
    if not venta:
        venta = Venta(usuario="POS", estado="Abierta", monto_total=0,
                      caja_id=caja.id, fecha=db.func.current_timestamp())
        db.session.add(venta)
        db.session.commit()

    vales_pendientes = Venta.query.filter_by(estado="Pendiente").all()

    # Si la venta ya tiene cliente asociado, lo pasamos al template
    cliente = venta.cliente if venta and venta.cliente_id else None

    return render_template('punto_venta.html',
                           venta=venta,
                           detalles=venta.detalles,
                           vales_pendientes=vales_pendientes,
                           cliente=cliente)


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
    venta = Venta.query.filter_by(estado="Abierta").order_by(Venta.id.desc()).first()
    if not venta or venta.monto_total == 0:
        flash("Error: La venta está vacía.", "danger")
        return redirect(url_for('punto_venta'))

    rut = request.form.get('cliente_rut')
    nombre = request.form.get('cliente_nombre')
    direccion = request.form.get('cliente_direccion')
    telefono = request.form.get('cliente_telefono')
    correo = request.form.get('cliente_correo')

    if not rut or not validar_rut(rut):
        flash("Error: RUT inválido.", "danger")
        return redirect(url_for('punto_venta'))

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
        if not nombre:
            flash("Error: Nombre es obligatorio para nuevo cliente.", "danger")
            return redirect(url_for('punto_venta'))
        cliente = Cliente(nombre=nombre, rut=rut,
                          direccion=direccion, telefono=telefono, correo=correo)
        db.session.add(cliente)

    db.session.commit()

    pendientes = Venta.query.filter_by(estado="Pendiente").count()
    venta.prioridad = pendientes + 1
    venta.cliente_id = cliente.id
    venta.estado = "Pendiente"
    db.session.commit()

    flash(f"Vale N°{venta.id} emitido para {cliente.nombre}. Turno {venta.prioridad}.", "info")
    return render_template('ticket_vale.html', venta=venta, detalles=venta.detalles, cliente=cliente)

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


# CAJA vales pendientes................................................................................
@app.route('/caja/vales_pendientes')
def caja_pendientes():
    vales = Venta.query.filter_by(estado="Pendiente").order_by(Venta.fecha.desc()).all()
    return render_template('caja_pendientes.html', vales=vales)

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

@app.route('/movimiento_caja', methods=['POST'])
def movimiento_caja():
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    movimiento = MovimientoCaja(
        caja_id=caja.id,
        tipo=request.form['tipo'],
        concepto=request.form['concepto'],
        monto=float(request.form['monto'])
    )
    db.session.add(movimiento)
    db.session.commit()
    flash("Movimiento registrado correctamente")
    return redirect(url_for('mostrar_movimientos'))

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

# proceso de Cobro en caja para vales pendientes...................................................
@app.route('/caja/cobrar/<int:id>', methods=['POST'])
def procesar_cobro_caja(id):
    venta = Venta.query.get_or_404(id)
    
    # 1. Capturamos datos del formulario
    venta.metodo_pago = request.form['metodo_pago']
    venta.monto_recibido = float(request.form['monto_recibido'])
    venta.vuelto = venta.monto_recibido - venta.total
    
    # 2. Cambiamos estado y descontamos stock....................................................
    venta.estado = "Pagada"
    
    for d in venta.detalles:
        prod = Producto.query.get(d.id_producto)
        if prod:
            prod.stock -= d.cantidad # Aquí ocurre el descuento real

    db.session.commit()
    
    # 3. Mostramos el ticket final (es_vale=False para que diga "BOLETA").........................
    return render_template('ticket.html', venta=venta, detalles=venta.detalles, es_vale=False)

# funciones de usuarios y roles de sistema.........................................................
@app.route('/usuarios')
def usuarios():
    usuarios = Usuario.query.all()
    roles = Rol.query.all()
    return render_template('usuarios.html', usuarios=usuarios, roles=roles)

# crea usuario....................................................................................
@app.route('/crear_usuario', methods=['POST'])
def crear_usuario():
    nombre = request.form['nombre']
    correo = request.form['correo']
    password = request.form['password']
    rol_id = request.form['rol_id']

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
@app.route('/eliminar_usuario/<int:id>', methods=['POST', 'GET'])
def eliminar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash("Usuario eliminado correctamente.", "success")
    return redirect(url_for('usuarios'))


# --- cierre del archivo ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


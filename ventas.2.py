# --- IMPORTS ---
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import csv
from io import TextIOWrapper

# --- CONFIGURACIÓN DE LA APP ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://mbecerra:clave_segura@localhost/ferreteria'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave_secreta_segura'
db = SQLAlchemy(app)

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

    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=True)
    caja = db.relationship('Caja', back_populates='ventas')
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
    id = db.Column(db.Integer, primary_key=True)
    rut = db.Column(db.String(12), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    giro = db.Column(db.String(100))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))

    #....................................................................

# --- RUTAS DE NAVEGACIÓN ---
@app.route('/')
def inicio():
    # Sumar todas las unidades en stock de productos activos
    stock_activo = db.session.query(db.func.sum(Producto.stock)).filter(
        Producto.activo == True,
        Producto.stock > 0
    ).scalar() or 0

    # Productos con bajo stock (ejemplo: menos de 5 unidades)
    bajo_stock = Producto.query.filter(
        Producto.stock < 5,
        Producto.activo == True
    ).count()

    # Ventas de hoy
    ventas_hoy = db.session.query(db.func.sum(Venta.monto_total)).filter(
        db.func.date(Venta.fecha) == db.func.current_date()
    ).scalar() or 0

    # Transacciones totales
    transacciones = Venta.query.count()

    return render_template(
        'inicio.html',
        stock_activo=stock_activo,
        bajo_stock=bajo_stock,
        ventas_hoy=ventas_hoy,
        transacciones=transacciones
    )

# --- PRODUCTOS ---
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
# --- PROVEEDORES ---
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

# --- VENTAS ---
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

    nueva_venta = Venta(usuario=usuario, caja_id=caja.id, monto_total=0)  # CORREGIDO
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
        detalle = DetalleVenta(id_venta=nueva_venta.id, id_producto=int(ids[i]), cantidad=cant, precio_unitario=prec)
        db.session.add(detalle)

    nueva_venta.total = acumulado_total
    db.session.commit()
    flash("Venta guardada con éxito.")
    return redirect(url_for('mostrar_ventas'))

@app.route('/eliminar_venta/<int:id>')
def eliminar_venta(id):
    venta = Venta.query.get_or_404(id)
    db.session.delete(venta)
    db.session.commit()
    return redirect(url_for('mostrar_ventas'))

@app.route('/editar_venta/<int:id>', methods=['GET', 'POST'])
def editar_venta(id):
    venta = Venta.query.get_or_404(id)
    productos = Producto.query.all()
    if request.method == 'POST':
        venta.usuario = request.form['usuario']
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
        return redirect(url_for('mostrar_ventas'))

    return render_template('editar_venta.html', venta=venta, productos=productos)

# --- PUNTO DE VENTA ---
@app.route('/punto_venta')
def punto_venta():
    caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
    if not caja:
        flash("No hay caja abierta. Debe abrir la caja antes de usar el punto de venta.")
        return redirect(url_for('mostrar_ventas'))

    venta = Venta.query.order_by(Venta.id.desc()).first()
    if not venta or venta.total == 0:
        venta = Venta(usuario="POS", monto_total=0, caja_id=caja.id)  # CORREGIDO
        db.session.add(venta)
        db.session.commit()

    return render_template('punto_venta.html', venta=venta, detalles=venta.detalles)

@app.route('/agregar_producto_venta', methods=['POST'])
def agregar_producto_venta():
    codigo = request.form['codigo']
    producto = Producto.query.filter_by(codigo_barra=codigo).first()
    if producto:
        cantidad = 1
        precio_unitario = producto.precio_venta
        venta = Venta.query.order_by(Venta.id.desc()).first()
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

@app.route('/eliminar_detalle/<int:id>')
def eliminar_detalle(id):
    detalle = DetalleVenta.query.get_or_404(id)
    venta = detalle.venta
    venta.total -= detalle.cantidad * detalle.precio_unitario
    db.session.delete(detalle)
    db.session.commit()
    return redirect(url_for('punto_venta'))

@app.route('/finalizar_venta', methods=['POST'])
def finalizar_venta():
    venta = Venta.query.order_by(Venta.id.desc()).first()
    if not venta or venta.total == 0:
        flash("Error: La venta está vacía.", "danger")
        return redirect(url_for('punto_venta'))

    venta.estado = "Pendiente"
    venta.fecha = db.func.current_timestamp()
    db.session.commit()
    flash(f"Vale N°{venta.id} generado. Dirija al cliente a caja.", "info")
    return render_template('ticket.html', venta=venta, detalles=venta.detalles, es_vale=True)

@app.route('/caja/vales_pendientes')
def caja_pendientes():
    vales = Venta.query.filter_by(estado="Pendiente").order_by(Venta.fecha.desc()).all()
    return render_template('caja_pendientes.html', vales=vales)

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

# proceso de Cobro en caja para vales pendientes
@app.route('/caja/cobrar/<int:id>', methods=['POST'])
def procesar_cobro_caja(id):
    venta = Venta.query.get_or_404(id)
    
    # 1. Capturamos datos del formulario
    venta.metodo_pago = request.form['metodo_pago']
    venta.monto_recibido = float(request.form['monto_recibido'])
    venta.vuelto = venta.monto_recibido - venta.total
    
    # 2. Cambiamos estado y descontamos stock
    venta.estado = "Pagada"
    
    for d in venta.detalles:
        prod = Producto.query.get(d.id_producto)
        if prod:
            prod.stock -= d.cantidad # Aquí ocurre el descuento real

    db.session.commit()
    
    # 3. Mostramos el ticket final (es_vale=False para que diga "BOLETA")
    return render_template('ticket.html', venta=venta, detalles=venta.detalles, es_vale=False)

# --- cierre del archivo ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


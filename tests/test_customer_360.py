import json
from datetime import datetime, timedelta
from uuid import uuid4

import app as m

db = m.db


def _rut_tmp():
    raw = str(uuid4().int)
    return f'99.{raw[-6:-3]}.{raw[-3:]}-1'


def _crear_cliente_tmp():
    cli = m.Cliente(
        rut=_rut_tmp(),
        nombre='QA Customer 360 Temporal',
        giro='Construccion',
        telefono='+56911112222',
        correo='qa-c360@example.com',
        limite_credito=800000,
        saldo_deudor=0.0,
        estado_credito='Activo',
    )
    db.session.add(cli)
    db.session.commit()
    return cli


def _crear_venta_pagada(cliente, producto, fecha_venta):
    venta = m.Venta(
        fecha=fecha_venta,
        monto_total=float(producto.precio_venta or 0),
        usuario='QA_C360',
        estado='Pagado',
        cliente_id=cliente.id,
        tipo_documento='Boleta',
        metodo_pago='Efectivo',
        neto=float(getattr(producto, 'precio_venta', 0) or 0),
        iva=0.0,
        punto_retiro='Tienda',
    )
    db.session.add(venta)
    db.session.flush()
    db.session.add(
        m.DetalleVenta(
            id_venta=venta.id,
            id_producto=producto.id,
            cantidad=1,
            precio_unitario=float(producto.precio_venta or 0),
            subtotal=float(producto.precio_venta or 0),
        )
    )
    db.session.commit()
    return venta


def _limpiar_cliente_tmp(cliente_id):
    venta_ids = [v[0] for v in db.session.query(m.Venta.id).filter(m.Venta.cliente_id == cliente_id).all()]
    if venta_ids:
        m.VentaCuotaCredito.query.filter(m.VentaCuotaCredito.venta_id.in_(venta_ids)).delete(
            synchronize_session=False
        )
        m.DetalleVenta.query.filter(m.DetalleVenta.id_venta.in_(venta_ids)).delete(synchronize_session=False)
        m.Venta.query.filter(m.Venta.id.in_(venta_ids)).delete(synchronize_session=False)
    m.ClientePrediccionLog.query.filter_by(cliente_id=cliente_id).delete(synchronize_session=False)
    m.C360LlamadaSnapshotDia.query.filter_by(cliente_id=cliente_id).delete(synchronize_session=False)
    m.C360ProactivaOferta.query.filter_by(cliente_id=cliente_id).delete(synchronize_session=False)
    m.Cliente.query.filter_by(id=cliente_id).delete(synchronize_session=False)
    db.session.commit()


def test_c360_predictor_guarda_fecha_y_log(app_ctx, productos_con_stock):
    m._asegurar_columnas_customer_360_legacy()
    m._asegurar_tabla_cliente_prediccion_log()
    producto = productos_con_stock[0]
    producto.fase_obra = 'OBRA_GRUESA'
    db.session.commit()

    cliente = _crear_cliente_tmp()
    try:
        fecha_venta = datetime.now() - timedelta(days=5)
        _crear_venta_pagada(cliente, producto, fecha_venta)

        perfil = m.c360_project_predictor_actualizar_cliente(
            cliente.id, commit=True, usuario_origen='QA C360 test'
        )
        db.session.expire_all()
        cli = db.session.get(m.Cliente, cliente.id)
        perfil_db = json.loads(cli.c360_perfil_json or '{}')

        assert perfil is not None
        assert cli.c360_etapa_actual == 'INSTALACIONES'
        assert perfil_db.get('elegible_credito_proactivo') is True
        assert perfil_db.get('fecha_estimada_siguiente_compra') == (
            fecha_venta.date() + timedelta(days=21)
        ).isoformat()
        assert perfil_db.get('ultima_compra_clasificada') == fecha_venta.date().isoformat()

        logs = m.ClientePrediccionLog.query.filter_by(
            cliente_id=cliente.id,
            tipo_recomendacion='EXTENSION_CREDITO_SUGERIDA',
        ).all()
        assert len(logs) == 1
        assert logs[0].usuario_origen == 'QA C360 test'

        m.c360_project_predictor_actualizar_cliente(cliente.id, commit=True, usuario_origen='QA C360 test')
        logs_2 = m.ClientePrediccionLog.query.filter_by(
            cliente_id=cliente.id,
            tipo_recomendacion='EXTENSION_CREDITO_SUGERIDA',
        ).all()
        assert len(logs_2) == 1
    finally:
        _limpiar_cliente_tmp(cliente.id)


def test_admin_cliente_c360_muestra_proxima_compra_y_compras(app_ctx, app_client, productos_con_stock):
    m._asegurar_columnas_customer_360_legacy()
    m._asegurar_tabla_cliente_prediccion_log()
    producto = productos_con_stock[1]
    producto.fase_obra = 'OBRA_GRUESA'
    db.session.commit()

    cliente = _crear_cliente_tmp()
    try:
        venta = _crear_venta_pagada(cliente, producto, datetime.now() - timedelta(days=2))
        m.c360_project_predictor_actualizar_cliente(cliente.id, commit=True, usuario_origen='QA C360 route')

        r = app_client.get(f'/admin/clientes/{cliente.id}/c360')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Próxima compra estimada' in html
        assert 'Actividad 90 días' in html
        assert 'Compras recientes' in html
        assert f'#{venta.id}' in html
        assert 'Elegible' in html
        assert producto.categoria in html
    finally:
        _limpiar_cliente_tmp(cliente.id)


def test_api_c360_cliente_resumen_entrega_backend_p0(app_ctx, app_client, productos_con_stock):
    m._asegurar_columnas_customer_360_legacy()
    m._asegurar_tabla_cliente_prediccion_log()
    producto = productos_con_stock[2]
    producto.fase_obra = 'ACABADOS'
    producto.categoria = 'Pinturas'
    db.session.commit()

    cliente = _crear_cliente_tmp()
    try:
        fecha_venta = datetime.now() - timedelta(days=4)
        venta = _crear_venta_pagada(cliente, producto, fecha_venta)
        m.c360_project_predictor_actualizar_cliente(cliente.id, commit=True, usuario_origen='QA API C360')

        r = app_client.get(f'/api/c360/clientes/{cliente.id}/resumen?recalcular=1')
        assert r.status_code == 200
        data = r.get_json()

        assert data.get('ok') is True
        assert data['cliente']['id'] == cliente.id
        assert data['resumen']['ventas_90d'] == 1
        assert data['resumen']['ultima_compra'] == fecha_venta.date().isoformat()
        assert data['compras_recientes'][0]['venta_id'] == venta.id
        assert data['resumen']['categorias_top'][0]['categoria'] == 'Pinturas'
        assert data['perfil']['fecha_estimada_siguiente_compra'] == (
            fecha_venta.date() + timedelta(days=21)
        ).isoformat()
        assert data['predicciones_recientes'][0]['tipo_recomendacion'] == 'EXTENSION_CREDITO_SUGERIDA'
    finally:
        _limpiar_cliente_tmp(cliente.id)

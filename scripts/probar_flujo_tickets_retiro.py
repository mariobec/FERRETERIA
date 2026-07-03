"""Script puntual DEV — validar flujo tickets sin pytest fixtures."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime

import app as m
from tests.conftest import crear_venta_pendiente, procesar_cobro_http, login_as


def main():
    with m.app.app_context():
        caja = m.obtener_caja_activa()
        if not caja:
            print('ERROR: no hay caja abierta. Abra caja en /caja/prototipo')
            return 1
        cliente = m.Cliente.query.filter_by(rut='11.111.111-1').first()
        if not cliente:
            print('ERROR: falta cliente final QA')
            return 1
        prods = (
            m.Producto.query.filter(m.Producto.activo.is_(True))
            .order_by(m.Producto.id.desc())
            .limit(20)
            .all()
        )
        prods = [p for p in prods if (m.stock_disponible_venta_tienda(p) or 0) > 0][:5]
        if len(prods) < 1:
            print('ERROR: no hay productos con stock en tienda')
            return 1
        if len(prods) < 3:
            print(f'AVISO: solo {len(prods)} producto(s) con stock; prueba mixta puede omitirse')

        client = m.app.test_client()
        with login_as(client, 'Admin'):
            # 1) Vale interno POS
            venta, _ = crear_venta_pendiente([(prods[0], 1)], caja, cliente)
            r1 = client.get(f'/pos/ticket/{venta.id}')
            h1 = r1.data.decode('utf-8', errors='replace')
            ok1 = r1.status_code == 200 and 'VALE INTERNO' in h1 and 'NO ES BOLETA' in h1
            print(f'[1] POS ticket vale #{venta.id}:', 'OK' if ok1 else f'FAIL {r1.status_code}')

            # 2) Cobro → vale interno caja
            r2 = procesar_cobro_http(client, venta)
            r3 = client.get(f'/caja/vale_retiro/{venta.id}?chain_retiro=1')
            h3 = r3.data.decode('utf-8', errors='replace')
            ok2 = r2.status_code == 200 and 'VALE INTERNO' in h3 and 'NO ES BOLETA' in h3
            print(f'[2] Vale interno caja #{venta.id}:', 'OK' if ok2 else f'FAIL cobro={r2.status_code} ticket={r3.status_code}')

            # 3) Ticket retiro QR
            r4 = client.get(f'/caja/ticket_retiro/{venta.id}')
            h4 = r4.data.decode('utf-8', errors='replace')
            ok3 = r4.status_code == 200 and 'TICKET DE RETIRO' in h4 and 'NO ES BOLETA' in h4
            print(f'[3] Ticket retiro QR #{venta.id}:', 'OK' if ok3 else f'FAIL {r4.status_code}')

            # 4) Mixto → 2 QR (si hay stock bodega)
            ok4 = True
            if len(prods) >= 3:
                from tests.conftest import asegurar_stock_bodega
                try:
                    asegurar_stock_bodega(prods[2], 5)
                except Exception:
                    pass
                venta_m, _ = crear_venta_pendiente(
                    [(prods[0], 1, 'Tienda'), (prods[2], 1, 'Bodega')],
                    caja,
                    cliente,
                    punto_retiro='Mixto',
                )
                procesar_cobro_http(client, venta_m)
                r5 = client.get(f'/caja/ticket_retiro/{venta_m.id}')
                h5 = r5.data.decode('utf-8', errors='replace')
                ok4 = (
                    r5.status_code == 200
                    and 'TICKET QR [TIENDA]' in h5
                    and 'TICKET QR [BODEGA]' in h5
                )
                print(f'[4] Mixto 2 tickets #{venta_m.id}:', 'OK' if ok4 else f'FAIL {r5.status_code}')
                vid_retiros = venta_m.id
            else:
                vid_retiros = venta.id
                print('[4] Mixto 2 tickets: SKIP (pocos productos)')

            # 5) Pantalla retiros
            r6 = client.get('/pos/retiros')
            r7 = client.get(f'/api/pos/retiros/buscar?q=VL{vid_retiros:06d}')
            body = r7.get_json() or {}
            ok5 = r6.status_code == 200 and body.get('ok') and body.get('puede_entregar')
            print(f'[5] /pos/retiros + buscar VL:','OK' if ok5 else f'FAIL pant={r6.status_code} api={r7.status_code}')

            print('\nURLs manuales (con sesión iniciada en navegador):')
            print(f'  http://127.0.0.1:5000/pos/ticket/{venta.id}')
            print(f'  http://127.0.0.1:5000/caja/vale_retiro/{venta.id}')
            print(f'  http://127.0.0.1:5000/caja/ticket_retiro/{vid_retiros}')
            print(f'  http://127.0.0.1:5000/pos/retiros')

            if all([ok1, ok2, ok3, ok4, ok5]):
                print('\nRESULTADO: flujo tickets OK')
                return 0
            print('\nRESULTADO: hay fallos — revisar arriba')
            return 1


if __name__ == '__main__':
    raise SystemExit(main())

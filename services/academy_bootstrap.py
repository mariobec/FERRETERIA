"""Seed idempotente — Manual V2 LhexIA Academy (rutas Vendedor / Cajero / Bodeguero)."""
from __future__ import annotations

from typing import Any

MANUAL_V2_ARTICLES: list[dict[str, Any]] = [
    {
        'dedupe_key': 'academy:manual_v2:seccion_a_pos_semaforos',
        'category': 'pos',
        'title': 'POS: búsqueda, semáforos y emisión de vale',
        'summary': (
            'Vender en mostrador con filtros Operativo / Tienda / Catálogo, leer semáforos de stock '
            'y emitir vale pendiente para cobro en caja.'
        ),
        'permissions_required': 'vendedor',
        'video_url': None,
        'content_markdown': """## POS en mostrador

> Invariante Financiera: El POS **no cobra** dinero real. El cobro se cierra **solo en Caja**.

### Objetivo
Atender al cliente rápido, con stock real y vale correcto para la fila de cobro.

### Semáforos de stock (Operativo)
- **Verde:** hay stock en tienda — podés prometer entrega inmediata.
- **Amarillo:** stock bajo o parcial — confirmá cantidad con el cliente.
- **Rojo / sin stock:** no prometas entrega inmediata; ofrecé pedido o alternativa.

### Filtros de búsqueda (igual que catálogo)
1. **Operativo** — lo vendible hoy (stock tienda + precio POS).
2. **Tienda** — solo productos con stock en mostrador.
3. **Catálogo** — todo el maestro con precio (incluso sin stock).

### Flujo recomendado
1. Presioná **F2** o tocá la barra de búsqueda / escaneá código.
2. Revisá semáforo, precio POS (SD) y cantidad.
3. Identificá cliente o usá cliente final.
4. Pulsá **Emitir vale** (F8) — el vale queda **Pendiente** para caja.
5. Entregá ticket al cliente para la fila de cobro.

### Errores que evitar
- Cobrar en POS — incorrecto; usa siempre caja.
- Ignorar semáforo rojo — genera reclamos.
- Vender sin revisar unidad de medida en productos fraccionables.

### Atajos
| Tecla | Acción |
|-------|--------|
| F2 | Foco búsqueda / escáner |
| F8 | Emitir vale pendiente |
| Esc | Cerrar modal o cancelar línea |
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_b_arqueo_ciego_plat11',
        'category': 'caja',
        'title': 'Cierre de caja y arqueo ciego',
        'summary': (
            'Cerrar turno contando efectivo sin ver el saldo del sistema primero; '
            'documentar descuadres según política PLAT-1.1.'
        ),
        'permissions_required': 'cajera',
        'video_url': None,
        'content_markdown': """## Cierre de caja — arqueo ciego

### Objetivo
Cerrar el turno con conteo físico independiente del saldo en pantalla.

### Antes de cerrar
1. Resolver **vales pendientes** de cobro o documentar excepción autorizada.
2. Separar efectivo, vouchers tarjeta y otros medios.
3. Imprimir resumen del turno si supervisión lo exige.

### Procedimiento
1. Menú **Caja → Cerrar caja**.
2. Ingresá montos **declarados** (el teórico se revela al confirmar).
3. El sistema muestra diferencia declarado vs. teórico.
4. Si hay descuadre: observación obligatoria y escalar a supervisor.
5. Confirmá cierre cuando la política lo permita.

### Buenas prácticas
- Contá la gaveta dos veces antes de declarar.
- No mezclés vuelto del turno anterior.
- Guardá comprobantes de depósito aparte del efectivo en caja.

### Atajos
| Tecla | Acción |
|-------|--------|
| Ctrl+Enter | Confirmar arqueo |
| Esc | Cerrar modal |
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_c_telemetria_v3',
        'category': 'bodega',
        'title': 'Enrolamiento de productos (Caso A / B / C)',
        'summary': (
            'Escanear códigos, vincular al maestro, dar de alta manual y sumar stock '
            'con las mismas reglas que el POS (alias, precio SD, kardex).'
        ),
        'permissions_required': 'bodega',
        'video_url': None,
        'content_markdown': """## Enrolamiento de inventario

### Objetivo
Registrar stock real alineado al maestro para que POS y tienda web muestren datos correctos.

### Casos al escanear
- **Caso A — Reconocido:** el código ya existe (maestro o alias). Revisá ficha y pulsá **Sumar** para confirmar cantidad.
- **Caso B — Código nuevo:** buscá producto en maestro y **Vincular** (crea alias, no pisa código maestro).
- **Caso C — Alta manual:** producto no está en maestro; completá nombre, precio venta y categoría.

### Reglas importantes
1. Elegí **almacén de la sesión** (Tienda = lo que vende POS).
2. Pill **Vendible en POS** usa precio POS (SD) + stock tienda.
3. Vincular usa **alias** — re-escaneá y debe resolver Caso A.
4. Stock sumado registra **kardex** automáticamente.

### Flujo típico
1. **Nueva sesión** → elegir Tienda o Bodega.
2. Pistoleá código → revisar pill POS.
3. **Sumar** cantidad en el almacén correcto.
4. Si hay duda, abrí **Salud del inventario** para desajustes.

### Atajos
| Tecla | Acción |
|-------|--------|
| Enter | Enviar código escaneado |
| Esc | Cerrar panel / overlay |
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_d_apertura_caja',
        'category': 'caja',
        'title': 'Apertura de caja (inicio de turno)',
        'summary': (
            'Declarar el efectivo real en gaveta para habilitar cobros y trazabilidad del turno.'
        ),
        'permissions_required': 'cajera',
        'video_url': None,
        'content_markdown': """## Apertura de caja

### Objetivo
Iniciar turno con el efectivo contado en gaveta y dejar registro en el sistema.

### Procedimiento
1. Ir a **Abrir caja** (menú o aviso de caja pendiente).
2. Contar billetes y monedas del fondo (sencillo).
3. Ingresar **saldo inicial** en CLP.
4. Confirmar **Iniciar jornada** — quedás asociado al turno.
5. Verificá que POS y **Vales pendientes** queden habilitados.

### Errores frecuentes
- Declarar sin contar físicamente la gaveta.
- Olvidar cerrar la caja del día anterior (bloquea POS).
- Mezclar vuelto del día previo con el fondo inicial.

### Buenas prácticas
- Anotá en papel si hay diferencia respecto al cierre anterior autorizado.
- No abras dos turnos en paralelo en la misma estación.
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_e_movimiento_caja',
        'category': 'caja',
        'title': 'Movimientos extraordinarios de caja',
        'summary': (
            'Registrar ingresos y egresos fuera del cobro de vales, con concepto claro '
            'y responsable en retiros.'
        ),
        'permissions_required': 'cajera',
        'video_url': None,
        'content_markdown': """## Movimientos de caja

### Objetivo
Documentar entradas y salidas de efectivo que **no** son cobro de un vale.

### Cuándo usar
- **Ingreso:** reposición de cambio, devolución de gasto, etc.
- **Egreso:** retiro autorizado, pago menor en efectivo desde caja, etc.

### Procedimiento
1. **Caja → Movimientos de caja**.
2. Elegí **Ingreso** o **Egreso**.
3. Escribí **concepto** claro y verificable.
4. En **Egreso**, completá **responsable del retiro** (obligatorio).
5. Ingresá monto en CLP y guardá.
6. Revisá que aparezca en el historial del turno.

### Errores frecuentes
- Egreso sin responsable — el sistema no debe permitir guardar.
- Usar movimiento de caja para “anular” un vale (usar anulación de vale o nota de crédito).
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_f_cobro_vales',
        'category': 'caja',
        'title': 'Cobro de vales y medios de pago',
        'summary': (
            'Procesar vales emitidos en POS, pedidos web Maylén y elegir efectivo, '
            'tarjeta o crédito según política de la tienda.'
        ),
        'permissions_required': 'cajera',
        'video_url': None,
        'content_markdown': """## Cobro en caja

### Objetivo
Recaudar vales pendientes y cerrar la venta con trazabilidad de medio de pago.

### Tipos de vale en bandeja
- **POS:** vale VL###### emitido en mostrador.
- **Web:** pedido PED-WEB###### (Maylén / tienda online).
- Escaneá código de barras del vale o buscá por folio.

### Procedimiento
1. Abrí **Vales pendientes** o escaneá el código en caja.
2. Verificá ítems, totales e IVA incluido.
3. Elegí medio de pago: efectivo, tarjeta, transferencia o crédito (si aplica).
4. Confirmá cobro — el vale pasa a **Pagado**.
5. Entregá comprobante; pedidos web siguen flujo de preparación en bodega.

### Buenas prácticas
- No cobres sin caja abierta en tu turno.
- Revisá identidad del cliente en ventas a crédito.
- Ante duda de monto, volvé a POS o bandeja e-commerce antes de confirmar.

### Atajos
| Tecla | Acción |
|-------|--------|
| F5 | Refrescar cola de vales |
| Esc | Cerrar modal |
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_g_tablet_bodega',
        'category': 'bodega',
        'title': 'Tablet y pistola en bodega',
        'summary': (
            'Acceso LAN, instalación en pantalla de inicio y uso de pistola BCST '
            'con el enrolador optimizado para tablet.'
        ),
        'permissions_required': 'bodega',
        'video_url': None,
        'content_markdown': """## Enrolador en tablet

### Objetivo
Contar y enrolar productos en pasillo con tablet + pistola inalámbrica, sin depender del PC de escritorio.

### Acceso en la red local
1. Tablet y PC servidor en la **misma WiFi**.
2. Abrí `http://IP_SERVIDOR:5000/login` e iniciá sesión.
3. Entrá a **Enrolador bodega** o escaneá el QR en `/bodega/enrolador`.
4. **Agregar a pantalla de inicio** para acceso directo (sin APK).

### Pistola BCST (modo teclado)
1. Emparejá Bluetooth en el tablet.
2. Tocá el recuadro de escaneo (campo visible en tablet).
3. Pistoleá — el Enter del lector envía el código.
4. Confirmá con **Sumar** cuando corresponda.

### Checklist rápido
- Ctrl+F5 tras actualizar el ERP.
- Sesión en almacén correcto (Tienda vs Bodega).
- Si el código es nuevo → Caso B vincular o Caso C alta manual.
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_h_salud_inventario',
        'category': 'bodega',
        'title': 'Salud del inventario y desajustes',
        'summary': (
            'Detectar diferencias entre stock maestro y suma en almacenes; '
            'priorizar traslados Bodega → Tienda.'
        ),
        'permissions_required': 'bodega',
        'video_url': None,
        'content_markdown': """## Salud del inventario

### Objetivo
Encontrar SKU con stock incoherente antes de que afecten ventas o conteos.

### Qué revisa la pantalla
- **Maestro vs depósitos:** suma de almacenes activos vs campo `stock` del producto.
- **Tienda en cero, bodega con stock:** candidatos a traslado al mostrador.

### Cuándo usarla
- Después de una jornada de enrolamiento.
- Antes de promociones o inventario físico.
- Cuando POS muestra sin stock pero “hay en bodega”.

### Acciones recomendadas
1. Filtrá por nombre o código.
2. Exportá CSV si necesitás trabajar en Excel.
3. Corregí con traslado, ajuste autorizado o nuevo conteo en enrolador.
4. Validá que el semáforo POS quede verde en productos clave.

### Buenas prácticas
- No ajustes masivos sin autorización de supervisión.
- Documentá la causa (recepción, rotura, error de conteo).
""",
    },
]


def asegurar_academy_seed() -> dict[str, int]:
    """Inserta artículos Manual V2 si no existen (por dedupe_key)."""
    from app import AcademyArticle, db

    creados = 0
    actualizados = 0
    for spec in MANUAL_V2_ARTICLES:
        row = AcademyArticle.query.filter_by(dedupe_key=spec['dedupe_key']).first()
        if row is None:
            db.session.add(AcademyArticle(**spec))
            creados += 1
            continue
        changed = False
        for field in (
            'category',
            'title',
            'summary',
            'content_markdown',
            'video_url',
            'permissions_required',
        ):
            val = spec.get(field)
            if val is not None and getattr(row, field) != val:
                setattr(row, field, val)
                changed = True
        if changed:
            actualizados += 1
    if creados or actualizados:
        db.session.commit()
    return {'creados': creados, 'actualizados': actualizados}

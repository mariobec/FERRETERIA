"""Seed idempotente — Manual V2 LhexIA Academy (Secciones A, B, C)."""
from __future__ import annotations

from typing import Any

MANUAL_V2_ARTICLES: list[dict[str, Any]] = [
    {
        'dedupe_key': 'academy:manual_v2:seccion_a_pos_semaforos',
        'category': 'pos',
        'title': 'POS y Semáforos de stock',
        'summary': (
            'Operación de mostrador: búsqueda, semáforos de disponibilidad, emisión de vale '
            'y derivación a caja sin cobrar en POS.'
        ),
        'permissions_required': 'vendedor',
        'video_url': None,
        'content_markdown': """## Sección A — POS y Semáforos

> Invariante Financiera: El POS jamás recauda dinero real; el flujo operativo se cierra única y exclusivamente en la estación de Caja.

### Objetivo
Emitir vales correctos en mostrador respetando alertas de stock y política de la tienda.

### 📌 PROTOCOLO — Semáforos de stock
- **Verde:** stock suficiente en bodega activa.
- **Amarillo:** stock bajo o reservado parcialmente — confirmar con cliente antes de prometer.
- **Rojo:** sin stock disponible — no prometer entrega inmediata; ofrecer a pedido si aplica.

### Flujo operativo
1. Enfocar búsqueda (`F2`) e ingresar código de barra o nombre parcial.
2. Revisar semáforo y cantidad sugerida en la línea.
3. Identificar cliente o usar cliente final configurado.
4. Verificar totales y pulsar **Emitir vale** — el cobro lo realiza caja.
5. Entregar ticket/vale al cliente para la fila de cobro.

Importante: Cobrar en POS es incorrecto — el vale debe quedar **pendiente de cobro** en la estación de Caja.

### Errores frecuentes
- Cobrar en POS (incorrecto): el vale debe quedar **pendiente de cobro**.
- Ignorar semáforo rojo: genera reclamos y devoluciones.
- No validar unidad de medida en productos fraccionables.

### Atajos críticos
| Tecla | Acción |
|-------|--------|
| F2 | Foco búsqueda de producto / Invocación de Escáner universal |
| F8 | Emitir vale de venta pendiente (Bloqueo de caja diferido) |
| Esc | Cerrar modal o cancelar línea actual |
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_b_arqueo_ciego_plat11',
        'category': 'caja',
        'title': 'Arqueo Ciego PLAT-1.1',
        'summary': (
            'Cierre de caja con arqueo ciego: declarar montos sin ver el sistema, cuadrar '
            'y documentar descuadres según PLAT-1.1.'
        ),
        'permissions_required': 'cajera',
        'video_url': None,
        'content_markdown': """## Sección B — Arqueo Ciego PLAT-1.1

### Objetivo
Cerrar turno con conteo físico independiente del saldo en pantalla (arqueo ciego).

### Antes de cerrar
1. Resolver **vales pendientes** de cobro o documentar excepción autorizada.
2. Imprimir o exportar resumen de movimientos del turno si la supervisión lo exige.
3. Separar efectivo, vouchers tarjeta y otros medios de pago.

### Procedimiento PLAT-1.1
1. Ir a **Cerrar caja** desde el menú de caja.
2. Ingresar montos **declarados** (ef-screen oculto hasta confirmar).
3. El sistema compara declarado vs. teórico y muestra diferencia.
4. Si hay descuadre: registrar observación obligatoria y escalar a supervisor.
5. Confirmar cierre solo cuando la política de la tienda lo permita.

### Buenas prácticas
- Contar gaveta dos veces antes de declarar.
- No mezclar vuelto del turno anterior.
- Guardar comprobantes de depósito bancario aparte del efectivo en caja.

### Atajos críticos
| Tecla | Acción |
|-------|--------|
| Ctrl+Enter | Confirmar declaración de arqueo |
| Esc | Cerrar modal o cancelar línea actual |
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_c_telemetria_v3',
        'category': 'bodega',
        'title': 'Estanterías de Telemetría V3',
        'summary': (
            'Enrolamiento y lectura de estanterías con telemetría Guardian V3: ubicación, '
            'sensores y alertas de inventario en tiempo real.'
        ),
        'permissions_required': 'bodega',
        'video_url': None,
        'content_markdown': """## Sección C — Estanterías de Telemetría V3

### Objetivo
Mantener ubicaciones físicas alineadas con el mapa de estanterías y telemetría V3 del ERP.

### Conceptos
- **Estantería:** unidad lógica de almacenamiento (pasillo · módulo · nivel).
- **Telemetría V3:** eventos de movimiento, lectura RFID/código y alertas al Centro VERTEX.
- **Enrolamiento:** asociar producto ↔ ubicación ↔ sensor cuando corresponda.

### Flujo de enrolamiento
1. Abrir **Inventario → Enrolamiento** o recepción con destino bodega.
2. Escanear producto y confirmar unidad de medida.
3. Asignar estantería destino según mapa de bodega.
4. Validar lectura de telemetría (semáforo verde en panel Guardian).
5. Confirmar — el stock queda visible para POS con semáforo actualizado.

### Alertas comunes
- Producto sin ubicación: bloquea picking eficiente.
- Lectura duplicada en estantería: revisar etiquetado físico.
- Desfase telemetría vs. stock ERP: ejecutar conteo focal en la estantería.

### Atajos críticos
| Tecla | Acción |
|-------|--------|
| F2 | Foco escaneo / código |
| F5 | Refrescar panel telemetría |
| Enter | Confirmar línea de enrolamiento |
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_d_apertura_caja',
        'category': 'caja',
        'title': 'Apertura de caja (inicio de turno)',
        'summary': (
            'Declarar saldo inicial real en gaveta para habilitar cobros y trazabilidad del turno.'
        ),
        'permissions_required': 'cajera',
        'video_url': None,
        'content_markdown': """## Sección D — Apertura de caja

### Objetivo
Iniciar turno con el efectivo contado en gaveta y dejar registro en el sistema.

### Procedimiento
1. Ir a **Abrir caja** desde el menú o el aviso de caja pendiente.
2. Contar billetes y monedas del fondo de caja (sencillo).
3. Ingresar el **saldo inicial** en CLP (puede usar punto como separador de miles).
4. Confirmar **Iniciar jornada** — el usuario queda asociado al turno.
5. Verificar que **Vales pendientes** y POS queden habilitados.

### Errores frecuentes
- Declarar un monto sin contar físicamente la gaveta.
- Olvidar cerrar la caja del día anterior (bloquea POS).
- Mezclar vuelto o depósitos del día previo con el fondo inicial.

### Buenas prácticas
- Anotar en papel si hay diferencia respecto al cierre anterior autorizado.
- No abrir dos turnos en paralelo en la misma estación.
""",
    },
    {
        'dedupe_key': 'academy:manual_v2:seccion_e_movimiento_caja',
        'category': 'caja',
        'title': 'Movimientos extraordinarios de caja',
        'summary': (
            'Registrar ingresos y egresos fuera del cobro de vales, con concepto y responsable en retiros.'
        ),
        'permissions_required': 'cajera',
        'video_url': None,
        'content_markdown': """## Sección E — Movimientos de caja

### Objetivo
Documentar entradas y salidas de efectivo que no son cobro de un vale.

### Cuándo usar
- Ingreso: reposición de cambio, devolución de gasto, etc.
- Egreso: retiro autorizado, pago menor en efectivo desde caja, etc.

### Procedimiento
1. Abrir **Movimientos de caja** desde el menú de caja.
2. Seleccionar **Ingreso** o **Egreso**.
3. Escribir **concepto** claro y verificable.
4. En **Egreso**, completar **responsable del retiro** (obligatorio).
5. Ingresar monto en CLP y guardar.
6. Revisar que aparezca en el historial del turno.

### Errores frecuentes
- Egreso sin responsable → el sistema no debe permitir guardar.
- Usar movimiento de caja para “anular” un vale (usar anulación de vale o NC).
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

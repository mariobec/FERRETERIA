# Manual de operación — Customer 360 (LhexIA IA ERP)

Documento para **supervisores, gerencia, ventas y administración**. Describe qué hace el módulo, cómo usarlo día a día y qué revisar si algo no cuadra.

---

## 1. Para qué sirve Customer 360

Customer 360 une tres ideas en un solo flujo:

1. **Etapa de obra (foco comercial)**  
   A partir de las **ventas de los últimos 30 días** y la **fase de obra** de cada producto (`fase_obra` en inventario), el sistema sugiere en qué fase está el proyecto del cliente: obra gruesa, instalaciones, acabados o terminaciones.

2. **Señales de crédito y prioridad de contacto**  
   Calcula un **score de puntualidad**, una **probabilidad de mora** (heurística) y un **cupo sugerido** para la siguiente fase cuando el comportamiento de pago es bueno. Marca clientes que conviene **llamar** (etapa avanzada con buen score, o “calidad de datos” cuando hay mucho monto sin clasificar en catálogo).

3. **Venta proactiva (ofertas y WhatsApp)**  
   Puede **armar cotizaciones** con un “kit” de productos según la etapa, enviar **WhatsApp** (manual desde la cola o automático al **subir de fase** si está configurado) y **medir clic** en el enlace público y **conversión** si la cotización pasa a venta.

---

## 2. Permisos y accesos

| Área | Ruta aproximada | Permiso habitual |
|------|-----------------|-------------------|
| Ficha 360 de un cliente | `/admin/clientes/<id>/c360` | `gestionar_usuarios` |
| Cola de llamadas | `/admin/c360/llamadas-hoy` | `gestionar_usuarios` |
| Enviar oferta IA (POST) | `/admin/c360/enviar-oferta-ia` | `gestionar_usuarios` |
| Command Center / ROI IA | `/gerencia/c360-ia-dashboard` | `panel_gerencia` y/o `gestionar_usuarios` |
| Ejecutar motor desde gerencia | `POST /gerencia/c360-ejecutar-motor` | `panel_gerencia` o `gestionar_usuarios` |

El **inicio** puede mostrar un resumen C360 a usuarios con permiso de gerencia si la base tiene columnas y datos listos.

---

## 3. Conceptos que verá en pantalla

### 3.1 Etapas (`c360_etapa_actual`)

Valores internos (mayúsculas):

| Código | Significado operativo |
|--------|------------------------|
| `OBRA_GRUESA` | Perfil mixto o inicio; muchas veces indica que falta clasificar productos. |
| `INSTALACIONES` | Enfoque tubería, eléctrico, instalaciones. |
| `ACABADOS` | Cerámica, grifería, pegamentos finos. |
| `TERMINACIONES` | Pinturas, iluminación, cierres. |

Las etiquetas amigables se muestran en formularios según `C360_FASE_OBRA_LABELS` en el sistema.

### 3.2 Perfil JSON (`c360_perfil_json`)

Guarda, entre otros: etapa actual, score de puntualidad, cupo sugerido, ventana en días, montos, bandera **`recomendar_llamada`**, **`motivo_recomendar_llamada`** (`ETAPA_AVANZADA` o `DATA_QUALITY`), fechas de última predicción.

### 3.3 Cola de llamadas — tipos de prioridad

- **Etapa avanzada:** etapa INSTALACIONES / ACABADOS / TERMINACIONES, score de puntualidad **> 88** y compras en la ventana.  
- **Calidad de datos:** etapa OBRA_GRUESA pero con reglas estrictas (monto mínimo, % sin clasificar alto, límite de crédito y score) para priorizar **llamada comercial** y **mejorar el catálogo** (`fase_obra` en productos).

La cola se ordena por **mayor cupo sugerido** primero (entre los que tienen `recomendar_llamada`).

### 3.4 Cupo sugerido

No es un aumento automático del límite de crédito. Es una **sugerencia** calculada cuando el score de puntualidad supera un umbral; la decisión sigue siendo humana y de política interna.

---

## 4. Motor predictivo — cuándo se ejecuta

El motor es la función interna que recalcula etapa, perfil y banderas. Se ejecuta:

- Al pulsar **“Recalcular predicción”** en la ficha `/admin/clientes/<id>/c360`.
- Al usar **“Correr motor”** en Command Center o en la cola de llamadas (`POST /gerencia/c360-ejecutar-motor`).
- En **lote** vía cron: `POST /api/c360/worker-noche` (ver sección 10).

**Ventana:** por defecto **30 días** de ventas para repartir montos por `fase_obra` del producto.

**Reglas resumidas del predictor**

- Si no hay compras en la ventana: se mantiene o vacía etapa según datos; mensaje orientado a clasificar productos.
- Si más del **60%** del monto es OBRA_GRUESA → etapa foco **INSTALACIONES**.
- Si más del **55%** es INSTALACIONES → **ACABADOS**.
- Si más del **45%** es ACABADOS → **TERMINACIONES**.
- Si más del **30%** es TERMINACIONES → se mantiene **TERMINACIONES** (cierre).
- Si no encaja lo anterior → **OBRA_GRUESA** (perfil mixto).

Luego se evalúan **recomendar_llamada** y el texto de alerta (incluyendo el caso “calidad de datos”).

---

## 5. Ficha del cliente (`/admin/clientes/<id>/c360`)

**Qué hace el operador aquí**

1. Ver **etapa detectada**, score, cupo sugerido y alertas.  
2. Ver **compras por fase** en los últimos 30 días (incluye “sin clasificar”).  
3. **Recalcular** para refrescar tras cambios en ventas o en `fase_obra` de productos.  
4. **OCR simulado (mock):** subir archivo o elegir fase máxima manual; si la fase inferida es **superior** a la etapa actual, el sistema puede actualizar etapa y ajustar el límite de crédito de forma **conservadora** (siempre revisar en negocio real).

**API JSON (para integraciones o pruebas):** `POST /api/c360/ocr-mock` con cuerpo JSON `cliente_id` y `fase_max_detectada` (requiere mismo permiso que la ficha).

---

## 6. Cola prioritaria de llamadas (`/admin/c360/llamadas-hoy`)

**Uso**

- Priorizar llamadas o visitas según impacto (cupo sugerido y motivo).
- Enlaces rápidos a **ficha 360** y **cartola** de crédito.
- **Correr motor** (bloque amarillo): mismo proceso que el worker, con tope de clientes seleccionable.

**Columnas de venta proactiva**

- **Seguimiento IA:** indica si hubo envío por WhatsApp, **clic** en el enlace público de la oferta o **venta** generada desde la cotización C360.
- **Enviar oferta:** genera una **cotización** con kit según la etapa del cliente, aplica **5% de descuento en línea** si el score de puntualidad es **> 90**, registra un **token** de seguimiento y envía **WhatsApp Cloud (Meta)** si las credenciales están configuradas.  
  - Si el cliente tiene **cuotas a crédito vencidas** con saldo pendiente, **no** envía oferta: envía **mensaje de cobranza** y lo deja registrado.

---

## 7. Command Center (`/gerencia/c360-ia-dashboard`)

Vista ejecutiva: KPIs de cartera, prioridad de llamada, suma de cupos sugeridos, distribución por etapa, gráfico de snapshots, top oportunidades y bloque de ROI del día (según lo que tenga cargado el tablero).

**Ejecutar motor:** formulario POST con máximo de clientes; opción de volver a la cola de llamadas tras ejecutar.

---

## 8. Venta proactiva — kits, cotización y enlaces públicos

### 8.1 Cómo se arma el kit

El sistema busca productos **activos con stock**, cuya **subcategoría, categoría o nombre** contengan palabras clave asociadas a la **etapa actual** del cliente (por ejemplo instalaciones: PVC, cable, eléctrico, etc.). El detalle exacto está en la constante `C360_KIT_SUBCATEGORIA_KEYWORDS` en `app.py` (ajustable por desarrollo si el catálogo usa otros nombres).

### 8.2 Cotización y link de seguimiento

- Se crea una cotización tipo **`COT-…`** con nota interna de oferta C360.  
- Se guarda un registro en **`c360_proactiva_ofertas`** con **token** único.

**Enlaces públicos (sin login del cliente):**

- `GET /p/c360-oferta/<token>` — página de confirmación; registra el **primer clic**.  
- `GET /p/c360-oferta/<token>/pdf` — vista imprimible de la cotización; también puede registrar clic si aún no estaba marcado.

### 8.3 WhatsApp automático al subir de fase

Solo si:

- Variable de entorno **`C360_WA_AUTO_PHASE=1`** (o `true` / `yes` / `on`).  
- La **etapa sube** respecto a la guardada antes del cálculo (por ejemplo de OBRA_GRUESA a INSTALACIONES).  
- No haya envío reciente del mismo tipo (antienfado, ventana de días).  
- Cliente con **teléfono** usable para Chile (`56…`).  
- **Meta Cloud API** configurada (`WHATSAPP_CLOUD_ACCESS_TOKEN`, `WHATSAPP_CLOUD_PHONE_NUMBER_ID`).

**Reglas de negocio automáticas**

- Si hay **mora** (cuota a crédito vencida con saldo pendiente): mensaje de **cobranza**, no de oferta.  
- Si **no** hay mora pero tampoco hay **cupo disponible ni saldo a favor** (ambos casi nulos): **no** se envía oferta automática.

Para que el enlace del mensaje sea **absoluto** en producción, defina **`PUBLIC_BASE_URL=https://su-dominio.com`** (sin barra final o con barra, según cómo lo monten en el servidor).

**Nota Meta:** los mensajes salen como texto. Meta puede exigir **plantillas aprobadas** en algunos casos (número nuevo, fuera de ventana 24 h, etc.). Si falla el envío, revisar el log / respuesta en `wa_result` del registro o en logs del servidor.

### 8.4 Conversión a venta

Si desde el ERP convierten la cotización en venta (`convertir` en el flujo de cotizaciones), el sistema intenta marcar en **`c360_proactiva_ofertas`** la **venta** y la **fecha de conversión** vinculada a esa cotización.

---

## 9. Productos — calidad del 360

Sin **`fase_obra`** coherente en los productos:

- Gran parte del monto puede caer en **“sin clasificar”**.  
- El predictor tiende a **OBRA_GRUESA** y puede activar la cola por **calidad de datos**.

**Recomendación operativa:** mantener `fase_obra` en productos de rotación y en los que compran los clientes a crédito / obra. Revisar también **subcategorías** legibles para que los kits de la venta proactiva encuentren SKU.

---

## 10. Cron nocturno — worker C360

**Endpoint:** `POST /api/c360/worker-noche`  

**Autenticación:** cabecera `Authorization: Bearer <secreto>` donde el secreto es:

- `C360_CRON_SECRET`, o si no existe,  
- `COBRANZA_DISPATCH_CRON_SECRET`.

**Cuerpo JSON opcional:** `{"max": 300}` (límite de clientes a procesar; el sistema acota a un rango seguro).

**Ejemplo (curl):**

```bash
curl -sS -X POST "https://SU_HOST/api/c360/worker-noche" \
  -H "Authorization: Bearer SU_SECRETO" \
  -H "Content-Type: application/json" \
  -d "{\"max\":400}"
```

Si el secreto no está definido en el servidor, el endpoint responde error de configuración.

---

## 11. Variables de entorno útiles (resumen)

| Variable | Uso |
|----------|-----|
| `C360_CRON_SECRET` | Bearer para el worker nocturno. |
| `WHATSAPP_CLOUD_ACCESS_TOKEN` | Token Meta para envío Cloud API. |
| `WHATSAPP_CLOUD_PHONE_NUMBER_ID` | ID del número en Meta. |
| `WHATSAPP_CLOUD_API_VERSION` | Opcional (por defecto se usa una versión tipo v21.0). |
| `C360_WA_AUTO_PHASE` | `1` / `true` / `yes` / `on` para activar WhatsApp automático al **subir de fase**. |
| `PUBLIC_BASE_URL` | URL base pública del ERP para armar enlaces en mensajes (ej. `https://erp.empresa.cl`). |
| `C360_COSTO_IA_DIARIO_CLP` | Referencia de costo diario para ROI en dashboard (si aplica). |

Detalle adicional puede estar en `.env.example` del proyecto.

---

## 12. Preguntas frecuentes

**¿Por qué muchos clientes salen OBRA_GRUESA en la cola?**  
Suele ser la rama **calidad de datos**: compras con alto porcentaje sin `fase_obra` en productos. Mejorar catálogo y volver a correr el motor.

**¿El cupo sugerido modifica el límite del cliente?**  
No automáticamente; es una guía para comercial o crédito.

**¿Por qué no llega el WhatsApp?**  
Revisar credenciales Meta, número del cliente, políticas de plantillas, y si `C360_WA_AUTO_PHASE` está activo solo para el envío **automático**; el manual desde la cola no depende de esa variable.

**¿El cliente POS genérico aparece en 360?**  
No; está excluido del motor y fichas C360.

---

## 13. Responsabilidades sugeridas

| Rol | Acciones típicas |
|-----|-------------------|
| **Administración / IT** | Configurar cron, secretos, `PUBLIC_BASE_URL`, credenciales WhatsApp; revisar logs. |
| **Gerencia** | Command Center, ejecutar motor antes de reuniones, interpretar KPIs. |
| **Ventas / crédito** | Cola de llamadas, fichas 360, enviar ofertas, convertir cotizaciones, cobranza cuando corresponde. |
| **Compras / mantenedor** | `fase_obra` y nombres de categoría/subcategoría alineados a las reglas de kits. |

---

*Documento alineado al código del ERP LhexIA IA. Si cambian rutas o reglas en una versión nueva, actualizar este manual junto al despliegue.*

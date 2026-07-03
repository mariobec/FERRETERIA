# Gmail — Filtro DTE XML · Ferretería Santo Domingo

Correo: **ferreteria426@gmail.com**  
RUT receptor SD (import ERP): **8054120-1**

---

## Paso 1 — Crear etiquetas en Gmail

1. Gmail → icono **Etiquetas** (menú izquierdo) → **Crear etiqueta**.
2. Crear estas tres (nombres exactos, recomendados):

| Etiqueta | Uso |
|----------|-----|
| `DTE-XML-Entrada` | Todo correo sospechoso de traer DTE (filtro automático) |
| `DTE-8054120-1` | XML cuyo **receptor** es Ferretería Santo Domingo |
| `DTE-Otra-Sociedad` | XML de otra razón social (no importar al ERP SD) |

Opcional: `DTE-XML-Sin-RUT` (XML ilegible).

---

## Paso 2 — Filtro Gmail (cada vez que llega un correo)

1. Gmail → ⚙️ **Ver toda la configuración** → pestaña **Filtros y direcciones bloqueadas**.
2. **Crear filtro nuevo**.

### Criterios (copiar en «Tiene las palabras»)

```
has:attachment (filename:xml OR filename:XML OR DTE OR "Documento Tributario" OR "Factura Electronica" OR sii.cl OR chilemat)
```

Alternativa más simple (más correos, menos precisa):

```
has:attachment filename:xml
```

3. **Crear filtro** → marcar:
   - ☑ **Aplicar la etiqueta:** `DTE-XML-Entrada`
   - ☐ No marcar «Eliminar» ni «Saltar Recibidos» (dejar en bandeja)
4. **Crear filtro**.

> Gmail **no puede** leer el RUT dentro del XML al recibir el correo.  
> Por eso el filtro solo marca **entrada posible DTE**; el RUT lo clasifica el script LhexIA.

---

## Paso 3 — Variables en `.env.local`

```env
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USE_SSL=1
IMAP_USER=ferreteria426@gmail.com
IMAP_PASSWORD=contraseña_de_aplicacion_16_caracteres
IMAP_FOLDER=INBOX
DTE_RUT_RECEPTOR=8054120-1
DTE_GMAIL_LABEL_ENTRADA=DTE-XML-Entrada
DTE_GMAIL_LABEL_SD=DTE-8054120-1
DTE_GMAIL_LABEL_OTRO=DTE-Otra-Sociedad
DTE_CORREO_CARPETA=datos_rcv
```

---

## Paso 4 — Script: etiquetar por RUT receptor

### Solo etiquetar (recomendado la primera vez, buzón grande)

```powershell
cd "c:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
.\venv\Scripts\python.exe scripts\lector_correo_dte.py --solo-etiquetar --recientes --limite 100 -v
```

### Etiquetar cola del filtro Gmail

```powershell
.\venv\Scripts\python.exe scripts\lector_correo_dte.py --solo-etiquetar --carpeta-imap "DTE-XML-Entrada" --recientes --limite 200 -v
```

### Etiquetar + importar al ERP (solo RUT 8054120-1)

```powershell
.\venv\Scripts\python.exe scripts\lector_correo_dte.py --carpeta-imap "DTE-8054120-1" --limite 50 -v
```

---

## Flujo operativo recomendado

```
Correo llega
    ↓  (filtro Gmail automático)
Etiqueta DTE-XML-Entrada
    ↓  (script cada 15–30 min o manual)
Lee XML → RUT receptor
    ├─ 8054120-1  → etiqueta DTE-8054120-1 + recepción documental ERP
    └─ otro RUT   → etiqueta DTE-Otra-Sociedad (no ERP)
    ↓  (operador recepciones)
Paso 2 confirmación física → cargar stock
```

---

## ¿Trae la historia al ERP?

| Escenario | ¿Entra al ERP? |
|-----------|----------------|
| **Correos nuevos** que el filtro Gmail etiqueta como `DTE` | Sí, si el XML tiene receptor **8054120-1** → recepción documental (sin stock hasta paso 2) |
| **~77.000 sin leer en Recibidos** (antes del filtro) | **No** — el job **no** lee todo INBOX |
| **DTE otra sociedad** (otro RUT receptor) | Solo etiqueta `DTE-Otra-Sociedad`, **no ERP** |
| **XML SII** (acuse/envío, no factura compra) | Etiqueta `DTE-XML-Sin-RUT`, **no ERP** |

Para migrar **historial** a propósito (proyecto aparte, por lotes):

```powershell
# Solo clasificar (no ERP) — lotes de 500, repetir manualmente
.\venv\Scripts\python.exe scripts\lector_correo_dte.py --solo-etiquetar --recientes --limite 500 -v

# Luego importar solo lo ya etiquetado SD
.\venv\Scripts\python.exe scripts\lector_correo_dte.py --carpeta-imap DTE-8054120-1 --todos --limite 100 -v
```

---

## ERP — Visor y cargador histórico

Rutas en LhexIA (permiso `gestionar_compras` o `admin_inventario`):

| Pantalla | URL | Uso |
|----------|-----|-----|
| **Visor facturas** | `/recepciones/visor` | Folio, proveedor, fechas, mes/año, origen correo; detalle de líneas al clic |
| **Cargador DTE** | `/recepciones/cargador-dte` | Carga por mes/año desde Gmail (solo RUT **8054120-1**) |
| Lista recepciones | `/recepciones` | Enlaces rápidos al visor y cargador |

### Carga 2026 desde la UI

1. Ir a **Recepciones → Cargador DTE correo**.
2. Elegir año **2026** (o mes concreto) → **Ejecutar carga**.
3. Opcional: **Cargar todo 2026** (puede tardar; revisar log).

### Carga 2026 por script (lotes)

```powershell
.\scripts\tareas\migracion_dte_2026.bat
# o
powershell -ExecutionPolicy Bypass -File scripts\tareas\migracion_dte_2026.ps1
```

Equivalente manual:

```powershell
.\venv\Scripts\python.exe scripts\lector_correo_dte.py --desde 2026-01-01 --hasta 2027-01-01 --carpeta-imap DTE-8054120-1 --todos --limite 200 -v
```

> Las recepciones documentales **no mueven stock** hasta el paso 2 del workflow.

---

## Job automático Windows (instalado)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\tareas\instalar_job_gmail_dte.ps1
```

- Tarea: **`LhexIA-Gmail-DTE-SantoDomingo`**
- Cada **30 min**: etiqueta carpeta `DTE` → importa carpeta `DTE-8054120-1`
- Log: `logs/gmail_dte_job_YYYY-MM-DD.log`

---

## Automatizar en Windows (Programador de tareas)

| Campo | Valor |
|-------|--------|
| Programa | `...\venv\Scripts\python.exe` |
| Argumentos | `scripts\lector_correo_dte.py --solo-etiquetar --carpeta-imap DTE-XML-Entrada --recientes --limite 100` |
| Iniciar en | `...\sistema_ventas_limpio` |
| Repetir | Cada 30 minutos |

Segundo job (import ERP):

```
scripts\lector_correo_dte.py --carpeta-imap DTE-8054120-1 --limite 30
```

---

## Preguntas frecuentes

**¿Llega DTE de otra sociedad al mismo correo?**  
Queda en `DTE-Otra-Sociedad` y **no** crea recepción en Santo Domingo.

**¿Transferencias bancarias en el mismo correo?**  
Ver **`MANUALES DE OPERACIÓN/GMAIL_FILTRO_TRANSFERENCIAS_SD.md`** — etiqueta `Transferencias-Banco` → bandeja `/caja/transferencias`.

**¿77.000 correos sin leer?**  
Use `--recientes --limite N` o procese solo la carpeta `DTE-XML-Entrada` tras crear el filtro en correos nuevos.

**¿Etiqueta no aparece?**  
Créela manualmente en Gmail una vez; el script también puede crearla vía IMAP al aplicarla.

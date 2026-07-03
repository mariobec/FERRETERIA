# Gmail — Filtro transferencias bancarias · Ferretería Santo Domingo

Correo: **ferreteria426@gmail.com** (misma cuenta IMAP que DTE)  
Bandeja ERP: **`/caja/transferencias`**

---

## Paso 1 — Etiquetas Gmail

El script `scripts/setup_gmail_transferencias_correo.py` crea vía IMAP:

| Etiqueta | Uso |
|----------|-----|
| `Transferencias-Entrada` | Reserva (filtros futuros / histórico) |
| `Transferencias-Banco` | Avisos banco confirmados → lee el ERP |

---

## Paso 2 — Importar filtros Gmail (una vez)

1. Gmail → ⚙️ **Ver toda la configuración** → **Filtros y direcciones bloqueadas**.
2. Desplácese abajo → **Importar filtros**.
3. Seleccione el archivo del repo:

```
config/gmail_filtro_transferencias.xml
```

4. Confirme importación (crea reglas automáticas para correos nuevos).

> Los filtros excluyen DTE/SII (`-filename:xml -DTE -sii.cl`) para no mezclar con facturas compra.

---

## Paso 3 — Variables `.env.local`

Tras ejecutar el setup, deben existir (el script las añade si faltan):

```env
TRF_CORREO_FOLDER=Transferencias-Banco
TRF_CORREO_DIAS=45
TRF_GMAIL_LABEL=Transferencias-Banco
TRF_GMAIL_LABEL_ENTRADA=Transferencias-Entrada
```

IMAP compartido con DTE: `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`.

---

## Paso 4 — Setup inicial (etiquetar + sync ERP)

```powershell
cd "c:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
.\.venv\Scripts\python.exe scripts\setup_gmail_transferencias_correo.py -v
```

Solo clasificar Gmail sin BD:

```powershell
.\.venv\Scripts\python.exe scripts\setup_gmail_transferencias_correo.py --solo-etiquetar --limite 200 -v
```

---

## Flujo operativo

```
Correo banco llega
    ↓  (filtro Gmail importado)
Etiqueta Transferencias-Banco
    ↓  (job cada 2 min o botón «Sincronizar correo»)
Bandeja /caja/transferencias
    ↓  (match monto/referencia ↔ vale Pagado Transferencia)
Confirmar con correo → habilita entrega QR
```

---

## Job automático Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\tareas\instalar_job_gmail_transferencias.ps1
```

- Tarea: **`LhexIA-Gmail-Transferencias-SantoDomingo`**
- Cada **2 min**: clasifica INBOX + sync carpeta `Transferencias-Banco` → ERP (**sin ventana de consola**)
- Log: `logs/gmail_transferencias_job_YYYY-MM-DD.log`

Si aparecía una ventana negra cada 2 min, ejecute de nuevo el instalador de arriba.

---

## Relación con DTE

| Módulo | Carpeta Gmail | Pantalla ERP |
|--------|---------------|--------------|
| DTE compra | `DTE-8054120-1` | `/recepciones/cargador-dte` |
| Transferencias caja | `Transferencias-Banco` | `/caja/transferencias` |

Misma cuenta, reglas separadas, sin cruce de stock.

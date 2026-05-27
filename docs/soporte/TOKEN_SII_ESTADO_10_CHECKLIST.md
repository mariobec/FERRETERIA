# Checklist: Token SII ESTADO 10 (Maullín) — LhexIA ERP

**Empresa:** Ferretería Santo Domingo · RUT `8054120-1`
**Ambiente:** Certificación → `https://maullin.sii.cl`
**Síntoma:** Semilla OK (`estado=00`) pero **token falla (`estado=10`, glosa *Error Interno*)** → facturas quedan `PENDIENTE_ENVIO` sin Track ID.

**Última verificación ERP (2026-05-26):**

| Ítem | Estado |
|------|--------|
| `instance/certs/emisor.pfx` existe | Sí |
| RUT certificado = `8054120-1` | Sí (Luis Gaston Rivera Perez, Firma.Digital, vigente hasta 2028-08-05) |
| Semilla Maullín | OK |
| Token Maullín | **ESTADO 10** |
| CAF factura 33 | id 66, folios 1–50, ~49 libres |
| Cola `PENDIENTE_ENVIO` | 1 venta (ej. #3040) |

**Conclusión:** El ERP conecta y firma; el SII **rechaza la autenticación** (habilitación portal / certificado / software de mercado). No marcar ventas como `ENVIADO` hasta tener token OK.

---

## Fase A — Revisión local (15 min, en el PC del ERP)

- [ ] **A1.** Archivo certificado: `instance/certs/emisor.pfx` (mismo que usas para entrar al portal SII si aplica).
- [ ] **A2.** Contraseña en `.env.local`: `SII_CERT_PFX_PASSWORD=` o `SII_CERT_PFX_PASSWORD_FILE=` (sin espacios raros ni BOM).
- [ ] **A3.** RUT empresa: `EMPRESA_RUT=8054120-1` (mismo que el certificado).
- [ ] **A4.** Ambiente: `SII_AMBIENTE=certificacion` (no `produccion` hasta cerrar certificación).
- [ ] **A5.** SOAP activo: `SII_SOAP_ENABLED=1` (o no definido = habilitado por defecto).
- [ ] **A6.** Resolución en XML (certificación típica):

  ```env
  SII_FCH_RESOLUCION=2021-03-24
  SII_NRO_RESOLUCION=0
  ```

- [ ] **A7.** Auditar el .pfx:

  ```powershell
  cd "C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
  .\venv\Scripts\python.exe scripts\auditar_pfx_sii.py instance\certs\emisor.pfx
  ```

  Debe mostrar: `Coincide empresa: True`, `Vigente: True`.

- [ ] **A8.** Diagnóstico SII:

  ```powershell
  .\venv\Scripts\python.exe scripts\fe_diagnostico_sii.py > fe_diag_ultimo.txt 2>&1
  ```

  **Éxito:** `Token: ok=True estado=00`. **Bloqueo:** `estado=10` → Fase B.

- [ ] **A9.** Si Maullín devuelve **503** en semilla: esperar 10–30 min y repetir A8 (caída del SII).

---

## Fase B — Portal SII certificación (Maullín) — crítico

Entrar con certificado digital de la empresa (titular `8054120-1` recomendado).

**URL:** https://maullin.sii.cl → menú **Certificación** / **Factura electrónica**.

### B1 — Certificado y usuario autorizado

- [ ] **B1.1** El certificado del ERP es el **mismo** con el que entras al portal (RUT `8054120-1`).
- [ ] **B1.2** Menú **Modificar usuarios**:
  - RUT `8054120-1` (Luis Gaston Rivera Perez): permisos **Firmar** y **Enviar**.
  - Alternativa solo si aplica: `9788569-9` (Ladislao Cortés) con su propio .pfx.

### B2 — Software de facturación (facturas 33)

**Importante:** *BOLETA ELECTRÓNICA MULTICAJA* es para **boletas 39** (Klap), no basta para **facturas 33** desde LhexIA.

- [ ] **B2.1** **Sistema de facturación de mercado** → **Actualización datos empresa autorizada**.
- [ ] **B2.2** Registrar software:
  - Nombre: `LhexIA ERP` / `LhexIA Ferretería`
  - URL: `https://www.lhexia.cl`
  - Tipo: facturación de mercado (facturas)
- [ ] **B2.3** Empresa autorizada a **enviar DTE** en certificación.

### B3 — CAF tipo 33 (Maullín)

- [ ] **B3.1** CAF 33 solo desde Maullín (no CAF de producción `www.sii.cl`).
- [ ] **B3.2** En ERP: `python scripts/cargar_caf_real.py` — CAF actual id **66**, folios **1–50**.

### B4 — Boletas vs facturas

| Documento | Envío SII | Portal |
|-----------|-----------|--------|
| Boleta 39 | Multicaja/Klap | MULTICAJA |
| Factura 33 | LhexIA ERP | Software **LhexIA** |

- [ ] **B4.1** ERP: `SII_FE_SOLO_FACTURA=1`.

---

## Fase C — Verificar (después del portal, esperar 5–15 min)

```powershell
.\venv\Scripts\python.exe scripts\fe_diagnostico_sii.py
.\venv\Scripts\python.exe scripts\fe_resolver_facturas.py
```

- [ ] **C1.** Semilla `estado=00`
- [ ] **C2.** Token `ok=True estado=00`
- [ ] **C3.** `fe_resolver_facturas` muestra `Token: True`

---

## Fase D — Destrabar cola (solo si C2 OK)

```powershell
.\venv\Scripts\python.exe scripts\fe_resolver_facturas.py --reintentar 3040
```

- [ ] **D1.** Venta pasa a `ENVIADO` + Track ID en `/admin/facturacion/cola`.

---

## Fase E — Escalación SII (si sigue ESTADO 10)

- [ ] **E1.** Tel. **227175600**
- [ ] **E2.** Adjuntar: `fe_diag_ultimo.txt`, capturas portal (usuarios + software LhexIA).
- [ ] **E3.** Consulta: GetToken ESTADO 10 con semilla 00; habilitación factura 33 Maullín.

---

## Códigos autenticación

| ESTADO | Significado |
|--------|-------------|
| `00` | OK |
| `10` | Rechazo firma / certificado / no habilitado Maullín |
| `12` | RUT certificado distinto al registrado |

---

## Qué NO hacer

- No Palena/producción hasta token OK en Maullín.
- No CAF producción en certificación.
- No `ENVIADO` manual sin Track ID.
- No enviar boletas 39 por LhexIA si van por Multicaja.

---

## Referencias repo

- `scripts/fe_diagnostico_sii.py`
- `scripts/fe_resolver_facturas.py`
- `scripts/auditar_pfx_sii.py`
- `memory.md` (FE 2026-05-26)

---

## Registro de avance

| Fecha | Acción | Token |
|-------|--------|-------|
| 2026-05-26 | Diagnóstico | ESTADO 10 |
| | | |

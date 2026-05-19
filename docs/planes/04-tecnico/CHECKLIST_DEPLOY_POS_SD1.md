# Checklist deploy POS SD-1 (local → Render/Neon)

**Estado:** preparado para commit único cuando Mario confirme estabilidad en piso.  
**No incluye** datos de tarjetas (tokens) ni PINs en el repo.

---

## 1. Dónde se crean las tarjetas de supervisor

| Dónde | URL / ruta | Quién |
|--------|------------|--------|
| **Pantalla admin (recomendado)** | `/admin/pos-autorizacion-descuentos` | Usuario con permiso `gestionar_usuarios` |
| **Atajo** | Admin empresa → enlace «POS — autorización descuentos» | Igual |
| **CLI (prod/local)** | `python scripts/pos_generar_tarjeta_supervisor.py --correo …` | Operador con `DATABASE_URL` correcto |

En la pantalla admin, tabla **Supervisores**:

1. El usuario debe tener permiso **`autorizar_descuento_pos`** (Roles y permisos).
2. Botón **PIN** → 4 dígitos.
3. Botón **Tarjeta** → genera código `LHX-SUP-…` + código de barras (solo se muestra una vez).
4. **Revocar** invalida la tarjeta anterior.

---

## 2. Antes del deploy en Neon (SQL)

Ejecutar en orden (o confiar en `_asegurar_*` al arrancar, pero en prod conviene explícito):

```bash
# Con psql o consola Neon:
psql "$DATABASE_URL" -f sql/2026_05_18_pos_autorizacion_descuento.sql
```

Opcional rendimiento (si aplica el plan SD-1 BD):

```bash
psql "$DATABASE_URL" -f sql/2026_05_21_rendimiento_sd1_postgresql.sql
```

---

## 3. Después del deploy (datos operativos — no van en git)

### Luis Gastón Rivera Pérez (producción)

1. Verificar usuario en prod (correo `ferreteria426@gmail.com` o el que use SD).
2. Corregir nombre si dice «Castro»: editar en **Usuarios** o:
   ```bash
   python scripts/pos_generar_tarjeta_supervisor.py \
     --correo ferreteria426@gmail.com \
     --nombre "LUIS GASTÓN RIVERA PEREZ" \
     --dar-permiso-rol \
     --pin 4321
   ```
   (Cambiar PIN por el acordado con el cliente; no documentar PIN en git.)
3. Si ya hay tarjeta local `LHX-SUP-HUKKT22T5HPC`, **no sirve en prod** — generar tarjeta nueva en prod.

### Umbral PIN empresa

En `/admin/pos-autorizacion-descuentos` → guardar umbral % (default 20).

---

## 4. Archivos del commit sugerido (bundle POS + descuentos)

### Código POS / descuentos (obligatorio)

- `app.py` — API nueva venta, `pos_vale_resume`, autorización descuento en `actualizar_item` / `finalizar_venta`
- `blueprints/pos.py` — `/api/pos/nueva-venta`
- `services/pos_autorizacion_descuento_service.py` — **nuevo**
- `static/js/pos.js` — vale resume, descuento %, modales
- `static/css/pos-premium-layout.css` — carrito, filtros, z-index modales
- `templates/punto_venta.html` — modales, config JSON
- `templates/pos/includes/premium_cart_cards.html` — chips stock, menú dto
- `templates/pos/includes/unified_search_vendedor.html` — filtros Tienda/Operativo/Catálogo
- `templates/admin_pos_autorizacion.html` — **nuevo**
- `templates/ticket_vale.html` — línea autorización descuento
- `sql/2026_05_18_pos_autorizacion_descuento.sql` — **nuevo**
- `tests/test_pos_autorizacion_descuento.py` — **nuevo**
- `tests/test_routes_criticas.py` — si hay cambios smoke POS

### Scripts

- `scripts/pos_generar_tarjeta_supervisor.py` — **nuevo** (solo operación, no secrets)

### Excluir del commit POS (revisar antes de `git add`)

- Carpetas scaffold vacías (`adapters/`, `application/`, `domain/`, …) si no son parte del entregable.
- `sql/2026_05_21_rendimiento_sd1_postgresql.sql` — solo si se validó en Neon.
- Cambios solo de documentación/planes no bloqueantes para POS.

---

## 5. Mensaje de commit propuesto (cuando Mario diga «commit»)

```
POS SD-1: vale reanudar/nueva venta, descuento % con tarjeta supervisor, carrito premium

- Modal vale en armado y API POST /api/pos/nueva-venta
- Autorización descuentos: tarjeta LHX-SUP, PIN umbral, admin y tests
- UX carrito: chips T/B, menú dto, filtros búsqueda Tienda primero
```

---

## 6. Verificación post-deploy

- [ ] `pytest tests/test_pos_autorizacion_descuento.py -m smoke -q`
- [ ] `pytest tests/test_routes_criticas.py -k finalizar_venta_pos -q`
- [ ] POS: Ctrl+F5, descuento 5% con tarjeta supervisor
- [ ] POS: modal vale → Continuar / Nueva venta
- [ ] Ticket vale muestra «Aut: …» si hubo supervisor

---

*Última actualización: 2026-05-19 — sesión Cursor POS SD-1.*

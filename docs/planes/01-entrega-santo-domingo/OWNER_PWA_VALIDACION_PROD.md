# PWA Dueño — validación completa en producción

**Commit:** `72f349a` · **Push:** 2026-05-21 · **URL:** https://www.lhexia.cl

---

## 1. Deploy (automático)

| Check | Cómo |
|-------|------|
| Render `main` desplegado | Dashboard Render → último deploy = `72f349a` o posterior |
| Manifest vivo | https://www.lhexia.cl/owner-pwa/manifest.webmanifest → JSON `LhexIA Dueño` |
| Service worker | https://www.lhexia.cl/owner-pwa/sw.js → 200, sin cachear `/api/` |
| API sin sesión | https://www.lhexia.cl/api/v1/owner/dashboard → **401** `login_required` (correcto) |

---

## 2. Variables Render (recomendadas)

En **Environment** del servicio web:

```env
OWNER_SUPERVISOR_TELEFONO=+56923739904
OWNER_PWA_SUCURSAL_LABEL=Santo Domingo
OWNER_GUARDIAN_UN_LOCAL=1
LHEXIA_CLIENTE_SD_NOMBRE=Ferretería Santo Domingo
```

*(Número de prueba supervisor — Mario, mayo 2026.)*

Sin teléfono: el botón «Llamar supervisor» queda deshabilitado (gris).

**Importante:** el número es el del **supervisor de turno** (variable de entorno), **no** el móvil del usuario que inició sesión en el ERP.

**Voz (micrófono):** no implementado en Guardián SD-1 — solo toast «próximamente SD-2». No es fallo; ver [`GUARDIAN_SD1_ALCANCE_CERRADO.md`](GUARDIAN_SD1_ALCANCE_CERRADO.md).

---

## 3. Permisos usuario

El dueño / gerente debe tener **al menos uno**:

- `panel_gerencia`
- `ver_gerencia`
- `gestionar_usuarios`

(Admin bypass automático.)

---

## 4. Checklist en teléfono (5 min)

1. Chrome → **https://www.lhexia.cl/login** → ingresar con cuenta gerencia.
2. Ir a **https://www.lhexia.cl/owner-mobile** (no debe quedar en login).
3. Ver **2 tarjetas semáforo**: Caja + Inventario (colores verde/amarillo/rojo).
4. Estado arriba: «En línea» tras ~2 s (poll API).
5. Tocar tarjeta **Caja** → abre `/admin/control-center`.
6. Tocar tarjeta **Inventario** → abre abastecimiento con filtro alerta.
7. **Actualizar** (botón) → datos refrescan sin recargar página.
8. *(Opcional)* Con `OWNER_SUPERVISOR_TELEFONO` en Render → **Llamar supervisor** habilitado → tocar abre app Teléfono con ese número.
9. *(No probar SD-1)* Botón **micrófono** → mensaje «SD-2» (voz Guardián no existe aún).
10. Menú Chrome → **Añadir a pantalla de inicio** → icono Guardián standalone.
11. Cerrar app y reabrir desde icono → shell carga (SW).

---

## 5. API (referencia JSON)

`GET /api/v1/owner/dashboard?nocache=1` (con cookie de sesión):

```json
{
  "status": "success",
  "data": {
    "tarjeta_caja": { "estado": "verde|amarillo|rojo", "titulo", "mensaje", "timestamp", "accion_requerida", "tipo_accion" },
    "tarjeta_inventario": { "estado", "titulo", "mensaje", "skus_bajo_minimo", ... },
    "meta": { "alertas_abiertas", "supervisor_telefono", "generado_en" }
  }
}
```

**Fuentes:** `agente_ejecuciones` (Operador) + contexto caja + conteo SKU &lt; 5.

---

## 6. Tests locales (regresión)

```bash
pytest tests/test_owner_dashboard_api.py -v
```

Esperado: **5 passed**, 1 skipped (gate permiso vendedor).

---

## 7. Cuidados operativos

- Primer escaneo masivo Operador en prod puede generar muchas alertas → hacer en horario bajo.
- La PWA **no** sustituye Control Center; es resumen + acceso rápido.
- Micrófono / voz: **SD-2** (botón presente, funcionalidad futura).

---

*Vinculado: `docs/memory.md` § PWA Dueño · `CHECKPOINT_RETOMAR_2026_05_21.md`*

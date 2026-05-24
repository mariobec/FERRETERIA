# SD-1 — Día 1 en piso (TIENDA + salud)

**Objetivo del día:** cerrar conteo del almacén **Tienda** y dejar **salud inventario** revisada. Caja abierta para prueba POS si el equipo puede.

**Checklist maestro:** [`SD1_CIERRE_FASE1_VERTEX.md`](SD1_CIERRE_FASE1_VERTEX.md)  
**Imprimir 1 página:** [`SD1_DIA1_PISO_HOJA_1_PAGINA.md`](SD1_DIA1_PISO_HOJA_1_PAGINA.md)  
**Backup Neon (C7):** [`SD1_BACKUP_NEON_C7.md`](SD1_BACKUP_NEON_C7.md)  
**Runbook corto:** [`CLIENTE_SANTO_DOMINGO.md`](CLIENTE_SANTO_DOMINGO.md)

---

## Antes de salir a piso (5 min)

```bash
python scripts/sd1_cierre_preflight.py
python scripts/sd1_estado_piso.py
```

| Script | Qué confirma |
|--------|----------------|
| `sd1_cierre_preflight.py` | Almacenes, rutas HTTP, catálogo |
| `sd1_estado_piso.py` | Caja, sesiones enrolamiento, ventas hoy, alertas |

- [ ] Backup Neon anotado (fecha: ___________) — **C7** → pasos en [`SD1_BACKUP_NEON_C7.md`](SD1_BACKUP_NEON_C7.md)
- [ ] Ctrl+F5 o “Añadir a inicio” si usan PWA Guardián

---

## Bloque 1 — Caja (15 min)

| Paso | Ruta | OK |
|------|------|-----|
| Abrir turno | `/abrir_caja` | [ ] |
| Verificar redirección POS no bloqueada | `/punto_venta` | [ ] |
| *(opcional)* Un vale de prueba + cobro | POS → Caja | [ ] |

Sin caja abierta el POS puede redirigir a abrir caja — es esperado.

---

## Bloque 2 — Enrolamiento TIENDA (bloque principal)

Almacén detectado en preflight (ajustar si en Admin cambió el nombre):

| Campo | Valor típico |
|-------|----------------|
| ID | `1` |
| Código | `TIENDA` |
| Nombre | Tienda / Mostrador |

| Paso | Acción | OK |
|------|--------|-----|
| 1 | Ir a `/inventario/enrolamiento` | [ ] |
| 2 | Crear sesión → almacén **TIENDA** | [ ] |
| 3 | Escanear / buscar productos (pistola o teclado) | [ ] |
| 4 | Registrar cantidades por pasillo acordado | [ ] |
| 5 | Anotar `# sesión` y cantidad SKU contados | [ ] |

**Cierre lógico del almacén:** equipo da por terminado el conteo de Tienda (no hay botón “cerrar sesión” en v1 — criterio operativo: sesión con líneas + revisión salud).

---

## Bloque 3 — Salud inventario (10 min)

| Paso | Ruta | OK |
|------|------|-----|
| 1 | `/inventario/salud` | [ ] |
| 2 | Revisar desajustes maestro vs almacenes | [ ] |
| 3 | Export CSV si hay diferencias (`export=desajuste`) | [ ] |
| 4 | Plan de corrección anotado (ajuste o segunda pasada) | [ ] |

---

## Bloque 4 — Guardián (5 min — gerencia)

| Paso | OK |
|------|-----|
| `/owner-mobile` en celular | [ ] |
| Ventas hoy coherentes con caja | [ ] |
| Semáforos caja / inventario leíbles | [ ] |

---

## Fin del día — marcar checklist

En `SD1_CIERRE_FASE1_VERTEX.md`:

- **§B** fila almacén TIENDA: sesión [x], salud [x]
- **§C** si hubo vale/cobro de prueba
- **§D** Guardián [x] si probado

---

## Día 2 (preview)

- Enrolamiento **BODEGA** (id `2` típico)
- Vale con retiro **Bodega** → cobro → preparación bodega

---

*SD-1 Día 1 = un almacén bien contado vale más que tres sucursales ficticias en demo.*

# Runbook — Ferretería Santo Domingo (cliente #1 LhexIA)

> **Documento completo de entrega y desarrollo:** [`SANTO_DOMINGO_ENTREGA.md`](SANTO_DOMINGO_ENTREGA.md)  
> Este archivo es el **runbook corto de piso** (checklist D0 y flujos).

**Tipo:** Cliente diseño + primer go-live  
**Alcance prototipo (~2 semanas):** POS + inventario (toma física)  
**URL producción:** [www.lhexia.cl](https://www.lhexia.cl)  

---

## Antes de la toma de inventario (D0)

### 1. Almacenes (3 sucursales)

En **Administración → Almacenes** (o script existente `crear_almacenes_tienda_bodega.py`):

- [ ] Cada sucursal tiene al menos un almacén **activo** (tienda y/o bodega según operación).
- [ ] Anotar `id` y nombre de cada almacén para capacitación.

### 2. Permisos

Usuarios que contarán en piso necesitan uno de:

- `enrolamiento_inventario`
- `admin_inventario`

Vendedores POS:

- `pos_emitir_vale` (layout fullwidth vendedor)
- Caja abierta para emitir/cobrar según rol

### 3. Backup

```bash
# Desde PC con NEON_DATABASE_URL en .env.local
python scripts/sync_local_neon_render.py --verify-only
# O backup Neon desde consola antes de ajustes masivos
```

### 4. Tablas enrolamiento

Si flash “Faltan tablas de enrolamiento”, aplicar en BD:

- `sql/2026_05_06_enrolamiento_inventario.sql`
- Migraciones almacenes si aplica (`sql/2026_04_30_stock_por_almacen.sql`)

---

## Durante la toma — flujo recomendado

### Opción A: Enrolamiento con sesión (recomendado)

1. Ir a **`/inventario/enrolamiento`**
2. Elegir **almacén / sucursal** de la sesión
3. Escanear código de barras (pistola) o buscar producto
4. Registrar cantidad contada (suma en sesión)
5. Repetir por pasillo / zona
6. Al terminar sucursal: export o revisar en **Salud inventario**

### Opción B: Salud y corrección

1. **`/inventario/salud`** — listar desajustes maestro vs suma almacenes
2. Export CSV `export=desajuste`
3. Corregir con procedimiento acordado (ajuste UI o enrolamiento)

### Opción C: Auditoría móvil (cierre)

- Lista auditorías → conteo → **ajuste automático** → kardex  
- Permiso `admin_inventario` para cierre con impacto en stock

---

## POS en paralelo (ventas durante inventario)

1. **`/punto_venta`** — Ctrl+F5 tras cada deploy
2. Búsqueda: escribir **3+ letras** (o 2 tras próximo fix); si no hay resultados probar filtro **Catálogo**
3. Emitir vale → cobrar en caja
4. Retiro por línea: Tienda / Bodega / Despacho según stock real

---

## Criterios “prototipo OK” (fin semana 2)

| Área | Criterio |
|------|----------|
| Inventario | Las 3 sucursales con conteo registrado o plan de corrección documentado |
| POS | Al menos 1 sucursal con flujo vale completo sin bloqueos críticos |
| Datos | Códigos de barra críticos existen en catálogo |
| Equipo | 2+ usuarios capacitados por módulo |

---

## Escalamiento a LhexIA producto

Santo Domingo **no** es un fork: es el tenant de referencia. Cambios que beneficien al cliente deben:

- Pasar tests (`pytest tests/ -m smoke`)
- Documentarse en `../02-producto-lhexia/` si afectan otros ferreteros futuros
- Evitar hardcode “Santo Domingo” en lógica — usar `obtener_config_empresa()` hasta existir `tenant_settings`

---

## Contacto y soporte

- **Producto / técnico:** Mario Becerra Olea  
- **Implementación repo:** Cursor + documentación en `docs/ERP_MAESTRO.md`

# SD-1 — Backup Neon (C7) antes de inventario masivo

**Obligatorio** antes de ajustes masivos de stock o cierre de enrolamiento con correcciones en lote.

---

## Opción A — Consola Neon (recomendado, 2 min)

1. Entrar a [console.neon.tech](https://console.neon.tech) → proyecto **LhexIA / Ferretería**.
2. **Branches** → rama `main` (producción).
3. **Restore** o **Create backup** / snapshot según plan Neon.
4. Anotar en `SD1_CIERRE_FASE1_VERTEX.md`:
   - Fecha y hora: ___________
   - ID o nombre del snapshot: ___________
   - Quién lo ejecutó: ___________

---

## Opción B — pg_dump local (si tienes `NEON_DATABASE_URL`)

```powershell
cd "d:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
# Requiere pg_dump en PATH y NEON_DATABASE_URL en .env.local
python scripts/sync_local_neon_render.py --verify-only
```

Ver también: `docs/MIGRACION_RENDER_NEON.md`, `CLIENTE_SANTO_DOMINGO.md` § backup.

---

## Cuándo repetir backup

- Antes del **primer día** de conteo masivo (D1 Tienda).
- Antes de **purga o recarga** de maestro productos.
- Antes de script `purge_maestro_productos_neon.py` o carga masiva >500 filas.

---

## Registro en cierre SD-1

| Campo | Valor |
|-------|--------|
| Fecha backup C7 | ___________ |
| Método (consola / pg_dump) | ___________ |
| OK operación | [ ] |

*No sustituye el backup automático de Neon; es ancla humana para SD-1.*

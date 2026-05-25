# Checklist migración — PC nuevo (dev) + PC ex tienda (espejo)

**Fecha referencia:** 2026-05-24  
**Commit remoto esperado:** `0008158` — alerta al cerrar caja + Guardián poll 15 s  
**Repo:** `https://github.com/mariobec/FERRETERIA.git`

> No subir `.env.local` a Git. Copiar secretos solo por USB/carpeta segura.

---

## Tarea 1 — PC nuevo (desarrollo)

### En PC actual (antes de dejarlo solo como sucursal)

- [ ] `git log -1 --oneline` → `0008158` (o posterior)
- [ ] `git push origin main` hecho (remoto al día)
- [ ] Copia segura: `.env.local`, `.env`, notas Render/Neon/dashboard
- [ ] (Opcional) `pip freeze > requirements-local.txt` como referencia

### En PC nuevo

- [ ] Git instalado
- [ ] Python 3.11+ (misma línea que usabas)
- [ ] Cursor instalado
- [ ] `git clone https://github.com/mariobec/FERRETERIA.git`
- [ ] `cd sistema_ventas_limpio`
- [ ] `python -m venv venv` → activar venv
- [ ] `pip install -r requirements.txt`
- [ ] Pegar `.env.local` (modo dev: `DATABASE_URL` = misma Neon que Render)
- [ ] `git pull origin main` si el clone es viejo
- [ ] `git log -1` confirma `0008158+`
- [ ] `pytest tests/test_agente_operador.py -q` (smoke)
- [ ] Abrir carpeta en Cursor
- [ ] Render: deploy de `main` OK (cierre caja → alerta inmediata)

### Modo dev recomendado (hasta espejo listo)

```env
# PC nuevo — paridad con Render (ver .env.example)
DATABASE_URL=<misma URL Neon que Render>
```

---

## Tarea 2 — PC ex tienda (espejo + Ollama + Operador)

### Rol de la máquina

| Sí | No |
|----|-----|
| PostgreSQL local (espejo) | Cursor / desarrollo diario |
| Ollama + modelo 3B | Exponer Postgres a Internet |
| Worker Operador (tarea Windows) | Reemplazar Neon como “nube” |

### Instalación

- [ ] PostgreSQL instalado, servicio automático
- [ ] BD local creada (ej. `ferreteria_sd`) + usuario/contraseña
- [ ] Ollama instalado + modelo cargado
- [ ] Repo clonado (mínimo para scripts/worker)
- [ ] Sin suspensión / UPS si hay cortes

### `.env.local` — modo espejo

Ver plantilla en `.env.example` (sección “espejo”).

- [ ] `DATABASE_URL=postgresql://...@localhost:5432/ferreteria_sd`
- [ ] `NEON_DATABASE_URL=postgresql://...@....neon.tech/neondb?sslmode=require`
- [ ] `AGENTE_OPERADOR_USE_NEON=1` (con internet: alertas en Neon para Guardián en Render)
- [ ] `AGENTE_OLLAMA_ENABLED=1`
- [ ] `OLLAMA_MODEL` y `OLLAMA_TIMEOUT_SEC` según PC i3

### Datos y sync

**Regla:** con internet, **Neon + Render = verdad** para POS y celular (Guardián).

- [ ] Backup Neon antes del primer sync grande
- [ ] Si local vacío: restaurar **Neon → local** (`pg_dump` / restore), no pisar Neon sin querer
- [ ] `python scripts/sync_local_neon_render.py --verify-only`
- [ ] Conteos local vs Neon coherentes
- [ ] Sync completo solo si sabes la dirección (local→Neon **pisa** tablas en Neon)
- [ ] Tarea nocturna opcional: `--verify-only` diario

Scripts: `sync_local_neon_render.py`, `schema_sync_neon.py` (raíz del repo).

### Operador

- [ ] Tarea Windows `LhexIA-Operador-SD` (~10 min) → `agente_operador_ciclo.py`
- [ ] Firewall: Postgres solo LAN, no WAN
- [ ] Probar: `python scripts/verificar_operador_ollama.py` (si existe en repo)

### Contingencia sin internet (probar aparte, post SD-1)

- [ ] Documentado: Flask en LAN + `DATABASE_URL=localhost`
- [ ] Procedimiento vuelta de red: reconciliar local → Neon

---

## Flujo operativo (recordatorio)

```text
Cerrar caja (Render) → alerta en Neon (0 s)
Guardián poll 15 s (Render + Neon, PWA abierta)
PC ex tienda: Ollama enrich → actualiza fila en Neon (1–2 min)
```

Cron Operador 10 min = respaldo (vales viejos), no camino principal de caja.

---

## Comandos útiles

```powershell
# PC nuevo — verificar repo
git log -1 --oneline
pytest tests/test_agente_operador.py -q

# PC ex tienda — solo verificar conteos
cd C:\ruta\sistema_ventas_limpio
python scripts/sync_local_neon_render.py --verify-only
```

---

## Hecho cuando

| Tarea | Criterio |
|-------|----------|
| 1 Dev | Cursor + tests + `.env.local` en PC nuevo |
| 2 Espejo | Postgres local con datos + verify-only OK + Operador + Ollama |

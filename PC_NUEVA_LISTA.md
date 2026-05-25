# PC nueva — LhexIA ERP (desarrollo local)

Checklist cerrado **2026-05-25** para seguir desarrollo en esta máquina.

## Estado validado

| Ítem | Valor |
|------|--------|
| Repo | `https://github.com/mariobec/FERRETERIA.git` |
| Rama | `main` (commit `36de2f5` o posterior tras `git pull`) |
| Python | 3.12 en `.venv` |
| Postgres | 18 local, BD `ferreteria_local` |
| Clave `postgres` (esta PC) | `Azby1928` en `env_qa.txt` / `.env.local` |
| Demo datos | Dump USB `local_ferreteria_*.dump` restaurado |
| Smoke tests | `151 passed, 1 skipped` |

---

## Rutina diaria

```powershell
cd "C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
git pull origin main
.\venv\Scripts\python.exe -m pip install -r requirements.txt -q
pip install pytest pytest-cov   # solo si pytest no está instalado
$env:PGCLIENTENCODING = "UTF8"
.\venv\Scripts\python.exe app.py
```

Navegador: **http://localhost:5000**

Alternativa arranque: doble clic en `arrancar_erp.bat` (usa `.venv\Scripts\python.exe`).

---

## Antes de commit / push

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -m smoke -q --tb=no
```

Suite más amplia (opcional):

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_routes_criticas.py -q
```

---

## Archivos de entorno (no van a Git)

| Archivo | Uso |
|---------|-----|
| `env_qa.txt` | `DATABASE_URL` local, `SECRET_KEY`, SII cert path |
| `.env.local` | Igual + `NEON_DATABASE_URL` solo para scripts sync |

**Regla:** desarrollo local → `DATABASE_URL` apunta a **Postgres local**, no a Neon de producción.

Ejemplo local:

```env
DATABASE_URL=postgresql://postgres:Azby1928@localhost:5432/ferreteria_local
```

---

## Restaurar demo desde USB (PC vieja)

Carpeta típica: `D:\LhexIA_Migracion_SD_20260525\`

| Dump | Cuándo usarlo |
|------|----------------|
| `01_BASE_DATOS\local_ferreteria_*.dump` | Demo con ventas/usuarios de la PC vieja |
| `01_BASE_DATOS\neon_*.dump` | Espejo catálogo nube (Render/Neon) — otro perfil de datos |

```powershell
$env:PGPASSWORD = "Azby1928"
# Cerrar app.py antes
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h 127.0.0.1 -d postgres -c "DROP DATABASE IF EXISTS ferreteria_local;"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h 127.0.0.1 -d postgres -c "CREATE DATABASE ferreteria_local ENCODING 'UTF8';"
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -h 127.0.0.1 -U postgres -d ferreteria_local --no-owner --no-acl --clean --if-exists "D:\LhexIA_Migracion_SD_20260525\01_BASE_DATOS\local_ferreteria_20260525_101817.dump"
```

Detalle completo: `scripts/CHECKLIST_MIGRACION_PC.md`, `scripts/PROMPT_CURSOR_PC_NUEVO_USB.md`.

---

## Si el venv se rompe (copia de carpeta desde otra PC)

```powershell
Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
pip install pytest pytest-cov
```

Usar **`.venv`** (con punto), no copiar `venv` de otra máquina.

---

## Git — actualizar sin conflictos de archivos sueltos

Si `git pull` dice *untracked files would be overwritten*:

```powershell
git fetch origin
git reset --hard origin/main
git clean -fd
```

Vuelve a revisar que `env_qa.txt` y `.env.local` sigan con `Azby1928`.

---

## Login local

- Usuario demo: `mariobec@gmail.com` (viene del dump local)
- Clave: la misma de la **PC vieja** (no la de Neon)

Si la BD está vacía, crear admin:

```powershell
$env:BOOTSTRAP_ADMIN_EMAIL = "mariobec@gmail.com"
$env:BOOTSTRAP_ADMIN_PASSWORD = "TuClaveLocal"
.\venv\Scripts\python.exe init_db.py
```

---

## Referencias

- Memoria proyecto: `memory.md`, `docs/memory.md`
- Planes SD-1: `docs/planes/01-entrega-santo-domingo/`
- Deploy / Neon: `docs/MIGRACION_RENDER_NEON.md`

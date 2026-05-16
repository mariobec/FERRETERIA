# Migración del ERP a Render + Neon

Esta guía es lo que debes ejecutar **en tu cuenta** (Neon y Render). El código del repo ya soporta `DATABASE_URL` en Postgres (Neon) y el despliegue con Gunicorn.

---

## 0. Paridad: local, Render y Neon “iguales”

Cuando decís que querés **el mismo ambiente** en la PC y en Render, hay dos formas honestas de interpretarlo:

### A) Una sola base de datos (lo más “igual” posible)

**Local y Render apuntan a la misma URL de Neon** (misma variable `DATABASE_URL` en Render y en tu `.env.local`).

| Ventaja | Desventaja |
|--------|--------------|
| Ves **los mismos datos** en la oficina y en la URL pública | Cualquier prueba en local **afecta** lo que ven los usuarios en Render |
| No hay que sincronizar tablas a mano | Los **tests automatizados** no deben usar esa URL (ver `tests/conftest.py`; solo con override explícito) |

Pasos mínimos:

1. Crear Neon y copiar la connection string (pooler + `sslmode=require` si aplica).

Checklist en tu PC (variables vs `render.yaml`):

```powershell
.\scripts\paridad_local_render_neon.ps1
```

Opcional: alinear esquema contra la misma URL Neon antes del push: `.\scripts\paridad_local_render_neon.ps1 -RunInitDb`

2. En **Render**: `DATABASE_URL` = esa URL.
3. En tu **PC** (`.env.local` en la raíz del repo, no commitear): `DATABASE_URL` = **la misma** URL.
4. Mismo **código** en ambos: `git pull` local y push para que Render despliegue la misma rama.
5. Tras cambios de modelos: en Render ya corre `init_db.py` en pre-deploy; en local conviene `python init_db.py` para no desfasarse.

Así **código + datos** quedan alineados con un solo Postgres (Neon).

### B) Postgres local + Neon solo en la nube (espejo)

**Local** usa `DATABASE_URL=postgresql://…localhost…`. **Render** usa Neon. Para **acercar** datos y esquema:

- Esquema: `python init_db.py` contra cada base cuando actualicé modelos; el script `scripts/schema_sync_neon.py` fuerza `DATABASE_URL` desde `NEON_DATABASE_URL` en `.env.local`.
- Datos local → Neon: `python scripts/sync_local_neon_render.py` (requiere `DATABASE_URL` + `NEON_DATABASE_URL` en `.env.local`; **borra y rellena** tablas en Neon según el script: leé el archivo antes de usarlo en producción).
- Volcado fiel: `pg_dump` / `pg_restore` (sección 3).

En este modo “igual” significa **mismo código y mismas migraciones**, no necesariamente los mismos bytes en la base en todo momento.

### Qué suele quedar distinto aunque la BD sea la misma

- **Archivos en disco** (`instance/`, certificados `.pfx`, XML DTE, uploads): Render tiene **otro filesystem**; no se duplican solos. Hay que subir/configurar secretos y rutas en variables de Render o almacenamiento externo.
- **`PUBLIC_SITE_URL`**: en Render la URL es `https://….onrender.com` (o tu dominio); en local suele ser `http://127.0.0.1:5000`. Es normal que difiera; afecta enlaces absolutos y SEO, no la lógica del POS dentro de sesión.

### Resumen rápido

| Objetivo | Configuración |
|----------|----------------|
| Misma BD en PC y Render | Misma `DATABASE_URL` (Neon) en Render y `.env.local` |
| Solo Render en Neon; local aparte | Render `DATABASE_URL` = Neon; local `DATABASE_URL` = Postgres local; opcional `NEON_DATABASE_URL` para scripts |
| Semillas en dos bases | `python scripts/run_demo_seeds_dual.py` (lee `.env.local`) |

---

## 1. Neon (PostgreSQL)

1. Entra a [Neon Console](https://console.neon.tech/) y crea un **proyecto** y una **base de datos** (Postgres).
2. Copia la **connection string**:
   - **Pooled** (recomendado para la app en Render): el host suele contener `-pooler`.
   - Asegura `sslmode=require` en la URL si Neon no lo agrega solo.
3. Si al conectar ves errores raros con **channel binding**, prueba la misma URL **sin** `channel_binding=require` (a veces molesta a clientes antiguos).
4. La app detecta el pooler de Neon y ajusta `PGOPTIONS` / mensajes de servidor; no hace falta tocar código.

**Guarda esa URL** como valor de `DATABASE_URL` en Render (siguiente sección).

---

## 2. Render (aplicación web)

1. Sube el repositorio a **GitHub** (rama que uses en producción, p. ej. `main`).
2. En [Render Dashboard](https://dashboard.render.com/): **New** → **Blueprint** (o edita el servicio existente si ya lo tienes).
3. Conecta el repo: Render debe leer el `render.yaml` de la raíz del proyecto.
4. En el flujo inicial del Blueprint, Render pedirá las variables con `sync: false`:
   - **`DATABASE_URL`**: pega la URL de Neon del paso 1.
   - **`BOOTSTRAP_ADMIN_EMAIL`** / **`BOOTSTRAP_ADMIN_PASSWORD`** / **`BOOTSTRAP_ADMIN_NAME`** (opcional pero recomendado): primer usuario administrador; `init_db.py` los crea si no existen.
   - **`PUBLIC_SITE_URL`**: pon la URL pública del sitio, p. ej. `https://TU-SERVICIO.onrender.com` (o tu dominio custom). Así sitemap y enlaces canónicos no caen en el fallback por defecto.
5. Lanza el deploy y revisa los **logs** del build y del **pre-deploy** (`python init_db.py`).

`render.yaml` incluye:

- `preDeployCommand: python init_db.py` — alinea tablas/columnas con los modelos SQLAlchemy y roles base (idempotente en la medida de lo posible).
- `healthCheckPath: /healthz` — comprobación ligera sin tocar la base.

Si cambias de plan (`starter` vs `free`) o de región, hazlo en el dashboard o editando `render.yaml` según [Blueprint spec](https://render.com/docs/blueprint-spec).

---

## 3. Datos: vacío vs copia desde otra base

### Opción A — Base nueva (demo / entorno limpio)

Solo Neon vacío + deploy: `init_db.py` crea esquema y el admin de `BOOTSTRAP_*` si lo configuraste.

### Opción B — Volcado completo desde Postgres actual (`pg_dump` / `pg_restore`)

En la máquina donde tengas `pg_dump`/`pg_restore` y red a ambas bases:

```powershell
# Origen (tu Postgres actual)
$env:PGPASSWORD = "CLAVE_ORIGEN"
pg_dump -h HOST_ORIGEN -p 5432 -U USUARIO -d BASE_ORIGEN -Fc -f ".\erp_respaldo.dump"
Remove-Item Env:PGPASSWORD

# Destino Neon (usa la URL o host/puerto de Neon)
$env:PGPASSWORD = "CLAVE_NEON"
pg_restore --clean --if-exists --no-owner --no-acl -h EP_NEON -p 5432 -U USUARIO -d neondb ".\erp_respaldo.dump"
Remove-Item Env:PGPASSWORD
```

Ajusta host, usuario y base según el panel de Neon. Si `--clean` es demasiado agresivo para tu caso, quítalo y restaura solo sobre una BD vacía.

### Opción C — Clonar datos desde tu Postgres local hacia Neon (desarrollo)

Con `.env.local` en la raíz del repo:

```text
DATABASE_URL=postgresql://...tu_local...
NEON_DATABASE_URL=postgresql://...neon...
```

Ejecuta (sobrescribe datos en destino según lo que haga el script; revisa antes):

```powershell
python scripts/sync_local_neon_render.py
```

Ese script aplica un subconjunto de migraciones SQL y copia tablas; para producción suele preferirse la opción B.

---

## 4. Después del primer deploy

- Cambia la clave del admin de bootstrap tras el primer login.
- Mantén `FLASK_DEBUG=0` en Render.
- Si usas facturación electrónica, certificados o rutas de archivos locales, configura las variables correspondientes en Render (no las subas al repositorio).
- Los tests locales no deben apuntar a Neon/Render sin override explícito (ver `tests/conftest.py` y `ALLOW_TESTS_ON_REMOTE`).

---

## 5. Cada vez: dejar Render y Neon al día con lo que tenés en local

**Importante:** no existe un botón “subir todo a Render y Neon” desde el IDE. Hay **dos canales distintos**:

| Qué querés subir | Cómo se hace |
|------------------|--------------|
| **Código** (Python, plantillas, CSS, `render.yaml`, etc.) | **Solo Git**: `git commit` + `git push` al remoto que Render tiene conectado. Render construye y despliega solo. |
| **Base de datos Neon** (tablas/columnas nuevos, roles, admin bootstrap) | Al desplegar, Render ejecuta **`python init_db.py`** en pre-deploy contra la `DATABASE_URL` que configuraste (Neon). Además podés correr lo mismo **desde tu PC** antes o después del push (script abajo). |
| **Datos** (filas: productos, ventas, etc.) | **No** van con el push. Usá `pg_dump`/`pg_restore`, o `scripts/sync_local_neon_render.py` (destructivo en Neon: leé el script), según la sección 3. |

### Checklist corto (modo “una sola Neon” — sección 0-A)

1. En **Render** → Environment: `DATABASE_URL` = URL de Neon (pooler si aplica).
2. En tu **PC**, `.env.local`: misma URL en `DATABASE_URL` **o** en `NEON_DATABASE_URL` si usás Postgres local como `DATABASE_URL`.
3. Esquema en Neon desde la PC (opcional pero útil antes de probar en la nube):

   ```powershell
   cd <raíz del repo>   # carpeta donde está app.py
   .\scripts\init_neon_desde_local.ps1
   ```

4. Subir **código** a lo que Render despliega:

   ```powershell
   git status
   git add -A
   git commit -m "Tu mensaje"
   git push origin main
   ```

   (Cambiá `main` por la rama que tenga enlazado el servicio en Render.)

5. En el dashboard de **Render** → **Events / Logs**: esperá build + pre-deploy `init_db.py` en verde.

6. **Variables y archivos** que no van en git (`.pfx`, API keys, etc.): copialas a mano en Render → Environment; los archivos subilos por Secret File / disco persistente / otra ruta que uses en prod.

### Si usás Postgres local + Neon (sección 0-B)

- Después del `git push`, alineá solo esquema en Neon: `python scripts/schema_sync_neon.py` (requiere `NEON_DATABASE_URL` en `.env.local`) **o** `.\scripts\init_neon_desde_local.ps1` si `NEON_DATABASE_URL` apunta a Neon.
- Para **copiar datos** local → Neon: `python scripts/sync_local_neon_render.py` (ojo: trunca tablas en destino según el script).

---

## 6. Referencias en el repo

| Recurso | Uso |
|--------|-----|
| `render.yaml` | Definición del servicio web Render |
| `init_db.py` | Esquema + roles + admin desde env |
| `scripts/paridad_local_render_neon.ps1` | Checklist: variables de `render.yaml` presentes en `.env.local` + modo Neon vs local |
| `scripts/init_neon_desde_local.ps1` | Corre `init_db.py` contra Neon usando `NEON_DATABASE_URL` o `DATABASE_URL` en `.env.local` |
| `scripts/sync_local_neon_render.py` | Migraciones SQL listadas en el script + copia de datos **local → Neon** (revisar antes de producción) |
| `scripts/schema_sync_neon.py` | Alinea esquema modelo vs **Neon** usando `NEON_DATABASE_URL` |
| `scripts/run_demo_seeds_dual.py` | Semillas demo en local y Neon según `.env.local` |
| `DEPLOY_GRATIS_PRUEBAS.md` | Resumen rápido demo gratis |
| `docs/RESPALDO_PROYECTO.md` | Respaldo ZIP + `pg_dump` antes de cortes grandes |
| `.env.example` | Ejemplo de `DATABASE_URL` y `NEON_DATABASE_URL` |

Si algo falla en el pre-deploy, copia el traceback de los logs de Render y revisa que `DATABASE_URL` sea Postgres (`postgresql://` o `postgres://`) y que Neon acepte conexiones desde la IP de Render (Neon suele permitir `0.0.0.0/0` en el firewall por defecto; restringe si lo necesitas).

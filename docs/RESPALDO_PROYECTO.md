# Respaldo completo del proyecto (código + datos + configuración)

Después de tus pruebas y migración, conviene **tres capas**: ZIP del repositorio, volcado de base de datos y copia de secretos/config local (sin subirlos a git).

---

## 1. ZIP del código (incluye historial Git si no usas `-SinHistorialGit`)

Desde PowerShell, en la raíz del repo:

```powershell
.\scripts\backup_proyecto_completo.ps1
```

Por defecto crea la carpeta `RESPALDOS_LHEXIA` **al mismo nivel** que la carpeta del proyecto (hermano de `sistema_ventas_limpio`) y guarda algo como `sistema_ventas_limpio_respaldo_YYYYMMDD_HHMMSS.zip`.

Opciones útiles:

| Parámetro | Efecto |
|-----------|--------|
| `-SinHistorialGit` | No incluye `.git` (archivo más pequeño; pierdes historial local en ese ZIP). |
| `-OmitirDtesEmitidos` | No incluye `storage/dtes/emitidos` (puede ser muy pesado). |
| `-CarpetaDestino "D:\MisRespaldos"` | Cambia dónde se guarda el ZIP. |

**Qué queda fuera del ZIP** (por diseño): `__pycache__`, virtualenvs, cachés de tests (pytest/mypy/ruff), `htmlcov`, `.coverage`, etc. El código fuente, plantillas, `static/`, `docs/`, tests, `.cursor` (reglas del IDE si existen en disco; puede ser pesado si hay caché de Cursor ahí), `.git` (salvo `-SinHistorialGit`) **sí** entran.

---

## 2. Base de datos PostgreSQL (obligatorio para “toda la información”)

El ZIP **no** sustituye la BD. Con `pg_dump` (ajusta host, usuario y base):

```powershell
$env:PGPASSWORD = "TU_PASSWORD"
pg_dump -h TU_HOST -p 5432 -U TU_USUARIO -d TU_BASE -Fc -f ".\RESPALDO_BD_$(Get-Date -Format yyyyMMdd_HHmmss).dump"
Remove-Item Env:PGPASSWORD
```

Formato `-Fc` es custom (recomendado para restaurar con `pg_restore`). Alternativa en SQL plano:

```powershell
pg_dump -h TU_HOST -U TU_USUARIO -d TU_BASE --no-owner -f respaldo.sql
```

Guarda el `.dump` o `.sql` en el mismo disco externo / nube que el ZIP.

---

## 3. Configuración y secretos locales (no van a git)

Revisa y respalda **aparte** (USB cifrado o gestor de secretos), sin commitear:

| Qué | Dónde suele estar |
|-----|-------------------|
| Variables de entorno / URL BD | `.env`, `.env.local`, `env_qa.txt` (ver `.gitignore`) |
| Config empresa en disco | Ruta definida en app: carpeta de configuración + `empresa_config.json` |
| CAF / folios SII | Lo que administren en admin CAF + copias XML si las guardan fuera del repo |
| Certificados / llaves FE | Solo si los tienen en filesystem (nunca en el repositorio público) |

---

## 4. Git (commit + remoto)

- **Commit**: fija el estado del código con mensaje claro.
- **Push** a `origin` (u otro remoto): copia en servidor.
- **Tag** opcional: `git tag -a v1.x-migracion -m "..."` para marcar el corte post-migración.

---

## 5. Checklist rápido antes de migrar

- [ ] ZIP con `backup_proyecto_completo.ps1` (o con flags que prefieras).
- [ ] `pg_dump` de la base productiva / la que migres.
- [ ] Copia de `.env` y configs locales sensibles.
- [ ] Commit + push (cuando corresponda).
- [ ] Probar restauración en una máquina limpia (descomprimir ZIP + `pg_restore` en BD vacía).

Si `tar` fallara en tu Windows, instala “Windows tar” actualizado o usa 7-Zip para comprimir la carpeta del proyecto manualmente aplicando las mismas exclusiones que lista el script.

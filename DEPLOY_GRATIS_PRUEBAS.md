# Deploy Gratis de Pruebas (Render + Neon)

Guía detallada (Neon, Render, `pg_dump` / datos, checklist): **[docs/MIGRACION_RENDER_NEON.md](docs/MIGRACION_RENDER_NEON.md)** — incluye **§0 Paridad** (misma Neon en local y Render vs espejo Postgres local + Neon).

## 1) Qué modelo usar

- **App Web:** Render (plan free)
- **Base de datos:** Neon Postgres (free tier)
- **Auto deploy:** desde GitHub en cada `push`

---

## 2) Preparación previa

Este repo ya queda preparado con:

- `render.yaml`
- `init_db.py` (crea tablas base y roles)
- `requirements.txt` con `gunicorn` y `psycopg2-binary`
- `app.py` compatible con `DATABASE_URL` (Render/Neon)

---

## 3) Pasos en 10 minutos

1. Sube este proyecto a GitHub (rama `main`).
2. Crea una cuenta en [Neon](https://neon.tech/) y crea una DB Postgres gratuita.
3. Copia la URL de conexión (formato `postgresql://...`).
4. En [Render](https://render.com/):
   - New + Blueprint
   - conecta tu repo de GitHub
   - Render detecta `render.yaml`.
5. Render pedirá las variables marcadas como secretas en `render.yaml` (`DATABASE_URL`, `BOOTSTRAP_*`, `PUBLIC_SITE_URL`). Complétalas (URL de Neon, admin inicial, URL pública tipo `https://….onrender.com`).
6. Deploy. En cada despliegue corre `preDeployCommand: python init_db.py` antes de Gunicorn.

Cuando levante, el esquema queda alineado con los modelos y se crea el usuario admin si definiste `BOOTSTRAP_*`.

---

## 4) Flujo de cambios “conectado contigo”

Para iterar rápido:

1. Tú me pides cambios aquí.
2. Yo te dejo el código listo en local.
3. Haces `git push`.
4. Render despliega en cada `push` (`autoDeployTrigger: commit` en el blueprint).
5. Validamos en URL pública.

---

## 5) Limitaciones del plan gratis

- Puede “dormirse” por inactividad.
- Primer request puede tardar más (cold start).
- Usar solo para demos/QA, no producción final.

---

## 6) Checklist mínimo de seguridad para demo

- Cambiar `BOOTSTRAP_ADMIN_PASSWORD` después del primer login.
- Mantener `FLASK_DEBUG=0`.
- No exponer datos reales sensibles.
- Mantener `PUBLICO_MUESTRA_PRECIO=0` si demo pública.

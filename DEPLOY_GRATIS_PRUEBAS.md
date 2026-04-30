# Deploy Gratis de Pruebas (Render + Neon)

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
5. En variables de entorno del servicio Render, agrega:
   - `DATABASE_URL` = URL de Neon
   - `BOOTSTRAP_ADMIN_EMAIL` = correo admin inicial
   - `BOOTSTRAP_ADMIN_PASSWORD` = clave admin inicial
   - `BOOTSTRAP_ADMIN_NAME` = nombre admin (opcional)
6. Deploy.

Cuando levante, `init_db.py` crea tablas y usuario admin inicial.

---

## 4) Flujo de cambios “conectado contigo”

Para iterar rápido:

1. Tú me pides cambios aquí.
2. Yo te dejo el código listo en local.
3. Haces `git push`.
4. Render despliega solo (autoDeploy=true).
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

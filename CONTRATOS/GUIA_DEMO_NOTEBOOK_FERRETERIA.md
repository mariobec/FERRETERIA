# Guía: ERP en un notebook para pruebas en la ferretería (sin el PC servidor)

Objetivo: llevar un **notebook** con el mismo sistema, conectarse desde el **tablet o celular** en la WiFi de la tienda, sin depender del equipo que hoy actúa como servidor.

---

## Qué necesitás en el notebook

| Requisito | Notas |
|-----------|--------|
| Windows 10/11 (recomendado) | Es lo que cubren los `.bat` del repo. |
| Python **3.11+** | Instalador oficial: marcar **Add Python to PATH**. |
| **MySQL** o **MariaDB** local | Ej.: [MySQL Installer](https://dev.mysql.com/downloads/installer/), o MySQL incluido en XAMPP (solo MySQL). |
| Copia del proyecto o paquete demo | Ver opciones A y B abajo. |
| WiFi de la ferretería | El notebook y los tablets deben estar en la **misma red**. |

El `app.py` ya arranca escuchando en **`0.0.0.0:5000`** por defecto, así que **otros equipos en la LAN** pueden entrar por la IP del notebook (ej. `http://192.168.1.45:5000`). Si Windows Firewall pregunta, permitir **red privada** para Python.

---

## Opción A — Demo “limpia” (rápida, sin copiar tu BD de producción)

Usá la carpeta **`demo_ferreteria`** (o el ZIP generado con `demo_ferreteria\empaquetar_demo_cliente.ps1`). Resumen del **`LEEME_INSTALACION_DEMO.txt`**:

1. **MySQL:** crear base vacía (script `demo_ferreteria\crear_mysql_bd_demo.sql` o a mano `CREATE DATABASE ferreteria_demo ...`).
2. Copiar **`demo_ferreteria\env.demo.ejemplo`** → **`.env.demo`** en la **raíz del paquete** (donde está `app.py` del demo) y editar usuario/clave/host y nombre de base.
3. **`instalar_demo_windows.bat`** → crea `.venv` e instala `requirements.txt`.
4. **`post_instalacion_demo.bat`** → tablas + usuario admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD` del `.env.demo`).
5. **`iniciar_demo_windows.bat`** → abrir en el notebook `http://127.0.0.1:5000`.
6. Desde el tablet: **`http://IP_DEL_NOTEBOOK:5000`** (ver IP con `ipconfig` en CMD).

Ventaja: no arrastrás datos sensibles. Desventaja: catálogo vacío salvo lo que cargues en la demo.

---

## Opción B — Misma carpeta que tu desarrollo (pruebas con lógica y datos parecidos al servidor)

1. **Copiar** toda la carpeta `sistema_ventas` al notebook (USB, red, zip) **o** clonar el mismo repo con Git.
2. En el notebook, instalar **MySQL** y crear una base dedicada, por ejemplo **`ferreteria_notebook`**, para no pisar otra instalación.
3. **Datos:**
   - **B)** *Copia del servidor de desarrollo:* en la **máquina servidor**, exportar:
     ```bash
     mysqldump -u root -p --databases ferreteria > respaldo_notebook.sql
     ```
     En el notebook, crear la base `ferreteria_notebook` e importar:
     ```bash
     mysql -u root -p ferreteria_notebook < respaldo_notebook.sql
     ```
     (Ajustá nombres de base si el dump trae `CREATE DATABASE`.)
   - **B2)** *Empezar vacío:* ejecutar en MySQL los scripts de `sql/` que uses (migraciones idempotentes) y crear usuario con `bootstrap_admin_local.py` si aplica a tu flujo.
4. **Conexión Flask:** en la raíz del proyecto en el notebook, creá **`env_qa.txt`** (o **`.env.qa`**) con la URI apuntando al MySQL **local del notebook**:
   ```text
   SQLALCHEMY_DATABASE_URI=mysql+pymysql://root:TU_CLAVE@localhost/ferreteria_notebook
   SECRET_KEY=una-clave-distinta-para-demo
   ```
   El `app.py` lee `env_qa.txt` y `.env.qa` al iniciar.
5. Entorno Python en el notebook:
   ```text
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
6. **Migraciones SQL** nuevas (enrolamiento, ventas, etc.): ejecutá en MySQL los archivos de `sql/` que correspondan a esa base (como hiciste con `2026_05_06_enrolamiento_inventario.sql`).
7. Arranque:
   ```text
   .venv\Scripts\activate
   python app.py
   ```
8. En el notebook: `http://127.0.0.1:5000`. En tablet/caja: **`http://IP_NOTEBOOK:5000`** (misma WiFi).

---

## Enrolamiento / tablet en la ferretería

- URL fija del módulo: **`/inventario/enrolamiento`**
- Ejemplo: `http://192.168.1.45:5000/inventario/enrolamiento`
- El usuario debe **iniciar sesión** en el tablet (misma cuenta con permiso de enrolamiento o admin inventario).

---

## Consejos prácticos

1. **Anotá la IP del notebook** (`ipconfig`) y fijá que no cambie (DHCP reservado en el router o IP fija en WiFi).
2. **No uses la misma base** que el servidor de producción remoto: siempre una base **local** en el notebook para demo.
3. **PDF / wkhtmltopdf:** opcional en demo; el resto del ERP funciona sin eso.
4. Para **volver a casa**, seguís trabajando en el PC servidor; el notebook es solo **espejo de prueba**.

---

## Resumen de comandos útiles (notebook)

```text
ipconfig                    → ver IPv4 (para el tablet)
python app.py               → servidor (host 0.0.0.0 por defecto)
```

Si algo no carga desde el tablet: firewall de Windows, que el notebook no esté en “WiFi pública” bloqueando, y que la URL use **http** y el **puerto correcto** (5000 salvo que cambies `FLASK_RUN_PORT`).

---

*Actualizado para el proyecto `sistema_ventas` con Flask y MySQL.*

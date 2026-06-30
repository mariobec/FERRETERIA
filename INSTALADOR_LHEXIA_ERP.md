# Instalador LhexIA ERP — Historial, fallas y solución

> Documento de referencia del instalador del ERP para el **servidor de la ferretería**.
> Última actualización: **2026-06-24**.
> Estado: **funcional y validado** (exe sirve `/login` HTTP 200 con PostgreSQL local).

---

## 1. Resumen ejecutivo

El ERP **no es un `.exe` tipo Word**: es un servidor web local (PostgreSQL + Flask) al que
caja, POS y tablets acceden por navegador en la WiFi de la tienda.

Para no entregar código fuente al cliente, el ERP se compila con **PyInstaller** a un
ejecutable (`LhexIA_ERP.exe`) que vive dentro de la carpeta portátil **`INSTALACION\`**.

**Flujo correcto:**

```
DEV (este PC)                         SERVIDOR FERRETERÍA
─────────────                         ───────────────────
COMPILAR_ERP_EXE.bat       →  (USB)  →  C:\LhexIA\INSTALACION
VALIDAR_PAQUETE_USB.bat                 00_Instalar_servidor_completo.bat (admin)
                                        02_Iniciar_ERP.bat (uso diario)
```

---

## 2. Estructura de `INSTALACION\` (única carpeta a copiar)

```
INSTALACION\
├── erp\                          ← APLICACIÓN compilada (COPIAR COMPLETA)
│   ├── LhexIA_ERP.exe            ← ejecutable (sin .py sueltos)
│   ├── _internal\                ← librerías + templates + static empaquetados
│   ├── data\                     ← empresa_config.json, etc.
│   ├── storage\, logs\
│   ├── scripts\servidor_erp_autostart.ps1
│   ├── servidor_erp_autostart.ps1
│   └── .env.local                ← (lo crea el instalador en el servidor)
├── paquete\
│   ├── 00_POSTGRESQL\            ← postgresql-18.4-1-windows-x64.exe (356 MB)
│   ├── 00_PYTHON\               ← (solo modo legacy; no usado con exe)
│   ├── 01_BASE_DATOS\           ← *.dump (base con usuarios, productos, stock…)
│   ├── 03_CONFIG\               ← .env.local.template, empresa_config.json
│   ├── 04_SCRIPTS_OPERACION\    ← scripts ops (url red, reset clave, autostart)
│   ├── INSTALAR_LHEXIA.bat
│   ├── _escribir_env_local.bat
│   ├── instalador.defaults.bat
│   └── 01..05_*.bat             ← pasos de instalación
├── servicios\                    ← .bat internos (arranque, intranet, reset)
├── LhexIA_Centro_Control.exe     ← panel gráfico (sin terminal)
├── 00_Instalar_servidor_completo.bat
├── 02_Iniciar_ERP.bat            ← operación diaria
├── COMPILAR_ERP_EXE.bat          ← solo DEV
├── COMPILAR_CENTRO_CONTROL.bat   ← solo DEV
├── VALIDAR_PAQUETE_USB.bat       ← solo DEV (antes del USB)
└── LEEME.txt
```

**Clave:** la aplicación va en `INSTALACION\erp\`, **hermana** de `paquete\`.
**NO existe** carpeta `02_APLICACION` en el instalador nuevo (eso era del formato viejo).

---

## 3. Pasos del instalador (`00_Instalar_servidor_completo.bat`)

| Paso | Script | Qué hace | Modo exe |
|------|--------|----------|----------|
| 1 | `01_instalar_postgresql.bat` | Instala PostgreSQL silencioso (servicio `postgresql-x64-18`); pide clave `postgres` | Requerido |
| 2 | `02_instalar_python.bat` | Instala Python 3.12 | **Omitido** (no hace falta con exe) |
| 3 | `03_instalar_aplicacion.bat` | Detecta `LhexIA_ERP.exe`, escribe `erp\.env.local`, copia config | Sin `.venv` |
| 4 | `04_instalar_base_datos.bat` | Crea BD `ferreteria_local`, restaura `*.dump`, escribe `.env.local` | Requerido |
| 5 | `05_configurar_intranet.bat` | Accesos directos en escritorio; guía firewall/URL | Requerido |

`instalador.defaults.bat` (portátil):
- `LHEXIA_INSTALL_DIR = <INSTALACION>\erp`
- `LHEXIA_DB_NAME = ferreteria_local`
- `LHEXIA_PG_PORT = 5432`, `LHEXIA_PG_USER = postgres`

---

## 4. Historial de fallas y soluciones

### 4.1 Cotizaciones — trabajo perdido (no relacionado al instalador, mismo hilo)
- **Falla:** cambios de homologación cotización↔PDF (membrete CHILEMAT) se perdieron por no estar en git.
- **Solución:** restaurado desde `respaldos/LhexIA_Instalador_SD/02_APLICACION/` y commit `102fe7d`.

### 4.2 Error "MySQL no conecta" al arrancar el exe
- **Falla:** sin `erp\.env.local`, `app.py` caía a un fallback antiguo
  `mysql+pymysql://...@localhost/ferreteria` → *"Can't connect to MySQL server"*.
- **Causa:** el exe arrancó antes de configurar la BD (sin `.env.local`).
- **Solución:**
  - `app.py` / `erp_launcher.py`: en modo frozen/exe ya **no usan MySQL**; exigen
    `DATABASE_URL` (PostgreSQL) o muestran error claro.
  - Pasos 3 y 4 crean `erp\.env.local` con `_escribir_env_local.bat`.
  - `02_Iniciar_ERP.bat` avisa si falta `.env.local`.

### 4.3 Paso 3 falla: "falta carpeta 02_APLICACION con app.py"
- **Falla:** mensaje al instalar.
- **Causa:** se ejecutó el **instalador VIEJO** (`respaldos\LhexIA_Instalador_SD\`)
  que buscaba `02_APLICACION\app.py`. El instalador nuevo usa `erp\LhexIA_ERP.exe`.
- **Solución:**
  - `03_instalar_aplicacion.bat` detecta exe (sin `02_APLICACION` ni `.venv`).
  - Instalador viejo redirige al nuevo si detecta carpeta `INSTALACION`.
  - `INSTALAR_LHEXIA.bat` acepta `LhexIA_ERP.exe` (no exige `app.py`).

### 4.4 Centro de Control: "Instalación paso a paso" fallaba en paso 3
- **Falla:** el botón del `LhexIA_Centro_Control.exe` lanzaba el instalador viejo.
- **Causa:** `lhexia_centro_control.py` buscaba `instalador_intranet` / `02_APLICACION`.
- **Solución:** reescrito para usar `INSTALACION\paquete\INSTALAR_LHEXIA.bat` y
  `00_Instalar_servidor_completo.bat`; valida que exista `erp\LhexIA_ERP.exe`.
  Exe recompilado (`COMPILAR_CENTRO_CONTROL.bat`).

### 4.5 Pasos 4 y 5: ".venv falta"
- **Falla:** scripts pedían `.venv` que no existe en modo exe.
- **Causa:** verificaciones heredadas del modo Python/legacy.
- **Solución:**
  - `INSTALAR_LHEXIA.bat`: con exe **omite paso 2 (Python)**.
  - `verificar_arranque_erp.bat`, `url_erp_red_local.bat`,
    `crear_usuario_test_piso.bat`, `resetear_clave_admin.bat`: usan el exe, no `.venv`.
  - `04`/`05`: no crean `.venv`; avisos de `pg_restore` no cortan la instalación.
  - **`.venv: FALTA` en modo exe NO es error.**

### 4.6 Faltaba el instalador de PostgreSQL en el paquete
- **Falla:** paso 1 no encontraba `postgresql-*.exe`.
- **Solución:** copiado `postgresql-18.4-1-windows-x64.exe` (356 MB) a
  `paquete\00_POSTGRESQL\`. Coincide con el servicio `postgresql-x64-18`.

### 4.7 Ubicación incorrecta en el servidor (Escritorio / OneDrive)
- **Falla:** la carpeta `INSTALACION` estaba en el **Escritorio** del servidor.
- **Causa:** el Escritorio suele estar sincronizado con **OneDrive**, que bloquea/duplica
  el `.exe` y archivos de BD → fallos intermitentes.
- **Solución:** mover a ruta local simple **`C:\LhexIA\INSTALACION`** y reinstalar desde ahí.
  - Evitar: USB directo, OneDrive, Escritorio, `Program Files`, rutas de red, tildes/espacios raros.

### 4.8 `VALIDAR_PAQUETE_USB.bat` — aviso de Python y código de salida invertido
- **Solución:** en modo exe muestra "Python NO requerido"; código de salida 0=OK, 1=incompleto.

---

## 5. Estado de validación (2026-06-24)

```
[OK] erp\LhexIA_ERP.exe                 (build hoy; sirve /login HTTP 200)
[OK] paquete\INSTALAR_LHEXIA.bat
[OK] Postgres en paquete\00_POSTGRESQL\ (postgresql-18.4)
[OK] Python NO requerido (modo LhexIA_ERP.exe)
[OK] Dump BD en paquete\01_BASE_DATOS\
[RESULTADO] Paquete listo para copiar al USB.
```

- `LhexIA_ERP.exe` y `LhexIA_Centro_Control.exe`: builds actuales (2026-06-23).
- Prueba real: `scripts/validar_build_pyinstaller_erp.py` → arranca exe + `/login` 200 OK
  contra PostgreSQL 18 local.

---

## 6. Procedimiento correcto (paso a paso)

### En DEV (este PC)
1. `INSTALACION\COMPILAR_ERP_EXE.bat` → genera `erp\LhexIA_ERP.exe` + valida.
2. (si cambió el panel) `INSTALACION\COMPILAR_CENTRO_CONTROL.bat`.
3. `INSTALACION\VALIDAR_PAQUETE_USB.bat` → debe decir **"Paquete listo"**.
4. Copiar **toda** la carpeta `INSTALACION\` al USB (incluye `erp\`).

### En el SERVIDOR de la ferretería
1. Copiar `INSTALACION\` del USB a **`C:\LhexIA\INSTALACION`** (no dejarla en USB/Escritorio).
2. Clic derecho `00_Instalar_servidor_completo.bat` → **Ejecutar como administrador**.
   - Anotar la **clave de `postgres`** que pida.
   - El paso de Python se salta solo (modo exe).
3. `07_Arranque_automatico.bat` (admin) — para que el ERP inicie al encender.
   - **Decidir la ubicación final ANTES de este paso**; si se mueve la carpeta después,
     repetir este paso (la tarea apunta a la ruta absoluta).
4. Operación diaria: `02_Iniciar_ERP.bat` o `LhexIA_Centro_Control.exe`.
5. Login: `http://127.0.0.1:5000/login` (tablets: `http://IP-DEL-SERVIDOR:5000/login`).

---

## 7. Comprobaciones / problemas conocidos

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| "falta 02_APLICACION" | USB con instalador viejo | Usar solo `INSTALACION\` y `00_Instalar_servidor_completo.bat` |
| "Can't connect to MySQL" | Falta `erp\.env.local` | Completar pasos 1 y 4; o crear `.env.local` con `DATABASE_URL=postgresql://...` |
| ".venv falta" | Verificación legacy | Normal en modo exe; ignorar |
| Fallos intermitentes del exe | Carpeta en OneDrive/Escritorio | Mover a `C:\LhexIA\INSTALACION` |
| Paso 1 no halla Postgres | Falta `.exe` en `00_POSTGRESQL\` | Copiar `postgresql-*-windows-x64.exe` |
| Paso 4 "no hay .dump" | Falta dump | Colocar `*.dump` en `01_BASE_DATOS\` |
| ERP no inicia al encender | Carpeta movida tras autostart | Re-ejecutar `07_Arranque_automatico.bat` |

---

## 8. Archivos clave (referencia DEV)

| Archivo | Rol |
|---------|-----|
| `scripts/erp_launcher.py` | Entry del exe (servidor + subcomandos reset-clave/url-red/usuario-test) |
| `scripts/build_pyinstaller_erp.py` | Compila onedir → `dist/` → stage `INSTALACION/erp/` |
| `scripts/validar_build_pyinstaller_erp.py` | Gate: 0 `.py` sueltos + `/login` 200 |
| `scripts/lhexia_centro_control.py` | GUI Centro de Control (apunta a `INSTALACION\paquete`) |
| `app.py` (`_resolver_database_uri`, `_erp_runtime_root`) | Soporte frozen + DB Postgres |
| `INSTALACION/paquete/_escribir_env_local.bat` | Genera `erp\.env.local` con Postgres local |

---

## 9. Notas

- El `python app.py` que corre en DEV (terminal del IDE) es el servidor de **desarrollo**;
  es independiente del `.exe` del instalador.
- Las carpetas `respaldos\LhexIA_Instalador_SD*` y cualquier `02_APLICACION` son **formato
  viejo**: no usarlas para instalar.
- Tareas de build "abortadas" que aparezcan en notificaciones suelen ser procesos colgados
  de sesiones anteriores; los builds vigentes son los validados en este documento.

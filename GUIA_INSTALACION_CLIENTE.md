# Guía rápida - Instalación de pruebas (cliente)

## 1) Requisitos
- Windows 10/11
- Python 3.11 o superior
- MySQL local o de red
- Base de datos creada: `ferreteria`

## 2) Primer arranque
1. Abrir carpeta del proyecto.
2. Ejecutar `instalar_pruebas_windows.bat`.
3. Editar archivo `.env.qa`:
   - `SQLALCHEMY_DATABASE_URI=mysql+pymysql://USUARIO:CLAVE@HOST/ferreteria`
4. Ejecutar `iniciar_pruebas_windows.bat`.
5. Abrir navegador en [http://127.0.0.1:5000](http://127.0.0.1:5000).

## 3) Migraciones SQL recomendadas (orden)
1. `sql/2026_04_30_movimiento_caja_add_responsable.sql`
2. `sql/2026_05_01_kardex_recepciones.sql`
3. `sql/2026_05_01_bitacora_costos_compra.sql`
4. `sql/2026_05_01_productos_ubicacion_unidades.sql`

## 4) Datos de prueba opcionales
- CSV de productos: `sql/seed_productos_prueba_recepcion.csv`
- Seed de recepción: `sql/2026_05_01_seed_recepcion_prueba.sql`

## 5) Nota importante
- Si no ves movimientos en Kardex de recepción, valida tabla `almacenes`:
  - debe existir al menos 1 almacén válido con `id` numérico.

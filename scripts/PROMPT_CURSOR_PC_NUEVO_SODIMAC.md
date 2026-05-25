# Prompt Cursor — PC nuevo: extraer catálogo Sodimac (búsqueda + paginación)

Copia **todo el bloque** entre `---` en un chat nuevo de Cursor (modo Agent).

---

```
Contexto: LhexIA ERP — módulo extractor catálogo proveedor (Sodimac Chile).

En este PC nuevo ya tengo:
- Repo clonado: https://github.com/mariobec/FERRETERIA.git (git pull al día)
- Python + venv (o créalo)
- PostgreSQL y migración USB ya hechas o en paralelo

## Objetivo

Extraer de Sodimac **todos los productos** de esta búsqueda pública:
https://www.sodimac.cl/sodimac-cl/buscar?Ntt=maquina%20de%20soldar

(~805 resultados en ~17 páginas de 48 productos c/u)

Salida requerida por producto:
- codigo_interno  → productId Sodimac (ej. 146395391)
- descripcion_producto
- precio          → entero CLP (precio internet, sin puntos)

Archivos finales:
- respaldos/sodimac_buscar_maquina_soldar.json  (completo)
- respaldos/sodimac_buscar_maquina_soldar.csv   (import ERP)

## Scripts ya en el repo (úsarlos / extenderlos)

- scripts/extraer_sodimac_buscar.py       — 1 página Playwright + parser JSON embebido
- scripts/_sodimac_listado_rapido.py      — parse_search_json() (lógica core)
- scripts/agente_extractor_proveedor.py   — flujo general + fallback parser
- respaldos/debug_extractor_proveedor/    — HTML debug

La 1ª página ya se validó: 48 productos con parser JSON (no depende de Ollama).

## Reglas

- Ejecuta comandos tú mismo (PowerShell), no solo instrucciones.
- Delay aleatorio ~2 s entre páginas (anti-bloqueo).
- NO guardar contraseñas en código ni en commits.
- PROVEEDOR_USER / PROVEEDOR_PASS en .env.local solo si hace falta login B2B (esta URL es pública).
- Si Playwright falla: pip install playwright && playwright install chromium
- No imprimir secretos del .env.local en el chat.

## Pasos que debes hacer

### A. Entorno
cd a la raíz del repo (donde está app.py)
git pull origin main
python -m venv venv  (si no existe)
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install playwright
playwright install chromium

### B. Probar 1 página (smoke)
python scripts/extraer_sodimac_buscar.py --url "https://www.sodimac.cl/sodimac-cl/buscar?Ntt=maquina%20de%20soldar"
Confirmar: total >= 40 productos en respaldos/sodimac_buscar_maquina_soldar.json

### C. Paginación (implementar si falta)
Sodimac suele paginar con parámetro en URL o botón "siguiente".
Investigar en el HTML guardado (pagina_buscar.html) o en la UI:
- Probar URLs como &page=2, &currentPage=2, offset, etc.
- O extender extraer_sodimac_buscar.py con --pagina-inicio 1 --pagina-fin 17
- Por cada página: fetch HTML → parse_search_json → merge sin duplicar codigo_interno
- Pausa 2–3 s + random entre páginas

Si implementas script nuevo, preferir:
  scripts/extraer_sodimac_buscar_paginado.py
y reutilizar parse_search_json de _sodimac_listado_rapido.py

### D. Exportar CSV
Columnas: codigo_interno,descripcion_producto,precio
UTF-8 con BOM si Excel en Windows.

### E. Resumen final (tabla en chat)

| Métrica | Valor |
|---------|-------|
| Páginas recorridas | N |
| Productos únicos | N |
| Archivo JSON | ruta |
| Archivo CSV | ruta |
| Errores / páginas vacías | lista |

Muestra 10 filas de ejemplo en la respuesta.

## No hacer sin permiso

- sync_local_neon_render.py sin --verify-only
- commit de .env.local
- Subir credenciales Sodimac a GitHub

## Si Ollama está disponible

Opcional; NO es necesario para esta URL (parser JSON basta).
No bloquees la extracción esperando Ollama.

Empieza con git pull, smoke de 1 página, luego paginación hasta reunir el catálogo completo.
```

---

## Variante corta

```
PC nuevo, repo LhexIA. Extraer TODOS los productos Sodimac de:
https://www.sodimac.cl/sodimac-cl/buscar?Ntt=maquina%20de%20soldar
Usar/extender scripts/extraer_sodimac_buscar.py y parse_search_json (_sodimac_listado_rapido.py).
Paginar ~17 páginas, delay 2s, dedupe por codigo_interno.
Salida: respaldos/sodimac_buscar_maquina_soldar.json + .csv (codigo_interno, descripcion_producto, precio).
pip install playwright && playwright install chromium. Ejecuta tú mismo. Sin Ollama obligatorio.
```

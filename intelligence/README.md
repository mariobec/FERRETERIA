# Intelligence — registros vitales de Chile

Trabajo aparte del ERP de ferretería. Esta carpeta no la carga Flask, no toca ventas, caja, stock ni la base del local.

Busca **bautismos**, **matrimonios** y **defunciones** de Chile en FamilySearch y los deja en CSV o JSON.

Usa la API oficial de registros históricos (`/platform/records/personas`). La contraseña se escribe solo en el sitio de FamilySearch. La herramienta no entra al portal, no descarga imágenes de los libros y no guarda la clave.

El portal de partida es [familysearch.org/es/home/portal](https://www.familysearch.org/es/home/portal/).

## Colecciones

| Tipo | Colección | Id |
| --- | --- | --- |
| Bautismo | Chile, Bautismos, 1585-1932 | 1520549 |
| Bautismo, matrimonio, defunción | Chile, Catholic Church Records, 1633-2015 | 3405096 |
| Matrimonio | Chile, Matrimonios, 1579-1930 | 1520558 |
| Defunción | Chile, Defunciones, 1700-1920 | 1520559 |
| Matrimonio y defunción | Chile, Registro Civil, 1885-1932 | 1630787 |

El Registro Civil también tiene nacimientos. Esta herramienta no los trata como bautismos.

En las colecciones mixtas se conserva la fila si el hecho o el título corresponde al tipo pedido.

## Qué necesitas

1. Una cuenta gratuita de FamilySearch.
2. Una app key en [FamilySearch Developers](https://www.familysearch.org/developers/).
3. Esta redirect URI registrada en esa app key:

```text
http://127.0.0.1:8765/callback
```

Python 3.10 o superior. No hay paquetes que instalar.

## Uso

Desde la raíz del repositorio:

```bash
python intelligence/registros.py login --client-id TU_APP_KEY
python intelligence/registros.py colecciones
python intelligence/registros.py buscar \
  --tipo bautismo \
  --nombre Juan \
  --apellido Pérez \
  --lugar "Santiago, Chile" \
  --desde 1880 \
  --hasta 1920 \
  --padre "Pedro Pérez" \
  --madre "Ana Soto" \
  --salida intelligence/salidas/bautismos.csv
```

Matrimonio:

```bash
python intelligence/registros.py buscar \
  --tipo matrimonio \
  --apellido González \
  --conyuge "Pedro Soto" \
  --lugar "Valparaíso, Chile" \
  --salida intelligence/salidas/matrimonios.json
```

Defunción:

```bash
python intelligence/registros.py buscar \
  --tipo defuncion \
  --nombre María \
  --apellido Rojas \
  --desde 1900 \
  --hasta 1920
```

La sesión queda en `~/.config/intelligence-registros-chile/token.json` con permiso de lectura solo para tu usuario. También puedes pasar `FAMILYSEARCH_ACCESS_TOKEN` o `--token`.

Por defecto trae hasta 100 filas, de a 20, con una pausa de 0,8 s entre páginas. El tope de la API es 5000. Si FamilySearch responde 429, la herramienta espera y reintenta.

El CSV sale en UTF-8 con BOM para que Excel en español abra los acentos bien.

## Pruebas

No llaman a FamilySearch:

```bash
cd intelligence
python -m unittest discover -s tests -v
```

## Límites

- Hace falta una sesión de una persona real. La búsqueda de registros históricos no está en la sesión anónima de la API.
- Un apellido compuesto en `--padre`, `--madre` o `--conyuge` se parte en el último token. Para un apellido doble conviene acotar con `--apellido` de la persona y el lugar.
- Las imágenes de los libros siguen las condiciones de FamilySearch y de los archivos. Esta herramienta solo exporta el índice que devuelve la API.

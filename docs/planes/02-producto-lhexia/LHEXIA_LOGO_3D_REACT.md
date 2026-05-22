# LhexIA — Logo 3D (React + Three.js)

**Estado:** coordenadas importadas desde CSV (mayo 2026).  
**Fuente:** [`docs/lhexia_logo_coordenadas.csv`](../../lhexia_logo_coordenadas.csv) — 3834 puntos, 38 elementos (`Elemento_ID`).  
**JSON generado:** `frontend/lhexia-logo-3d/src/data/lhexiaLogoFromCsv.json` (regenerar con `python scripts/build_lhexia_logo_from_csv.py`).  
**Código:** `frontend/lhexia-logo-3d/`  
**ERP actual:** Flask/Jinja (sin React en producción); este módulo es **opcional** para landing o demo.

---

## Objetivo

Componente React que dibuje el isotipo LhexIA en espacio 3D:

| Elemento | Material / color |
|----------|------------------|
| **Nodos** | Esferas brillantes verde neón (`#39ff9f` / emissive `#20ff88`) |
| **Circuitos** | Tubos/líneas cobre (`#c87941`, metalness alto) |
| **Fondo** | Oscuro `#0a0e16` (alineado a landing) |

---

## Dónde va el código

```
frontend/lhexia-logo-3d/
├── src/
│   ├── components/LhexiaLogo3D.tsx   ← Canvas + escena
│   ├── data/lhexiaLogoCoordinates.ts ← NODOS y ARISTAS (editar o reemplazar)
│   ├── App.tsx                        ← demo local
│   └── main.tsx
├── package.json
└── README.md
```

**Probar en local:**

```bash
cd frontend/lhexia-logo-3d
npm install
npm run dev
```

→ http://localhost:5174

---

## Coordenadas (CSV — importado)

| Campo CSV | Uso en 3D |
|-----------|-----------|
| `Elemento_ID` | Un trazo cobre (tubo Catmull-Rom por polilínea) |
| `Punto_ID` | Orden de los vértices del trazo |
| `Normalizado_X`, `Normalizado_Y` | Posición en espacio Three.js (centrado, escala 5.2) |
| `Coordenada_X/Y` | Solo referencia px (no usado en runtime) |

Nodos verdes: inicio/fin de cada elemento + muestra cada ~6 puntos (~288 esferas).

---

## Coordenadas manuales (legacy / opcional)

### Sistema de referencia

- **Origen 2D provisional:** `static/img/lhexia_logo_redraw.svg` (centro hex ≈ `90, 100` en viewBox `650×200`).
- **Conversión a Three.js:** función `svgToThree(x, y, z)` en `lhexiaLogoCoordinates.ts`.
- Si las coordenadas vienen de otro tool (Blender, Figma, CSV), documentar escala y eje abajo.

| Parámetro | Valor |
|-----------|--------|
| Unidad | _(ej. px SVG / metros Blender)_ |
| Escala global | _(ej. 0.022)_ |
| Centro | _(x, y, z)_ |
| Eje Y | _(arriba = +Y en Three)_ |

### Hexágono (6 vértices)

Pegar como `x,y` o `x,y,z` por fila:

```
# vértice_1:
# vértice_2:
# vértice_3:
# vértice_4:
# vértice_5:
# vértice_6:
```

### Nodos verdes (esferas)

| id | x | y | z | scale (opc.) | notas |
|----|---|---|---|--------------|-------|
|    |   |   |   |              |       |

### Aristas cobre (circuitos)

| id | from_id | to_id | notas |
|----|---------|-------|-------|
|    |         |       |       |

### Path letra «L» (opcional)

```
# puntos en orden:
```

---

## Uso del componente (cuando las coords estén listas)

```tsx
import { LhexiaLogo3D } from './components/LhexiaLogo3D';
import { DEFAULT_LOGO_NODES, DEFAULT_LOGO_EDGES } from './data/lhexiaLogoCoordinates';

<LhexiaLogo3D
  nodes={DEFAULT_LOGO_NODES}
  edges={DEFAULT_LOGO_EDGES}
  autoRotate
  showLPath
  style={{ height: 480 }}
/>
```

Props:

| Prop | Tipo | Default | Descripción |
|------|------|---------|-------------|
| `nodes` | `LogoNode[]` | coords por defecto | Esferas neón |
| `edges` | `LogoEdge[]` | coords por defecto | Tubos cobre entre ids |
| `autoRotate` | `boolean` | `true` | Gira el grupo |
| `showLPath` | `boolean` | `true` | Dibuja la L interna |

---

## Integración con www.lhexia.cl (fase posterior)

1. `npm run build` → copiar `dist/` a `static/lhexia-logo-3d/`.
2. Embeber en `templates/index.html` (o login) con `<script type="module">`.
3. **No bloquea SD-1** (POS / inventario).

---

## Checklist

- [x] CSV `docs/lhexia_logo_coordenadas.csv` importado
- [x] Script `scripts/build_lhexia_logo_from_csv.py`
- [ ] `npm run build` sin errores (probar en `frontend/lhexia-logo-3d`)
- [ ] Revisión visual vs wordmark oficial
- [ ] Decidir si entra en landing o solo demo/marketing

---

*Última actualización: 2026-05-19 — scaffold Cursor; coords definitivas pendientes en este archivo.*

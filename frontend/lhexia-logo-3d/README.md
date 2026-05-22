# LhexIA Logo 3D (React + Three.js)

**Especificación y coordenadas:** ver `docs/planes/02-producto-lhexia/LHEXIA_LOGO_3D_REACT.md` (completar tablas ahí).

Componente que dibuja el isotipo LhexIA en 3D a partir de coordenadas (hexágono + circuitos).

- **Nodos:** esferas verde neón con pulso y luz puntual
- **Circuitos:** tubos cobre (curvas Bezier entre nodos)
- **Coordenadas:** `src/data/lhexiaLogoCoordinates.ts` (derivadas de `static/img/lhexia_logo_redraw.svg`)

## Uso

```bash
cd frontend/lhexia-logo-3d
npm install
npm run dev
```

Abre http://localhost:5174

## En tu app React

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

### Coordenadas propias

```ts
import { svgToThree, type LogoNode, type LogoEdge } from './data/lhexiaLogoCoordinates';

const nodes: LogoNode[] = [
  { id: 'a', position: svgToThree(90, 25), scale: 1.2 },
];
```

## Integración con Flask (opcional)

Tras `npm run build`, copia `dist/` a `static/lhexia-logo-3d/` y embebe con `<script type="module">` en una landing.

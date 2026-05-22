/**
 * Coordenadas del isotipo LhexIA (hex + circuitos neurales).
 * Origen 2D: static/img/lhexia_logo_redraw.svg (viewBox 650×200, centro hex ≈ 90,100).
 * Conversión: centrar, escalar y voltear Y para espacio Three.js (Y arriba).
 */

export type Vec3 = readonly [number, number, number];

export type LogoNode = {
  id: string;
  position: Vec3;
  /** Radio relativo del nodo (1 = estándar) */
  scale?: number;
};

export type LogoEdge = {
  id: string;
  from: string;
  to: string;
};

const SVG_CENTER: Vec3 = [90, 100, 0];
const SCALE = 0.022;

/** SVG (x,y) → Three.js [x, y, z] */
export function svgToThree(svgX: number, svgY: number, z = 0): Vec3 {
  return [
    (svgX - SVG_CENTER[0]) * SCALE,
    -(svgY - SVG_CENTER[1]) * SCALE,
    z,
  ] as const;
}

/** Vértices del hexágono (polígono del SVG) */
export const HEX_SVG_POINTS: readonly [number, number][] = [
  [90, 25],
  [155, 62.5],
  [155, 137.5],
  [90, 175],
  [25, 137.5],
  [25, 62.5],
] as const;

export const HEX_VERTICES_3D: Vec3[] = HEX_SVG_POINTS.map(([x, y]) => svgToThree(x, y, 0));

/** Aristas del hexágono (cerrado) */
export const HEX_EDGES: readonly [number, number][] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
  [5, 0],
] as const;

/** Letra «L» estilizada (vértices del path SVG simplificado) */
const L_SVG_POINTS: readonly [number, number][] = [
  [50, 55],
  [85, 55],
  [85, 115],
  [130, 115],
  [130, 145],
  [50, 145],
  [50, 55],
] as const;

export const L_PATH_3D: Vec3[] = L_SVG_POINTS.map(([x, y]) => svgToThree(x, y, 0.02));

/**
 * Nodos verdes neón: esquinas del hex, vértices de la L y puntos de ramificación
 * (circuitos que salen del isotipo, inspirados en el wordmark oficial).
 */
export const DEFAULT_LOGO_NODES: LogoNode[] = [
  { id: 'hex-0', position: HEX_VERTICES_3D[0], scale: 1.1 },
  { id: 'hex-1', position: HEX_VERTICES_3D[1], scale: 1.1 },
  { id: 'hex-2', position: HEX_VERTICES_3D[2], scale: 1.1 },
  { id: 'hex-3', position: HEX_VERTICES_3D[3], scale: 1.1 },
  { id: 'hex-4', position: HEX_VERTICES_3D[4], scale: 1.1 },
  { id: 'hex-5', position: HEX_VERTICES_3D[5], scale: 1.1 },
  { id: 'l-1', position: svgToThree(85, 55, 0.03), scale: 0.85 },
  { id: 'l-2', position: svgToThree(85, 115, 0.03), scale: 0.9 },
  { id: 'l-3', position: svgToThree(130, 115, 0.03), scale: 0.95 },
  { id: 'l-4', position: svgToThree(130, 145, 0.03), scale: 1 },
  { id: 'core', position: svgToThree(90, 100, 0.05), scale: 1.25 },
  { id: 'key', position: svgToThree(115, 65, 0.04), scale: 0.75 },
  // Ramas de circuito (nodos periféricos)
  { id: 'branch-ne', position: svgToThree(175, 45, 0.01), scale: 0.9 },
  { id: 'branch-e', position: svgToThree(185, 100, 0), scale: 0.85 },
  { id: 'branch-se', position: svgToThree(170, 155, -0.01), scale: 0.9 },
  { id: 'branch-sw', position: svgToThree(15, 165, -0.01), scale: 0.85 },
  { id: 'branch-w', position: svgToThree(5, 100, 0), scale: 0.8 },
  { id: 'branch-nw', position: svgToThree(20, 40, 0.01), scale: 0.85 },
];

/** Líneas de cobre entre nodos (circuitos + hex + L) */
export const DEFAULT_LOGO_EDGES: LogoEdge[] = [
  ...HEX_EDGES.map(([a, b], i) => ({
    id: `hex-${i}`,
    from: `hex-${a}`,
    to: `hex-${b}`,
  })),
  { id: 'l-a', from: 'hex-5', to: 'l-1' },
  { id: 'l-b', from: 'l-1', to: 'l-2' },
  { id: 'l-c', from: 'l-2', to: 'l-3' },
  { id: 'l-d', from: 'l-3', to: 'l-4' },
  { id: 'core-hex0', from: 'core', to: 'hex-0' },
  { id: 'core-hex2', from: 'core', to: 'hex-2' },
  { id: 'core-key', from: 'core', to: 'key' },
  { id: 'branch-0', from: 'hex-0', to: 'branch-ne' },
  { id: 'branch-1', from: 'hex-1', to: 'branch-ne' },
  { id: 'branch-2', from: 'hex-1', to: 'branch-e' },
  { id: 'branch-3', from: 'hex-2', to: 'branch-se' },
  { id: 'branch-4', from: 'hex-3', to: 'branch-se' },
  { id: 'branch-5', from: 'hex-4', to: 'branch-sw' },
  { id: 'branch-6', from: 'hex-5', to: 'branch-w' },
  { id: 'branch-7', from: 'hex-5', to: 'branch-nw' },
  { id: 'branch-8', from: 'hex-0', to: 'branch-nw' },
];

/** Colores de marca */
export const LHEXIA_COLORS = {
  neonGreen: '#39ff9f',
  neonGreenEmissive: '#20ff88',
  copper: '#c87941',
  copperDark: '#8b5a2b',
  copperEmissive: '#ff9f4a',
  background: '#0a0e16',
} as const;

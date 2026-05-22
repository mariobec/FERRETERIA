import raw from './lhexiaLogoFromCsv.json';
import type { LogoNode, Vec3 } from './lhexiaLogoCoordinates';

export type LogoPathMap = Record<string, Vec3[]>;

export type LogoCsvData = {
  meta: {
    source: string;
    scale: number;
    elements: number;
    points: number;
    nodes: number;
  };
  paths: LogoPathMap;
  nodes: LogoNode[];
};

const data = raw as unknown as LogoCsvData;

export const LOGO_CSV_META = data.meta;
export const LOGO_CSV_PATHS: LogoPathMap = data.paths;
export const LOGO_CSV_NODES: LogoNode[] = data.nodes;

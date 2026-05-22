import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import {
  DEFAULT_LOGO_NODES,
  LHEXIA_COLORS,
  type LogoNode,
  type Vec3,
} from '../data/lhexiaLogoCoordinates';
import {
  LOGO_CSV_NODES,
  LOGO_CSV_PATHS,
  type LogoPathMap,
} from '../data/loadLogoFromCsv';

export type LhexiaLogo3DProps = {
  /** Nodos verdes (esferas). Por defecto: CSV de Mario. */
  nodes?: LogoNode[];
  /** Trazos cobre por Elemento_ID (modo CSV). */
  paths?: LogoPathMap;
  /** Usar docs/lhexia_logo_coordenadas.csv vía JSON generado. */
  useCsvData?: boolean;
  className?: string;
  style?: React.CSSProperties;
  autoRotate?: boolean;
};

const NODE_BASE_RADIUS = 0.038;
const COPPER_RADIUS = 0.009;

function NeonNode({ node, lite }: { node: LogoNode; lite?: boolean }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const scale = (node.scale ?? 1) * NODE_BASE_RADIUS;

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const pulse = 1 + Math.sin(clock.elapsedTime * 2.4 + node.position[0] * 12) * 0.1;
    meshRef.current.scale.setScalar(pulse);
  });

  return (
    <mesh ref={meshRef} position={node.position}>
      <sphereGeometry args={[scale, 16, 16]} />
      <meshStandardMaterial
        color={LHEXIA_COLORS.neonGreen}
        emissive={LHEXIA_COLORS.neonGreenEmissive}
        emissiveIntensity={lite ? 2.8 : 2.2}
        toneMapped={false}
        roughness={0.12}
        metalness={0.4}
      />
      {!lite ? (
        <pointLight
          color={LHEXIA_COLORS.neonGreen}
          intensity={0.2}
          distance={0.5}
          decay={2}
        />
      ) : null}
    </mesh>
  );
}

function CopperPath({ elementId, points }: { elementId: string; points: Vec3[] }) {
  const tube = useMemo(() => {
    const vectors = points.map((p) => new THREE.Vector3(...p));
    if (vectors.length < 2) return null;
    const curve =
      vectors.length === 2
        ? new THREE.LineCurve3(vectors[0], vectors[1])
        : new THREE.CatmullRomCurve3(vectors, false, 'centripetal');
    const tubularSegments = Math.min(Math.max(vectors.length, 12), 160);
    const geom = new THREE.TubeGeometry(curve, tubularSegments, COPPER_RADIUS, 6, false);
    const mat = new THREE.MeshStandardMaterial({
      color: LHEXIA_COLORS.copper,
      emissive: LHEXIA_COLORS.copperEmissive,
      emissiveIntensity: 0.4,
      metalness: 0.88,
      roughness: 0.25,
    });
    return { geom, mat };
  }, [points]);

  if (!tube) return null;

  return <mesh geometry={tube.geom} material={tube.mat} userData={{ elementId }} />;
}

function CopperCircuitPaths({ paths }: { paths: LogoPathMap }) {
  return (
    <group>
      {Object.entries(paths).map(([elId, pts]) => (
        <CopperPath key={elId} elementId={elId} points={pts} />
      ))}
    </group>
  );
}

function LogoScene({
  nodes,
  paths,
  autoRotate,
  csvMode,
}: {
  nodes: LogoNode[];
  paths?: LogoPathMap;
  autoRotate: boolean;
  csvMode: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (autoRotate && groupRef.current) {
      groupRef.current.rotation.y += delta * 0.35;
    }
  });

  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight position={[2, 3, 4]} intensity={1.15} color="#fff5e8" />
      <directionalLight position={[-3, -1, 2]} intensity={0.45} color="#39ff9f" />

      <group ref={groupRef} scale={csvMode ? 1 : 0.85}>
        {csvMode && paths ? <CopperCircuitPaths paths={paths} /> : null}
        {nodes.map((node) => (
          <NeonNode key={node.id} node={node} lite={csvMode} />
        ))}
      </group>

      <OrbitControls
        enablePan={false}
        minDistance={1.4}
        maxDistance={5}
        autoRotate={autoRotate}
        autoRotateSpeed={0.5}
      />
    </>
  );
}

/**
 * Logo LhexIA en 3D desde docs/lhexia_logo_coordenadas.csv
 * (esferas verde neón + tubos cobre por Elemento_ID).
 */
export function LhexiaLogo3D({
  nodes,
  paths,
  useCsvData = true,
  className,
  style,
  autoRotate = true,
}: LhexiaLogo3DProps) {
  const csvMode = useCsvData;
  const resolvedNodes = nodes ?? (csvMode ? LOGO_CSV_NODES : DEFAULT_LOGO_NODES);
  const resolvedPaths = paths ?? (csvMode ? LOGO_CSV_PATHS : undefined);
  return (
    <div
      className={className}
      style={{ width: '100%', height: '100%', minHeight: 320, ...style }}
      aria-label="Logo LhexIA 3D"
    >
      <Canvas
        camera={{ position: [0, 0, 3.6], fov: 38 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 2]}
      >
        <color attach="background" args={[LHEXIA_COLORS.background]} />
        <fog attach="fog" args={[LHEXIA_COLORS.background, 3, 7]} />
        <LogoScene
          nodes={resolvedNodes}
          paths={resolvedPaths}
          autoRotate={autoRotate}
          csvMode={csvMode}
        />
      </Canvas>
    </div>
  );
}


export default LhexiaLogo3D;

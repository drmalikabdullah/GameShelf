import { Suspense, useMemo, useRef, type MutableRefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import { useTexture } from '@react-three/drei';
import * as THREE from 'three';
import type { Game } from '../../types';

const ANGLE_STEP = 0.34; // radians between neighboring covers on the arc
const RADIUS = 3.4;
const MAX_VISIBLE_OFFSET = 6.5; // covers further than this fully fade out
const ELEVATION = 0.22; // how high the focused cover rises - no visible pedestal, just lift

// Exact scale steps: center 1.0, next 0.82, next 0.70, next 0.55 - linearly
// interpolated between them for the continuous (spring-animated) offset,
// held at 0.55 beyond the third cover.
const SCALE_STOPS: [number, number][] = [
  [0, 1.0],
  [1, 0.82],
  [2, 0.7],
  [3, 0.55],
];

function lerpStops(stops: [number, number][], absOffset: number): number {
  if (absOffset <= 0) return stops[0][1];
  for (let i = 0; i < stops.length - 1; i++) {
    const [x0, y0] = stops[i];
    const [x1, y1] = stops[i + 1];
    if (absOffset <= x1) {
      const t = (absOffset - x0) / (x1 - x0);
      return THREE.MathUtils.lerp(y0, y1, t);
    }
  }
  return stops[stops.length - 1][1];
}

const scaleForOffset = (absOffset: number) => lerpStops(SCALE_STOPS, absOffset);

// Exact rotation steps (degrees, replacing the old linear
// offset*ANGLE_STEP tilt): center faces the camera dead-on, next 10°,
// next 14°, next 18° - each card tilting a little further to "face" the
// focus point rather than a uniform per-step increment.
const ROTATION_STOPS: [number, number][] = [
  [0, 0],
  [1, 10],
  [2, 14],
  [3, 18],
];

const rotationDegForOffset = (absOffset: number) => lerpStops(ROTATION_STOPS, absOffset);

function CoverTexture({ url }: { url: string }) {
  const texture = useTexture(url);
  return <meshStandardMaterial map={texture} roughness={0.4} metalness={0.05} toneMapped />;
}

function Placeholder({ color }: { color: string }) {
  return <meshStandardMaterial color={color} roughness={0.5} metalness={0.1} />;
}

interface CoverCardProps {
  game: Game;
  coverSrc: string | null;
  offsetRef: MutableRefObject<number>;
  index: number;
}

/**
 * One game's cover, floating on its own - a plain textured plane, no case,
 * frame, or backing of any kind. Positioned every frame along a virtual
 * arc based on its distance from the carousel's current (spring-animated)
 * focus point - a hand-rolled 3D coverflow rather than a carousel library.
 * The focused cover (offset 0) lifts slightly higher than the rest - an
 * invisible pedestal implied purely by position, no geometry for it.
 */
export function CoverCard({ game, coverSrc, offsetRef, index }: CoverCardProps) {
  const group = useRef<THREE.Group>(null);
  const color = useMemo(() => game.case_color_override || game.case_color || '#2f8fd4', [game]);

  useFrame(() => {
    const g = group.current;
    if (!g) return;
    const offset = index - offsetRef.current;
    const theta = offset * ANGLE_STEP;
    const x = Math.sin(theta) * RADIUS;
    const z = -Math.cos(theta) * RADIUS + RADIUS;
    const scale = scaleForOffset(Math.abs(offset));
    const visible = Math.abs(offset) < MAX_VISIBLE_OFFSET;

    const liftT = THREE.MathUtils.clamp(1 - Math.abs(offset), 0, 1);
    const lift = liftT * liftT * (3 - 2 * liftT) * ELEVATION; // smoothstep

    const rotSign = offset > 0 ? -1 : offset < 0 ? 1 : 0;
    const rotationRad = THREE.MathUtils.degToRad(rotationDegForOffset(Math.abs(offset))) * rotSign;

    g.position.set(x, visible ? lift : -100, z);
    g.rotation.y = rotationRad;
    g.scale.setScalar(scale);

    // Not a continuous fade-to-black with distance - every non-focused
    // cover settles at the same fixed look (70% opacity, 80% brightness),
    // easing in from the focused card's 100%/100% as it moves off-center.
    const mat = (g.children[0] as THREE.Mesh)?.material as THREE.MeshStandardMaterial | undefined;
    if (mat) {
      const focusT = liftT * liftT * (3 - 2 * liftT); // 1 at center, 0 by one step away
      mat.opacity = THREE.MathUtils.lerp(0.7, 1.0, focusT);
      mat.transparent = true;
      const brightness = THREE.MathUtils.lerp(0.8, 1.0, focusT);
      mat.color.setScalar(brightness);
    }
  });

  return (
    <group ref={group}>
      <mesh>
        <planeGeometry args={[0.94, 1.4]} />
        <Suspense fallback={<Placeholder color={color} />}>
          {coverSrc ? <CoverTexture url={coverSrc} /> : <Placeholder color={color} />}
        </Suspense>
      </mesh>
    </group>
  );
}

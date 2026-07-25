import { Canvas, useFrame } from '@react-three/fiber';
import { useRef, type MutableRefObject } from 'react';
import type { MotionValue } from 'framer-motion';
import { CoverCard } from './scene/CoverCard';
import { Lighting } from './scene/Lighting';
import { PostFX } from './scene/PostFX';
import type { Game } from '../types';
import { coverUrl } from '../api';

function ProgressSync({
  progress,
  offsetRef,
}: {
  progress: MotionValue<number>;
  offsetRef: MutableRefObject<number>;
}) {
  useFrame(() => {
    offsetRef.current = progress.get();
  });
  return null;
}

interface MuseumProps {
  games: Game[];
  progress: MotionValue<number>;
}

/**
 * Clean-slate scene: just the carousel of game covers, lit enough to be
 * visible. No floor, pedestal, glass case, or spotlight beam - those were
 * removed wholesale to restart the visual design from scratch.
 */
export function Museum({ games, progress }: MuseumProps) {
  const offsetRef = useRef(0);

  return (
    <Canvas dpr={[1, 1.75]} camera={{ position: [0, 0, 5.4], fov: 36 }} gl={{ antialias: true }}>
      <color attach="background" args={['#05050a']} />
      <ProgressSync progress={progress} offsetRef={offsetRef} />
      <Lighting />
      {games.map((game, i) => (
        <CoverCard key={game.id} game={game} coverSrc={coverUrl(game)} offsetRef={offsetRef} index={i} />
      ))}
      <PostFX />
    </Canvas>
  );
}

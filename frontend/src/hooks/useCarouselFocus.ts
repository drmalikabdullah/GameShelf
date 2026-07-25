import { useCallback, useEffect, useState } from 'react';
import { useMotionValue, animate } from 'framer-motion';

/**
 * Drives the carousel: `index` is React state for anything that should
 * update immediately (title, info panel), `progress` is a Framer Motion
 * value spring-animating toward that index for the 3D scene to read every
 * frame (see useCarouselProgress) - the two are deliberately decoupled so
 * the UI text feels instant while the geometry eases in behind it.
 */
export function useCarouselFocus(count: number, initial = 0) {
  const [index, setIndex] = useState(() => Math.min(initial, Math.max(count - 1, 0)));
  const progress = useMotionValue(index);

  useEffect(() => {
    const controls = animate(progress, index, {
      type: 'spring',
      stiffness: 110,
      damping: 18,
      mass: 1.1,
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  const goTo = useCallback(
    (next: number) => {
      setIndex(Math.max(0, Math.min(count - 1, next)));
    },
    [count]
  );

  const move = useCallback((delta: number) => goTo(index + delta), [goTo, index]);

  return { index, progress, goTo, move };
}

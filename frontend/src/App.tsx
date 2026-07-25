import { Suspense, useEffect, useState } from 'react';
import { Museum } from './components/Museum';
import { Overlay } from './components/ui/Overlay';
import { useCarouselFocus } from './hooks/useCarouselFocus';
import { fetchGames } from './api';
import type { Game } from './types';

const PLATFORM = new URLSearchParams(window.location.search).get('platform') || 'gog';

function exitToShelf() {
  window.location.href = '/';
}

export default function App() {
  const [games, setGames] = useState<Game[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGames(PLATFORM)
      .then(setGames)
      .catch((e) => setError(e.message));
  }, []);

  const { index, progress, move } = useCarouselFocus(games?.length ?? 0);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'ArrowRight') move(1);
      else if (e.key === 'ArrowLeft') move(-1);
      else if (e.key === 'Escape') exitToShelf();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [move]);

  if (error) {
    return (
      <div className="flex h-full w-full items-center justify-center text-white/70">
        Couldn't load your library: {error}
      </div>
    );
  }

  if (!games) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm tracking-widest text-white/40 uppercase">
        Loading collection…
      </div>
    );
  }

  if (games.length === 0) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-4 text-white/60">
        <div>No games on this shelf yet.</div>
        <button
          onClick={exitToShelf}
          className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs text-white/80"
        >
          ✕ Back to shelf
        </button>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <Suspense fallback={null}>
        <Museum games={games} progress={progress} />
      </Suspense>
      <Overlay game={games[index]} onExit={exitToShelf} onPrev={() => move(-1)} onNext={() => move(1)} />
    </div>
  );
}

import { AnimatePresence, motion } from 'framer-motion';
import type { Game } from '../../types';

interface OverlayProps {
  game: Game | undefined;
  onExit: () => void;
  onPrev: () => void;
  onNext: () => void;
}

export function Overlay({ game, onExit, onPrev, onNext }: OverlayProps) {
  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-8 text-white">
      <div className="pointer-events-auto flex items-start justify-between">
        <div>
          <div className="text-[11px] tracking-[0.35em] uppercase text-white/45">Collection Museum</div>
          <AnimatePresence mode="wait">
            <motion.div
              key={game?.id ?? 'none'}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
              className="mt-1 text-lg font-medium tracking-wide"
            >
              {game?.title ?? ''}
            </motion.div>
          </AnimatePresence>
        </div>
        <button
          onClick={onExit}
          className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs tracking-wide text-white/80 backdrop-blur-md transition hover:border-white/30 hover:bg-white/10"
        >
          ✕ Exit
        </button>
      </div>

      <div className="pointer-events-auto mx-auto flex max-w-xl flex-col items-center gap-3 pb-2 text-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={game?.id ?? 'none'}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="flex flex-col items-center gap-2"
          >
            {game && (
              <>
                <h1 className="text-3xl font-semibold tracking-tight">
                  {game.title}
                  {game.release_date && (
                    <span className="ml-2 text-white/40 font-normal">({game.release_date})</span>
                  )}
                </h1>
                <div className="text-xs text-white/50 tracking-wide">
                  {game.size_human}
                  {game.rating ? ` · ${'★'.repeat(Math.round(game.rating / 2))}` : ''}
                  {game.developer ? ` · ${game.developer}` : ''}
                </div>
              </>
            )}
          </motion.div>
        </AnimatePresence>

        <div className="mt-2 flex items-center gap-6">
          <button
            onClick={onPrev}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/5 text-white/80 backdrop-blur-md transition hover:border-white/30 hover:bg-white/10"
          >
            ◄
          </button>
          <span className="text-[11px] tracking-[0.2em] text-white/35">◄ ► ARROW KEYS · ESC CLOSE</span>
          <button
            onClick={onNext}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/5 text-white/80 backdrop-blur-md transition hover:border-white/30 hover:bg-white/10"
          >
            ►
          </button>
        </div>
      </div>
    </div>
  );
}

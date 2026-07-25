import type { Game } from './types';

export async function fetchGames(platform: string): Promise<Game[]> {
  const params = new URLSearchParams({ platform, status: 'all', q: '', sort: 'title' });
  const res = await fetch(`/api/games?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load games: ${res.status}`);
  return res.json();
}

export function coverUrl(game: Game): string | null {
  if (!game.cover_url) return null;
  return `${game.cover_url}?t=${encodeURIComponent(game.updated_at)}`;
}

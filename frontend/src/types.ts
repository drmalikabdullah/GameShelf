export interface Game {
  id: number;
  title: string;
  platform: string;
  status: string;
  rating: number | null;
  size_human: string;
  release_date: string | null;
  developer: string | null;
  genres: string | null;
  description: string | null;
  cover_url: string | null;
  hero_url: string | null;
  case_color: string | null;
  case_color_override: string | null;
  gog_id: string | null;
  folder_path: string | null;
  exe_path: string | null;
  updated_at: string;
}

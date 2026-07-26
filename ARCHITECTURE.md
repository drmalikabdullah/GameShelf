# GameShelf Architecture — Complete Technical Reference

## Overview

**GameShelf** is a self-hosted, offline game library cataloging system. It combines a Python Flask backend, SQLite database, and dual-mode frontend (static HTML/JS + optional React/Three.js 3D interface) to provide a complete game collection management solution with zero cloud dependencies.

### Core Principle
No cloud, no accounts, no telemetry. Everything lives on your machine in `games.db`.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User's Browser                          │
├──────────────────────┬──────────────────┬───────────────────┤
│   Static Shelf       │   3D Museum      │    Dashboard      │
│  (index.html)        │  (React/Three)   │  (analytics)      │
│  HTML/CSS/JS         │  Optional build  │                   │
└──────────────────────┴──────────────────┴───────────────────┘
           │                    │                   │
           └────────────────────┼───────────────────┘
                                │
                    HTTP/REST API (JSON)
                                │
        ┌───────────────────────▼───────────────────────┐
        │   Flask Backend (app.py) — Port 5000          │
        │  ┌─────────────────────────────────────────┐  │
        │  │  /api/games          (CRUD)             │  │
        │  │  /api/stats          (analytics)        │  │
        │  │  /api/dashboard      (overview)         │  │
        │  │  /api/settings       (config)           │  │
        │  │  /api/build_status   (version check)    │  │
        │  └─────────────────────────────────────────┘  │
        └────────────────────────┬─────────────────────┘
                                 │
        ┌────────────────────────▼─────────────────────┐
        │         SQLite Database (games.db)           │
        │  ┌──────────────────────────────────────┐   │
        │  │  games (primary table)               │   │
        │  │  bonus_content (DLC/patches)         │   │
        │  │  game_screenshots (local paths)      │   │
        │  │  deleted_games (soft-delete archive) │   │
        │  └──────────────────────────────────────┘   │
        └─────────────────────────────────────────────┘
                                 │
        ┌────────────────────────▼─────────────────────┐
        │     Persistent Local Storage                 │
        │  games.db, covers/, heroes/, screenshots/    │
        └─────────────────────────────────────────────┘
```

---

## Layer 1: Frontend (User Interface)

### 1.1 Static Shelf (Primary Interface)

**Files:** `static/index.html`, `static/app.js`, `static/style.css`

**Technology:** Plain HTML5, CSS3, Vanilla JavaScript

**Features:**
- Grid layout of game tiles (book-spine style with case color)
- Platform tabs (GOG/Steam/PS3/PS4)
- Fuzzy search (normalizes punctuation)
- Status filter tabs (Backlog/Playing/Completed/Abandoned)
- Sort options (title, size, rating, added date, missing folders)
- Modal for editing game details (title, status, rating, notes, tags)
- Drag-and-drop cover upload
- Folder/executable path pickers
- Soft-delete recovery (trash bin)
- Floating action buttons (+Add Game, Search, Trash, Big Picture)

**Why it works:**
- Zero build step
- Works offline
- Lightweight
- No JavaScript framework overhead

### 1.2 Platform-Specific Views

**Files:** `static/steam.html`, `static/ps3.html`, `static/ps4.html`

Identical UI to GOG shelf but filtered by platform. PS3/PS4 omit:
- Executable launching
- GOG version checking
- Build status tracking

### 1.3 Dashboard (Analytics)

**Files:** `static/dashboard.html`, `static/dashboard.js`

**Displays:**
- Total games, total storage, status breakdown
- Per-platform stats
- Top 5 rated games, largest games, recently added
- Histograms:
  - Library size distribution (bucketed: <1G, 1-5G, 5-15G, etc.)
  - Rating distribution (1-10 scale)
  - Games added per month (last 12 months)
- GOG build status:
  - Up-to-date / outdated / unverified breakdown
  - List of outdated games with recommendations
  - Upload gamelist.txt to refresh version info

### 1.4 Settings Page

**Files:** `static/settings.html`, `static/settings.js`

- SteamGridDB API key management
- Display key source (env var vs. saved file)
- Optional: other future configuration

### 1.5 Optional: 3D Museum (React + Three.js)

**Files:** `static/museum/` (pre-built output)

**Technology:** React 19, TypeScript, Three.js, Framer Motion, Vite (build only)

**Features:**
- 3D game carousel with smooth spring animations
- Arrow key navigation
- Focused card: 100% scale, 100% opacity, 100% brightness
- Unfocused cards: 0.55–0.82x scale, 70% opacity, 80% brightness
- Depth of field blur for cinematic look
- Screenshot lightbox
- Detail modal for editing
- ESC key to exit back to shelf

**Components (if rebuilding):**
- `App.tsx` — Root component, carousel state, keyboard input
- `Museum.tsx` — Three.js Canvas setup
- `CoverCard.tsx` — Individual 3D game cover (textured plane)
- `Lighting.tsx` — Professional lighting (key/fill/back/ambient)
- `PostFX.tsx` — Post-processing effects (DoF, bloom, noise)
- `Overlay.tsx` — HTML overlay (info, nav, modal)
- `useCarouselFocus.ts` — Spring animation hook (Framer Motion)

**Note:** This is optional. The app works perfectly without it. Requires Node.js + npm to rebuild.

---

## Layer 2: Backend API (Flask)

**File:** `backend/app.py` (36,909 bytes)

### 2.1 Core Endpoints

#### Games CRUD

```
GET /api/games
  Query params: platform, status, tag, search, sort
  Returns: List of games matching filters
  
POST /api/games
  Body: { title, platform }
  Returns: New game record
  Side effects: Fetches cover art, calculates dominant color
  
PATCH /api/games/<id>
  Body: { title, status, rating, notes, tags, folder_path, exe_path, ... }
  Returns: Updated game record
  Side effects: Auto-calculates folder size, re-fetches cover if title changed
  
DELETE /api/games/<id>
  Returns: Soft-deleted game record (moved to deleted_games table)
```

#### Game Actions

```
POST /api/games/<id>/play
  Effect: Launches game executable (Windows: CreateProcess, Unix: subprocess)
  
POST /api/games/<id>/open_folder
  Effect: Opens folder in explorer/file manager
  
GET /api/games/<id>/bonus
  Returns: List of DLC/patches linked to this game
  
GET /api/games/<id>/screenshots
  Returns: List of local screenshot paths for this game
```

#### Analytics

```
GET /api/stats
  Returns: Per-platform counts, status breakdown, total storage
  
GET /api/dashboard
  Returns: Cross-shelf overview (totals, top-rated, recently added)
  
GET /api/dashboard/insights
  Returns: Histogram data (size distribution, ratings, activity timeline)
  
GET /api/build_status
  Returns: GOG version comparison (up-to-date vs. outdated)
```

#### Settings

```
GET /api/settings/steamgriddb_key
  Returns: { has_key: bool, source: "env" | "file" }
  
POST /api/settings/steamgriddb_key
  Body: { key: string }
  Effect: Saves key to file
```

#### Export/Import

```
GET /api/export/gamelist
  Returns: Plaintext export of library (GOG gamelist.txt format)
  
POST /api/build_status/upload
  Body: File upload (gamelist.txt)
  Effect: Compares against current library, updates latest_build field
```

#### Page Routes

```
GET /                    → GOG Shelf (index.html)
GET /steam              → Steam Shelf
GET /ps3                → PS3 Shelf
GET /ps4                → PS4 Shelf
GET /dashboard          → Analytics Dashboard
GET /settings           → Settings Page
GET /museum             → 3D Museum (if built)
```

### 2.2 Key Functions

**`dominant_color(image_path: str) -> str | None`**
- Opens image with PIL, resizes to 64×64
- Quantizes to 6 colors (median cut algorithm)
- Extracts most common color
- Returns hex string `#rrggbb`
- Used to tint game tile backgrounds for visual shelf effect

**`calculate_folder_size(folder_path: str) -> int | None`**
- Recursively walks directory tree
- Sums file sizes
- Returns total in bytes
- Returns None if path doesn't exist or isn't a directory

**`normalize_search(text: str) -> str`**
- Lowercase all text
- Strip all non-alphanumeric characters
- Example: "S.T.A.L.K.E.R." → "stalker" matches "stalker" search

**`apply_title(title: str) -> tuple[str, str | None]`**
- Attempts to resolve game title via external APIs
- Tries SteamGridDB first (if key available)
- Falls back to GOG catalog
- Returns (resolved_title, cover_url)

**`verify_gog_id(title: str) -> str | None`**
- Looks up real GOG catalog product ID
- Fetches metadata (description, genres, developer, release date)
- Returns gog_catalog_id or None

**`serialize_game(row: sqlite3.Row) -> dict`**
- Converts database row to JSON
- Formats size_bytes as human-readable (e.g., "5.2 GB")
- Splits tags string into array
- Includes all metadata fields

### 2.3 Database Connection & Transactions

- Uses `sqlite3.connect()` with row factory for dict-like access
- Implements per-request `g.db` pattern (Flask request context)
- Automatic rollback on exceptions
- No explicit transaction management (auto-commit mode)

### 2.4 Configuration

**Environment Variables (optional):**
- `STEAMGRIDDB_API_KEY` — SteamGridDB API key (free tier)

**Fallback Locations:**
- `BASE_DIR / "cover_overrides.json"` — Manual color overrides per game
- `BASE_DIR / "games.db"` — SQLite database (auto-created if missing)

**File Paths:**
- If running as PyInstaller exe → `BASE_DIR = sys.executable.parent`
- Otherwise → `BASE_DIR = app.py.parent`

---

## Layer 3: Data Layer

### 3.1 SQLite Database Schema

**File:** `backend/schema.sql`

#### Table: `games` (Primary)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `gog_id` | TEXT | Build/version number from folder name (user's scheme, not authoritative) |
| `gog_catalog_id` | TEXT | Real GOG product ID (from api.gog.com) |
| `platform` | TEXT | `gog` \| `steam` \| `ps3` \| `ps4` |
| `title` | TEXT NOT NULL | Game name (editable) |
| `size_bytes` | INTEGER | Total folder size in bytes (auto-calculated if folder_path set) |
| `folder_path` | TEXT | Path to installation folder on disk |
| `exe_path` | TEXT | Path to launch executable (GOG/Steam only) |
| `raw_paths` | TEXT | JSON array of original folder names (read-only) |
| `status` | TEXT DEFAULT 'backlog' | `backlog` \| `playing` \| `completed` \| `abandoned` |
| `rating` | INTEGER | 1-10 (nullable, user's rating) |
| `notes` | TEXT | Freeform text (user's notes) |
| `tags` | TEXT | Comma-separated user tags |
| `cover_url` | TEXT | Local path or remote URL to cover image |
| `hero_url` | TEXT | Wide banner art for detail modal |
| `genres` | TEXT | Comma-separated (from enrichment) |
| `description` | TEXT | Game description |
| `developer` | TEXT | Comma-separated developer names |
| `release_date` | TEXT | Release year or full date |
| `latest_build` | TEXT | Newest GOG build ID (from version checking) |
| `build_checked_at` | TEXT | Timestamp of last version check |
| `case_color` | TEXT | Hex color auto-detected from cover |
| `case_color_override` | TEXT | User-selected color (wins over auto-detected) |
| `added_at` | TEXT DEFAULT now() | Timestamp when added to library |
| `updated_at` | TEXT DEFAULT now() | Last modification timestamp |

#### Table: `bonus_content`

Tracks DLC, patches, extras:

| Column | Type |
|--------|------|
| `id` | INTEGER PK |
| `kind` | TEXT — `extras` or `patch` |
| `title` | TEXT |
| `size_bytes` | INTEGER |
| `raw_paths` | TEXT — JSON array |
| `game_id` | INTEGER FK → games(id) ON DELETE SET NULL |

#### Table: `game_screenshots`

Local screenshot paths:

| Column | Type |
|--------|------|
| `id` | INTEGER PK |
| `game_id` | INTEGER FK → games(id) ON DELETE CASCADE |
| `path` | TEXT — local path like `/screenshots/<game_id>/<n>.jpg` |
| `position` | INTEGER — display order |

#### Table: `deleted_games`

Soft-delete archive (full copy of game row + deleted_at timestamp). Keeps newest 50 entries; purges oldest when limit exceeded.

| Column | Type |
|--------|------|
| `id` | INTEGER PK |
| `original_id` | INTEGER — reference to deleted game's original id |
| ... | [All game table columns] |
| `deleted_at` | TEXT DEFAULT now() |

### 3.2 Indexing

```sql
CREATE INDEX idx_games_status ON games(status);
CREATE INDEX idx_games_title ON games(title);
CREATE INDEX idx_screenshots_game ON game_screenshots(game_id);
```

Fast lookups by status, title, and screenshot retrieval.

---

## Layer 4: Data Import & Processing

### 4.1 Parsing Modules

**`backend/parse_gog.py`** — GOG folder listing parser

**Input:** Raw `du -sh * > gog.txt` folder listing (UTF-8 or UTF-16)

**Output:** `games.json` (JSON array of game objects)

**Processing:**
- Auto-detects UTF-8 vs. UTF-16 encoding
- Parses size strings (e.g., "5.2G" → 5,597,380,608 bytes)
- Extracts GOG build IDs from folder names: `-(57222)`, `-(74575)(1)`
- Cleans platform suffixes: `_windows_gog_`, `_game_windows_gog_`
- Normalizes titles (title case, handles Roman numerals, acronyms like "GOTY")
- Deduplicates by GOG ID or title (keeps largest size)
- Categorizes as game, extra, or patch

**Example:**
```
Input:  5.2G    Cyberpunk.2077.Game-(2.21)
Output: { "title": "Cyberpunk 2077", "size_bytes": 5597380608, "gog_id": "2.21", "platform": "gog" }
```

**`backend/parse_steam.py`** — Steam folder listing parser

**Input:** Steam `libraryfolders.vdf` manifest file

**Output:** `games.json` (Steam games)

**`backend/parse_ps3.py`** — PS3 folder listing parser

**Input:** PS3 game folder structure

**Output:** `games.json` (PS3 games)

### 4.2 Database Loader

**`backend/load_db.py`**

**Input:** `games.json` (from any parser)

**Process:**
- Upsert by `gog_id` (primary) or title (fallback)
- No duplicates created
- Refreshes `size_bytes` and `raw_paths`
- **Preserves** user edits: status, rating, notes, tags, folder_path, exe_path
- Links bonus content to games by title matching
- Safe to re-run after parsing new lists

**Usage:**
```bash
# Parse and load both lists at once
python3 parse_gog.py gog.txt second_list.txt -o games.json
python3 load_db.py games.json --db games.db
```

### 4.3 Enrichment Modules

**`backend/enrich.py`** — Cover art from GOG catalog

- Calls `api.gog.com/products/{id}` for each game with gog_catalog_id
- Fetches and saves cover images to `static/covers/`
- Backfills `cover_url` and `case_color`
- Re-runs only fill games still missing a cover (cheap to re-run)

**`backend/enrich_steamgriddb.py`** — Cover art from SteamGridDB

- Requires API key (free signup at steamgriddb.com)
- Fetches high-quality cover art, hero banners, logos
- Supports Steam official art
- Better image quality than GOG catalog

**`backend/enrich_story.py`** — Screenshots

- Fetches game screenshots
- Saves to `static/screenshots/`
- Stores paths in `game_screenshots` table

**`backend/check_latest_builds.py`** — GOG version checking

- Compares current build IDs against official gamelist.txt snapshot
- Identifies outdated installations
- Updates `latest_build` field for each game
- Runs from dashboard upload or CLI

### 4.4 Supporting Modules

**`backend/gog_catalog.py`** — GOG API client

- HTTP client for GOG's public product catalog
- Used by `apply_title()` and `verify_gog_id()`
- Fallback when SteamGridDB unavailable

**`backend/steamgriddb.py`** — SteamGridDB API client

- HTTP client for SteamGridDB
- Requires API key
- Fetches high-quality cover art and metadata

**`backend/launcher.py`** — Game launcher utility

- Abstracts platform differences (Windows vs. Unix)
- Handles executable launching with proper working directory
- Used by POST `/api/games/<id>/play` endpoint

**`backend/build.py`** — PyInstaller packaging script

- Rebuilds React app (`npm run build`)
- Bundles Python + Flask + static assets
- Produces Windows `.exe` or native binary
- `--fresh` flag excludes personal data for distribution to friends

**`backend/assign_case_colors.py`** — Batch color extraction

- Re-compute dominant colors for entire library
- Useful for fixing color palette issues

---

## Layer 5: Storage & Assets

### 5.1 Directory Structure

```
backend/
├── games.db                    # SQLite database (user data)
├── schema.sql                  # Schema definition
├── cover_overrides.json        # Manual color overrides { game_id: "#hex" }
│
└── static/
    ├── covers/                 # Downloaded cover images (<game_id>.jpg/png)
    ├── heroes/                 # Hero banner images
    ├── screenshots/            # Game screenshots (<game_id>/<n>.jpg)
    └── museum/                 # Built React app (dist output)
        └── assets/
```

### 5.2 Image Formats

- **Covers:** JPG or PNG (max 1-2 MB typical)
- **Heroes:** JPG or PNG (wide aspect ratio, ~16:9)
- **Screenshots:** JPG or PNG (as provided by source)

### 5.3 Cover Art Resolution

- **SteamGridDB:** 512×512 (covers), 1920×620 (heroes)
- **GOG Catalog:** Variable, typically 250×350
- **User Uploads:** Any size (resized by browser before upload)

---

## Data Flow Patterns

### 1. Initial Library Import

```
1. Export folder listing:
   du -sh * > gog.txt

2. Parse:
   parse_gog.py gog.txt -o games.json

3. Load into database:
   load_db.py games.json --db games.db

4. (Optional) Enrich metadata:
   enrich.py --db games.db

5. Start server:
   app.py

6. Browse at:
   http://127.0.0.1:5000
```

### 2. Adding a Game at Runtime

```
User clicks "+ Add Game" button
         ↓
User types title
         ↓
Frontend: POST /api/games { title: "Elden Ring", platform: "steam" }
         ↓
Backend:
  1. Insert into games table
  2. Call apply_title() → fetch cover from SteamGridDB/GOG
  3. Call dominant_color() → extract color from cover
  4. Call verify_gog_id() → lookup GOG product ID
  5. Save cover image to static/covers/
  6. Return full game record as JSON
         ↓
Frontend re-renders grid
         ↓
Game appears with cover art and auto-tinted tile
```

### 3. User Edits Game

```
User clicks game card → modal opens
         ↓
User edits field (e.g., status: "playing")
         ↓
Frontend: PATCH /api/games/<id> { status: "playing" }
         ↓
Backend:
  1. Validate input
  2. Update database row
  3. If folder_path changed: recalculate size_bytes
  4. If title changed: re-fetch cover_url
  5. If status changed: update timestamp
  6. Return updated game record
         ↓
Frontend re-renders card
```

### 4. Search & Filter

```
User types in search bar
         ↓
Normalize query: lowercase, strip punctuation
  "S.T.A.L.K.E.R." → "stalker"
         ↓
Filter chain:
  1. Platform (gog/steam/ps3/ps4)
  2. Status (backlog/playing/completed/abandoned)
  3. Tag (substring match in comma-list)
  4. Sort (title/size/rating/added/missing)
  5. Search (normalized substring match)
         ↓
Frontend re-renders matching games
```

---

## Dependencies & Requirements

### Python Runtime

```
flask           # Web server + REST API framework
Pillow          # Image processing (PIL) for dominant_color()
pywebview       # Optional: embedded WebView for desktop mode
pyinstaller     # Optional: package as standalone executable
requests        # HTTP client (usually included with Python)
sqlite3         # Database (built into Python 3)
```

### External APIs (Optional)

- **GOG Catalog API** — Free, no key required
  - Endpoint: `https://api.gog.com/products/{id}`
  - Used by: `gog_catalog.py`, `enrich.py`, `verify_gog_id()`

- **SteamGridDB API** — Free tier with API key
  - Signup: https://www.steamgriddb.com/
  - Used by: `steamgriddb.py`, `enrich_steamgriddb.py`, `apply_title()`
  - Better image quality than GOG catalog

### Frontend (if rebuilding React app)

```
React 19
Three.js 0.185+
@react-three/fiber 9.6+
@react-three/drei 10.7+
@react-three/postprocessing 3.0+
Framer Motion 12.42+
Tailwind CSS 4.3+
TypeScript 6.0+
Vite 8.1+
Oxlint 1.71+
```

**Note:** Pre-built in `static/museum/`. Only needed if modifying React source.

### Development Tools

- Node.js + npm (for React rebuilds)
- Git (for version control)
- Python 3.8+ (for backend)

---

## Key Design Decisions

### 1. Soft Deletes

Games are never permanently destroyed. When deleted:
- Full row copied to `deleted_games` table
- Original row removed from `games` table
- Only oldest entries beyond `DELETED_GAMES_LIMIT` (50) are purged
- Cover/hero images kept on disk for restore

**Benefit:** Users can recover accidentally deleted games.

### 2. Separate `gog_id` and `gog_catalog_id`

- **`gog_id`** — Version/build number from folder naming (e.g., "2.21")
  - User's own scheme, extracted from folder names
  - Not authoritative, sometimes collides across games
  
- **`gog_catalog_id`** — Real GOG product ID
  - Looked up from `api.gog.com`
  - Used for API calls and metadata

**Benefit:** Handles folder naming schemes that don't match GOG's catalog IDs.

### 3. No Destructive Reimport

User edits (status, rating, notes, tags) are **never** touched by reimport. When re-running `load_db.py`:
- Size/title/paths refreshed if changed
- User data (status, rating, notes, tags) preserved
- New games added, duplicates merged

**Benefit:** Users can safely re-import updated game lists without losing personal data.

### 4. Graceful Fallback Architecture

If primary service unavailable → fallback to secondary:

```
apply_title():
  Try SteamGridDB (if key set)
    ↓ Fail/timeout
  Try GOG Catalog (free)
    ↓ Fail/timeout
  Return original title, no cover

enrich.py:
  Try SteamGridDB
    ↓ Fail
  Try GOG Catalog
    ↓ Fail
  Skip, game saves anyway (no cover)
```

**Benefit:** App never breaks due to API unavailability. Worse case: games save without cover art.

### 5. Image Color Extraction

Dominant color extracted via PIL quantization:

```python
# Resize to small size (64×64) to avoid artifacts
im = Image.open(path).resize((64, 64))

# Quantize to 6 colors (median cut algorithm)
quantized = im.quantize(colors=6, method=Image.MEDIANCUT)

# Find most common color
counts = quantized.getcolors()
_, idx = counts[0]

# Extract RGB from palette
r, g, b = palette[idx*3:idx*3+3]
return f"#{r:02x}{g:02x}{b:02x}"
```

**Benefit:** Produces visually representative colors. Quantization merges similar shades, avoiding vote-splitting by small high-contrast elements (logos, text).

### 6. Responsive Platform Design

Each platform has different capabilities:

| Feature | GOG | Steam | PS3 | PS4 |
|---------|-----|-------|-----|-----|
| Executable launch | ✓ | ✓ | ✗ | ✗ |
| Version checking | ✓ | ✗ | ✗ | ✗ |
| Cover art | ✓ | ✓ | ✓ | ✓ |
| Folder browsing | ✓ | ✓ | ✓ | ✓ |
| Notes/rating | ✓ | ✓ | ✓ | ✓ |

**Benefit:** Each platform's UI reflects its actual capabilities.

### 7. Per-Request Database Connection

Flask pattern for thread-safe database access:

```python
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

**Benefit:** Each request gets its own connection. Automatic cleanup on request end.

---

## Deployment & Packaging

### Development Mode

```bash
cd backend
python3 app.py
# Open http://127.0.0.1:5000
```

### Production Build

```bash
cd frontend
npm install
npm run build        # Creates dist/ with optimized bundle

cd backend
python3 build.py     # Packages Windows .exe
python3 build.py --fresh  # Clean distribution (no personal data)
```

Output: `backend/dist/GameShelf.exe` (Windows) or native binary (Linux/macOS)

### Docker (if needed)

Not included. Can be added if needed:
- Dockerfile with Python 3.9+, Flask
- Expose port 5000
- Volume mount for games.db persistence
- Pre-built React assets

---

## Performance Considerations

### Database Queries

- Status/title indexed for fast filtering
- Pagination recommended for large libraries (100+ games)
- Can be added to `/api/games?limit=50&offset=0`

### Image Processing

- dominant_color() runs on first add (blocking)
- Can be moved to background task for large imports
- enrich.py scripts can be parallelized

### Frontend Performance

- Static shelf: instant (pure HTML/CSS/JS)
- 3D museum: WebGL rendering, smooth 60fps on most hardware
- Lazy loading: cover images load async with placeholder

### Frontend Caching

- Cover images cached by browser (2-week TTL via Cache-Control header)
- React app bundled with tree-shaking (only needed Three.js features included)

---

## Security Notes

### Data Isolation

- No network access for user data
- SQLite database local only
- Cover images stored locally after fetch

### API Keys

- SteamGridDB key stored in optional `cover_overrides.json` or env var
- Never logged or exposed in API responses
- Users should use free tier key with limited permissions

### Input Validation

- Folder paths checked to exist before saving
- Executable paths checked to be files
- Rating validated to be 1-10
- Status validated against enum

### Not Implemented (Acceptable Risk)

- SQL injection: Using parameterized queries throughout
- CSRF: Single-machine app, not applicable
- XSS: User data echoed in UI (notes, tags), but only user can edit and view
- Authentication: Single-machine app, no auth needed

---

## Future Enhancement Opportunities

### High Priority

- Pagination for large libraries (100+ games)
- Background tasks for enrichment (don't block UI)
- Game screenshot management (upload, organize)
- Custom categories/collection groups

### Medium Priority

- PS5 cover art source
- Local screenshot auto-capture
- Game time tracking (how long played)
- Achievement tracking
- Multi-user support (separate profiles)

### Low Priority

- Cloud sync (conflicts with core philosophy)
- Online multiplayer features
- Game streaming integration
- Community tagging/ratings

---

## Troubleshooting

### Cover Art Not Loading

1. Check SteamGridDB key is set (if using):
   ```bash
   echo $STEAMGRIDDB_API_KEY
   ```

2. Run enrichment manually:
   ```bash
   python3 enrich.py --db games.db
   ```

3. Check network connectivity (can reach api.gog.com, api.steamgriddb.com)

### Games Not Showing Up

1. Check database file exists:
   ```bash
   ls -la games.db
   ```

2. Check file permissions (readable by app)

3. Verify data loaded:
   ```bash
   sqlite3 games.db "SELECT COUNT(*) FROM games;"
   ```

### Slow Search/Filtering

1. Check indices are created:
   ```bash
   sqlite3 games.db ".indices"
   ```

2. Rebuild indices if corrupted:
   ```bash
   sqlite3 games.db < schema.sql
   ```

---

## Conclusion

GameShelf is a elegant, modular system designed for simplicity and reliability:
- **No unnecessary complexity** — Static HTML/JS works out of the box
- **Graceful degradation** — Missing API keys → fallback to free services
- **User control** — All data local, all edits preserved
- **Optional enhancements** — 3D UI, rich metadata, version checking all optional

The architecture prioritizes user sovereignty over flashiness, making it a long-term viable solution for personal game library management.

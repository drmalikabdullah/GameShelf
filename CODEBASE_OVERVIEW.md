# GameShelf — Complete Codebase Overview

## What This Project Does

**GameShelf** is a self-hosted, offline game library cataloging system with a stunning **3D carousel/museum interface**. It's a full-stack application that lets you manage a curated collection of games from GOG, Steam, PS3, and PS4 platforms without relying on cloud services or external accounts.

Think of it as a **personal game collection museum** — a visually immersive 3D gallery where your games float on an interactive carousel with professional lighting, depth-of-field effects, and smooth spring animations. You organize, rate, track your playthrough status, add notes, and browse everything through a beautiful React + Three.js interface.

---

## Architecture Overview

```
┌─────────────────────────────────────┬──────────────────────────────────────┐
│   Flask Backend (Port 5000)         │   React Frontend (Port 5173 dev)     │
│   app.py - REST API + Asset Serving │   Vite + React 19 + Three.js         │
└────────────────┬────────────────────┴──────────────┬───────────────────────┘
                 │                                  │
           ┌─────▼─────┐                    ┌──────▼────────┐
           │ SQLite DB │                    │  3D Museum    │
           │ games.db  │                    │  Canvas/Three │
           └───────────┘                    │  Carousel Viz │
                                            └───────────────┘
                 │                                  │
                 └──────────────────┬───────────────┘
                                   │
                          /api/* endpoints
                       (JSON REST responses)
```

**Two Dev Servers (launch.json):**
1. **gog-app** — Flask backend on port 5000 (data, APIs)
2. **museum-dev** — Vite dev server on port 5173 (3D UI, React build)

---

## Key Components

### 1. **Database Layer** (`schema.sql`, `games.db`)

SQLite database with 4 main tables:

#### **games** (primary table)
- `id` — unique game ID
- `gog_id` — version/build number from folder naming (user's own, not GOG's catalog ID)
- `gog_catalog_id` — actual GOG product ID (looked up from GOG's public catalog)
- `platform` — one of: `gog`, `steam`, `ps3`, `ps4`
- `title` — game name (editable)
- `size_bytes` — total folder size in bytes
- `folder_path` — where the game files live on disk (optional, for uninstalled backups)
- `exe_path` — direct path to launch executable (for Play button)
- `status` — one of: `backlog`, `playing`, `completed`, `abandoned`
- `rating` — 1-10 star rating (user's own)
- `notes` — freeform text notes
- `tags` — comma-separated user tags
- `cover_url` — path to cover art image
- `hero_url` — wide banner art for detail modal
- `genres`, `description`, `developer`, `release_date` — enrichment metadata
- `latest_build` — newest known GOG build ID (from version checking)
- `case_color` — auto-detected dominant color from cover (for visual shelf effect)
- `case_color_override` — manual color override

#### **bonus_content**
- Tracks DLC, patches, and extras
- Linked to parent game by title matching

#### **game_screenshots**
- Local screenshot paths for each game

#### **deleted_games**
- Soft-delete archive (keeps data for restore, only purges oldest beyond limit)

---

### 2. **Backend** (Python + Flask)

#### **app.py** — Main server (929 lines)
REST API endpoints for:

**Games CRUD:**
- `GET /api/games` — list all games with filtering/sorting
- `POST /api/games` — add new game (auto-fetches cover art)
- `PATCH /api/games/<id>` — update game fields
- `DELETE /api/games/<id>` — soft-delete game

**Game Actions:**
- `POST /api/games/<id>/play` — launch game executable
- `POST /api/games/<id>/open_folder` — open folder in explorer
- `GET /api/games/<id>/bonus` — list DLC/patches
- `GET /api/games/<id>/screenshots` — list screenshots

**Stats & Analytics:**
- `GET /api/stats` — per-platform counts, status breakdown
- `GET /api/dashboard` — cross-shelf overview (totals, recent, top-rated)
- `GET /api/dashboard/insights` — histograms (size distribution, ratings, monthly activity)
- `GET /api/build_status` — GOG version checking (up-to-date vs outdated)

**Cover Art & Enrichment:**
- Auto-fetches from SteamGridDB (requires API key) or GOG's public catalog
- Extracts dominant color from cover for visual shelf styling
- Falls back gracefully if services unavailable

**Settings:**
- `GET/POST /api/settings/steamgriddb_key` — manage SteamGridDB API key

**Export/Import:**
- `GET /api/export/gamelist` — export library as text gamelist
- `POST /api/build_status/upload` — upload gamelist.txt to check for updates

**Page Routes:**
- `/` → GOG Shelf
- `/steam`, `/ps3`, `/ps4` → platform-specific views
- `/dashboard` → analytics overview
- `/settings` → configuration page
- `/museum` → 3D museum view (React/Three.js, optional)

**Key Functions:**
- `dominant_color()` — PIL-based image analysis (resize to 64×64, quantize, find most common color)
- `calculate_folder_size()` — recursively sum directory sizes
- `apply_title()` — resolve ambiguous titles by fetching from SteamGridDB/GOG APIs
- `verify_gog_id()` — look up real GOG catalog ID and fetch metadata
- `serialize_game()` — convert DB row to JSON with human-readable sizes, tags array

---

#### **parse_gog.py** — GOG folder list parser
Converts raw folder-listing text (e.g., `du -sh * > gog.txt`) into `games.json`:

```
Input:  5.2G    Cyberpunk.2077.Game-(2.21)
Output: { "title": "Cyberpunk 2077", "size_bytes": 5368709120, "gog_id": "2.21" }
```

**Handles:**
- UTF-16 and UTF-8 encoding (auto-detected)
- Size parsing (K/M/G/T units)
- GOG build ID extraction from folder names: `-(57222)`, `-(74575)(1)`
- Platform suffix cleanup: `_windows_gog_`, `_game_windows_gog_`
- Title case normalization with special rules (Roman numerals, acronyms like "GOTY", "DLC")
- Duplicate detection: same GOG ID or cleaned title → merged, keeping largest size
- Categorization: games vs. extras vs. patches

---

#### **load_db.py** — Database loader
Loads parsed JSON into `games.db`:
- Upserts by `gog_id` (primary) or title (fallback) — no duplicates
- Refreshes sizes and raw paths, **preserves** user edits (status, rating, notes, tags)
- Links bonus content to games by title matching
- Safe to re-run after parsing new lists

```bash
python3 parse_gog.py gog.txt second_list.txt -o games.json
python3 load_db.py games.json --db games.db  # merge into existing DB
```

---

#### **Supporting Modules:**

**gog_catalog.py** — GOG public catalog API
- Fetches metadata (title, cover, description, release year, rating) from `api.gog.com/products/{id}`
- Used as fallback when SteamGridDB unavailable

**steamgriddb.py** — SteamGridDB API integration
- Fetches cover art and hero banners by game title or exact ID
- Requires user-provided API key (free signup at steamgriddb.com)
- Supports Steam official art fetch

**enrich.py**, **enrich_steamgriddb.py**, **enrich_story.py** — Metadata enrichment
- Optional scripts to backfill cover art, descriptions, and screenshots across library
- Run once per library or when adding new games

**check_latest_builds.py** — GOG version checking
- Compares current build IDs against a gamelist.txt snapshot
- Identifies outdated installations vs. up-to-date releases

---

### 3. **Frontend — Two Tiers**

#### **Primary: 3D Museum (React + Three.js)**
The main experience is a fully-featured React application built with Vite, rendering a custom 3D carousel using Three.js for the WebGL visualization.

**Architecture:**
- **Vite** — dev server with HMR (hot module reloading), builds to `frontend/dist/`
- **React 19** — component-based UI with Suspense for async data
- **Three.js** — WebGL rendering engine
- **@react-three/fiber** — React renderer for Three.js (renders React components to 3D)
- **@react-three/drei** — Three.js helpers (useTexture, OrbitControls, etc.)
- **@react-three/postprocessing** — post-FX (depth of field, bloom)
- **Framer Motion** — smooth spring animations for carousel movement
- **Tailwind CSS** — utility-first styling for UI overlay

**Main Components:**

**App.tsx** (74 lines) — Root component
- Fetches games from `/api/games?platform={platform}`
- Manages carousel focus state via `useCarouselFocus` hook
- Renders 3D Museum + UI Overlay
- Keyboard controls: Arrow keys to navigate, Escape to exit back to shelf
- Platform selector via URL params (`?platform=gog|steam|ps3|ps4`)

**Museum.tsx** (47 lines) — 3D Scene Manager
- Sets up Three.js Canvas with camera positioned at [0, 0, 5.4]
- FOV 36° (default), antialiasing enabled
- Dark background: `#05050a`
- Renders game cards in a carousel arc
- Professional lighting setup
- Post-processing effects (depth of field, subtle bloom)

**CoverCard.tsx** (121 lines) — Individual Game Cover
The visual centerpiece of the 3D experience. Each game is a textured plane floating in 3D space.

**Key Features:**
- **Carousel Arc**: Games positioned on a virtual circle arc, with adjustable radius (3.4 units)
- **Smooth Spring Animation**: Uses Framer Motion to animate index position continuously
- **Scale Interpolation**: Center card is 1.0x scale, gradually shrinks (1.0 → 0.82 → 0.7 → 0.55) with distance
- **Rotation Interpolation**: Each card tilts slightly (0° → 10° → 14° → 18°) to face the focus point
- **Elevation**: Focused card lifts slightly higher (invisible pedestal, no geometry)
- **Opacity Falloff**: Focused card at 100% opacity, non-focused at 70%, with smooth easing
- **Brightness Modulation**: Focused card at 100% brightness, others dimmed to 80%
- **Texture Loading**: Async texture fetch via useTexture, fallback placeholder with case color while loading
- **Material Properties**: roughness 0.4, metalness 0.05 for subtle reflectivity

**Visual Constants:**
```
ANGLE_STEP = 0.34 radians      (spacing between cards on arc)
RADIUS = 3.4 units              (arc radius)
MAX_VISIBLE_OFFSET = 6.5        (fade out beyond 6.5 steps)
ELEVATION = 0.22 units          (lift height at center)
```

**Lighting.tsx** (26 lines) — Scene Lighting
Professional lighting setup:
- Key light (main)
- Fill light (soften shadows)
- Back light (rim)
- Ambient light for base visibility

**PostFX.tsx** (13 lines) — Post-Processing Effects
- Depth of field (camera focus blur)
- Bloom (glow on bright areas)
- Noise (subtle film grain)

**Overlay.tsx** (84 lines) — UI Layer
Rendered on top of the 3D scene (not in Three.js):
- Current game info display
- Navigation buttons (← / →)
- Hints/controls legend
- Exit button (back to shelf)
- Game detail modal (expandable)
- Screenshot lightbox (click cover to view full-res)

**Hooks:**
- **useCarouselFocus** (36 lines) — Spring animation state
  - Tracks current index and animated progress value
  - `move(delta)` to navigate
  - Framer Motion spring for smooth interpolation

---

#### **Secondary: Static Shelf (HTML/CSS/JavaScript)**
Fallback interface served by Flask (legacy, but still functional). Single-page app with no build step.

#### **index.html** — Main GOG shelf view
- Grid layout of games as book-spine-styled tiles
- Each tile:
  - Cover art (if available)
  - Title
  - Dominant case color (from cover analysis)
  - Status badge (backlog/playing/completed/abandoned)
  - Rating stars
- Sidebar with platform tabs (GOG/Steam/PS3/PS4)
- Search bar with fuzzy matching (ignores punctuation: "stalker" finds "S.T.A.L.K.E.R.")
- Status filter tabs (Backlog/Playing/Completed/Abandoned)
- Sort options: title, size, rating, recently added, missing folders
- Floating "+Add Game", "🗑 Trash", "🔎 Search All", "🎮 Big Picture" buttons

#### **app.js** — Main frontend logic
- Loads games from `/api/games` endpoint
- Renders grid of game cards
- Modal interface for editing individual games:
  - Inline title edit with auto-title-resolution (fetches cover art)
  - Drag-and-drop cover upload
  - Status selector
  - 1-10 star rating
  - Notes textarea
  - Tag comma-separated list
  - GOG ID display (read-only)
  - Folder path picker with auto-size calculation
  - Exe path picker with auto-launch capability
- Search filtering with normalization (non-alphanumeric stripping)
- Trash restoration (soft-delete recovery)

#### **dashboard.html + dashboard.js** — Analytics dashboard
- Overall stats: total games, total storage, games by status
- Per-platform breakdown
- Top 5 rated games
- Largest games
- Recently added
- Histograms:
  - Library size distribution (bucketed: <1G, 1-5G, 5-15G, etc.)
  - Rating distribution (1-5 stars)
  - Games added per month (last 12 months)
- Build status dashboard (GOG only):
  - Up-to-date / outdated / unverified breakdown
  - List of outdated games with update recommendations
  - Upload gamelist.txt to refresh version info

#### **settings.html + settings.js** — Settings panel
- SteamGridDB API key configuration
- API key source display (environment variable vs. saved file)

#### **steam.html, ps3.html, ps4.html** — Platform-specific views
- Same UI as GOG shelf, filtered by platform
- PS3/PS4 have no version checking or executable launching

#### **style.css** — Responsive design
- Dark theme by default
- Sidebar navigation
- Grid layout with 6-column shelf view
- Modal overlay for game details
- Big Picture mode: full-screen 3D bookshelf with gamepad navigation

---

## Data Flow

### **Initial Setup**
```
1. User runs: du -sh * > gog.txt  (on their GOG install folder)
2. python3 parse_gog.py gog.txt -o games.json  (normalize & extract metadata)
3. python3 load_db.py games.json --db games.db  (populate database)
4. python3 app.py  (start Flask server)
5. Open http://127.0.0.1:5000  (browse shelf in browser)
```

### **Adding a New Game**
```
1. User clicks "+ Add Game"
2. Types title in modal
3. Frontend calls POST /api/games { title, platform }
4. Backend:
   a. Inserts into games table
   b. Calls apply_title() → fetches cover from SteamGridDB or GOG
   c. Calculates dominant_color() from cover
   d. Calls verify_gog_id() → looks up real GOG product ID + metadata
5. Game appears on shelf with cover art and auto-colored tile

```

### **User Edits**
```
1. Click game card → modal opens
2. Edit field (title, status, rating, notes, tags, folder, exe)
3. Save → PATCH /api/games/<id>
4. Backend:
   a. Validates (folder exists, exe is file, status is valid, rating 1-10)
   b. If folder set: auto-calculate size_bytes
   c. If title changed: re-fetch cover art
   d. If folder empty: nullify exe_path
   e. Write to database
5. Reload grid display

```

### **Search & Filter**
```
Normalize search:
- Lowercase
- Strip all non-alphanumeric chars
- Example: "S.T.A.L.K.E.R." → "stalker" ✓ matches "stalker" search

Filter chain:
1. Platform (gog/steam/ps3/ps4)
2. Status (backlog/playing/completed/abandoned)
3. Tag (substring match in comma-list)
4. Sort (title/size/rating/added/missing)
5. Search (normalized substring)
```

---

## Notable Design Decisions

### **Soft Deletes**
Games aren't permanently destroyed — they're archived in `deleted_games` table with full row copy. Only oldest entries beyond `DELETED_GAMES_LIMIT` (50) are purged. Cover/hero images left on disk for restore.

### **GOG ID ≠ Catalog ID**
- `gog_id` = version/build number from user's folder naming (e.g., "2.21" from folder "Cyberpunk.2077-(2.21)")
- `gog_catalog_id` = real GOG product ID (looked up from `api.gog.com`)
- Two separate fields because folder schemes sometimes reuse numbers and aren't authoritative.

### **No Destructive Export**
User edits (status, rating, notes, tags) are never touched by reimport. Size/title refresh only if changed.

### **Graceful Fallback**
If SteamGridDB key missing or API fails, falls back to GOG's public catalog. If both unavailable, game still saves (just no cover art). Philosophy: better incomplete than broken.

### **Cover Art Color Extraction**
Images resized to 64×64, quantized down to 6 colors, then the dominant color extracted. This avoids losing to small-area high-contrast elements like logos.

### **Responsive Platform Design**
- GOG/Steam get full features (executable launch, version checking)
- PS3/PS4 get simplified view (folder-linked only, no launchers)
- All share same core search/filter/edit UI

---

## File Structure

```
GameShelf/
│
├── backend/                          # Python Flask API server
│   ├── app.py                        # Main REST API (929 lines)
│   ├── games.db                      # SQLite database (user data)
│   ├── schema.sql                    # Database schema
│   ├── parse_gog.py                  # Parse GOG folder listings → JSON
│   ├── parse_steam.py                # Parse Steam folder listings
│   ├── parse_ps3.py                  # Parse PS3 folder listings
│   ├── load_db.py                    # Load JSON into SQLite
│   ├── gog_catalog.py                # GOG public API client
│   ├── steamgriddb.py                # SteamGridDB API client
│   ├── enrich.py                     # Metadata enrichment (covers, metadata)
│   ├── enrich_steamgriddb.py         # SteamGridDB-specific enrichment
│   ├── enrich_story.py               # Screenshot/story enrichment
│   ├── check_latest_builds.py        # GOG version checking
│   ├── launcher.py                   # Game launching utility
│   ├── build.py                      # PyInstaller build script
│   ├── assign_case_colors.py         # Batch dominant color extraction
│   ├── cover_overrides.json          # Manual cover art overrides
│   ├── requirements.txt              # Python dependencies
│   ├── static/                       # Legacy static assets (fallback UI)
│   │   ├── index.html                # GOG shelf UI
│   │   ├── steam.html, ps3.html, ps4.html  # Platform views
│   │   ├── dashboard.html            # Analytics dashboard
│   │   ├── settings.html             # Settings page
│   │   ├── app.js, dashboard.js, settings.js
│   │   ├── style.css                 # Styling
│   │   ├── covers/                   # Downloaded cover images
│   │   ├── heroes/                   # Hero banner images
│   │   ├── screenshots/              # Game screenshots
│   │   └── museum/                   # Built React app (dist output)
│   └── .gitignore
│
├── frontend/                         # React + Three.js 3D Museum (PRIMARY UI)
│   ├── src/
│   │   ├── App.tsx                   # Root component (carousel control)
│   │   ├── main.tsx                  # React entry point
│   │   ├── api.ts                    # API client helper
│   │   ├── types.ts                  # TypeScript interfaces
│   │   ├── index.css                 # Global styles
│   │   ├── components/
│   │   │   ├── Museum.tsx            # 3D scene renderer (Canvas setup)
│   │   │   ├── ui/
│   │   │   │   └── Overlay.tsx       # UI overlay (info, controls, detail modal)
│   │   │   └── scene/
│   │   │       ├── CoverCard.tsx     # Individual 3D game cover (plane geometry)
│   │   │       ├── Lighting.tsx      # Scene lighting (key/fill/back/ambient)
│   │   │       └── PostFX.tsx        # Post-processing (depth of field, bloom)
│   │   └── hooks/
│   │       └── useCarouselFocus.ts   # Spring animation state (Framer Motion)
│   ├── index.html                    # Vite entry point
│   ├── package.json                  # Dependencies (React, Three, Vite, Tailwind)
│   ├── tsconfig.json                 # TypeScript config
│   ├── vite.config.ts                # Vite build config
│   ├── tailwind.config.js            # Tailwind CSS config
│   ├── public/
│   │   └── favicon.svg
│   ├── dist/                         # Built output (npm run build)
│   └── node_modules/                 # npm packages
│
├── .claude/
│   └── launch.json                   # Claude Code dev server config
├── launch.json                       # VSCode dev server config (TWO SERVERS)
├── .vscode/
│   └── settings.json
│
├── Documentation/
│   ├── README.md                     # Main project overview
│   ├── README_GITHUB.md              # GitHub setup guide
│   ├── BUILDING.md                   # Build & packaging instructions
│   ├── EDITING_GUIDE.md              # Code editing guide
│   ├── SETUP_GUIDE.md                # Initial setup
│   ├── MANIFEST.md                   # Feature manifest
│   ├── START_HERE.txt                # Quick start guide
│   ├── FILE_TREE.txt                 # File structure reference
│   ├── GITHUB_SETUP_COMPLETE.md      # Post-GitHub setup notes
│   └── CODEBASE_OVERVIEW.md          # This document
│
└── .gitignore
```

---

## Key Technologies

| Layer | Tech | Version/Purpose |
|-------|------|-----------------|
| **Backend** | Python 3 | Main language |
| | Flask | Web server + REST API |
| | SQLite 3 | Local data persistence |
| | Pillow (PIL) | Image processing (dominant color extraction) |
| | requests | HTTP client (API calls to GOG/SteamGridDB) |
| **Frontend - 3D** | React | 19.2.7 — component framework |
| | Three.js | 0.185.1 — WebGL rendering |
| | @react-three/fiber | 9.6.1 — React renderer for Three.js |
| | @react-three/drei | 10.7.7 — Three.js helpers/utilities |
| | @react-three/postprocessing | 3.0.4 — depth of field, bloom effects |
| | Framer Motion | 12.42.2 — spring animation library |
| | Tailwind CSS | 4.3.3 — utility-first styling |
| **Frontend - Build** | Vite | 8.1.1 — dev server + build tool |
| | TypeScript | ~6.0.2 — type safety |
| | Oxlint | 1.71.0 — linter |
| **Frontend - Legacy** | HTML5/CSS3 | Fallback static shelf UI |
| | Vanilla JS | Query selectors, fetch API |
| **Deployment** | PyInstaller | Optional executable packaging |
| **Dev Tools** | npm | Package management |
| | Vite dev server | HMR for React/Three.js development |

---

## What You Can Do With This

### 3D Museum Interface (Primary)
1. **3D Game Carousel** — Browse library with smooth spring-animated carousel of game covers
2. **Smooth Navigation** — Arrow keys to navigate, spring physics for organic motion
3. **Beautiful Lighting** — Professional key/fill/back/rim lighting with depth effects
4. **Game Info Overlay** — Current selection info, ratings, tags, status displayed on-screen
5. **Detail Modal** — Click to expand full game details (notes, folders, artwork)
6. **Screenshot Lightbox** — View game screenshots in full-screen with left/right navigation
7. **Per-Platform Views** — Separate 3D carousel for GOG/Steam/PS3/PS4

### Catalog Management (Shared)
8. **Catalog Your Library** — Organize GOG/Steam/PS3/PS4 collections in one place
9. **Track Playstyle** — backlog/playing/completed/abandoned status
10. **Rate Games** — Personal 1-10 ratings
11. **Take Notes** — Freeform text per game (personal reviews, tips, strategies)
12. **Tag Games** — Custom comma-separated tags for organization
13. **Search & Filter** — Fuzzy search (ignores punctuation), filter by platform/status/tags
14. **Launch Games** — "Play" button directly executes games (if exe path set)

### Admin & Maintenance
15. **Check Updates** — GOG version/build comparison against official gamelist.txt
16. **Analytics Dashboard** — Library stats, size distribution, activity timeline
17. **Soft-Delete Recovery** — Trash bin with restore functionality (keeps data for recovery)
18. **Cover Art Sync** — Auto-fetch from SteamGridDB or GOG catalog
19. **Metadata Enrichment** — Grab descriptions, genres, release dates, screenshots

---

## Typical Workflow

### Initial Setup (Data Import)
1. Export folder listing from your GOG install: `du -sh * > gog.txt`
2. Parse it: `python3 backend/parse_gog.py gog.txt -o games.json`
3. Load into DB: `python3 backend/load_db.py games.json --db backend/games.db`
4. (Optional) Enrich metadata: `python3 backend/enrich.py --db backend/games.db`

### Development Mode (Two Dev Servers)
Using Claude Code, VSCode, or manually:

**Terminal 1 — Flask API (port 5000):**
```bash
cd backend
python3 app.py
```

**Terminal 2 — Vite dev server (port 5173):**
```bash
cd frontend
npm install
npm run dev -- --host
```

Then open your browser:
- **http://localhost:5173** — 3D Museum (primary interface, HMR enabled)
- **http://localhost:5000** — Static Shelf (fallback)

### Production Build
```bash
cd frontend
npm run build              # Creates dist/ with optimized bundle
# Then serve dist/ via Flask static routes
```

### Daily Usage
1. Browse library in 3D museum (arrow keys to navigate)
2. Click covers to see details, edit notes, mark status
3. Search and filter by tags/platform/status
4. Launch games directly from interface
5. Check dashboard for library stats
6. Add new games via "+ Add Game" button

### Maintenance
- Re-import updated lists: `python3 load_db.py new_list.json`
- Check for game updates: upload gamelist.txt to dashboard
- Soft-delete and restore games via trash bin

---

## Quick Git Status

**Current state:**
- **Branch**: main (up to date with origin)
- **Latest commits**:
  - `f151407` — Fix preview server autoPort configuration (launch.json)
  - `f5da673` — Initial commit: GameShelf 3D game library viewer (2.8k+ changes)

**Untracked files** (generated during dev):
- `.claude/` — Claude Code settings
- `backend/*.py` — Enrichment and utility scripts
- Various setup/guide markdown files

---

## Development Architecture Notes

### Why Two Dev Servers?
- **Flask (port 5000)** — REST API + data management, runs continuously
- **Vite (port 5173)** — React dev server with HMR, rebuilds TypeScript/CSS instantly
- Frontend calls Flask API via `fetch()` requests to `http://localhost:5000/api/*`

### Build & Deployment
- **Dev**: Both servers running side-by-side (Vite + Flask)
- **Production**: `npm run build` creates `/frontend/dist/`, served by Flask static routes
- **Packaging**: PyInstaller bundle includes both backend and built frontend

### Performance Optimizations
- Lazy texture loading (three.js useTexture with Suspense)
- Opacity/brightness modulation to reduce draw calls on non-focused cards
- Spring physics (Framer Motion) instead of per-frame tweening
- Vite tree-shaking removes unused Three.js features

---

**No cloud. No accounts. Just your data, locally. With stunning 3D visualization.**


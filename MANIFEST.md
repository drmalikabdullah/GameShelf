# The Shelf - 3D Game Library Viewer

## Complete File Structure & Purpose

This folder contains **everything needed** to build and run the Shelf program - a cross-platform 3D game library viewer with a React + Three.js frontend and Python Flask backend.

---

## BACKEND (Python Flask Server)

### Core Application
- **`backend/app.py`** — Main Flask web server. Serves the API endpoints (`/api/games`, `/api/settings/*`), handles the SQLite database, and serves static files including the built React app at `/museum`.

### Database & Schema
- **`backend/schema.sql`** — SQLite database schema. Auto-created on first launch if `games.db` doesn't exist. Defines the games table with all columns (title, platform, status, cover_url, etc.).

### External Data
- **`backend/gog_catalog.py`** — GOG database integration. Fetches free cover art from GOG's public catalog when SteamGridDB API key is unavailable. No external dependencies beyond standard `requests` library.
- **`backend/cover_overrides.json`** — Per-game manual color overrides for case styling. Can be empty on first run.

### Build & Distribution
- **`backend/build.py`** — PyInstaller packaging script. Rebuilds the museum frontend automatically (`npm run build`), bundles Python + Flask + static assets into `dist/`, and produces `GameShelf.exe` (Windows) or native binary (Linux/macOS). Supports `--fresh` flag for clean distribution to friends.

---

## FRONTEND (React 19 + Vite + TypeScript)

### Configuration
- **`frontend/package.json`** — NPM dependencies. Lists React, Three.js, Framer Motion, TailwindCSS, Vite, TypeScript, and all R3F ecosystem libraries.
- **`frontend/vite.config.ts`** — Vite build config. Sets base path to `/museum/`, proxies `/api/*` calls to Flask dev server (:5000), outputs compiled bundle to `../static/museum/`.
- **`frontend/tsconfig.json`** — TypeScript compiler config.
- **`frontend/index.html`** — HTML entry point. Loads `src/main.tsx` and renders into `<div id="root">`.

### Styling & Entry
- **`frontend/src/index.css`** — Global CSS (TailwindCSS imports) + minimal setup (full-height body, dark background `#05050a`).
- **`frontend/src/main.tsx`** — React root. Creates React 19 root and mounts `<App>`.

### Core Application Logic
- **`frontend/src/App.tsx`** — Main React component. Fetches game list from `/api/games`, manages carousel focus state, wires up keyboard controls (arrows/ESC), renders the 3D `<Museum>` scene and overlay UI.
- **`frontend/src/types.ts`** — TypeScript `Game` interface matching the backend's SQLite schema.
- **`frontend/src/api.ts`** — HTTP client. `fetchGames(platform)` queries `/api/games` and `coverUrl(game)` constructs cacheable image URLs.

### 3D Scene (Three.js + React Three Fiber)
- **`frontend/src/components/Museum.tsx`** — Canvas setup. Initializes R3F with camera/lighting/games, syncs Framer Motion `progress` value to cover positions every frame, renders `<PostFX>`.
- **`frontend/src/components/scene/CoverCard.tsx`** — Individual game cover plane. Reads spring-animated `progress` offset every frame, positions/scales/rotates each cover along the arc, applies opacity & brightness based on distance from focus.
- **`frontend/src/components/scene/Lighting.tsx`** — Three core lights: warm spotlight from above, cool point light from behind (rim), soft ambient fill. All native Three.js primitives — no visible geometry.
- **`frontend/src/components/scene/PostFX.tsx`** — Post-processing (EffectComposer). Adds subtle depth-of-field blur (~1px) so non-focused covers read slightly soft.

### UI Overlay
- **`frontend/src/components/ui/Overlay.tsx`** — Framer Motion-animated HUD. Title/metadata, exit button, prev/next buttons, keyboard hints. Positioned absolutely over the canvas.

### State Management
- **`frontend/src/hooks/useCarouselFocus.ts`** — Custom hook. Manages carousel index (React state, instant UI updates) and spring-animated `progress` (drives 3D scene every frame). Decouples text updates from geometry easing.

### Assets
- **`frontend/public/favicon.svg`** — Browser tab icon.

---

## Build & Run

### Development
```bash
# Terminal 1: Backend
cd backend
python app.py  # Runs on :5000

# Terminal 2: Frontend (in background, or in another terminal)
cd frontend
npm install    # First time only
npm run dev    # Runs on :5173, proxies /api to :5000
```
Then open `http://localhost:5173/museum/` in a browser.

### Production Build
```bash
cd frontend
npm run build   # Outputs to ../static/museum/

# Then from project root:
python build.py         # Packages Windows exe
python build.py --fresh # Clean distribution for friends
```

---

## Required (Already Installed via npm/pip)

**Frontend:**
- React 19, React DOM 19
- Three.js + @react-three/fiber + @react-three/drei + @react-three/postprocessing
- Framer Motion (spring animations)
- TailwindCSS 4 (Vite plugin)
- Vite 8, TypeScript

**Backend:**
- Flask (web framework)
- SQLite3 (database, built into Python)
- PyInstaller (for binary builds only)
- Pillow (image processing, if using color quantization)

---

## Key Design Decisions

1. **No Game Cases / Pedestals / Shelves** — Only floating game cover planes in space, lit by 3 lights. Minimal scene.

2. **Spring-Animated Carousel** — Hand-rolled 3D coverflow (not a library), scale/rotation/position driven by spring-animated `progress` value every frame.

3. **Exact Scale Steps** — Center 1.0, next 0.82, next 0.70, next 0.55 (interpolated continuously).

4. **Exact Rotation Steps** — Center 0°, next 10°, next 14°, next 18° (interpolated continuously).

5. **Opacity & Brightness** — Non-focused covers: 70% opacity, 80% brightness (eased smoothly from focused 100%/100%).

6. **No Visible Light Cones** — All lighting via native Three.js primitives (spotLight, pointLight, ambientLight), no volumetric/beam geometry.

7. **Subtle DoF Blur** — Focused cover stays sharp; adjacent covers get ~1px blur via `@react-three/postprocessing`.

8. **Cross-Platform Distribution** — PyInstaller builds native binaries for Windows/Linux/macOS. `--fresh` flag excludes personal data (games.db, API keys, cover art) so friends start with a clean slate.

---

## Files Summary

**Total files:** ~20 core source files
**Backend:** 5 Python files
**Frontend:** 15 TypeScript/React files + 1 HTML + 2 configs

This is **the complete, minimal set** needed to run the 3D shelf. No extra scaffolding, no unused files.

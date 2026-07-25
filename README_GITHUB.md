# GameShelf

A premium 3D game library viewer inspired by PlayStation 5's visual language. Browse your game collection in a beautifully lit 3D environment with smooth carousel navigation.

## Features

✨ **3D Carousel Display**
- Hand-rolled 3D coverflow (no carousel libraries)
- Spring-animated transitions between games
- Precise scale & rotation steps for each position
- Floating game covers in space with dynamic lighting

🎨 **Professional Rendering**
- Custom Three.js scene with three-light setup:
  - Warm spotlight from above
  - Cool rim light from behind
  - Soft ambient fill
- Subtle depth-of-field blur on non-focused covers
- 70% opacity & 80% brightness for side covers
- Almost-black background (#05050a)

⌨️ **Intuitive Controls**
- Arrow keys to navigate carousel
- ESC to exit
- Smooth spring-animated movement

💾 **Cross-Platform**
- Python Flask backend with SQLite database
- React 19 + TypeScript + Vite frontend
- PyInstaller packaging for Windows/Linux/macOS
- Double-click to run, no terminal needed

🎮 **Game Library Management**
- Add games from your library
- Auto-detect cover art from SteamGridDB (with API key)
- Fallback to free GOG catalog covers
- Organize by platform (GOG, Steam, PS3, PS4)
- Color-coded status indicators

## Tech Stack

**Backend:**
- Python 3
- Flask (web server & API)
- SQLite3 (database)

**Frontend:**
- React 19
- TypeScript
- Three.js + React Three Fiber
- Framer Motion (spring animations)
- TailwindCSS 4
- Vite (build tool)

## Getting Started

### Development Mode

**Terminal 1 - Backend:**
```bash
cd backend
python app.py
# Server runs on http://localhost:5000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install        # First time only
npm run dev        # Dev server on http://localhost:5173
```

Then open: `http://localhost:5173/museum/`

### Production Build

```bash
cd frontend
npm run build      # Compiles to ../static/museum/

cd ..
python build.py            # Package for your system
python build.py --fresh    # Clean distribution for others
```

Result: `dist/GameShelf.exe` (Windows) or native binary (Linux/macOS)

## Project Structure

```
GameShelf/
├── backend/               # Python Flask server
│   ├── app.py            # Main application
│   ├── schema.sql        # Database schema
│   ├── gog_catalog.py    # Cover art fetcher
│   ├── build.py          # PyInstaller packaging
│   └── games.db          # Game library (not in git)
│
├── frontend/             # React + Three.js app
│   ├── src/
│   │   ├── App.tsx       # Main component
│   │   ├── components/
│   │   │   ├── Museum.tsx         # 3D scene
│   │   │   ├── scene/
│   │   │   │   ├── CoverCard.tsx  # Game covers
│   │   │   │   ├── Lighting.tsx   # Lights
│   │   │   │   └── PostFX.tsx     # Effects
│   │   │   └── ui/
│   │   │       └── Overlay.tsx    # HUD
│   │   └── hooks/
│   │       └── useCarouselFocus.ts # Carousel state
│   └── package.json
│
├── MANIFEST.md           # Complete file guide
├── EDITING_GUIDE.md      # Which file to edit for what
└── START_HERE.txt        # Quick start guide
```

## Configuration

### Adding Your Game Library

1. Place your `games.db` in `backend/` folder
2. Add your `steamgriddb_key.txt` (optional) for better cover art
3. Run `python app.py`

### SteamGridDB API Key

Get a free API key from https://www.steamgriddb.com/profile/preferences/api

Add it to `backend/steamgriddb_key.txt`:
```
your-api-key-here
```

Without it, the app automatically falls back to free GOG catalog covers.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `←` / `→` | Navigate carousel |
| `ESC` | Exit to shelf |

## Documentation

- **`MANIFEST.md`** — Full breakdown of every file and its purpose
- **`EDITING_GUIDE.md`** — Quick reference for customizing the app
- **`BUILDING.md`** — Detailed build & packaging instructions
- **`START_HERE.txt`** — Quick orientation guide

## Development Notes

### Carousel Configuration

Edit `frontend/src/components/scene/CoverCard.tsx`:
- **Scale steps**: Lines 15-20
- **Rotation angles**: Lines 41-46
- **Opacity/brightness**: Lines 98-109

### Lighting

Edit `frontend/src/components/scene/Lighting.tsx`:
- Adjust light positions, colors, intensities
- Add or remove lights
- Change shadow settings

### UI/HUD

Edit `frontend/src/components/ui/Overlay.tsx`:
- Modify title, metadata display
- Change button styling
- Update keyboard hints

## Performance

Target: 60+ FPS on modern hardware

- Minimal geometry (flat planes only)
- Efficient lighting setup (3 lights)
- Subtle depth-of-field (no expensive bloom/vignette stack)
- Spring animations via Framer Motion (GPU-accelerated)

## Future Enhancements

- [ ] PS5-style background (radial gradient, warm tone, noise, vignette)
- [ ] Game details panel with descriptions & screenshots
- [ ] Search & filter functionality
- [ ] Custom cover art management
- [ ] Achievements & statistics
- [ ] Multiplayer share feature

## License

No license specified. Personal project.

## Author

Made by [@drmalikabdullah](https://github.com/drmalikabdullah)

---

**Ready to explore your game library in 3D?** Clone this repo and follow the Getting Started guide!

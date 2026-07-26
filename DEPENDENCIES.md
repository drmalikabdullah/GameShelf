# GameShelf Dependencies Reference

Complete breakdown of all required and optional dependencies for running and developing GameShelf.

---

## Runtime Dependencies

### Python Backend

All dependencies must be installed via `pip install -r backend/requirements.txt`

#### Required

```
flask           # Web server and REST API framework
                # Version: 3.1+
                # Purpose: Serves API endpoints, static files, page routes
                # Used by: app.py

Pillow          # Python Imaging Library (PIL) - image processing
                # Version: 10.0+
                # Purpose: dominant_color() function for extracting cover art colors
                # Used by: app.py (dominant_color), enrich.py, assign_case_colors.py
```

#### Optional

```
pywebview       # Embedded WebView for desktop mode
                # Version: 4.0+
                # Purpose: Run app in native window instead of browser
                # Used by: launcher.py (if desktop mode enabled)

pyinstaller     # Package Python app as standalone executable
                # Version: 6.0+
                # Purpose: Build Windows .exe, Linux/macOS binary
                # Used by: build.py (only needed for distribution)
```

#### Built-in (No install needed)

```
sqlite3         # SQLite database driver
                # Version: Built into Python 3.8+
                # Purpose: Database operations

requests        # HTTP client library
                # Version: Built-in to most Python distributions
                # Purpose: API calls to GOG/SteamGridDB
                # Note: May need pip install requests on minimal Python installations

json            # JSON encoding/decoding (stdlib)
os              # Operating system interfaces (stdlib)
sys             # System-specific parameters (stdlib)
re              # Regular expressions (stdlib)
pathlib         # Path operations (stdlib)
datetime        # Date/time handling (stdlib)
subprocess      # Process spawning (stdlib)
```

### External APIs (Optional, Free)

#### GOG Catalog API

- **Endpoint:** `https://api.gog.com/products/{product_id}`
- **Authentication:** None required (public API)
- **Rate limit:** Reasonable per-second (no official documentation)
- **Used by:**
  - `gog_catalog.py` — fetch metadata
  - `enrich.py` — backfill cover art
  - `app.py` `verify_gog_id()` — lookup GOG product ID
- **Fallback:** Yes, used if SteamGridDB unavailable

#### SteamGridDB API

- **Endpoint:** `https://www.steamgriddb.com/api/v2/...`
- **Authentication:** API key (free tier available at https://www.steamgriddb.com/)
- **Rate limit:** 900 requests/day on free tier
- **Used by:**
  - `steamgriddb.py` — fetch high-quality cover art
  - `enrich_steamgriddb.py` — backfill covers
  - `app.py` `apply_title()` — fetch covers when adding games
- **Fallback:** No, optional enhancement

#### Steam VDF Format (No API needed)

- **Used for:** `parse_steam.py` — read libraryfolders.vdf manifest
- **Authentication:** None (local file parsing)

---

## Frontend Dependencies

### Static Shelf (Always Included)

No dependencies needed for the static HTML/CSS/JS frontend. It works in any modern browser.

```
HTML5           # Static markup (index.html, etc.)
CSS3            # Styling (style.css)
Vanilla JS      # Client-side logic (app.js, dashboard.js, settings.js)
```

Supports:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### 3D Museum (Optional, Pre-built)

Located in `static/museum/` (pre-built output, no runtime dependencies).

If you rebuild the React app from source, you'll need:

#### Required (Node.js ecosystem)

```
npm                     # Package manager for Node.js
node                    # JavaScript runtime
                        # Install from https://nodejs.org/
                        # Version: 18+ LTS recommended

react 19.2+             # Component framework
react-dom 19.2+         # React DOM renderer

three.js 0.185+         # WebGL 3D engine
@react-three/fiber 9.6+ # React renderer for Three.js
@react-three/drei 10.7+ # Three.js utilities and helpers
@react-three/postprocessing 3.0+ # Post-processing effects (DoF, bloom)

framer-motion 12.42+    # Spring animation library
tailwindcss 4.3+        # Utility-first CSS framework
```

#### Build Tools

```
vite 8.1+               # Development server and build tool
                        # Hot Module Replacement (HMR) during development
                        # Fast production bundling

typescript 6.0+         # TypeScript compiler
                        # Type safety for React + Three.js code

oxlint 1.71+            # JavaScript/TypeScript linter
```

#### Development Only

```
@types/react            # TypeScript types for React
@types/react-dom        # TypeScript types for React DOM
@types/three            # TypeScript types for Three.js
@types/node             # TypeScript types for Node.js
```

### Installation

```bash
cd frontend
npm install             # Install all dependencies from package.json
npm run dev -- --host   # Development mode with HMR
npm run build           # Production build
npm run lint            # Linting
```

---

## Build & Deployment Dependencies

### PyInstaller

Used by `build.py` to package the app as a standalone executable.

```
pyinstaller 6.0+        # CLI tool for creating standalone binaries
                        # Bundles Python, Flask, static assets into .exe (Windows)
                        # or native binary (Linux/macOS)
```

**Installation:**
```bash
pip install pyinstaller
```

**Usage:**
```bash
cd backend
python3 build.py        # Create GameShelf.exe (Windows)
python3 build.py --fresh  # Clean build without personal data
```

---

## System Requirements

### Minimum

- **OS:** Windows 7+, macOS 10.12+, Linux (any distribution)
- **Python:** 3.8+
- **RAM:** 256 MB
- **Disk:** 100 MB (plus storage for game database and cover images)
- **Browser:** Any modern browser (Chrome, Firefox, Safari, Edge)

### Recommended

- **OS:** Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)
- **Python:** 3.11+
- **RAM:** 1 GB
- **Disk:** 1 GB
- **Browser:** Chrome 120+ or Firefox 121+

### For Development

- **Python:** 3.11+
- **Node.js:** 20+ LTS
- **Git:** For version control
- **Editor:** VS Code, PyCharm, WebStorm recommended

---

## Installation Guide

### Backend Only (Static Shelf)

```bash
# Clone repository
git clone https://github.com/yourusername/GameShelf.git
cd GameShelf

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r backend/requirements.txt

# Run Flask server
cd backend
python3 app.py

# Open browser
# http://127.0.0.1:5000
```

### With Optional 3D Museum (Requires Node.js)

```bash
# Do backend setup first (above)

# Build React app (one-time)
cd frontend
npm install
npm run build

# Back to backend
cd ../backend
python3 app.py

# Then visit:
# http://127.0.0.1:5000/museum (3D Museum)
# http://127.0.0.1:5000 (Static Shelf fallback)
```

### Development Mode (Hot Reload)

```bash
# Terminal 1: Backend
cd backend
python3 app.py

# Terminal 2: Frontend with HMR
cd frontend
npm install              # First time only
npm run dev -- --host

# Open http://localhost:5173 (not :5000)
# Any changes to React code auto-reload
```

---

## Version Compatibility Matrix

### Known Working Versions

| Component | Version | Status | Notes |
|-----------|---------|--------|-------|
| Python | 3.11.7 | ✅ Tested | Recommended |
| Flask | 3.1.3 | ✅ Tested | Current stable |
| Pillow | 10.0.0+ | ✅ Tested | Image processing |
| React | 19.0+ | ✅ Tested | Latest stable |
| Three.js | 0.185+ | ✅ Tested | WebGL 2 support |
| TypeScript | 5.3+ | ✅ Tested | Type safety |
| Vite | 5.0+ | ✅ Tested | Build tool |
| Node.js | 20 LTS | ✅ Tested | Latest LTS |

### Known Issues

None currently documented. Report issues on GitHub.

---

## Optional Enhancements

### API Keys & Configuration

#### SteamGridDB API Key

1. Sign up at https://www.steamgriddb.com/
2. Get free API key (900 requests/day)
3. Set environment variable:
   ```bash
   export STEAMGRIDDB_API_KEY="your_key_here"
   ```
   Or save to `backend/cover_overrides.json`:
   ```json
   {
     "_api_key": "your_key_here"
   }
   ```

### Screenshots & Assets

Store game screenshots in `backend/static/screenshots/` for display in UI.

### Cover Art Overrides

Manual color overrides in `backend/cover_overrides.json`:

```json
{
  "42": "#FF5733",
  "100": "#3333FF"
}
```

Where key is game ID and value is hex color.

---

## Dependency Update Strategy

### Pinned Versions

`backend/requirements.txt` uses specific versions for reproducibility:

```
flask==3.1.3
Pillow==10.0.0
```

To update:
```bash
pip install --upgrade -r backend/requirements.txt
```

### Frontend Dependencies

`frontend/package.json` uses caret ranges (allows patch/minor updates):

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "three": "^0.185.0"
  }
}
```

To update:
```bash
cd frontend
npm update
```

### Checking for Outdated Dependencies

```bash
# Python
pip list --outdated

# Node.js
cd frontend
npm outdated
```

---

## Troubleshooting Dependency Issues

### Module Not Found Error

```
ModuleNotFoundError: No module named 'flask'
```

**Fix:**
```bash
pip install flask
# or
pip install -r backend/requirements.txt
```

### Import Error for Pillow

```
ImportError: cannot import name 'Image' from 'PIL'
```

**Fix:**
```bash
pip install --upgrade Pillow
```

### Cannot Connect to API

```
ConnectionError: Failed to connect to api.gog.com
```

**Cause:** Network issue or API unavailable

**Fix:**
- Check internet connection
- Verify firewall allows outbound HTTPS
- Try fallback: if using SteamGridDB, app will fallback to GOG catalog; if both unavailable, game saves without cover

### npm Install Fails

```
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
```

**Fix:**
```bash
cd frontend
npm install --legacy-peer-deps
```

### Vite Build Fails

```
Error: Transform failed with 1 error:
error: Could not resolve "@react-three/fiber"
```

**Fix:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

## Security & Licensing

### License Compliance

All dependencies are MIT, Apache 2.0, or BSD licensed. No GPL/AGPL dependencies.

```
Flask           - BSD
Pillow          - HPND
React           - MIT
Three.js        - MIT
Framer Motion   - MIT
Vite            - MIT
TypeScript      - Apache 2.0
```

### Security Audit

To check for known vulnerabilities:

```bash
# Python
pip check
pip install safety
safety check

# Node.js
cd frontend
npm audit
npm audit fix  # Auto-fix if possible
```

---

## Dependency Cleanup

### Remove Unused Packages

```bash
# Python
pip uninstall [package-name]

# Node.js
cd frontend
npm uninstall [package-name]
```

### Virtual Environment Cleanup

```bash
# Remove venv
rm -rf venv

# Recreate
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

---

## Docker & Container Support

Not currently provided. To add Docker support:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/ /app/backend/
COPY frontend/dist /app/static/museum/

RUN pip install -r backend/requirements.txt

EXPOSE 5000
CMD ["python", "backend/app.py"]
```

---

## Summary

**Minimal Setup (Static Shelf):**
- Python 3.8+
- Flask, Pillow
- 5 minutes to install

**Full Setup (3D Museum):**
- Python 3.8+, Node.js 18+
- Flask, Pillow, React, Three.js, Vite
- 10 minutes to install and build

**Optional Enhancements:**
- SteamGridDB API key (free)
- PyInstaller for distribution
- Docker for containerization

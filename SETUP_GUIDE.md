# GameShelf Setup Guide

Complete guide to getting GameShelf running on your machine from the GitHub repository.

## What You Need

- **Python 3.7+** installed on your system
- **Git** to clone the repository
- **Node.js 14+** (optional, only if you want to work on the 3D Museum view)

## Step 1: Clone the Repository

```bash
git clone https://github.com/drmalikabdullah/GameShelf.git
cd GameShelf
```

## Step 2: Set Up the Backend (Python/Flask)

The backend is a Flask REST API that serves your game library database.

### Windows

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

### macOS / Linux

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python3 app.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
```

**Keep this terminal open** — the Flask server needs to stay running.

## Step 3: Access the App

Open your browser to: **http://127.0.0.1:5000**

You should see your game library (already populated with games from `backend/games.db`).

## Step 4: (Optional) Set Up the 3D Museum Frontend

The modern 3D Museum view uses React + Three.js. To work on it:

**In a new terminal:**

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start dev server
npm run dev
```

You should see:
```
VITE v... ready in ... ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

Open **http://localhost:5173** in your browser.

The dev server automatically proxies API calls to the Flask backend on :5000.

## What You Can Do Now

### View Your Library
- Open http://127.0.0.1:5000 to browse games
- Search, filter, add notes, rate games
- All changes are saved to `backend/games.db`

### Add More Games

If you have GOG game lists (folder listings as `.txt` files):

```bash
cd backend

# Parse the list
python parse_gog.py your_game_list.txt -o games.json

# Load into database
python load_db.py games.json --db games.db
```

Then refresh your browser — new games appear automatically.

### Download Cover Art

Automatically fetch cover art from GOG:

```bash
cd backend
python enrich.py --db games.db
```

Or use SteamGridDB (more cover art sources):

```bash
cd backend

# Get a free API key at https://www.steamgriddb.com/profile/preferences/api
echo "your-api-key" > steamgriddb_key.txt

python enrich_steamgriddb.py --db games.db
```

### Add Game Stories/Descriptions

```bash
cd backend
python enrich_story.py --db games.db
```

## File Structure

```
GameShelf/
├── backend/                    # Flask REST API
│   ├── app.py                 # Main application
│   ├── games.db               # SQLite database (your game library)
│   ├── requirements.txt        # Python dependencies
│   ├── static/                # Web UI + cover art
│   │   ├── index.html         # Main interface
│   │   ├── style.css          # Styles
│   │   ├── app.js             # Frontend logic
│   │   ├── covers/            # Cover art images (auto-downloaded)
│   │   ├── heroes/            # Hero images
│   │   └── screenshots/       # Game screenshots
│   ├── schema.sql             # Database schema
│   ├── gog_catalog.py         # GOG API client
│   ├── parse_gog.py           # List parser
│   ├── load_db.py             # Database loader
│   ├── enrich.py              # Cover art downloader (GOG)
│   ├── enrich_steamgriddb.py  # Cover art downloader (SteamGridDB)
│   ├── enrich_story.py        # Game descriptions
│   └── steamgriddb.py         # SteamGridDB API client
│
├── frontend/                   # React 3D Museum (optional)
│   ├── src/                   # React components
│   ├── package.json           # Node.js dependencies
│   └── vite.config.ts         # Build config
│
├── README.md                  # Project overview
├── BUILDING.md                # Build standalone app
└── SETUP_GUIDE.md            # This file
```

## Troubleshooting

### Python: "ModuleNotFoundError" or import errors

Make sure your virtual environment is **activated**:

**Windows:**
```bash
cd backend
venv\Scripts\activate
```

**macOS/Linux:**
```bash
cd backend
source venv/bin/activate
```

Then run the app again.

### "Address already in use" on port 5000

Another app is using port 5000. Either:
- Close the other app, or
- Modify `app.py` line 450 to change the port:
  ```python
  app.run(debug=True, host="127.0.0.1", port=5001)  # Use 5001 instead
  ```

### Database file not found

The app auto-creates `backend/games.db` if it doesn't exist. If you see database errors:

```bash
cd backend
python load_db.py games.json --db games.db
```

### Frontend won't load at /museum

You need Node.js installed and the frontend built. Run:

```bash
cd frontend
npm install
npm run build
```

Then the museum will be available at http://127.0.0.1:5000/museum

## Next Steps

- **Add your games**: Use `parse_gog.py` to import your library
- **Customize**: Edit the database directly in the UI
- **Get cover art**: Run `enrich.py` or `enrich_steamgriddb.py`
- **Build standalone app**: See `BUILDING.md` to create an `.exe` (Windows) or app bundle (macOS)

## Questions?

Check the comments in the Python scripts — they explain what each one does.

For the database schema, see `backend/schema.sql`.

# GameShelf Data Flow Reference

Comprehensive documentation of all data flows in GameShelf, from user input to database storage and back.

---

## 1. Initial Library Import Flow

### 1.1 Export Folder Listing (User Manual Step)

**Goal:** Generate a text file listing game folders and their sizes

**User Action:**
```bash
# On GOG install folder (Windows)
dir /s > gog.txt

# Or on Unix-like systems
du -sh * > gog.txt
```

**Output:** `gog.txt` (plain text)

**Example Content:**
```
5.2G    Cyberpunk.2077.Game-(2.21)
3.1G    The.Witcher.3.Wild.Hunt-(1.4)
12.4G   Red.Dead.Redemption.2-(6.1)
```

### 1.2 Parse Folder Listing

**Command:**
```bash
python3 backend/parse_gog.py gog.txt -o games.json
```

**Input:** `gog.txt` (raw folder listing)

**Process:** (`backend/parse_gog.py`)

```
1. Detect encoding (UTF-8 or UTF-16)
2. For each line:
   a. Parse size: "5.2G" → 5597380608 bytes
   b. Extract title: "Cyberpunk.2077.Game-(2.21)" → "Cyberpunk 2077"
   c. Extract GOG ID: "-(2.21)" → "2.21"
   d. Detect platform: "_windows_gog_" → "gog"
   e. Normalize title case (handle Roman numerals, acronyms)
   f. Create game object:
      {
        "title": "Cyberpunk 2077",
        "size_bytes": 5597380608,
        "gog_id": "2.21",
        "platform": "gog",
        "raw_paths": ["Cyberpunk.2077.Game-(2.21)"]
      }
3. Dedup by GOG ID or title (keep largest)
4. Categorize as game, extra, or patch
5. Output JSON array
```

**Output:** `games.json` (JSON array)

**Example:**
```json
[
  {
    "title": "Cyberpunk 2077",
    "size_bytes": 5597380608,
    "gog_id": "2.21",
    "platform": "gog",
    "raw_paths": ["Cyberpunk.2077.Game-(2.21)"]
  },
  ...
]
```

### 1.3 Load into Database

**Command:**
```bash
python3 backend/load_db.py games.json --db backend/games.db
```

**Input:** `games.json` (parsed games)

**Process:** (`backend/load_db.py`)

```
1. Connect to SQLite database
2. Create schema if not exists (from schema.sql)
3. For each game in JSON:
   a. Check if exists by gog_id (primary key)
   b. If not found, check by title (fallback)
   c. If exists:
      - UPDATE size_bytes, raw_paths
      - PRESERVE status, rating, notes, tags, folder_path, exe_path
   d. If not exists:
      - INSERT new row
      - Set status = "backlog", rating = NULL
   e. Link bonus_content (DLC/patches) by title matching
4. Commit transaction
5. Print summary (added, updated, merged)
```

**Output:** `games.db` (SQLite database)

**Database State After:**
```sql
-- 3 new games inserted (from above example)
INSERT INTO games (gog_id, platform, title, size_bytes, status, rating, ...)
VALUES 
  ('2.21', 'gog', 'Cyberpunk 2077', 5597380608, 'backlog', NULL, ...),
  ('1.4', 'gog', 'The Witcher 3', 3244589056, 'backlog', NULL, ...),
  ('6.1', 'gog', 'Red Dead Redemption 2', 13353088000, 'backlog', NULL, ...);
```

### 1.4 Optional: Enrich with Cover Art

**Command:**
```bash
python3 backend/enrich.py --db backend/games.db
```

**Process:** (`backend/enrich.py`)

```
1. For each game in database:
   a. If already has cover_url: skip
   b. If gog_catalog_id set: use it (already looked up)
   c. Else: lookup via verify_gog_id()
      - Query api.gog.com/products/{gog_id}
      - Get response JSON
      - Extract title, description, genres, cover_url, etc.
      - Save as gog_catalog_id
   d. Download cover image from cover_url
   e. Save to static/covers/{game_id}.jpg
   f. Call dominant_color() on downloaded image
   g. Extract hex color (e.g., "#FF5733")
   h. UPDATE games table:
      - cover_url = "/static/covers/{game_id}.jpg"
      - case_color = "#FF5733"
      - gog_catalog_id = "123456" (if looked up)
      - description, genres, developer, release_date (if available)
2. Commit transaction
3. Skip games already with cover_url (cheap to re-run)
```

**Output:** 
- `static/covers/*.jpg` (downloaded cover images)
- Updated `games.db` with cover_url, case_color, metadata

**Example Database State:**
```sql
UPDATE games SET
  cover_url = '/static/covers/1.jpg',
  case_color = '#FF5733',
  gog_catalog_id = '1207658051',
  description = 'An open-world action-adventure...',
  genres = 'RPG,Action,Open World',
  developer = 'CD Projekt Red'
WHERE id = 1;
```

---

## 2. Runtime: Adding a New Game

### 2.1 User Initiates Add Game

**UI Interaction:**
1. User clicks "+ Add Game" button
2. Modal dialog appears with title input field
3. User types: "Elden Ring"
4. User selects platform: "Steam"
5. User clicks "Save"

### 2.2 Frontend Sends Add Request

**API Call:**
```javascript
POST /api/games HTTP/1.1
Content-Type: application/json

{
  "title": "Elden Ring",
  "platform": "steam"
}
```

### 2.3 Backend Processes Add Request

**Endpoint:** `app.py` → `POST /api/games`

**Process:**

```python
1. Parse JSON request body
2. Validate inputs:
   - title: required, string
   - platform: required, one of (gog, steam, ps3, ps4)
3. Insert into games table:
   INSERT INTO games (title, platform, status, rating, added_at)
   VALUES ('Elden Ring', 'steam', 'backlog', NULL, now())
   → Returns game_id = 42

4. Call apply_title(title="Elden Ring", platform="steam"):
   a. Query SteamGridDB API (if API key available):
      GET https://www.steamgriddb.com/api/v2/search/autocomplete?query=Elden+Ring
      Response: [
        { "id": 123456, "name": "Elden Ring" },
        ...
      ]
   b. If SteamGridDB fails or no key:
      Query GOG Catalog API (free fallback):
      GET https://api.gog.com/products/search?query=Elden%20Ring
      Response: { "products": [...] }
   c. Get cover URL from best match
   → Returns ("Elden Ring", "https://steamgriddb.com/cover/123456.jpg")

5. Download cover image:
   GET https://steamgriddb.com/cover/123456.jpg
   → Binary image data
   Save to static/covers/42.jpg

6. Extract dominant color:
   Call dominant_color("/path/to/static/covers/42.jpg")
   → PIL quantize(colors=6) → find most common
   → Returns "#3B7A9E" (teal-ish)

7. Optional: Call verify_gog_id(title="Elden Ring"):
   Query api.gog.com to find GOG product ID
   → If found: gog_catalog_id = "1696389047"
   → Fetch description, genres, developer, release_date

8. UPDATE games table:
   UPDATE games SET
     cover_url = '/static/covers/42.jpg',
     case_color = '#3B7A9E',
     gog_catalog_id = '1696389047',
     description = 'Explore the Lands Between...',
     genres = 'RPG,Action,Adventure',
     developer = 'FromSoftware'
   WHERE id = 42

9. Serialize game record (convert DB row to JSON):
   {
     "id": 42,
     "title": "Elden Ring",
     "platform": "steam",
     "status": "backlog",
     "rating": null,
     "notes": null,
     "tags": null,
     "cover_url": "/static/covers/42.jpg",
     "case_color": "#3B7A9E",
     "size_bytes": 0,
     "gog_catalog_id": "1696389047",
     ...
   }

10. Return JSON response (HTTP 201 Created)
```

### 2.4 Frontend Updates UI

**Response Received:**
```javascript
// JavaScript received the game object
{
  "id": 42,
  "title": "Elden Ring",
  "platform": "steam",
  "cover_url": "/static/covers/42.jpg",
  ...
}
```

**UI Update:**
1. Close "+ Add Game" modal
2. Re-fetch games from `/api/games?platform=steam`
3. Re-render game grid
4. New "Elden Ring" tile appears with teal-colored case and cover image

---

## 3. Runtime: User Edits Game

### 3.1 User Clicks Game Card

**UI Interaction:**
1. User clicks "Elden Ring" game tile
2. Modal dialog opens (detail view)
3. Modal shows all fields:
   - Title (editable)
   - Status dropdown (backlog/playing/completed/abandoned)
   - Rating star selector (1-10)
   - Notes textarea
   - Tags comma-separated list
   - Folder path (with picker)
   - Exe path (with picker)
   - Cover art (drag-and-drop to replace)

### 3.2 User Changes Status

**User Action:**
1. User clicks Status dropdown
2. Selects "playing"
3. Modal shows unsaved change indicator
4. User clicks "Save"

### 3.3 Frontend Sends Edit Request

**API Call:**
```javascript
PATCH /api/games/42 HTTP/1.1
Content-Type: application/json

{
  "status": "playing"
}
```

### 3.4 Backend Processes Edit Request

**Endpoint:** `app.py` → `PATCH /api/games/<id>`

**Process:**

```python
1. Parse JSON request body
2. Get current game record from database:
   SELECT * FROM games WHERE id = 42

3. Validate inputs:
   - status: must be in (backlog, playing, completed, abandoned)
   - rating: if set, must be 1-10
   - folder_path: if set, must exist as directory
   - exe_path: if set, must exist as file

4. Update database:
   UPDATE games SET
     status = 'playing',
     updated_at = now()
   WHERE id = 42

5. If folder_path changed:
   a. Check folder exists
   b. Recursively sum file sizes
   c. UPDATE size_bytes = calculated_size
   d. If folder_path becomes empty: set exe_path = NULL

6. If title changed:
   a. Call apply_title() to re-fetch cover
   b. Update cover_url, case_color

7. Serialize updated game record
8. Return JSON response (HTTP 200 OK)
```

### 3.5 Frontend Updates UI

**Response Received:**
```javascript
{
  "id": 42,
  "title": "Elden Ring",
  "status": "playing",  // Changed!
  ...
}
```

**UI Update:**
1. Close modal
2. Re-render game grid
3. "Elden Ring" tile now shows "Playing" badge
4. Updated timestamp displayed

---

## 4. Runtime: Search & Filter

### 4.1 User Types in Search Box

**UI Interaction:**
1. User types "stalker" in search box
2. Frontend normalizes search query:
   ```javascript
   normalize("stalker") = "stalker"
   ```

### 4.2 Frontend Sends Filtered Request

**API Call:**
```javascript
GET /api/games?platform=gog&status=backlog&search=stalker HTTP/1.1
```

### 4.3 Backend Filters Games

**Endpoint:** `app.py` → `GET /api/games`

**Process:**

```python
1. Parse query parameters:
   - platform: "gog" (filter to GOG games only)
   - status: "backlog" (filter to backlog games only)
   - search: "stalker" (search term)
   - sort: "title" (default)
   - tag: null (no tag filter)

2. Build SQL query:
   SELECT * FROM games WHERE 1=1
   
3. Add WHERE clauses:
   - If platform: AND platform = 'gog'
   - If status: AND status = 'backlog'
   - If tag: AND tags LIKE '%tag%'
   
4. For search (if provided):
   a. Normalize each game title:
      normalize("S.T.A.L.K.E.R. - Anomaly") = "stalkeranomalу"
   b. Normalize search query:
      normalize("stalker") = "stalker"
   c. Check if normalized title contains normalized search:
      "stalkeranomalу".contains("stalker") = TRUE ✓
   d. Include game in results

5. Apply sort:
   ORDER BY title ASC (default, customizable)

6. Execute query and get results:
   [
     {
       "id": 123,
       "title": "S.T.A.L.K.E.R. - Anomaly",
       "platform": "gog",
       "status": "backlog",
       "cover_url": "/static/covers/123.jpg",
       ...
     },
     {
       "id": 124,
       "title": "S.T.A.L.K.E.R. - Call of Pripyat",
       "platform": "gog",
       "status": "backlog",
       "cover_url": "/static/covers/124.jpg",
       ...
     }
   ]

7. Serialize each game to JSON
8. Return array of matching games
```

### 4.4 Frontend Renders Results

**Response Received:**
```javascript
// Array of 2 matching S.T.A.L.K.E.R. games
[
  { id: 123, title: "S.T.A.L.K.E.R. - Anomaly", ... },
  { id: 124, title: "S.T.A.L.K.E.R. - Call of Pripyat", ... }
]
```

**UI Update:**
1. Clear previous grid
2. Re-render with only 2 games
3. User sees search results filtered to backlog S.T.A.L.K.E.R. games

---

## 5. Analytics & Dashboard

### 5.1 User Opens Dashboard

**User Action:**
1. User clicks "Dashboard" link
2. Browser navigates to `/dashboard`
3. Page loads `dashboard.html` and `dashboard.js`

### 5.2 Dashboard Fetches Data

**API Call:**
```javascript
GET /api/stats
GET /api/dashboard
GET /api/dashboard/insights
```

### 5.3 Backend Calculates Stats

**Endpoint:** `app.py` → `GET /api/stats`

**Process:**

```python
1. Execute SQL queries:
   
   # Total games per platform
   SELECT platform, COUNT(*) as count
   FROM games
   GROUP BY platform
   → { "gog": 150, "steam": 75, "ps3": 30, "ps4": 20 }
   
   # Status breakdown
   SELECT status, COUNT(*) as count
   FROM games
   GROUP BY status
   → { "backlog": 180, "playing": 45, "completed": 40, "abandoned": 10 }
   
   # Total storage
   SELECT SUM(size_bytes) as total_bytes
   FROM games
   → 5,497,558,016 bytes = 5.1 TB (formatted)
   
   # Top-rated games
   SELECT * FROM games
   WHERE rating IS NOT NULL
   ORDER BY rating DESC
   LIMIT 5
   → [ { title: "Best Game", rating: 10, ... }, ... ]

2. Return stats JSON:
   {
     "platforms": { "gog": 150, "steam": 75, ... },
     "status": { "backlog": 180, "playing": 45, ... },
     "total_games": 275,
     "total_storage_bytes": 5497558016,
     "top_rated": [ ... ]
   }
```

**Endpoint:** `app.py` → `GET /api/dashboard/insights`

**Process:**

```python
1. Execute histogram queries:
   
   # Size distribution (bucketed)
   SELECT
     CASE
       WHEN size_bytes < 1*1024^3 THEN '<1GB'
       WHEN size_bytes < 5*1024^3 THEN '1-5GB'
       WHEN size_bytes < 15*1024^3 THEN '5-15GB'
       ELSE '15GB+'
     END as bucket,
     COUNT(*) as count
   FROM games
   GROUP BY bucket
   
   # Rating distribution
   SELECT rating, COUNT(*) as count
   FROM games
   WHERE rating IS NOT NULL
   GROUP BY rating
   
   # Games added per month (last 12 months)
   SELECT
     DATE(added_at) as month,
     COUNT(*) as count
   FROM games
   WHERE added_at > date('now', '-12 months')
   GROUP BY month
   ORDER BY month

2. Return histograms JSON:
   {
     "size_distribution": [
       { "bucket": "<1GB", "count": 45 },
       { "bucket": "1-5GB", "count": 120 },
       { "bucket": "5-15GB", "count": 80 },
       { "bucket": "15GB+", "count": 30 }
     ],
     "rating_distribution": [
       { "rating": 1, "count": 5 },
       { "rating": 10, "count": 25 },
       ...
     ],
     "activity_timeline": [
       { "month": "2024-01", "count": 10 },
       { "month": "2024-02", "count": 15 },
       ...
     ]
   }
```

### 5.4 Frontend Renders Charts

**Response Received:**
```javascript
{
  "size_distribution": [ ... ],
  "rating_distribution": [ ... ],
  "activity_timeline": [ ... ]
}
```

**UI Renders:**
1. Bar chart: Library size distribution
2. Pie chart: Rating distribution
3. Line chart: Games added per month timeline
4. Stat tiles: Total games, total storage, per-platform breakdown

---

## 6. Version Checking (GOG Only)

### 6.1 User Uploads Gamelist

**User Action:**
1. User downloads gamelist.txt from GOG
   ```
   # File from GOG Galaxy backup or manual export
   1207658051=2.31
   1207658052=1.4
   ...
   ```

2. User visits Dashboard
3. User clicks "Check for Updates"
4. User selects gamelist.txt file
5. Browser uploads file

### 6.2 Frontend Sends Upload Request

**API Call:**
```javascript
POST /api/build_status/upload HTTP/1.1
Content-Type: multipart/form-data

[gamelist.txt file content]
```

### 6.3 Backend Processes Version Check

**Endpoint:** `app.py` → `POST /api/build_status/upload`

**Process:** (via `backend/check_latest_builds.py`)

```python
1. Parse uploaded gamelist.txt:
   1207658051=2.31
   1207658052=1.4
   → Dictionary: { "1207658051": "2.31", "1207658052": "1.4", ... }

2. For each game in database:
   a. Get gog_catalog_id from database
   b. Look up in parsed gamelist dictionary
   c. If found:
      - Parse build ID: "2.31" → 2.31
      - Compare with current latest_build in database
      - If newer: game is OUTDATED
      - If same: game is UP-TO-DATE
      - If not in DB yet: game is UNVERIFIED
   d. UPDATE games table:
      UPDATE games SET
        latest_build = '2.31',
        build_checked_at = now()
      WHERE gog_catalog_id = '1207658051'

3. Build status report:
   {
     "checked": true,
     "total": 150,
     "up_to_date": 130,
     "outdated": 15,
     "unverified": 5,
     "outdated_games": [
       {
         "id": 42,
         "title": "Cyberpunk 2077",
         "current_build": "2.21",
         "latest_build": "2.31"
       },
       ...
     ]
   }
```

### 6.4 Frontend Displays Results

**Response Received:**
```javascript
{
  "checked": true,
  "up_to_date": 130,
  "outdated": 15,
  "unverified": 5,
  "outdated_games": [
    { "title": "Cyberpunk 2077", "current_build": "2.21", "latest_build": "2.31" },
    ...
  ]
}
```

**UI Update:**
1. Display version check summary
2. List outdated games
3. User can manually update GOG installations if needed

---

## 7. Soft Delete & Recovery

### 7.1 User Deletes Game

**UI Interaction:**
1. User clicks game card
2. User clicks "Delete" button
3. Confirmation dialog: "Are you sure?"
4. User clicks "Yes, delete"

### 7.2 Frontend Sends Delete Request

**API Call:**
```javascript
DELETE /api/games/42 HTTP/1.1
```

### 7.3 Backend Performs Soft Delete

**Endpoint:** `app.py` → `DELETE /api/games/<id>`

**Process:**

```python
1. Get current game record:
   SELECT * FROM games WHERE id = 42

2. Copy to deleted_games table:
   INSERT INTO deleted_games
   (original_id, gog_id, platform, title, size_bytes, ..., deleted_at)
   VALUES (42, '...', 'steam', 'Elden Ring', ..., now())

3. Delete from games table:
   DELETE FROM games WHERE id = 42

4. Prune deleted_games table:
   If COUNT(*) > DELETED_GAMES_LIMIT (50):
     DELETE FROM deleted_games
     WHERE deleted_at < (
       SELECT deleted_at FROM deleted_games
       ORDER BY deleted_at DESC
       LIMIT 1 OFFSET 50
     )
   (Keeps only 50 newest deleted games)

5. Return deleted game record
```

**Database State:**
```sql
-- Game removed from games table
DELETE FROM games WHERE id = 42;

-- Game archived in deleted_games table
INSERT INTO deleted_games (...) VALUES (...);
```

### 7.4 Frontend Updates UI

**Response Received:**
```javascript
{
  "status": "deleted",
  "message": "Elden Ring deleted"
}
```

**UI Update:**
1. Remove game from grid
2. Show undo/recovery option (if enabled)
3. User can click "Trash" to see deleted games

### 7.5 User Recovers Deleted Game

**UI Interaction:**
1. User clicks "Trash" button
2. Modal shows deleted games
3. User clicks "Restore" on "Elden Ring"

**API Call:**
```javascript
POST /api/games/recover/42 HTTP/1.1
```

**Backend Process:**

```python
1. Get deleted game record:
   SELECT * FROM deleted_games WHERE original_id = 42

2. Re-insert into games table:
   INSERT INTO games (...)
   VALUES (... all fields from deleted_games ...)

3. Remove from deleted_games table:
   DELETE FROM deleted_games WHERE original_id = 42

4. Return restored game record
```

**UI Update:**
1. Close trash modal
2. Re-fetch games
3. "Elden Ring" reappears in grid with original data intact

---

## 8. 3D Museum Carousel Navigation

### 8.1 User Opens Museum

**UI Interaction:**
1. User clicks "3D Museum" or navigates to `/museum`
2. React app loads
3. Fetches games via `/api/games?platform=gog`
4. Renders 3D carousel with Framer Motion

### 8.2 User Navigates Carousel

**Keyboard Input:**
- User presses RIGHT arrow key
- JavaScript event handler fires

**Process:**

```javascript
// useCarouselFocus hook
1. Increment focusIndex (current = 0, next = 1)
2. Framer Motion animates spring:
   progress: 0 → 1 (smooth easing)
   
3. Every frame, CoverCard component:
   a. Read spring progress value
   b. Calculate position on carousel arc:
      angle = baseAngle + (progress * ANGLE_STEP)
      x = RADIUS * cos(angle)
      y = RADIUS * sin(angle)
   c. Calculate scale (interpolate based on distance):
      scale = lerp(1.0, 0.82, 0.70, 0.55)
   d. Calculate rotation (interpolate):
      rotation = lerp(0°, 10°, 14°, 18°)
   e. Calculate opacity (distance-based):
      opacity = lerp(1.0, 0.9, 0.8, 0.7)
   f. Update Three.js geometry:
      mesh.position.set(x, y, z)
      mesh.scale.set(scale, scale, scale)
      mesh.rotation.z = rotation
      material.opacity = opacity
   
4. After animation completes (spring settles):
   a. Update UI overlay with new game info
   b. Fetch screenshots (if available)
```

### 8.3 User Clicks Game Cover

**Mouse Input:**
1. User clicks on game cover in center

**Process:**

```javascript
1. Detect click on CoverCard mesh
2. Raycast from camera through mouse coordinates
3. Find intersected objects
4. If CoverCard hit:
   a. Open detail modal
   b. Fetch full game metadata
   c. Display notes, rating, screenshots
   d. Allow editing (same as static shelf)
```

---

## 9. Export Flow

### 9.1 User Exports Library

**UI Interaction:**
1. User clicks "Export Library" button
2. Browser downloads text file

### 9.2 Frontend Requests Export

**API Call:**
```javascript
GET /api/export/gamelist HTTP/1.1
```

### 9.3 Backend Generates Export

**Endpoint:** `app.py` → `GET /api/export/gamelist`

**Process:**

```python
1. Query all games:
   SELECT * FROM games ORDER BY platform, title

2. Format as GOG gamelist.txt:
   [GOG] (Platform)
   Title 1 (ID)
   Title 2 (ID)
   ...
   
   [Steam]
   Title 3 (ID)
   ...
   
   [PS3]
   ...

3. Include metadata as comments:
   # Total games: 275
   # Total storage: 5.1 TB
   # Last updated: 2024-01-15
   # Per-platform:
   #   GOG: 150 games
   #   Steam: 75 games
   #   PS3: 30 games
   #   PS4: 20 games

4. Return as plain text with UTF-8 encoding
5. Browser receives and downloads as gamelist.txt
```

---

## 10. Cover Art Upload

### 10.1 User Uploads Custom Cover

**UI Interaction:**
1. User opens game modal
2. Drags image onto cover art area
3. Or clicks to browse and select image

### 10.2 Frontend Sends Upload

**API Call:**
```javascript
POST /api/games/42/cover HTTP/1.1
Content-Type: multipart/form-data

[Image binary data]
```

### 10.3 Backend Processes Upload

**Endpoint:** `app.py` → `POST /api/games/<id>/cover`

**Process:**

```python
1. Receive multipart file upload
2. Validate:
   - Is image file (JPG, PNG)
   - File size < 5MB
3. Save to static/covers/{game_id}_{timestamp}.jpg
4. Call dominant_color() on new image
5. UPDATE games table:
   UPDATE games SET
     cover_url = '/static/covers/{game_id}_custom.jpg',
     case_color = extracted_hex_color
   WHERE id = 42
6. Return updated game record
```

---

## Data Integrity & ACID Properties

### Transactions

SQLite auto-commit mode (default):
- Each UPDATE/INSERT/DELETE is its own transaction
- Rolled back automatically on exception
- No explicit transaction management needed

### Referential Integrity

- `bonus_content.game_id` → `games.id` (ON DELETE SET NULL)
- `game_screenshots.game_id` → `games.id` (ON DELETE CASCADE)
- `deleted_games` has no foreign keys (archive only)

### Constraints

- `games.id` — PRIMARY KEY (unique, auto-increment)
- `games.title` — NOT NULL (required)
- `games.platform` — NOT NULL DEFAULT 'gog'
- Indexes on `status`, `title`, `game_id` for fast queries

---

## Error Handling & Recovery

### Network Failures

```
API call to SteamGridDB fails
  → Try GOG Catalog API
    → If that fails too
      → Save game without cover
```

### File System Issues

```
Cover download succeeds, save fails
  → Game saved, but cover_url set to remote URL
  → Next time app loads, it lazy-loads from remote
```

### Database Corruption

```
If games.db becomes corrupted
  → Delete games.db
  → Run app.py (auto-recreates from schema.sql)
  → Re-import from games.json backup
```

---

## Summary

GameShelf data flows follow a simple pattern:

1. **Import:** Folder listing → Parse → JSON → Load → SQLite
2. **Runtime:** User action → API call → DB query/update → JSON response → UI refresh
3. **Export:** DB query → Format → Download

All flows gracefully degrade if external APIs unavailable, ensuring the app never breaks due to network issues.

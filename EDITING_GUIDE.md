# Which File to Edit for What?

## Editing the 3D Scene

**File: `frontend/src/components/scene/CoverCard.tsx`**
- Change scale steps (currently 1.0 → 0.82 → 0.70 → 0.55)
- Change rotation angles (currently 0° → 10° → 14° → 18°)
- Adjust carousel arc radius & speed
- Modify opacity/brightness of non-focused covers

**File: `frontend/src/components/scene/Lighting.tsx`**
- Adjust light positions, colors, intensities
- Add/remove lights
- Change shadow settings

**File: `frontend/src/components/scene/PostFX.tsx`**
- Enable/disable depth-of-field blur
- Adjust blur amount & focus distance
- Add bloom, vignette, color grading, etc.

## Editing the UI Overlay

**File: `frontend/src/components/ui/Overlay.tsx`**
- Change title, metadata, button styling
- Add/remove buttons or sections
- Adjust keyboard hints text

## Editing Global Styles

**File: `frontend/src/index.css`**
- Change background color (currently `#05050a` = almost black)
- Change text colors, fonts
- Add gradients or patterns to the DOM background (not the 3D canvas)

## Editing the Carousel Logic

**File: `frontend/src/hooks/useCarouselFocus.ts`**
- Change spring animation stiffness/damping (smoothness of transitions)
- Adjust initial cover index
- Change movement behavior (arrow key increments, etc.)

**File: `frontend/src/components/Museum.tsx`**
- Change camera position/FOV
- Add/remove 3D scene elements
- Modify canvas rendering settings

## Editing API / Data Fetching

**File: `frontend/src/api.ts`**
- Change which API endpoints are called
- Modify URL query parameters
- Update cache/refresh logic

**File: `frontend/src/App.tsx`**
- Change how games are fetched from `/api/games`
- Add error handling
- Modify keyboard shortcuts (arrows, escape)

## Editing Backend

**File: `backend/app.py`**
- Add/modify Flask routes
- Change database queries
- Adjust API response structure
- Modify `/museum` route behavior

**File: `backend/schema.sql`**
- Add columns to games table
- Change data types
- Add new tables

**File: `backend/gog_catalog.py`**
- Modify how cover art is fetched from GOG
- Add caching logic

**File: `backend/build.py`**
- Change PyInstaller settings (to include/exclude files)
- Modify `--fresh` build behavior

## Editing Build Configuration

**File: `frontend/vite.config.ts`**
- Change output folder
- Adjust dev server proxy settings
- Modify build optimization

**File: `frontend/tsconfig.json`**
- Change TypeScript strictness
- Add path aliases

**File: `package.json`**
- Add/remove npm dependencies
- Change build scripts

## Quick Reference by Feature

| Feature | File |
|---------|------|
| Scale sizes | `CoverCard.tsx` line 15-20 |
| Rotation angles | `CoverCard.tsx` line 41-46 |
| Opacity/brightness | `CoverCard.tsx` line 98-109 |
| Light colors | `Lighting.tsx` |
| Blur effect | `PostFX.tsx` |
| Background color | `index.css` line 6 |
| Title & HUD | `Overlay.tsx` |
| Spring smoothness | `useCarouselFocus.ts` line 16-21 |
| API endpoint | `api.ts` |
| Keyboard controls | `App.tsx` line 27-33 |
| Backend routes | `app.py` |

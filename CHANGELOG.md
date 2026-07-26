# Changelog

All notable changes to GameShelf are documented here.

## [Latest] — 2026-07-26

### Added
- Dashboard redesign with professional glassmorphism UI
- Folder integrity check to verify game installations exist on disk
- Steam API screenshot fetching for Steam games (79/96 games enriched)
- Metric cards showing library statistics
- Chart.js integration for data visualization
- Big Picture carousel mode with hero backgrounds and adjacent games display
- Logo rendering for Steam games

### Fixed
- Dashboard background changed to pure black for modern look
- Glassy frosted-glass effect on all UI cards

### Improved
- Professional dark theme throughout dashboard
- Responsive grid layouts
- Real-time folder scan for missing game installations

## [v1.0] — 2026-07-25

### Initial Release
- Full GitHub version with all local features restored
- 12 Python utility scripts for data management
- SQLite database with 100+ games pre-loaded
- Web UI with search, filters, and game management
- GOG, Steam, PS3, PS4 game parsers
- Cover art enrichment from GOG and SteamGridDB
- Standalone app compilation with PyInstaller

### Features
- View your game library with multiple platforms (GOG, Steam, PS3, PS4)
- Search games by title, platform, or tags
- Rate games (1-5 stars)
- Track playthrough status (Backlog, Playing, Completed, Abandoned)
- Add custom notes and tags
- Download cover art and metadata
- Build standalone .exe for Windows distribution

## Technical Details

See [BUILDING.md](BUILDING.md) for compilation instructions.
See [ARCHITECTURE.md](ARCHITECTURE.md) for system design details.
See [DATA_FLOW.md](DATA_FLOW.md) for how data flows through the app.

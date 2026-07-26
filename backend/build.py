#!/usr/bin/env python3
"""
Build the standalone GameShelf desktop app for whichever OS this script is
run on (Windows, Linux, macOS). PyInstaller cannot cross-compile, so this
must be run natively on each target machine - there is no way to produce a
Linux build from Windows or vice versa.

What it does:
    1. Runs `pyinstaller GameShelf.spec` to produce dist/GameShelf(.exe).
    2. Copies the runtime data files the exe expects next to it
       (schema.sql, static/, cover_overrides.json, and - unless --fresh -
       your own games.db and steamgriddb_key.txt) into dist/, since
       PyInstaller's datas=[] intentionally leaves those out.

Run:
    python build.py            # your own copy, with your existing library
    python build.py --fresh    # a clean copy to give someone else - no
                                # games, no cover art, no API key; app.py
                                # creates an empty database on first launch

Then distribute the whole dist/ folder - the exe only works together with
the files alongside it, it is not a fully self-contained single file.

Linux note: pywebview needs a native GUI toolkit installed on the build/run
machine - see BUILDING.md for the system packages to install first.
"""
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
DIST_DIR = BASE_DIR / "dist"

# Always safe to ship: app code's own runtime needs, none of it personal.
COMMON_ITEMS = ["schema.sql", "cover_overrides.json"]
# Your actual library data - only copied for your own rebuilds, never into
# a --fresh package meant for someone else.
PERSONAL_ITEMS = ["games.db", "steamgriddb_key.txt"]
# Subfolders of static/ that hold per-game downloaded art keyed by your own
# database's row ids - meaningless (and irrelevant) without your games.db.
PERSONAL_STATIC_SUBDIRS = {"covers", "heroes", "screenshots"}


def copy_static(fresh):
    src = BASE_DIR / "static"
    dest = DIST_DIR / "static"
    if not fresh:
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return
    ignore = shutil.ignore_patterns(*PERSONAL_STATIC_SUBDIRS)
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=ignore)


def main():
    fresh = "--fresh" in sys.argv

    print("Running PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "GameShelf.spec", "--noconfirm"],
        cwd=str(BASE_DIR),
    )
    if result.returncode != 0:
        sys.exit("PyInstaller failed - see output above.")

    if not DIST_DIR.exists():
        sys.exit(f"Expected {DIST_DIR} to exist after build, but it doesn't.")

    print("Copying runtime data files into dist/ ...")
    for name in COMMON_ITEMS + ([] if fresh else PERSONAL_ITEMS):
        src = BASE_DIR / name
        if not src.exists():
            print(f"  ! skipping {name} (not found in project folder)")
            continue
        shutil.copy2(src, DIST_DIR / name)
        print(f"  copied {name}")

    copy_static(fresh)
    print(f"  copied static/{' (without covers/heroes/screenshots)' if fresh else ''}")

    # Also copy static folder into GameShelf subfolder for exe's BASE_DIR detection
    game_shelf_dir = DIST_DIR / "GameShelf"
    if game_shelf_dir.exists():
        game_shelf_static = game_shelf_dir / "static"
        shutil.copytree(DIST_DIR / "static", game_shelf_static, dirs_exist_ok=True)
        print(f"  copied static/ into GameShelf/")

    print(f"\nDone. Distribute the whole '{DIST_DIR}' folder - "
          f"double-click GameShelf inside it to run.")
    if fresh:
        print("This is a --fresh build: no games.db, no API key, no cover "
              "art shipped - a fresh empty library is created on first launch.")


if __name__ == "__main__":
    main()

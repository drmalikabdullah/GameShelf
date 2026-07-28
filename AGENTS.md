# GameShelf Working Rules

These instructions apply to every task involving GameShelf.

## Authoritative directory

- The only authorized GameShelf working directory is `E:\Projects\GameShelf`.
- Perform all source inspection, editing, testing, development-server work, builds, and Git operations from this directory.
- Verify the repository path before changing any file or starting the application.
- Do not inspect, edit, run, build, commit, or push another GameShelf copy unless the user explicitly names and authorizes that directory.
- In particular, do not use `C:\Users\Admin\Desktop\GameShelf` or `E:\Projects\GOG Database Initial`.
- If `E:\Projects\GameShelf` is unavailable or not writable, stop and tell the user instead of switching to another copy.

## Development and generated files

- Treat the normal source files in `E:\Projects\GameShelf` as authoritative.
- Run the development server from `E:\Projects\GameShelf`.
- Do not edit generated files inside `dist` or `build`.
- Do not rebuild or modify `GameShelf.exe` unless the user explicitly requests a production build.
- Test source changes in the development version before proposing or creating a production build.

## Git and reporting

- Do not commit or push unless the user explicitly asks.
- Preserve unrelated user changes.
- Revert only changes made for the current request unless the user explicitly requests a broader revert.
- Before reporting completion, state the exact files changed and confirm they are under `E:\Projects\GameShelf`.
- When testing, verify that the running server is serving `E:\Projects\GameShelf`, not a stale executable or another repository copy.

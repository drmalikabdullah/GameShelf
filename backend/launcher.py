#!/usr/bin/env python3
"""
Desktop launcher for the GOG/Steam/PS3/PS4 game shelf.

Runs the Flask app in a background thread and opens it in a native window
(via pywebview) instead of requiring the user to open a browser and type
a URL. This is the entry point built into the standalone .exe - build with:

    pyinstaller --onefile --noconsole --name GameShelf launcher.py

The resulting exe expects games.db, static/, cover_overrides.json, and
steamgriddb_key.txt to sit in the same folder as the exe itself (app.py and
steamgriddb.py already resolve paths that way when frozen).
"""
import socket
import threading
import time

import webview

import app as flask_app

HOST = "127.0.0.1"
PORT = 5000


def port_is_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def run_flask():
    flask_app.app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def main():
    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()

    for _ in range(100):
        if port_is_open(HOST, PORT):
            break
        time.sleep(0.1)

    webview.create_window(
        "GameShelf",
        f"http://{HOST}:{PORT}/",
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()

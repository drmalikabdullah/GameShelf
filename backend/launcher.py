#!/usr/bin/env python3
"""Native desktop launcher used by the packaged GameShelf executable."""
import threading

import webview
from werkzeug.serving import make_server

import app as flask_app

HOST = "127.0.0.1"


class DesktopServer:
    """Run Flask on a free local port and stop it with the desktop window."""

    def __init__(self):
        # Port 0 asks Windows for an available port. This avoids the old
        # "port 5000 is already in use" failure when another dev copy is open.
        self.httpd = make_server(HOST, 0, flask_app.app, threaded=True)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="GameShelfServer",
            daemon=True,
        )
        self._stop_lock = threading.Lock()
        self._stopped = False

    def start(self):
        self.thread.start()

    def stop(self):
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
        self.httpd.shutdown()
        self.httpd.server_close()


def main():
    server = DesktopServer()
    server.start()

    window = webview.create_window(
        "GameShelf",
        f"http://{HOST}:{server.port}/",
        width=1280,
        height=860,
        min_size=(900, 600),
        background_color="#05070b",
    )
    window.events.closed += server.stop
    try:
        webview.start()
    finally:
        server.stop()


if __name__ == "__main__":
    main()

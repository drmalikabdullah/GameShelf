import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class RecycleBinTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "games.db"
        db = sqlite3.connect(self.db_path)
        db.executescript(
            (Path(app.__file__).parent / "schema.sql").read_text(encoding="utf-8")
        )
        db.execute(
            """
            INSERT INTO games (
                title, platform, steam_app_id, exe_path, logo_url, trailer_url,
                case_color, case_color_override
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Restore Test",
                "steam",
                "123",
                r"C:\Games\Test\game.exe",
                "/logos/1.png",
                "/trailers/1.webm",
                "#112233",
                "#445566",
            ),
        )
        db.execute(
            "INSERT INTO game_screenshots (game_id, path, position) VALUES (1, ?, 0)",
            ("/screenshots/1/1.jpg",),
        )
        db.commit()
        db.close()

        self.original_db_path = app.DB_PATH
        app.DB_PATH = self.db_path
        self.client = app.app.test_client()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_restore_preserves_metadata_and_reconnects_screenshots(self):
        self.assertEqual(self.client.delete("/api/games/1").status_code, 204)

        deleted = self.client.get("/api/deleted_games").get_json()
        self.assertEqual(len(deleted), 1)
        response = self.client.post(
            f"/api/deleted_games/{deleted[0]['id']}/restore"
        )
        self.assertEqual(response.status_code, 201)
        restored = response.get_json()

        self.assertEqual(restored["steam_app_id"], "123")
        self.assertEqual(restored["exe_path"], r"C:\Games\Test\game.exe")
        self.assertEqual(restored["logo_url"], "/logos/1.png")
        self.assertEqual(restored["trailer_url"], "/trailers/1.webm")
        self.assertEqual(restored["case_color"], "#112233")
        self.assertEqual(restored["case_color_override"], "#445566")
        self.assertEqual(
            self.client.get(
                f"/api/games/{restored['id']}/screenshots"
            ).get_json(),
            ["/screenshots/1/1.jpg"],
        )


class CachePolicyTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_api_responses_are_never_cached(self):
        response = self.client.get("/api/games")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_code_is_revalidated(self):
        response = self.client.get("/app.js")
        self.addCleanup(response.close)
        self.assertEqual(response.headers["Cache-Control"], "no-cache")

    def test_artwork_can_be_cached_locally(self):
        response = self.client.get("/covers/1.jpg")
        self.addCleanup(response.close)
        self.assertEqual(
            response.headers["Cache-Control"],
            "private, max-age=3600",
        )

    def test_offline_trailers_can_be_cached_locally(self):
        response = self.client.get("/trailers/missing.webm")
        self.addCleanup(response.close)
        self.assertEqual(
            response.headers["Cache-Control"],
            "private, max-age=3600",
        )


class StaticPathSafetyTests(unittest.TestCase):
    def test_local_artwork_path_stays_inside_static(self):
        path = app.static_file_from_url("/covers/1.jpg")
        self.assertIsNotNone(path)
        self.assertEqual(path.parent, (app.BASE_DIR / "static" / "covers").resolve())

    def test_parent_traversal_is_rejected(self):
        self.assertIsNone(app.static_file_from_url("/../../games.db"))

    def test_absolute_path_is_kept_under_static(self):
        self.assertIsNone(app.static_file_from_url(r"C:\Windows\system.ini"))


class SteamTrailerAddTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "games.db"
        db = sqlite3.connect(self.db_path)
        db.executescript(
            (Path(app.__file__).parent / "schema.sql").read_text(encoding="utf-8")
        )
        db.close()
        self.original_db_path = app.DB_PATH
        app.DB_PATH = self.db_path
        self.client = app.app.test_client()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    @mock.patch("app.refresh_steam_microtrailer")
    @mock.patch("app.refresh_steam_screenshots")
    @mock.patch("app.refresh_steam_release_year")
    @mock.patch("app.apply_title")
    def test_adding_steam_game_attempts_microtrailer(
        self, apply_title, refresh_metadata, refresh_screenshots, refresh_trailer
    ):
        apply_title.return_value = "Trailer Test"
        response = self.client.post(
            "/api/games", json={"title": "Trailer Test", "platform": "steam"}
        )
        self.assertEqual(response.status_code, 201)
        game_id = response.get_json()["id"]
        refresh_metadata.assert_called_once_with(mock.ANY, game_id, "Trailer Test")
        refresh_screenshots.assert_called_once_with(mock.ANY, game_id)
        refresh_trailer.assert_called_once_with(mock.ANY, game_id)

    @mock.patch("app.enrich_steam_microtrailers.download_for_game")
    def test_trailer_failure_is_non_fatal(self, download):
        download.side_effect = OSError("offline")
        with app.app.app_context():
            db = app.get_db()
            cursor = db.execute(
                "INSERT INTO games (title, platform, steam_app_id) VALUES (?, ?, ?)",
                ("Offline Trailer Test", "steam", "123"),
            )
            db.commit()
            self.assertFalse(app.refresh_steam_microtrailer(db, cursor.lastrowid))


class InstallationStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "games.db"
        db = sqlite3.connect(self.db_path)
        db.executescript(
            (Path(app.__file__).parent / "schema.sql").read_text(encoding="utf-8")
        )
        db.execute(
            "INSERT INTO games (title, platform, status) VALUES (?, ?, ?)",
            ("Uninstalled Test", "steam", "playing"),
        )
        db.commit()
        db.close()
        self.original_db_path = app.DB_PATH
        app.DB_PATH = self.db_path
        self.client = app.app.test_client()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_clearing_last_install_path_moves_playing_game_to_backlog(self):
        response = self.client.patch("/api/games/1", json={"exe_path": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "backlog")

    def test_update_installed_clears_stale_paths_and_updates_count(self):
        valid_exe = Path(self.temp_dir.name) / "installed.exe"
        valid_exe.write_bytes(b"test")
        db = sqlite3.connect(self.db_path)
        db.execute(
            "UPDATE games SET folder_path = ?, exe_path = ? WHERE id = 1",
            (
                str(Path(self.temp_dir.name) / "missing"),
                str(Path(self.temp_dir.name) / "missing.exe"),
            ),
        )
        db.execute(
            "INSERT INTO games (title, platform, status, exe_path) VALUES (?, ?, ?, ?)",
            ("Installed Test", "steam", "playing", str(valid_exe)),
        )
        db.commit()
        db.close()

        response = self.client.post("/api/scan/update-installed")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["installed_count"], 1)
        self.assertEqual(data["installed_by_platform"]["steam"], 1)
        self.assertEqual(data["installed_by_platform"]["gog"], 0)
        self.assertEqual(data["cleared_folders"], 1)
        self.assertEqual(data["cleared_executables"], 1)
        self.assertEqual(data["moved_to_backlog"], 1)
        self.assertEqual(data["unavailable_paths"], 0)

    def test_refresh_sizes_recalculates_reachable_game_folders(self):
        game_folder = Path(self.temp_dir.name) / "installed-game"
        game_folder.mkdir()
        (game_folder / "game.bin").write_bytes(b"1234567890")
        nested = game_folder / "data"
        nested.mkdir()
        (nested / "assets.bin").write_bytes(b"12345")
        db = sqlite3.connect(self.db_path)
        db.execute(
            "UPDATE games SET folder_path = ?, size_bytes = ? WHERE id = 1",
            (str(game_folder), 1),
        )
        db.commit()
        db.close()

        response = self.client.post("/api/scan/refresh-sizes")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["scanned_count"], 1)
        self.assertEqual(data["updated_count"], 1)
        self.assertEqual(data["total_size_bytes"], 15)
        self.assertEqual(data["updated_games"][0]["old_size_human"], "1B")
        self.assertEqual(data["updated_games"][0]["new_size_human"], "15B")

        db = sqlite3.connect(self.db_path)
        stored_size = db.execute("SELECT size_bytes FROM games WHERE id = 1").fetchone()[0]
        db.close()
        self.assertEqual(stored_size, 15)

    def test_nsfw_category_filters_by_tag(self):
        db = sqlite3.connect(self.db_path)
        db.execute("UPDATE games SET tags = ? WHERE id = 1", ("action, NSFW",))
        db.execute(
            "INSERT INTO games (title, platform, tags) VALUES (?, ?, ?)",
            ("Family Test", "steam", "action, coop"),
        )
        db.commit()
        db.close()

        response = self.client.get("/api/games?platform=steam&status=nsfw")
        self.assertEqual(response.status_code, 200)
        games = response.get_json()
        self.assertEqual([game["title"] for game in games], ["Uninstalled Test"])

        response = self.client.get("/api/games?platform=steam&sort=nsfw")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [game["title"] for game in response.get_json()], ["Uninstalled Test"]
        )

    def test_abandoned_status_is_rejected(self):
        response = self.client.patch("/api/games/1", json={"status": "abandoned"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("status must be one of", response.get_json()["error"])


class ElevatedLaunchTests(unittest.TestCase):
    @mock.patch("app.os.startfile")
    @mock.patch("app.platform.system", return_value="Windows")
    @mock.patch("app.subprocess.Popen")
    def test_windows_elevation_error_uses_runas(self, popen, _system, startfile):
        error = OSError("elevation required")
        error.winerror = 740
        popen.side_effect = error

        with tempfile.TemporaryDirectory() as temp_dir:
            exe_path = Path(temp_dir) / "admin-game.exe"
            exe_path.write_bytes(b"test")
            db_path = Path(temp_dir) / "games.db"
            db = sqlite3.connect(db_path)
            db.executescript(
                (Path(app.__file__).parent / "schema.sql").read_text(encoding="utf-8")
            )
            db.execute(
                "INSERT INTO games (title, platform, exe_path) VALUES (?, ?, ?)",
                ("Admin Game", "steam", str(exe_path)),
            )
            db.commit()
            db.close()
            original_db_path = app.DB_PATH
            app.DB_PATH = db_path
            try:
                response = app.app.test_client().post("/api/games/1/play")
            finally:
                app.DB_PATH = original_db_path

        self.assertEqual(response.status_code, 204)
        startfile.assert_called_once_with(str(exe_path), "runas")


if __name__ == "__main__":
    unittest.main()

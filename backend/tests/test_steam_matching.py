import unittest

import steamgriddb


class SteamMatchingTests(unittest.TestCase):
    def test_parses_steam_store_url(self):
        self.assertEqual(
            steamgriddb.parse_steam_appid(
                "https://store.steampowered.com/app/765900/example/"
            ),
            "765900",
        )

    def test_parses_bare_steam_app_id(self):
        self.assertEqual(steamgriddb.parse_steam_appid("765900"), "765900")

    def test_numeric_sequel_does_not_match_title_without_number(self):
        candidates = [
            {"id": 210098, "name": "Street Fighter X Tekken: 10 Gem Pack"},
        ]
        self.assertIsNone(steamgriddb.best_match("Tekken 6", candidates))

    def test_numeric_sequel_matches_same_number(self):
        candidates = [
            {"id": 123, "name": "Example Fighter 5"},
            {"id": 456, "name": "Example Fighter 6"},
        ]
        self.assertEqual(
            steamgriddb.best_match("Example Fighter 6", candidates)["id"], 456
        )

    def test_cross_store_trailer_requires_same_title(self):
        self.assertTrue(
            steamgriddb.is_exact_game_title("Along the Edge", "Along the Edge")
        )
        self.assertFalse(
            steamgriddb.is_exact_game_title(
                "Tekken 6", "Street Fighter X Tekken: 10 Gem Pack"
            )
        )


if __name__ == "__main__":
    unittest.main()

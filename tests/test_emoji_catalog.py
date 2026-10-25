import json
import unittest

from habit_garden.emoji_catalog import CATALOG_PATH, DEFAULT_EMOJI, allowed_emojis


class EmojiCatalogTests(unittest.TestCase):
    def test_catalog_contains_localized_emoji_and_default(self):
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.assertIn(DEFAULT_EMOJI, allowed_emojis())
        self.assertIn("📚", allowed_emojis())
        self.assertEqual(len(catalog["items"]), len(allowed_emojis()))
        book = next(item for item in catalog["items"] if item[0] == "📚")
        self.assertIn("книг", book[1])
        self.assertIn("читать", book[2])


if __name__ == "__main__":
    unittest.main()

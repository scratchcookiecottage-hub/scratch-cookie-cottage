"""Smoke checks for the brand pass. Does not change order logic — asserts it still holds."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import pytz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class PublicPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_public_gets_ok(self):
        for path in ("/", "/order", "/story", "/markets", "/merch", "/wholesale"):
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200, path)

    def test_nav_and_tagline_on_home(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("From Scratch. From the Cottage.", html)
        self.assertIn("Order for This Weekend", html)
        self.assertIn("Our Story", html)
        self.assertIn("From Scratch", html)
        self.assertIn("Small Batch", html)
        self.assertIn("Cottage Made", html)
        self.assertIn("DSHS ID #17384", html)
        self.assertIn("THIS PRODUCT WAS PRODUCED IN A PRIVATE RESIDENCE", html)
        self.assertNotIn("Scan a booth QR", html)
        self.assertNotIn("See you at the farmers market", html)

    def test_story_and_markets_pages(self):
        story = self.client.get("/story").get_data(as_text=True)
        self.assertIn("cottage kitchen", story.lower())
        markets = self.client.get("/markets").get_data(as_text=True)
        self.assertIn("cottage", markets.lower())
        self.assertIn("/order", markets)
        self.assertNotIn("Scan a booth QR", markets)

    def test_order_form_fields_preserved(self):
        html = self.client.get("/order").get_data(as_text=True)
        self.assertIn('name="pack_chocolate_chip"', html)
        self.assertIn('name="single_chocolate_chip"', html)
        self.assertIn('name="pickup_date"', html)
        self.assertIn('name="fulfillment"', html)
        self.assertIn("qty-thumb", html)
        self.assertIn("id=\"pack-status\"", html)


class OrderLogicFreezeTest(unittest.TestCase):
    def test_six_pack_must_be_multiple_of_six(self):
        from app import build_line_items

        _, _, errors = build_line_items({}, {"chocolate_chip": 5})
        self.assertTrue(errors)

        lines, subtotal, errors = build_line_items({}, {"chocolate_chip": 6})
        self.assertEqual(errors, [])
        self.assertEqual(subtotal, 2000)
        kinds = {line["kind"] for line in lines}
        self.assertIn("six_pack_cookie", kinds)
        self.assertIn("six_pack_fee", kinds)

        lines, subtotal, errors = build_line_items({"macadamia": 2}, {})
        self.assertEqual(errors, [])
        self.assertEqual(subtotal, 800)

        _, _, errors = build_line_items({}, {})
        self.assertTrue(errors)

    def test_wednesday_cutoff_still_locks_same_weekend(self):
        from order_window import is_pickup_date_available

        tz = pytz.timezone("America/Chicago")
        friday = date(2026, 8, 21)
        before = tz.localize(datetime(2026, 8, 19, 23, 59, 59))
        after = tz.localize(datetime(2026, 8, 20, 0, 0, 1))

        ok, _ = is_pickup_date_available(friday, before)
        self.assertTrue(ok)

        ok, reason = is_pickup_date_available(friday, after)
        self.assertFalse(ok)
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()

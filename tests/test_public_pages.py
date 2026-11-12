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
        for path in ("/", "/order", "/story", "/blog", "/markets", "/merch", "/wholesale"):
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200, path)
        self.assertEqual(self.client.get("/blog/not-a-real-note").status_code, 404)
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Sitemap:", robots.data)
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b"/blog", sitemap.data)

    def test_nav_and_tagline_on_home(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("From Scratch. From the Cottage.", html)
        self.assertIn("Order for This Weekend", html)
        self.assertIn("Our Story", html)
        self.assertIn("From Scratch", html)
        self.assertIn("Small Batch", html)
        self.assertIn("Fresh weekly", html)
        self.assertNotIn("Cottage Made", html)
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
        self.assertIn('name="minis_chocolate_chip"', html)
        self.assertIn('id="minis-packs"', html)
        self.assertIn('name="pickup_date"', html)
        self.assertIn('name="fulfillment"', html)
        self.assertIn("qty-thumb", html)
        self.assertIn("id=\"pack-status\"", html)


class BlogLoaderTest(unittest.TestCase):
    def test_markdown_post_and_images(self):
        import tempfile
        from pathlib import Path

        import blog

        tmp = Path(tempfile.mkdtemp())
        (tmp / "hello.md").write_text(
            "---\n"
            "title: Hello cottage\n"
            "slug: hello-cottage\n"
            "date: 2026-09-04\n"
            "description: A test kitchen note\n"
            "image: cookie.jpg\n"
            "draft: false\n"
            "---\n\n"
            "Hello **cottage**.\n\n"
            "![A cookie](cookie.jpg)\n",
            encoding="utf-8",
        )
        old = blog.POSTS_DIR
        blog.POSTS_DIR = tmp
        try:
            posts = blog.list_posts()
            self.assertEqual(len(posts), 1)
            post = posts[0]
            self.assertEqual(post["slug"], "hello-cottage")
            self.assertIn("<strong>cottage</strong>", post["html"])
            self.assertIn("/static/images/blog/cookie.jpg", post["html"])
            self.assertTrue(post["image"].endswith("/static/images/blog/cookie.jpg"))
            self.assertEqual(blog.get_post("hello-cottage")["title"], "Hello cottage")
            saved = blog.save_post(
                title="Draft note",
                slug="draft-note",
                date_value="2026-09-05",
                description="Hidden",
                body="Not live yet",
                draft=True,
            )
            self.assertTrue(saved["draft"])
            self.assertIsNone(blog.get_post("draft-note"))
            self.assertEqual(len(blog.list_posts(include_drafts=True)), 2)
        finally:
            blog.POSTS_DIR = old


class AdminAppGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app
        from config import Config

        cls._secret = Config.PUSH_REGISTER_SECRET
        Config.PUSH_REGISTER_SECRET = "test-admin-gate"
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        from config import Config

        Config.PUSH_REGISTER_SECRET = cls._secret

    def test_admin_hidden_without_app_key(self):
        resp = self.client.get("/admin")
        self.assertEqual(resp.status_code, 404)

    def test_admin_login_with_header_sets_gate_cookie(self):
        resp = self.client.get("/admin", headers={"X-SCC-App": "test-admin-gate"})
        self.assertIn(resp.status_code, (200, 302))
        self.assertTrue(resp.headers.get("Set-Cookie", "").startswith("scc_app="))


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


class MinisPackTest(unittest.TestCase):
    """Single-flavor 8-packs at $10, drawn from the live catalog."""

    def test_home_and_order_list_every_current_flavor(self):
        from app import app

        app.config["TESTING"] = True
        client = app.test_client()
        home = client.get("/").get_data(as_text=True)
        start = home.index('id="minis-packs"')
        section = home[start:home.index("</section>", start)]
        for name in (
            "Brown Butter Chocolate Chip",
            "Macadamia White Chocolate",
            "Salted Caramel Chocolate Pecan",
            "White Miso Peanut Butter",
        ):
            self.assertIn(name, section)
        self.assertIn("$10.00", section)
        self.assertIn("8 mini cookies", section)
        self.assertIn("no mixing", section.lower())
        self.assertIn("/order#minis-packs", section)

        order = client.get("/order").get_data(as_text=True)
        for cookie_id in (
            "chocolate_chip",
            "macadamia",
            "salted_caramel",
            "peanut_butter",
        ):
            self.assertIn(f'name="minis_{cookie_id}"', order)
        self.assertIn('data-price-minis-pack="1000"', order)
        self.assertIn('data-minis-per-pack="8"', order)
        self.assertIn("No mixing", order)

    def test_new_catalog_flavor_gets_a_minis_pack(self):
        from unittest.mock import patch

        from app import app
        from config import Config

        catalog = {
            "future_flavor": {
                "name": "Future Flavor Crumble",
                "description": "Added after launch.",
                "img_default": "",
                "img_hover": "",
            }
        }
        app.config["TESTING"] = True
        client = app.test_client()
        with patch.object(Config, "cookie_catalog", return_value=catalog):
            home = client.get("/").get_data(as_text=True)
            order = client.get("/order").get_data(as_text=True)
        start = home.index('id="minis-packs"')
        section = home[start:home.index("</section>", start)]
        self.assertIn("Future Flavor Crumble", section)
        self.assertNotIn("Brown Butter Chocolate Chip", section)
        self.assertIn('name="minis_future_flavor"', order)
        self.assertNotIn('name="minis_chocolate_chip"', order)

    def test_minis_line_items_stay_out_of_full_size_bake_counts(self):
        from app import _order_item_summary, build_line_items, stripe_line_items_from_order
        from db import (
            aggregate_cookie_counts,
            aggregate_minis_counts,
            aggregate_product_summary,
        )
        from notify import order_summary

        lines, subtotal, errors = build_line_items(
            {}, {}, {"chocolate_chip": 1, "macadamia": 2}
        )
        self.assertEqual(errors, [])
        self.assertEqual(subtotal, 3000)
        chip = next(line for line in lines if line["cookie_id"] == "chocolate_chip")
        self.assertEqual(chip["kind"], "minis_pack")
        self.assertEqual(chip["qty"], 1)
        self.assertEqual(chip["unit_price_cents"], 1000)
        self.assertEqual(chip["line_total_cents"], 1000)
        self.assertEqual(chip["minis_per_pack"], 8)
        self.assertEqual(chip["cookies_per_unit"], 0)
        self.assertEqual(chip["name"], "Brown Butter Chocolate Chip minis 8-pack")

        mixed, mixed_total, errors = build_line_items(
            {"peanut_butter": 1}, {}, {"salted_caramel": 1}
        )
        self.assertEqual(errors, [])
        self.assertEqual(mixed_total, 1400)

        _, _, errors = build_line_items({}, {"chocolate_chip": 5}, {"macadamia": 1})
        self.assertTrue(errors)
        _, _, errors = build_line_items({}, {}, {})
        self.assertTrue(errors)

        order = {
            "order_number": "SCC-TEST",
            "customer_name": "Ada",
            "customer_email": "ada@example.com",
            "customer_phone": "555",
            "fulfillment": "pickup",
            "pickup_date": "2026-11-20",
            "items": mixed,
            "total_cents": mixed_total,
        }
        counts = aggregate_cookie_counts([order])
        self.assertEqual(counts.get("salted_caramel", 0), 0)
        self.assertEqual(counts["peanut_butter"], 1)
        self.assertEqual(aggregate_minis_counts([order])["salted_caramel"], 1)
        summary = aggregate_product_summary([order])
        self.assertEqual(summary["minis_packs"], 1)
        self.assertEqual(summary["singles"], 1)
        self.assertEqual(summary["six_packs"], 0)

        slips = _order_item_summary(order)
        self.assertIn("1× Salted Caramel Chocolate Pecan minis 8-pack", slips)
        self.assertIn("1× White Miso Peanut Butter", slips)
        _, body = order_summary(order)
        self.assertIn("1× Salted Caramel Chocolate Pecan minis 8-pack", body)
        self.assertIn("$14.00", body)

        stripe_items = stripe_line_items_from_order(lines, 0)
        self.assertEqual(len(stripe_items), 2)
        chip_stripe = next(
            item
            for item in stripe_items
            if "Brown Butter" in item["price_data"]["product_data"]["name"]
        )
        self.assertEqual(chip_stripe["quantity"], 1)
        self.assertEqual(chip_stripe["price_data"]["unit_amount"], 1000)

    def test_order_flow_stores_minis_pack_and_charges_ten_dollars(self):
        import re
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch

        from app import app
        from config import Config
        from db import get_order_by_number, init_db
        from notify import order_summary
        from order_window import list_pickup_slots

        slot = next(item for item in list_pickup_slots() if item["available"])
        notified = []
        captured = {}

        def fake_create(**kwargs):
            captured["create"] = kwargs
            return SimpleNamespace(
                id="cs_test_minis",
                client_secret="cs_test_secret",
                status="open",
                payment_status="unpaid",
                metadata=kwargs.get("metadata") or {},
            )

        def fake_retrieve(session_id):
            self.assertEqual(session_id, "cs_test_minis")
            return SimpleNamespace(
                id="cs_test_minis",
                status="complete",
                payment_status="paid",
                metadata=captured["create"].get("metadata") or {},
            )

        app.config["TESTING"] = True
        client = app.test_client()
        old_db = Config.DATABASE_PATH
        old_secret = Config.STRIPE_SECRET_KEY
        old_pub = Config.STRIPE_PUBLISHABLE_KEY
        tmp = tempfile.TemporaryDirectory()
        try:
            Config.DATABASE_PATH = str(Path(tmp.name) / "orders.db")
            Config.STRIPE_SECRET_KEY = "sk_test_minis"
            Config.STRIPE_PUBLISHABLE_KEY = "pk_test_minis"
            init_db()

            page = client.get("/order")
            token = re.search(
                r'name="csrf_token" value="([^"]+)"',
                page.get_data(as_text=True),
            ).group(1)
            with (
                patch("app.stripe.checkout.Session.create", side_effect=fake_create),
                patch("app.stripe.checkout.Session.retrieve", side_effect=fake_retrieve),
                patch("app.notify_new_order", side_effect=notified.append),
            ):
                pay = client.post(
                    "/order",
                    data={
                        "csrf_token": token,
                        "customer_name": "Minis Tester",
                        "customer_email": "minis@example.com",
                        "customer_phone": "512-555-0100",
                        "fulfillment": "pickup",
                        "pickup_date": slot["date"],
                        "minis_chocolate_chip": "1",
                        "minis_peanut_butter": "2",
                    },
                )
                self.assertEqual(pay.status_code, 200)
                pay_html = pay.get_data(as_text=True)
                self.assertIn("$30.00", pay_html)
                self.assertIn("Checkout", pay_html)

                done = client.get(
                    "/order/return?session_id=cs_test_minis",
                    follow_redirects=True,
                )
            done_html = done.get_data(as_text=True)
            self.assertIn("Thank you", done_html)
            self.assertIn("1 × Brown Butter Chocolate Chip minis 8-pack ($10.00)", done_html)
            self.assertIn("2 × White Miso Peanut Butter minis 8-pack ($20.00)", done_html)
            self.assertIn("$30.00", done_html)

            stripe_items = captured["create"]["line_items"]
            self.assertEqual(
                sorted(
                    (
                        item["price_data"]["product_data"]["name"],
                        item["quantity"],
                        item["price_data"]["unit_amount"],
                    )
                    for item in stripe_items
                ),
                [
                    ("Brown Butter Chocolate Chip minis 8-pack", 1, 1000),
                    ("White Miso Peanut Butter minis 8-pack", 2, 1000),
                ],
            )

            order_number = re.search(r"SCC-\d{6}-[A-F0-9]+", pay_html).group(0)
            stored = get_order_by_number(order_number)
            self.assertEqual(stored["total_cents"], 3000)
            self.assertEqual(stored["payment_status"], "paid")
            kinds = {item["kind"] for item in stored["items"]}
            self.assertEqual(kinds, {"minis_pack"})
            self.assertEqual(len(notified), 1)
            _, email_body = order_summary(notified[0])
            self.assertIn("1× Brown Butter Chocolate Chip minis 8-pack", email_body)
            self.assertIn("2× White Miso Peanut Butter minis 8-pack", email_body)
            self.assertIn("Total: $30.00", email_body)
        finally:
            Config.DATABASE_PATH = old_db
            Config.STRIPE_SECRET_KEY = old_secret
            Config.STRIPE_PUBLISHABLE_KEY = old_pub
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()

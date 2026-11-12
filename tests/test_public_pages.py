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
        self.assertIn("Triangle Farmers Market", markets)
        self.assertIn("722 W. 46th St.", markets)
        self.assertIn("10am", markets)
        self.assertIn("2pm", markets)
        self.assertNotIn("Friday", markets)

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
        # Week of Monday Nov 16, 2026: Sat Nov 21 and Sun Nov 22.
        saturday = date(2026, 11, 21)
        sunday = date(2026, 11, 22)
        friday = date(2026, 11, 20)
        before = tz.localize(datetime(2026, 11, 18, 23, 59, 59))
        after = tz.localize(datetime(2026, 11, 19, 0, 0, 1))

        self.assertEqual(saturday.weekday(), 5)
        self.assertEqual(sunday.weekday(), 6)
        self.assertTrue(is_pickup_date_available(saturday, before)[0])
        self.assertTrue(is_pickup_date_available(sunday, before)[0])

        ok, reason = is_pickup_date_available(saturday, after)
        self.assertFalse(ok)
        self.assertTrue(reason)
        self.assertFalse(is_pickup_date_available(sunday, after)[0])

        ok, reason = is_pickup_date_available(friday, before)
        self.assertFalse(ok)
        self.assertIn("Saturdays and Sundays", reason)


class MinisPackTest(unittest.TestCase):
    """Single-flavor 8-packs at $10, drawn from the live catalog."""

    def test_home_hides_minis_and_order_lists_every_flavor(self):
        from app import app

        app.config["TESTING"] = True
        client = app.test_client()
        home = client.get("/").get_data(as_text=True)
        self.assertNotIn('id="minis-packs"', home)
        self.assertNotIn("Minis Packs", home)
        self.assertNotIn("minis-card", home)
        self.assertNotIn("Order Minis", home)
        for name in (
            "Brown Butter Chocolate Chip",
            "Macadamia White Chocolate",
            "Salted Caramel Chocolate Pecan",
            "White Miso Peanut Butter",
        ):
            self.assertIn(name, home)

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
        self.assertIn("Minis Packs", order)
        minis_order = order[order.index('id="minis-packs"'):order.index("Your info")]
        self.assertNotIn("qty-thumb", minis_order)
        self.assertNotIn("<img", minis_order)
        for name in (
            "Brown Butter Chocolate Chip",
            "Macadamia White Chocolate",
            "Salted Caramel Chocolate Pecan",
            "White Miso Peanut Butter",
        ):
            self.assertIn(name, minis_order)

    def test_minis_photos_return_when_the_flag_is_on(self):
        from app import app
        from config import Config

        app.config["TESTING"] = True
        client = app.test_client()
        previous = Config.SHOW_MINIS_PHOTOS
        Config.SHOW_MINIS_PHOTOS = True
        try:
            home = client.get("/").get_data(as_text=True)
            self.assertNotIn('id="minis-packs"', home)
            self.assertNotIn("has-photo", home)

            order = client.get("/order").get_data(as_text=True)
            minis_order = order[order.index('id="minis-packs"'):order.index("Your info")]
            self.assertIn("qty-thumb", minis_order)
            self.assertIn("images/chocolate_chip.jpg", minis_order)
        finally:
            Config.SHOW_MINIS_PHOTOS = previous

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
        self.assertNotIn('id="minis-packs"', home)
        self.assertIn("Future Flavor Crumble", home)
        self.assertNotIn("Brown Butter Chocolate Chip", home)
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


class WeekendScheduleTest(unittest.TestCase):
    """Saturday cottage fulfillment stays; Sunday is market pickup only."""

    def test_public_copy_drops_friday_and_names_the_market(self):
        from app import app

        app.config["TESTING"] = True
        client = app.test_client()
        paths = (
            "/",
            "/order",
            "/markets",
            "/story",
            "/blog/fresh-cookie-delivery-austin",
            "/blog/corporate-cookies-austin",
            "/blog/cookie-gift-box-austin",
            "/blog/what-does-miso-do-in-cookies",
        )
        for path in paths:
            html = client.get(path).get_data(as_text=True)
            with self.subTest(path=path):
                self.assertNotIn("Friday", html)
                self.assertIn("Triangle Farmers Market", html)
                self.assertIn("722 W. 46th", html)

        from flask import render_template

        with app.test_request_context("/"):
            closed = render_template("order_closed.html", message="Orders are open.")
        self.assertNotIn("Friday", closed)
        self.assertIn("722 W. 46th", closed)
        self.assertIn("10am", closed)

    def test_sunday_shares_saturday_batch_and_slots_skip_friday(self):
        from order_window import (
            batch_pickup_dates,
            batch_week_from_pickup_date,
            is_pickup_date_available,
            list_pickup_slots,
            same_week_status,
        )

        tz = pytz.timezone("America/Chicago")
        saturday = date(2026, 11, 21)
        sunday = date(2026, 11, 22)
        self.assertEqual(batch_week_from_pickup_date(saturday), "2026-11-16")
        self.assertEqual(
            batch_week_from_pickup_date(sunday),
            batch_week_from_pickup_date(saturday),
        )

        labels = batch_pickup_dates("2026-11-16")
        self.assertEqual(labels["saturday_iso"], "2026-11-21")
        self.assertEqual(labels["sunday_iso"], "2026-11-22")
        self.assertEqual(labels["friday_iso"], "2026-11-20")
        self.assertIn("Sunday", labels["sunday"])

        before = tz.localize(datetime(2026, 11, 18, 12, 0, 0))
        after = tz.localize(datetime(2026, 11, 19, 12, 0, 0))
        open_msg = same_week_status(before)["message"]
        closed_msg = same_week_status(after)["message"]
        self.assertIn("Sat/Sun", open_msg)
        self.assertIn("Saturday or Sunday", closed_msg)
        self.assertNotIn("Fri", open_msg)
        self.assertNotIn("friday", same_week_status(before))

        slots = list_pickup_slots(at=before)
        self.assertTrue(slots)
        self.assertTrue(all(slot["weekday"] in ("saturday", "sunday") for slot in slots))
        by_date = {slot["date"]: slot for slot in slots}
        self.assertEqual(by_date["2026-11-22"]["batch_week"], by_date["2026-11-21"]["batch_week"])
        self.assertFalse(by_date["2026-11-22"]["delivery_ok"])
        self.assertTrue(by_date["2026-11-21"]["delivery_ok"])
        self.assertNotIn("2026-11-20", by_date)

        early_sunday = date(2026, 11, 8)
        early_saturday = date(2026, 11, 7)
        early = tz.localize(datetime(2026, 11, 3, 12, 0, 0))
        ok, reason = is_pickup_date_available(early_sunday, early)
        self.assertFalse(ok)
        self.assertIn("November 15, 2026", reason)
        self.assertTrue(is_pickup_date_available(early_saturday, early)[0])

    def test_sort_places_sunday_after_saturday_and_keeps_legacy_friday(self):
        import tempfile
        from pathlib import Path

        from config import Config
        from db import create_order, init_db, list_orders

        old_db = Config.DATABASE_PATH
        tmp = tempfile.TemporaryDirectory()
        try:
            Config.DATABASE_PATH = str(Path(tmp.name) / "orders.db")
            init_db()
            created = (
                ("monday", "2026-11-01T01:00:00"),
                ("sunday", "2026-11-01T02:00:00"),
                ("saturday", "2026-11-01T03:00:00"),
                ("friday", "2026-11-01T04:00:00"),
            )
            for day, stamp in created:
                create_order(
                    {
                        "order_number": f"SCC-SORT-{day}",
                        "created_at": stamp,
                        "customer_name": day,
                        "customer_email": "ada@example.com",
                        "customer_phone": "512-555-0100",
                        "fulfillment": "pickup",
                        "pickup_day": day,
                        "pickup_date": "",
                        "address": "",
                        "notes": "",
                        "items": [],
                        "subtotal_cents": 400,
                        "delivery_fee_cents": 0,
                        "total_cents": 400,
                        "payment_method": "stripe",
                        "payment_status": "paid",
                        "batch_week": "2026-11-16",
                        "status": "confirmed",
                    }
                )
            ordered = [row["pickup_day"] for row in list_orders(batch_week="2026-11-16")]
            self.assertEqual(ordered, ["friday", "saturday", "sunday", "monday"])
        finally:
            Config.DATABASE_PATH = old_db
            tmp.cleanup()

    def test_server_rejects_friday_and_sunday_delivery(self):
        import re
        import tempfile
        from datetime import timedelta
        from pathlib import Path

        from app import app
        from config import Config
        from db import init_db

        sunday = date.today() + timedelta(days=10)
        while sunday.weekday() != 6:
            sunday += timedelta(days=1)
        if sunday < date(2026, 11, 15):
            sunday = date(2026, 11, 22)
        friday = date(2026, 11, 20)
        self.assertEqual(friday.weekday(), 4)

        app.config["TESTING"] = True
        client = app.test_client()
        old_db = Config.DATABASE_PATH
        old_secret = Config.STRIPE_SECRET_KEY
        old_pub = Config.STRIPE_PUBLISHABLE_KEY
        tmp = tempfile.TemporaryDirectory()
        try:
            Config.DATABASE_PATH = str(Path(tmp.name) / "orders.db")
            Config.STRIPE_SECRET_KEY = ""
            Config.STRIPE_PUBLISHABLE_KEY = ""
            init_db()

            def post(pickup_date, fulfillment):
                page = client.get("/order")
                token = re.search(
                    r'name="csrf_token" value="([^"]+)"',
                    page.get_data(as_text=True),
                ).group(1)
                data = {
                    "csrf_token": token,
                    "customer_name": "Pat",
                    "customer_email": "pat@example.com",
                    "customer_phone": "512-555-0199",
                    "fulfillment": fulfillment,
                    "pickup_date": pickup_date,
                    "pack_chocolate_chip": "6",
                }
                if fulfillment == "delivery":
                    data["delivery_zip"] = "78746"
                    data["address"] = "1 Main St, Austin, TX 78746"
                return client.post("/order", data=data).get_data(as_text=True)

            friday_html = post(friday.isoformat(), "pickup")
            self.assertIn("Friday pickup and delivery are no longer available", friday_html)

            sunday_flash = (
                "Sunday is pickup only at the Triangle Farmers Market "
                "(Triangle Commons Pocket Park, 722 W. 46th St., Austin, TX 78751, 10am"
            )
            sunday_html = post(sunday.isoformat(), "delivery")
            self.assertIn(sunday_flash, sunday_html)
            self.assertIn("Delivery is not available on Sunday", sunday_html)

            def accepted(html):
                self.assertIn("Card payment is required", html)
                self.assertNotIn(sunday_flash, html)
                self.assertNotIn("no longer available", html)
                self.assertNotIn("already passed", html)
                self.assertNotIn("later weekend", html)
                self.assertNotIn("market pickup starts", html)
                self.assertNotIn("only available on Saturdays and Sundays", html)

            accepted(post(sunday.isoformat(), "pickup"))
            saturday = sunday - timedelta(days=1)
            self.assertEqual(saturday.weekday(), 5)
            accepted(post(saturday.isoformat(), "delivery"))
        finally:
            Config.DATABASE_PATH = old_db
            Config.STRIPE_SECRET_KEY = old_secret
            Config.STRIPE_PUBLISHABLE_KEY = old_pub
            tmp.cleanup()

    def test_admin_and_success_keep_legacy_friday_and_show_sunday(self):
        import tempfile
        from pathlib import Path

        from app import app
        from config import Config
        from db import create_order, init_db

        app.config["TESTING"] = True
        client = app.test_client()
        old_db = Config.DATABASE_PATH
        old_secret = Config.PUSH_REGISTER_SECRET
        tmp = tempfile.TemporaryDirectory()
        try:
            Config.DATABASE_PATH = str(Path(tmp.name) / "orders.db")
            Config.PUSH_REGISTER_SECRET = "test-weekend-gate"
            init_db()
            orders = [
                ("SCC-FRI", "friday", "", "2026-11-01T01:00:00"),
                ("SCC-SAT", "saturday", "2026-11-21", "2026-11-01T02:00:00"),
                ("SCC-SUN", "sunday", "", "2026-11-01T03:00:00"),
            ]
            for number, day, pickup_date, stamp in orders:
                create_order(
                    {
                        "order_number": number,
                        "created_at": stamp,
                        "customer_name": day,
                        "customer_email": "ada@example.com",
                        "customer_phone": "512-555-0100",
                        "fulfillment": "pickup",
                        "pickup_day": day,
                        "pickup_date": pickup_date,
                        "address": "",
                        "notes": "",
                        "items": [],
                        "subtotal_cents": 400,
                        "delivery_fee_cents": 0,
                        "total_cents": 400,
                        "payment_method": "stripe",
                        "payment_status": "paid",
                        "batch_week": "2026-11-16",
                        "status": "confirmed",
                    }
                )

            with client.session_transaction() as sess:
                sess["admin"] = True
            headers = {"X-SCC-App": "test-weekend-gate"}
            dashboard = client.get("/admin?batch=2026-11-16", headers=headers)
            self.assertEqual(dashboard.status_code, 200)
            html = dashboard.get_data(as_text=True)
            self.assertIn("Saturday pickups/deliveries", html)
            self.assertIn("Sunday market pickups", html)
            self.assertIn("Friday pickups/deliveries (earlier orders)", html)
            self.assertIn("Fri · Nov 20", html)
            self.assertIn("Sun · Nov 22", html)
            self.assertIn("Saturday, November 21, 2026", html)

            printed = client.get(
                "/admin/print/orders?batch=2026-11-16", headers=headers
            )
            self.assertEqual(printed.status_code, 200)
            sheet = printed.get_data(as_text=True)
            self.assertIn("FRIDAY (Friday, November 20)", sheet)
            self.assertIn("SUNDAY (Sunday, November 22)", sheet)
            self.assertIn("SATURDAY, NOVEMBER 21, 2026", sheet)

            success = client.get("/order/success/SCC-SUN")
            self.assertEqual(success.status_code, 200)
            thanks = success.get_data(as_text=True)
            self.assertIn("Sunday, November 22", thanks)
            self.assertIn("Triangle Commons Pocket Park", thanks)
            self.assertIn("722 W. 46th St.", thanks)
            self.assertIn("10am", thanks)
            self.assertIn("no Sunday delivery", thanks)

            legacy = client.get("/order/success/SCC-FRI").get_data(as_text=True)
            self.assertIn("Friday, November 20", legacy)
            self.assertNotIn("Saturday pickup is at our cottage", legacy)
        finally:
            Config.DATABASE_PATH = old_db
            Config.PUSH_REGISTER_SECRET = old_secret
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()

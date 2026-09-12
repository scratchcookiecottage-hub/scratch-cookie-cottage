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


class LivePythonAnywhereBlogSyncTest(unittest.TestCase):
    """Lock the posts/images/stretch fix that are live on www.scratchcookiecottage.com."""

    LIVE_SLUGS = {
        "what-does-miso-do-in-cookies",
        "cookie-gift-box-austin",
        "fresh-cookie-delivery-austin",
        "corporate-cookies-austin",
    }
    LIVE_IMAGES = {
        "white-miso-peanut-butter-cookie-austin.jpg",
        "cottage-kitchen-mise-en-place.jpg",
        "austin-cookie-gift-box-macadamia.jpg",
        "fresh-cookie-delivery-austin.jpg",
        "corporate-cookies-austin.jpg",
    }
    SHOTS_DOC_ID = "1OrB2p3p2OdTih9LBm80MdNOscDEkgrX-Xry-bP8OCdY"

    def test_only_the_four_live_posts_are_published(self):
        import blog

        posts = blog.list_posts()
        self.assertEqual({post["slug"] for post in posts}, self.LIVE_SLUGS)
        for post in posts:
            self.assertFalse(post["draft"], post["slug"])
            self.assertEqual(post["date"].isoformat(), "2026-09-04")
        for missing in (
            "small-batch",
            "sweet-and-salty",
            "texture-guide",
        ):
            self.assertIsNone(blog.get_post(missing))

    def test_live_blog_images_are_present(self):
        for name in self.LIVE_IMAGES:
            path = ROOT / "static" / "images" / "blog" / name
            self.assertTrue(path.is_file(), name)
            self.assertGreater(path.stat().st_size, 0, name)

    def test_blog_templates_do_not_force_hero_size(self):
        post = (ROOT / "templates" / "blog" / "post.html").read_text(encoding="utf-8")
        index = (ROOT / "templates" / "blog" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('width="800"', post)
        self.assertNotIn('height="480"', post)
        self.assertNotIn('width="400"', index)
        self.assertNotIn('height="240"', index)
        self.assertIn('<img src="{{ post.image }}" alt="{{ post.title }}">', post)
        self.assertIn('<img src="{{ post.image }}" alt="">', index)

    def test_blog_css_keeps_natural_hero_aspect(self):
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn("object-fit: contain;", css)
        self.assertIn("max-height: min(70vh, 720px);", css)
        self.assertIn(".blog-card-photo img { height: 100%; min-height: 180px; object-fit: cover;", css)

    def test_factory_shots_doc_defaults_to_live_id(self):
        config_src = (ROOT / "config.py").read_text(encoding="utf-8")
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn(self.SHOTS_DOC_ID, config_src)
        self.assertNotIn("1QbKiuTuagaNv37k0xSvkWJdsfuP-0iFcXnhRkteI8ec", config_src)
        self.assertIn(f"FACTORY_SHOTS_DOC_ID={self.SHOTS_DOC_ID}", example)
        self.assertIn(self.SHOTS_DOC_ID, example)
        self.assertNotIn("1QbKiuTuagaNv37k0xSvkWJdsfuP-0iFcXnhRkteI8ec", example)


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


if __name__ == "__main__":
    unittest.main()

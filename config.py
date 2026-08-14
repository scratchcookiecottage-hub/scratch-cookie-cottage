import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

    TIMEZONE = os.getenv("TIMEZONE", "America/Chicago")
    # Weekly pickup cutoff: after this instant, same-week Fri/Sat cannot be selected.
    # Wednesday=2, hour/minute local to TIMEZONE (CST/CDT for America/Chicago).
    CUTOFF_WEEKDAY = _int("CUTOFF_WEEKDAY", 2)  # Wednesday
    CUTOFF_HOUR = _int("CUTOFF_HOUR", 23)
    CUTOFF_MINUTE = _int("CUTOFF_MINUTE", 59)
    # How many weeks of Friday/Saturday slots to show on the calendar
    PICKUP_WEEKS_AHEAD = _int("PICKUP_WEEKS_AHEAD", 8)

    # Individual cookie and half-dozen (6-pack) prices in cents
    PRICE_INDIVIDUAL_CENTS = _int("PRICE_INDIVIDUAL_CENTS", 400)  # $4.00
    PRICE_SIX_PACK_CENTS = _int("PRICE_SIX_PACK_CENTS", 2000)  # $20.00
    DELIVERY_FEE_CENTS = _int("DELIVERY_FEE_CENTS", 0)

    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    # Merch (Printify Pop-Up Store) — available 24/7 via third party
    PRINTIFY_SHOP_URL = os.getenv(
        "PRINTIFY_SHOP_URL",
        "https://scratchcookiecottage.printify.me/",
    ).rstrip("/") + "/"
    # Optional: deep Printify API (product catalog / order submit). Leave blank to link out only.
    PRINTIFY_API_TOKEN = os.getenv("PRINTIFY_API_TOKEN", "").strip()
    PRINTIFY_SHOP_ID = os.getenv("PRINTIFY_SHOP_ID", "").strip()

    DATABASE_PATH = os.getenv(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(__file__), "data", "orders.db"),
    )

    @classmethod
    def stripe_enabled(cls) -> bool:
        return bool(cls.STRIPE_SECRET_KEY and cls.STRIPE_PUBLISHABLE_KEY)

    @classmethod
    def printify_api_enabled(cls) -> bool:
        return bool(cls.PRINTIFY_API_TOKEN and cls.PRINTIFY_SHOP_ID)

    @classmethod
    def cookie_catalog(cls) -> dict:
        """id -> display name, description, image urls"""
        return {
            "chocolate_chip": {
                "name": "Brown Butter Chocolate Chip",
                "description": "Rich, nutty brown butter with classic chocolate chips. Soft centers, golden edges.",
                "img_default": "images/chocolate_chip.jpg",
                "img_hover": "images/chocolate_chip_alt.jpg",
            },
            "macadamia": {
                "name": "Macadamia White Chocolate",
                "description": "Buttery macadamia nuts and smooth white chocolate in every bite.",
                "img_default": "images/macadamia.jpg",
                "img_hover": "images/macadamia_alt.jpg",
            },
            "salted_caramel": {
                "name": "Salted Caramel Chocolate Pecan",
                "description": "Gooey caramel, chocolate, and toasted pecans with a kiss of sea salt.",
                "img_default": "images/salted_caramel.jpg",
                "img_hover": "images/salted_caramel_alt.jpg",
            },
            "peanut_butter": {
                "name": "White Miso Peanut Butter",
                "description": "Creamy peanut butter with a gentle savory depth from white miso.",
                "img_default": "images/peanut_butter.jpg",
                "img_hover": "images/peanut_butter_alt.jpg",
            },
        }

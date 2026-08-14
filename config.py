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
                "img_default": "https://scontent-hou1-1.xx.fbcdn.net/v/t39.30808-6/771844380_122107801077414493_8097330256772646541_n.jpg?stp=dst-jpg_tt6&cstp=mx1216x1171&ctp=s1216x1171&_nc_cat=102&ccb=1-7&_nc_sid=127cfc&_nc_ohc=kulWUEjlmD4Q7kNvwGyyGoE&_nc_oc=AdpIrfjDaGPyOtSuiAro0TIVEsIQ7bLtEW8BRLAykf1jlwaGaUu2panE6UDkwthBEFbkQWqrDX3mrM3d1eKJC57u&_nc_zt=23&_nc_ht=scontent-hou1-1.xx&_nc_gid=ISN1G3P0Cw9SxtszMbyu_g&_nc_ss=7b2a8&oh=00_AQEfwsupbSJuFXxbuYV9NB939pjOo5kdOyFE3TVIxfxWmQ&oe=6A81995E",
                "img_hover": "https://scontent-hou1-1.xx.fbcdn.net/v/t39.30808-6/773580837_122107572291414493_5895687146750392091_n.jpg?stp=dst-jpg_tt6&cstp=mx1027x1027&ctp=s1027x1027&_nc_cat=104&ccb=1-7&_nc_sid=833d8c&_nc_ohc=jTM62DIscfgQ7kNvwEQHhxA&_nc_oc=Adpx4mxTfxSrYktRY_37fAijO9P-TppsOr34eJ65xy2p2EFB5NLYaAODeCVwa5ScuQGG_ASCqwdownqhF6rSz40L&_nc_zt=23&_nc_ht=scontent-hou1-1.xx&_nc_gid=PSUmQINS5IQg60wX99a5_w&_nc_ss=7b2a8&oh=00_AQFzgoYbCspHdvIC7J6aBeo3wHpBb-qlfqdRDZ1UKC33Yg&oe=6A819E88",
            },
            "macadamia": {
                "name": "Macadamia White Chocolate",
                "description": "Buttery macadamia nuts and smooth white chocolate in every bite.",
                "img_default": "https://scontent-hou1-1.xx.fbcdn.net/v/t39.30808-6/765929390_122107801035414493_2576688302104320753_n.jpg?stp=dst-jpg_tt6&cstp=mx1129x1102&ctp=s1129x1102&_nc_cat=111&ccb=1-7&_nc_sid=127cfc&_nc_ohc=iiMh4YAcL7UQ7kNvwH0Fza3&_nc_oc=AdrZch64C_YGIuWb0As_QM4W_BOjpdoQZsmzdPq025W3KNr4wwacQ2NuIyrwkNreEgf0KXbWB3R-hOvvgOPHdBuw&_nc_zt=23&_nc_ht=scontent-hou1-1.xx&_nc_gid=barCj6F9gXczR66ytsMVbw&_nc_ss=7b2a8&oh=00_AQH4EDoKFuMHLOYoVBPm1Y3KLzLRwRdTllfJtIO_Jef4xg&oe=6A8188F2",
                "img_hover": "https://scontent-hou1-1.xx.fbcdn.net/v/t39.30808-6/763018606_122104573833414493_1072829447698767456_n.jpg?stp=dst-jpg_tt6&cstp=mx1168x880&ctp=s1168x880&_nc_cat=106&ccb=1-7&_nc_sid=127cfc&_nc_ohc=XCEz2uADg44Q7kNvwFo6syR&_nc_oc=AdrGilUvYzDVBwEAIkwZ2tmVii4cyplqHEQE1nA4DPFEUhEpcSwdPEQtbKU9sb0bo3HVNCt5k90TfFOSejECNWhb&_nc_zt=23&_nc_ht=scontent-hou1-1.xx&_nc_gid=9voSWnjxFcTCsLMi5Ri43Q&_nc_ss=7b2a8&oh=00_AQERCeYfaMUmFgonzR811sbqeB-5Jmqqdy0eKUi2z2NrUw&oe=6A7E4F02",
            },
            "salted_caramel": {
                "name": "Salted Caramel Chocolate Pecan",
                "description": "Gooey caramel, chocolate, and toasted pecans with a kiss of sea salt.",
                "img_default": "",
                "img_hover": "",
            },
            "peanut_butter": {
                "name": "White Miso Peanut Butter",
                "description": "Creamy peanut butter with a gentle savory depth from white miso.",
                "img_default": "https://scontent-hou1-1.xx.fbcdn.net/v/t39.30808-6/768408728_122107801023414493_1300102988743959417_n.jpg?stp=dst-jpg_tt6&cstp=mx1145x1101&ctp=s1145x1101&_nc_cat=109&ccb=1-7&_nc_sid=127cfc&_nc_ohc=B8FJhFvP_6sQ7kNvwESKmf6&_nc_oc=AdqHk9AVcGTan1HJsmid_xzrEhcmxfPrUjQR51OJ71WWpq5wvJJf4rhv0DIcogOu06-vaUdhf4QeDmVfyMKK5dS5&_nc_zt=23&_nc_ht=scontent-hou1-1.xx&_nc_gid=ahMBgGF5pZMz24yIB4oRyA&_nc_ss=7b2a8&oh=00_AQEeMy2EZLKZLoVLN0NTtSzF7wBoS5pbVb6LMy9I3_pYQw&oe=6A81945C",
                "img_hover": "https://scontent-hou1-1.xx.fbcdn.net/v/t39.30808-6/760033673_122102208255414493_8939993557948681595_n.jpg?stp=dst-jpegr_tt6&cstp=mx1542x2048&ctp=s1542x2048&_nc_cat=103&ccb=1-7&_nc_sid=cc71e4&_nc_ohc=GB9V2NcDN8sQ7kNvwFepH17&_nc_oc=AdrEhjm5lzw4mxAUIXmIbnYnhLkFum0IsFBXFUWPXW7O66HNM0owWGtGcKMmqp2Hc2mZIE9gNsKfTs0YFHxQrzs6&_nc_zt=23&se=-1&_nc_ht=scontent-hou1-1.xx&_nc_gid=SkMgguI56auPKKqATHYGxw&_nc_ss=7b2a8&oh=00_AQHlKWOfJfl8fhYTp0b2HbdlSWv-TLhE9zpzKeChwq6DVA&oe=6A7E42E0",
            },
        }

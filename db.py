import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from config import Config

SEASONAL_ID = "seasonal"
SEASONAL_UPLOAD_REL = "images/seasonal"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    import os

    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                fulfillment TEXT NOT NULL,
                pickup_day TEXT,
                pickup_date TEXT,
                address TEXT,
                notes TEXT,
                items_json TEXT NOT NULL,
                subtotal_cents INTEGER NOT NULL,
                delivery_fee_cents INTEGER NOT NULL DEFAULT 0,
                total_cents INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                payment_status TEXT NOT NULL,
                stripe_session_id TEXT,
                batch_week TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new'
            );
            CREATE INDEX IF NOT EXISTS idx_orders_batch ON orders(batch_week);
            CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
            """
        )
        # Lightweight migrations for existing DBs
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(orders)").fetchall()
        }
        if "pickup_day" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN pickup_day TEXT")
        if "pickup_date" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN pickup_date TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS push_tokens (
                token TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seasonal_listing (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                ingredients TEXT NOT NULL DEFAULT '',
                allergens TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seasonal_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS factory_shots (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                body TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        existing = conn.execute(
            "SELECT id FROM seasonal_listing WHERE id = 1"
        ).fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO seasonal_listing
                    (id, name, description, ingredients, allergens, active, updated_at)
                VALUES (1, ?, ?, '', '', 1, ?)
                """,
                (
                    "Seasonal Rotation",
                    "This week’s guest cookie. The flavor changes — check the name and photos.",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


def create_order(data: dict[str, Any]) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO orders (
                order_number, created_at, customer_name, customer_email, customer_phone,
                fulfillment, pickup_day, pickup_date, address, notes, items_json,
                subtotal_cents, delivery_fee_cents, total_cents, payment_method,
                payment_status, stripe_session_id, batch_week, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["order_number"],
                data["created_at"],
                data["customer_name"],
                data["customer_email"],
                data["customer_phone"],
                data["fulfillment"],
                data.get("pickup_day") or "",
                data.get("pickup_date") or "",
                data.get("address") or "",
                data.get("notes") or "",
                json.dumps(data["items"]),
                data["subtotal_cents"],
                data["delivery_fee_cents"],
                data["total_cents"],
                data["payment_method"],
                data["payment_status"],
                data.get("stripe_session_id"),
                data["batch_week"],
                data.get("status", "new"),
            ),
        )
        return int(cur.lastrowid)


def update_order_payment(
    order_id: int,
    *,
    payment_status: str,
    stripe_session_id: Optional[str] = None,
    status: Optional[str] = None,
) -> None:
    with get_db() as conn:
        if status is not None:
            conn.execute(
                """
                UPDATE orders
                SET payment_status = ?, stripe_session_id = COALESCE(?, stripe_session_id), status = ?
                WHERE id = ?
                """,
                (payment_status, stripe_session_id, status, order_id),
            )
        else:
            conn.execute(
                """
                UPDATE orders
                SET payment_status = ?, stripe_session_id = COALESCE(?, stripe_session_id)
                WHERE id = ?
                """,
                (payment_status, stripe_session_id, order_id),
            )


def get_order_by_number(order_number: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_number = ?", (order_number,)
        ).fetchone()
    return _row_to_order(row) if row else None


def get_order_by_id(order_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return _row_to_order(row) if row else None


def get_order_by_stripe_session(session_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE stripe_session_id = ?", (session_id,)
        ).fetchone()
    return _row_to_order(row) if row else None


def list_orders(
    batch_week: Optional[str] = None,
    paid_only: bool = True,
) -> list[dict]:
    """
    Orders for the admin bake sheet and pick list.
    Unpaid / failed / abandoned checkouts are excluded so they are not baked.
    """
    with get_db() as conn:
        sql = "SELECT * FROM orders WHERE 1=1"
        params: list[Any] = []
        if batch_week:
            sql += " AND batch_week = ?"
            params.append(batch_week)
        if paid_only:
            sql += " AND payment_status = 'paid' AND status != 'cancelled'"
        sql += " ORDER BY COALESCE(NULLIF(pickup_date, ''), '9999-99-99') ASC, CASE pickup_day WHEN 'friday' THEN 0 WHEN 'saturday' THEN 1 ELSE 2 END, created_at ASC"
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_order(r) for r in rows]


def list_batch_weeks() -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT batch_week FROM orders
            WHERE payment_status = 'paid' AND status != 'cancelled'
            ORDER BY batch_week DESC
            """
        ).fetchall()
    return [r["batch_week"] for r in rows]


def save_push_token(token: str) -> None:
    token = (token or "").strip()
    if not token:
        return
    from datetime import datetime, timezone

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO push_tokens (token, created_at) VALUES (?, ?)
            ON CONFLICT(token) DO UPDATE SET created_at = excluded.created_at
            """,
            (token, datetime.now(timezone.utc).isoformat()),
        )


def list_push_tokens() -> list[str]:
    with get_db() as conn:
        rows = conn.execute("SELECT token FROM push_tokens").fetchall()
    return [r["token"] for r in rows]


def delete_push_token(token: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM push_tokens WHERE token = ?", (token,))


def set_order_status(order_id: int, status: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


def seasonal_upload_dir() -> str:
    root = os.path.join(os.path.dirname(__file__), "static", "images", "seasonal")
    os.makedirs(root, exist_ok=True)
    return root


def get_seasonal() -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM seasonal_listing WHERE id = 1").fetchone()
        images = conn.execute(
            "SELECT id, filename, sort_order FROM seasonal_images ORDER BY sort_order ASC, id ASC"
        ).fetchall()
    if not row:
        return {
            "id": 1,
            "name": "Seasonal Rotation",
            "description": "",
            "ingredients": "",
            "allergens": "",
            "active": False,
            "updated_at": "",
            "images": [],
        }
    d = dict(row)
    d["active"] = bool(d.get("active"))
    d["images"] = [
        {
            "id": img["id"],
            "filename": img["filename"],
            "path": f"{SEASONAL_UPLOAD_REL}/{img['filename']}",
        }
        for img in images
    ]
    return d


def save_seasonal(
    *,
    name: str,
    description: str,
    ingredients: str,
    allergens: str,
    active: bool,
) -> None:
    name = (name or "").strip() or "Seasonal Rotation"
    with get_db() as conn:
        conn.execute(
            """
            UPDATE seasonal_listing
            SET name = ?, description = ?, ingredients = ?, allergens = ?,
                active = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                name,
                (description or "").strip(),
                (ingredients or "").strip(),
                (allergens or "").strip(),
                1 if active else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def add_seasonal_image(filename: str) -> None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) AS m FROM seasonal_images"
        ).fetchone()
        nxt = int(row["m"]) + 1 if row else 0
        conn.execute(
            "INSERT INTO seasonal_images (filename, sort_order) VALUES (?, ?)",
            (filename, nxt),
        )


def delete_seasonal_image(image_id: int) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT filename FROM seasonal_images WHERE id = ?", (image_id,)
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM seasonal_images WHERE id = ?", (image_id,))
    return row["filename"]


def store_catalog(*, include_inactive: bool = False) -> dict:
    """Core flavors plus the seasonal listing when it should be shown."""
    catalog: dict = {}
    seasonal = get_seasonal()
    show = include_inactive or seasonal.get("active")
    if show:
        paths = [img["path"] for img in seasonal.get("images") or []]
        catalog[SEASONAL_ID] = {
            "name": seasonal["name"],
            "description": seasonal.get("description") or "",
            "img_default": paths[0] if paths else "",
            "img_hover": paths[1] if len(paths) > 1 else "",
            "images": paths,
            "ingredients": seasonal.get("ingredients") or "",
            "allergens": seasonal.get("allergens") or "",
            "seasonal": True,
            "active": bool(seasonal.get("active")),
        }
    catalog.update(Config.cookie_catalog())
    return catalog


def get_factory_shots() -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT body, updated_at FROM factory_shots WHERE id = 1").fetchone()
    if not row:
        return {"body": "", "updated_at": ""}
    return {"body": row["body"] or "", "updated_at": row["updated_at"] or ""}


def save_factory_shots(body: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO factory_shots (id, body, updated_at) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET body = excluded.body, updated_at = excluded.updated_at
            """,
            ((body or "").strip(), now),
        )


def seasonal_label_flavor() -> Optional[dict]:
    seasonal = get_seasonal()
    name = (seasonal.get("name") or "").strip()
    if not name:
        return None
    allergens = (seasonal.get("allergens") or "").strip()
    if allergens and not allergens.lower().startswith("contains"):
        contains = f"Contains: {allergens}"
    elif allergens:
        contains = allergens
    else:
        contains = "Contains: See ingredients"
    return {
        "id": SEASONAL_ID,
        "name": name,
        "contains": contains,
        "ingredients": (seasonal.get("ingredients") or "").strip(),
    }


def _row_to_order(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["items"] = json.loads(d.pop("items_json"))
    return d


def aggregate_cookie_counts(orders: list[dict]) -> dict[str, int]:
    """
    Sum individual cookies by flavor for baking.
    Each line item contributes qty * cookies_per_unit (1 for singles, 1 already
    expanded per flavor in pack lines).
    """
    totals: dict[str, int] = {}
    for order in orders:
        for item in order["items"]:
            if item.get("kind") == "six_pack_fee":
                continue
            key = item.get("cookie_id") or item.get("id")
            if not key:
                continue
            # qty is number of cookies of this flavor (singles or pack allocations)
            cookies = int(item["qty"]) * int(item.get("cookies_per_unit", 1))
            totals[key] = totals.get(key, 0) + cookies
    return totals


def aggregate_product_summary(orders: list[dict]) -> dict[str, int]:
    """High-level product counts: singles cookies, six-packs, etc."""
    singles = 0
    six_packs = 0
    for order in orders:
        for item in order["items"]:
            kind = item.get("kind", "single")
            if kind == "single":
                singles += int(item["qty"])
            elif kind == "six_pack_cookie":
                # counted per cookie; pack count from six_pack_fee lines
                pass
            elif kind == "six_pack_fee":
                six_packs += int(item["qty"])
    # If older orders only have pack cookies without fee line, derive packs
    if six_packs == 0:
        pack_cookies = 0
        for order in orders:
            for item in order["items"]:
                if item.get("kind") == "six_pack_cookie":
                    pack_cookies += int(item["qty"])
        six_packs = pack_cookies // 6
    return {"singles": singles, "six_packs": six_packs}

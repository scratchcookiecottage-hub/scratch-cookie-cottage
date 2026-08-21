import hmac
import secrets
import time
from functools import wraps

from flask import abort, request, session

from db import get_db


CSRF_EXEMPT_PATHS = {"/stripe/webhook", "/api/push-token"}


def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def csrf_ok() -> bool:
    sent = (request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or "").strip()
    expected = (session.get("_csrf") or "").strip()
    if not sent or not expected:
        return False
    return hmac.compare_digest(sent, expected)


def safe_equal(left: str, right: str) -> bool:
    a = (left or "").encode("utf-8")
    b = (right or "").encode("utf-8")
    if len(a) != len(b):
        hmac.compare_digest(b, b)
        return False
    return hmac.compare_digest(a, b)


def client_ip() -> str:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (request.remote_addr or "unknown")


def too_many(bucket: str, limit: int, window_seconds: int) -> bool:
    key = f"{bucket}:{client_ip()}"
    now = int(time.time())
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY,
                window_start INTEGER NOT NULL,
                count INTEGER NOT NULL
            )
            """
        )
        row = conn.execute(
            "SELECT window_start, count FROM rate_limits WHERE key = ?", (key,)
        ).fetchone()
        if not row or now - int(row["window_start"]) >= window_seconds:
            conn.execute(
                "INSERT OR REPLACE INTO rate_limits (key, window_start, count) VALUES (?, ?, 1)",
                (key, now),
            )
            return False
        count = int(row["count"]) + 1
        conn.execute(
            "UPDATE rate_limits SET count = ? WHERE key = ?", (count, key)
        )
        return count > limit


def apply_security(app):
    https = (app.config.get("PUBLIC_BASE_URL") or "").startswith("https://")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = https
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def _csrf_guard():
        if request.method != "POST":
            return
        if request.path in CSRF_EXEMPT_PATHS:
            return
        if not csrf_ok():
            abort(400, description="Your form expired. Refresh the page and try again.")

    @app.after_request
    def _headers(resp):
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if https:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

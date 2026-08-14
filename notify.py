import logging
import smtplib
from email.message import EmailMessage

from config import Config

log = logging.getLogger(__name__)


def money(cents: int) -> str:
    return f"${cents / 100:.2f}"


def _item_lines(order: dict) -> str:
    lines = []
    for item in order.get("items") or []:
        if item.get("kind") == "six_pack_fee" and int(item.get("line_total_cents") or 0) <= 0:
            continue
        qty = item.get("qty", "")
        name = item.get("name") or item.get("cookie_id") or "Item"
        if item.get("kind") == "six_pack_fee":
            lines.append(str(name))
        else:
            lines.append(f"{qty}× {name}")
    return "\n".join(lines) or "(no items)"


def order_summary(order: dict) -> tuple[str, str]:
    pickup = order.get("pickup_date") or order.get("pickup_day") or "—"
    fulfillment = (order.get("fulfillment") or "pickup").capitalize()
    title = f"New order {order.get('order_number', '')}"
    body = (
        f"{order.get('customer_name', '')} placed a paid order.\n\n"
        f"Order: {order.get('order_number', '')}\n"
        f"{fulfillment} date: {pickup}\n"
        f"Phone: {order.get('customer_phone', '')}\n"
        f"Email: {order.get('customer_email', '')}\n"
    )
    if order.get("address"):
        body += f"Address: {order['address']}\n"
    body += f"\n{_item_lines(order)}\n\nTotal: {money(int(order.get('total_cents') or 0))}\n"
    return title, body


def send_admin_email(order: dict) -> None:
    to_addr = Config.ADMIN_NOTIFY_EMAIL
    user = Config.SMTP_USER
    password = Config.SMTP_PASSWORD
    if not to_addr or not user or not password:
        return
    title, body = order_summary(order)
    msg = EmailMessage()
    msg["Subject"] = f"Scratch Cookie Cottage — {title}"
    msg["From"] = Config.SMTP_FROM or user
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
    except Exception:
        log.exception("Admin email failed")


def send_admin_push(order: dict) -> None:
    cred_path = Config.FIREBASE_CREDENTIALS
    if not cred_path:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError:
        log.warning("firebase-admin is not installed")
        return

    from db import delete_push_token, list_push_tokens

    tokens = list_push_tokens()
    if not tokens:
        return

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
    except Exception:
        log.exception("Firebase init failed")
        return

    title, body = order_summary(order)
    short = body.split("\n\n", 1)[0]
    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(
            title=title,
            body=short.replace("\n", " · "),
        ),
        data={
            "order_number": str(order.get("order_number") or ""),
        },
        android=messaging.AndroidConfig(priority="high"),
    )
    try:
        result = messaging.send_each_for_multicast(message)
    except Exception:
        log.exception("FCM send failed")
        return
    for idx, resp in enumerate(result.responses):
        if resp.success:
            continue
        err = str(getattr(resp, "exception", "") or "")
        if "not-found" in err.lower() or "registration-token" in err.lower():
            delete_push_token(tokens[idx])


def notify_new_order(order: dict) -> None:
    if not order:
        return
    send_admin_email(order)
    send_admin_push(order)

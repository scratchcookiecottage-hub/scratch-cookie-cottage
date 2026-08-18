import os
import secrets
from datetime import date, datetime
from functools import wraps
from io import BytesIO

import stripe
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from config import Config
from db import (
    SEASONAL_ID,
    add_seasonal_image,
    aggregate_cookie_counts,
    aggregate_product_summary,
    create_order,
    delete_seasonal_image,
    get_order_by_id,
    get_order_by_number,
    get_order_by_stripe_session,
    get_seasonal,
    init_db,
    list_batch_weeks,
    list_orders,
    list_push_tokens,
    save_push_token,
    save_seasonal,
    seasonal_label_flavor,
    seasonal_upload_dir,
    set_order_status,
    store_catalog,
    update_order_payment,
)
from notify import notify_new_order, send_admin_push
from order_window import (
    batch_pickup_dates,
    batch_week_from_pickup_date,
    batch_week_label,
    current_batch_week,
    cutoff_display,
    format_pickup_date,
    is_pickup_date_available,
    list_pickup_slots,
    now_local,
    same_week_status,
    window_status,
)

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

if Config.stripe_enabled():
    stripe.api_key = Config.STRIPE_SECRET_KEY


def money(cents: int) -> str:
    return f"${cents / 100:.2f}"


app.jinja_env.filters["money"] = money
app.jinja_env.filters["pickup_date_fmt"] = format_pickup_date
app.jinja_env.globals["batch_week_label"] = batch_week_label
app.jinja_env.globals["cutoff_display"] = cutoff_display
app.jinja_env.globals["stripe_enabled"] = Config.stripe_enabled
app.jinja_env.globals["printify_shop_url"] = Config.PRINTIFY_SHOP_URL


@app.context_processor
def inject_globals():
    _, msg = window_status()
    sw = same_week_status()
    return {
        "order_open": True,  # cookies can be ordered anytime
        "window_message": msg,
        "same_week_open": sw["same_week_open"],
        "business_name": "Scratch Cookie Cottage",
        "catalog": store_catalog(),
        "price_individual": Config.PRICE_INDIVIDUAL_CENTS,
        "price_six_pack": Config.PRICE_SIX_PACK_CENTS,
        "delivery_zips": Config.DELIVERY_ZIPS,
    }


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def parse_qty_form(prefix: str) -> dict[str, int]:
    """Read qty fields named {prefix}_{cookie_id}."""
    catalog = store_catalog()
    items = {}
    for cookie_id in catalog:
        raw = request.form.get(f"{prefix}_{cookie_id}", "0") or "0"
        try:
            qty = int(raw)
        except ValueError:
            qty = 0
        if qty < 0:
            qty = 0
        if qty > 100:
            qty = 100
        if qty > 0:
            items[cookie_id] = qty
    return items


def build_line_items(
    singles: dict[str, int], pack: dict[str, int]
) -> tuple[list[dict], int, list[str]]:
    """
    Build order line items from individual cookies and a build-your-own 6-pack mix.

    Pack rules: total cookies across flavors must be 0 or a multiple of 6.
    Each complete set of 6 cookies = one $20 six-pack.

    Returns (lines, subtotal_cents, errors).
    """
    catalog = store_catalog()
    errors: list[str] = []
    lines: list[dict] = []
    subtotal = 0

    pack_total = sum(pack.values())
    if pack_total > 0 and pack_total % 6 != 0:
        errors.append(
            f"Build-your-own 6-pack must total a multiple of 6 cookies "
            f"(you selected {pack_total})."
        )

    single_total = sum(singles.values())
    if single_total == 0 and pack_total == 0:
        errors.append("Please add individual cookies and/or build a 6-pack.")

    if errors:
        return [], 0, errors

    # Individual cookies
    for cookie_id, qty in singles.items():
        info = catalog[cookie_id]
        unit = Config.PRICE_INDIVIDUAL_CENTS
        line_total = unit * qty
        subtotal += line_total
        lines.append(
            {
                "id": f"single_{cookie_id}",
                "cookie_id": cookie_id,
                "kind": "single",
                "name": f"{info['name']} (individual)",
                "qty": qty,
                "cookies_per_unit": 1,
                "unit_price_cents": unit,
                "line_total_cents": line_total,
            }
        )

    # Six-pack: store flavor allocation (qty = cookie count) + one fee line per pack
    if pack_total > 0:
        packs = pack_total // 6
        pack_price = Config.PRICE_SIX_PACK_CENTS
        pack_fee_total = pack_price * packs
        subtotal += pack_fee_total

        for cookie_id, qty in pack.items():
            info = catalog[cookie_id]
            lines.append(
                {
                    "id": f"pack_{cookie_id}",
                    "cookie_id": cookie_id,
                    "kind": "six_pack_cookie",
                    "name": f"{info['name']} (in 6-pack)",
                    "qty": qty,
                    "cookies_per_unit": 1,
                    "unit_price_cents": 0,
                    "line_total_cents": 0,
                }
            )

        lines.append(
            {
                "id": "six_pack",
                "cookie_id": None,
                "kind": "six_pack_fee",
                "name": f"Build-your-own 6-pack × {packs}",
                "qty": packs,
                "cookies_per_unit": 0,
                "unit_price_cents": pack_price,
                "line_total_cents": pack_fee_total,
                "pack_mix": pack,
            }
        )

    return lines, subtotal, []


def stripe_line_items_from_order(lines: list[dict], delivery_fee: int) -> list[dict]:
    """Only chargeable lines go to Stripe (skip zero-price pack mix lines)."""
    stripe_items = []
    for line in lines:
        if line["line_total_cents"] <= 0:
            continue
        stripe_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": line["name"]},
                    "unit_amount": line["unit_price_cents"],
                },
                "quantity": line["qty"],
            }
        )
    if delivery_fee:
        stripe_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Local delivery fee"},
                    "unit_amount": delivery_fee,
                },
                "quantity": 1,
            }
        )
    return stripe_items


# ── Public pages ──────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/merch")
def merch():
    """Merch is fulfilled by Printify 24/7 — we link out (or show API products later)."""
    return render_template(
        "merch.html",
        shop_url=Config.PRINTIFY_SHOP_URL,
        api_enabled=Config.printify_api_enabled(),
    )


def _order_page_context(form=None):
    catalog = store_catalog()
    slots = list_pickup_slots()
    sw = same_week_status()
    return {
        "catalog": catalog,
        "delivery_fee": Config.DELIVERY_FEE_CENTS,
        "publishable_key": Config.STRIPE_PUBLISHABLE_KEY,
        "price_individual": Config.PRICE_INDIVIDUAL_CENTS,
        "price_six_pack": Config.PRICE_SIX_PACK_CENTS,
        "pickup_slots": slots,
        "pickup_slots_json": slots,
        "same_week": sw,
        "form": form,
        "delivery_zips": Config.DELIVERY_ZIPS,
    }


@app.route("/order", methods=["GET", "POST"])
def order():
    if request.method == "GET":
        return render_template("order.html", **_order_page_context())

    # POST — create order (always allowed; pickup date is constrained)
    name = (request.form.get("customer_name") or "").strip()
    email = (request.form.get("customer_email") or "").strip()
    phone = (request.form.get("customer_phone") or "").strip()
    fulfillment = (request.form.get("fulfillment") or "pickup").strip()
    pickup_date_raw = (request.form.get("pickup_date") or "").strip()
    address = (request.form.get("address") or "").strip()
    delivery_zip = Config.normalize_zip(request.form.get("delivery_zip") or "")
    notes = (request.form.get("notes") or "").strip()

    singles = parse_qty_form("single")
    pack = parse_qty_form("pack")

    errors = []
    if not name:
        errors.append("Name is required.")
    if not email:
        errors.append("Email is required.")
    if not phone:
        errors.append("Phone is required.")
    if fulfillment not in ("pickup", "delivery"):
        errors.append("Choose pickup or delivery.")
    if fulfillment == "delivery" and not address:
        errors.append("Delivery address is required for delivery orders.")
    if fulfillment == "delivery" and not delivery_zip:
        errors.append("Enter a 5-digit delivery ZIP code.")
    elif fulfillment == "delivery" and not Config.delivery_zip_ok(delivery_zip):
        errors.append(
            "Sorry — we only deliver to ZIP codes within about 20 minutes of 78746. "
            "Please choose pickup or see the map for the delivery area."
        )
    if fulfillment == "delivery" and delivery_zip and address:
        if delivery_zip not in address:
            address = f"{address.rstrip()}\nAustin, TX {delivery_zip}"
    if not Config.stripe_enabled():
        errors.append("Card payment is required. Online checkout is temporarily unavailable.")

    pickup_day = ""
    pickup_date_iso = ""
    batch = ""
    if not pickup_date_raw:
        errors.append("Please select a Friday or Saturday pickup date on the calendar.")
    else:
        try:
            pickup_d = date.fromisoformat(pickup_date_raw)
        except ValueError:
            errors.append("Invalid pickup date.")
            pickup_d = None
        if pickup_d is not None:
            ok, reason = is_pickup_date_available(pickup_d)
            if not ok:
                errors.append(reason or "That pickup date is not available.")
            else:
                pickup_date_iso = pickup_d.isoformat()
                pickup_day = "friday" if pickup_d.weekday() == 4 else "saturday"
                batch = batch_week_from_pickup_date(pickup_d)

    lines, subtotal, line_errors = build_line_items(singles, pack)
    errors.extend(line_errors)

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("order.html", **_order_page_context(form=request.form))

    # Re-check availability right before write (strict cutoff for same week)
    ok, reason = is_pickup_date_available(date.fromisoformat(pickup_date_iso))
    if not ok:
        flash(reason or "That pickup date is no longer available.", "error")
        return redirect(url_for("order"))

    delivery_fee = Config.DELIVERY_FEE_CENTS if fulfillment == "delivery" else 0
    total = subtotal + delivery_fee
    order_number = f"SCC-{now_local().strftime('%y%m%d')}-{secrets.token_hex(3).upper()}"

    order_payload = {
        "order_number": order_number,
        "created_at": now_local().isoformat(),
        "customer_name": name,
        "customer_email": email,
        "customer_phone": phone,
        "fulfillment": fulfillment,
        "pickup_day": pickup_day,
        "pickup_date": pickup_date_iso,
        "address": address,
        "notes": notes,
        "items": lines,
        "subtotal_cents": subtotal,
        "delivery_fee_cents": delivery_fee,
        "total_cents": total,
        "payment_method": "stripe",
        "batch_week": batch,
    }

    # Card payment is required at order time — create a pending order, then Checkout.
    order_payload["payment_status"] = "pending"
    order_payload["status"] = "pending_payment"
    order_id = create_order(order_payload)

    stripe_items = stripe_line_items_from_order(lines, delivery_fee)
    try:
        checkout_session = stripe.checkout.Session.create(
            ui_mode="embedded_page",
            mode="payment",
            customer_email=email,
            line_items=stripe_items,
            payment_intent_data={
                "receipt_email": email,
                "metadata": {
                    "order_number": order_number,
                    "pickup_day": pickup_day,
                    "pickup_date": pickup_date_iso,
                },
            },
            metadata={
                "order_number": order_number,
                "order_id": str(order_id),
                "pickup_day": pickup_day,
                "pickup_date": pickup_date_iso,
                "customer_name": name,
            },
            return_url=(
                Config.PUBLIC_BASE_URL
                + url_for("order_return")
                + "?session_id={CHECKOUT_SESSION_ID}"
            ),
        )
    except stripe.error.StripeError as exc:
        update_order_payment(order_id, payment_status="failed", status="cancelled")
        flash(f"Payment setup failed: {exc.user_message or str(exc)}", "error")
        return redirect(url_for("order"))

    update_order_payment(
        order_id,
        payment_status="pending",
        stripe_session_id=checkout_session.id,
    )

    return render_template(
        "pay.html",
        client_secret=checkout_session.client_secret,
        publishable_key=Config.STRIPE_PUBLISHABLE_KEY,
        order_number=order_number,
        total_cents=total,
    )


@app.route("/order/return")
def order_return():
    session_id = request.args.get("session_id")
    if not session_id or not Config.stripe_enabled():
        flash("Missing payment session.", "error")
        return redirect(url_for("index"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        flash("Could not verify payment.", "error")
        return redirect(url_for("index"))

    order = get_order_by_stripe_session(session_id)
    if not order:
        order_number = (checkout_session.metadata or {}).get("order_number")
        order = get_order_by_number(order_number) if order_number else None

    if not order:
        flash("Order not found for this payment.", "error")
        return redirect(url_for("index"))

    if checkout_session.status == "complete" and checkout_session.payment_status == "paid":
        _mark_order_paid(order, session_id)
        return redirect(url_for("order_success", order_number=order["order_number"]))

    flash("Payment was not completed. You can try again anytime.", "error")
    return redirect(url_for("order"))


def _mark_order_paid(order: dict, session_id: str | None = None) -> bool:
    """Mark paid once, then email/push the admin. Returns True if newly paid."""
    if not order or order.get("payment_status") == "paid":
        return False
    update_order_payment(
        order["id"],
        payment_status="paid",
        stripe_session_id=session_id,
        status="confirmed",
    )
    notify_new_order(get_order_by_id(order["id"]) or order)
    return True


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    if not Config.STRIPE_WEBHOOK_SECRET:
        return "webhook not configured", 400
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, Config.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return "invalid signature", 400

    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        session_id = session_obj.get("id")
        order = get_order_by_stripe_session(session_id) if session_id else None
        if not order:
            order_number = (session_obj.get("metadata") or {}).get("order_number")
            order = get_order_by_number(order_number) if order_number else None
        if (
            order
            and session_obj.get("payment_status") == "paid"
        ):
            _mark_order_paid(order, session_id)
    return "", 200


@app.route("/api/push-token", methods=["POST"])
def api_push_token():
    data = request.get_json(silent=True) or {}
    secret = (data.get("secret") or request.headers.get("X-Push-Secret") or "").strip()
    token = (data.get("token") or "").strip()
    if not Config.PUSH_REGISTER_SECRET or secret != Config.PUSH_REGISTER_SECRET:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not token:
        return jsonify({"ok": False, "error": "missing token"}), 400
    save_push_token(token)
    return jsonify({"ok": True})


@app.route("/order/success/<order_number>")
def order_success(order_number):
    order = get_order_by_number(order_number)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("index"))
    if order["payment_method"] == "stripe" and order["payment_status"] == "pending":
        flash("This order is still awaiting payment.", "error")
        return redirect(url_for("order"))
    return render_template("success.html", order=order)


@app.route("/api/window")
def api_window():
    sw = same_week_status()
    return jsonify(
        {
            "open": True,
            "message": sw["message"],
            "same_week_open": sw["same_week_open"],
            "cutoff": cutoff_display(),
            "timezone": Config.TIMEZONE,
            "now": now_local().isoformat(),
            "slots": list_pickup_slots(),
        }
    )


# ── Admin ─────────────────────────────────────────────────────


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username", "")
        password = request.form.get("password", "")
        if user == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session["admin"] = True
            nxt = request.args.get("next") or url_for("admin_dashboard")
            return redirect(nxt)
        flash("Invalid username or password.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    weeks = list_batch_weeks()
    selected = request.args.get("batch") or (weeks[0] if weeks else current_batch_week())
    orders = list_orders(batch_week=selected)
    counts = aggregate_cookie_counts(orders)
    products = aggregate_product_summary(orders)
    catalog = store_catalog(include_inactive=True)
    pickup_dates = batch_pickup_dates(selected)

    count_rows = []
    total_cookies = 0
    for cookie_id, info in catalog.items():
        q = counts.get(cookie_id, 0)
        total_cookies += q
        count_rows.append({"id": cookie_id, "name": info["name"], "qty": q})
    for cookie_id, q in counts.items():
        if cookie_id not in catalog:
            count_rows.append({"id": cookie_id, "name": cookie_id, "qty": q})
            total_cookies += q

    fri = sum(1 for o in orders if (o.get("pickup_day") or "") == "friday")
    sat = sum(1 for o in orders if (o.get("pickup_day") or "") == "saturday")

    return render_template(
        "admin/dashboard.html",
        orders=orders,
        count_rows=count_rows,
        total_cookies=total_cookies,
        products=products,
        weeks=weeks,
        selected_batch=selected,
        batch_label=batch_week_label(selected),
        pickup_dates=pickup_dates,
        pickup_friday_orders=fri,
        pickup_saturday_orders=sat,
        push_phone_count=len(list_push_tokens()),
        firebase_ready=bool(Config.FIREBASE_CREDENTIALS),
        seasonal=get_seasonal(),
    )


@app.route("/admin/notify-test", methods=["POST"])
@admin_required
def admin_notify_test():
    result = send_admin_push(
        {
            "order_number": "TEST",
            "customer_name": "Test notification",
            "customer_phone": "",
            "customer_email": "",
            "fulfillment": "pickup",
            "pickup_date": "",
            "items": [],
            "total_cents": 0,
        }
    )
    flash(result, "error" if "Sent" not in result else "ok")
    return redirect(url_for("admin_dashboard", batch=request.form.get("batch")))


@app.route("/admin/print/orders")
@admin_required
def admin_print_orders():
    selected = request.args.get("batch") or current_batch_week()
    orders = list_orders(batch_week=selected)
    pickup_dates = batch_pickup_dates(selected)
    return render_template(
        "admin/print_orders.html",
        orders=orders,
        selected_batch=selected,
        batch_label=batch_week_label(selected),
        pickup_dates=pickup_dates,
        printed_at=now_local().strftime("%b %d, %Y %I:%M %p"),
    )


@app.route("/admin/print/counts")
@admin_required
def admin_print_counts():
    selected = request.args.get("batch") or current_batch_week()
    orders = list_orders(batch_week=selected)
    counts = aggregate_cookie_counts(orders)
    products = aggregate_product_summary(orders)
    catalog = store_catalog(include_inactive=True)
    count_rows = []
    total_cookies = 0
    for cookie_id, info in catalog.items():
        q = counts.get(cookie_id, 0)
        total_cookies += q
        count_rows.append({"name": info["name"], "qty": q})
    return render_template(
        "admin/print_counts.html",
        count_rows=count_rows,
        total_cookies=total_cookies,
        products=products,
        order_count=len(orders),
        selected_batch=selected,
        batch_label=batch_week_label(selected),
        printed_at=now_local().strftime("%Y-%m-%d %H:%M"),
    )


def _label_rows_for_batch(selected: str) -> tuple[list[dict], int]:
    orders = list_orders(batch_week=selected)
    counts = aggregate_cookie_counts(orders)
    catalog = store_catalog(include_inactive=True)
    rows = []
    total = 0
    for cookie_id, info in catalog.items():
        raw = request.values.get(f"qty_{cookie_id}")
        if raw is None or str(raw).strip() == "":
            qty = int(counts.get(cookie_id, 0) or 0)
        else:
            try:
                qty = int(raw)
            except ValueError:
                qty = 0
        qty = max(0, min(qty, 500))
        ordered = int(counts.get(cookie_id, 0) or 0)
        rows.append(
            {
                "id": cookie_id,
                "name": info["name"],
                "ordered": ordered,
                "qty": qty,
            }
        )
        total += qty
    return rows, total


@app.route("/admin/print/labels")
@admin_required
def admin_print_labels():
    selected = request.args.get("batch") or current_batch_week()
    rows, total = _label_rows_for_batch(selected)
    sheets = (total + 9) // 10
    return render_template(
        "admin/print_labels.html",
        rows=rows,
        total_labels=total,
        sheets=sheets,
        selected_batch=selected,
        batch_label=batch_week_label(selected),
        order_count=len(list_orders(batch_week=selected)),
    )


@app.route("/admin/print/labels.pdf")
@admin_required
def admin_print_labels_pdf():
    selected = request.args.get("batch") or current_batch_week()
    rows, total = _label_rows_for_batch(selected)
    if total <= 0:
        flash("Enter at least one label to print.", "error")
        return redirect(url_for("admin_print_labels", batch=selected))
    qty_map = {row["id"]: row["qty"] for row in rows}
    try:
        from labels.generate_labels import build_labels_pdf

        extra = {}
        seasonal_flavor = seasonal_label_flavor()
        if seasonal_flavor:
            extra[SEASONAL_ID] = seasonal_flavor
        pdf = build_labels_pdf(
            qty_map,
            title=f"Scratch Cookie Cottage labels — {batch_week_label(selected)}",
            extra_flavors=extra,
        )
    except ImportError:
        flash(
            "Label printing needs the reportlab package. "
            "In a PythonAnywhere Bash console run: pip install reportlab",
            "error",
        )
        return redirect(url_for("admin_print_labels", batch=selected))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin_print_labels", batch=selected))
    filename = f"SCC-labels-{selected}-{total}.pdf"
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


MAJOR_ALLERGENS = (
    "Wheat",
    "Eggs",
    "Milk",
    "Soy",
    "Peanuts",
    "Tree nuts",
    "Sesame",
    "Fish",
    "Shellfish",
)
ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _build_allergen_line(selected: list[str], tree_nuts: str) -> str:
    parts = []
    tree_nuts = (tree_nuts or "").strip()
    for name in MAJOR_ALLERGENS:
        if name not in selected:
            continue
        if name == "Tree nuts" and tree_nuts:
            parts.append(f"Tree nuts ({tree_nuts})")
        else:
            parts.append(name)
    return ", ".join(parts)


def _save_uploaded_seasonal_photos(files) -> int:
    from uuid import uuid4
    from werkzeug.utils import secure_filename

    saved = 0
    dest_dir = seasonal_upload_dir()
    for storage in files:
        if not storage or not storage.filename:
            continue
        ext = os.path.splitext(storage.filename)[1].lower()
        if ext not in ALLOWED_PHOTO_EXT:
            continue
        safe = secure_filename(storage.filename) or f"photo{ext}"
        filename = f"{uuid4().hex[:10]}_{safe}"
        storage.save(os.path.join(dest_dir, filename))
        add_seasonal_image(filename)
        saved += 1
    return saved


@app.route("/admin/seasonal", methods=["GET", "POST"])
@admin_required
def admin_seasonal():
    if request.method == "POST":
        action = request.form.get("action") or "save"
        if action == "delete_photo":
            try:
                image_id = int(request.form.get("image_id") or "0")
            except ValueError:
                image_id = 0
            filename = delete_seasonal_image(image_id)
            if filename:
                path = os.path.join(seasonal_upload_dir(), filename)
                if os.path.isfile(path):
                    os.remove(path)
            flash("Photo removed.", "ok")
            return redirect(url_for("admin_seasonal"))

        if action == "set_visible":
            listing = get_seasonal()
            show = request.form.get("active") == "1"
            save_seasonal(
                name=listing["name"],
                description=listing.get("description") or "",
                ingredients=listing.get("ingredients") or "",
                allergens=listing.get("allergens") or "",
                active=show,
            )
            flash(
                "Seasonal cookie is now visible on the website."
                if show
                else "Seasonal cookie is hidden from the website.",
                "ok",
            )
            nxt = request.form.get("next") or url_for("admin_seasonal")
            return redirect(nxt)

        selected = request.form.getlist("allergen")
        tree_nuts = request.form.get("tree_nuts") or ""
        save_seasonal(
            name=request.form.get("name") or "",
            description=request.form.get("description") or "",
            ingredients=request.form.get("ingredients") or "",
            allergens=_build_allergen_line(selected, tree_nuts),
            active=request.form.get("active") == "1",
        )
        uploaded = _save_uploaded_seasonal_photos(request.files.getlist("photos"))
        if uploaded:
            flash(f"Saved listing and added {uploaded} photo(s).", "ok")
        else:
            flash("Seasonal listing saved.", "ok")
        return redirect(url_for("admin_seasonal"))

    listing = get_seasonal()
    allergen_line = listing.get("allergens") or ""
    selected = []
    tree_nuts = ""
    for chunk in [c.strip() for c in allergen_line.split(",") if c.strip()]:
        low = chunk.lower()
        if low.startswith("tree nuts"):
            selected.append("Tree nuts")
            if "(" in chunk:
                tree_nuts = chunk.split("(", 1)[1].split(")", 1)[0].strip()
            continue
        for name in MAJOR_ALLERGENS:
            if name.lower() == low:
                selected.append(name)
                break
    return render_template(
        "admin/seasonal.html",
        listing=listing,
        major_allergens=MAJOR_ALLERGENS,
        selected_allergens=selected,
        tree_nuts=tree_nuts,
    )


@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_set_status(order_id):
    status = request.form.get("status", "new")
    if status in ("new", "confirmed", "baked", "picked_up", "delivered", "cancelled"):
        set_order_status(order_id, status)
    return redirect(url_for("admin_dashboard", batch=request.form.get("batch")))


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database ready.")


@app.template_filter("localdt")
def localdt_filter(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return iso_str


@app.template_filter("pickup_label")
def pickup_label_filter(day: str) -> str:
    if not day:
        return "—"
    return day.capitalize()


@app.template_filter("order_pickup_display")
def order_pickup_display_filter(order: dict) -> str:
    """Prefer full ISO pickup_date; fall back to day name + batch weekend."""
    pd = (order or {}).get("pickup_date") or ""
    if pd:
        return format_pickup_date(pd)
    day = (order or {}).get("pickup_day") or ""
    batch = (order or {}).get("batch_week") or ""
    if day and batch:
        dates = batch_pickup_dates(batch)
        key = "friday" if day == "friday" else "saturday"
        return dates.get(key, day.capitalize())
    return day.capitalize() if day else "—"


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)

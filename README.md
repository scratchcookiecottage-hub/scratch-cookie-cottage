# Scratch Cookie Cottage — Order System

Flask storefront for **Scratch Cookie Cottage**:

- **Individual cookies** — $4.00 each  
- **Build-your-own 6-pack** (half dozen) — $20.00  
- Flavors: Brown Butter Chocolate Chip, Macadamia White Chocolate, Salted Caramel Chocolate Pecan, White Miso Peanut Butter  
- **Order anytime** — no closed storefront for cookies  
- **Pickup calendar:** choose a future Friday or Saturday  
- **Weekly cutoff:** after Wednesday 11:59 PM CST, same-week Fri/Sat are greyed out  
- **Stripe** card checkout (embedded on-site) + email receipt  
- **Admin** bake sheet: cookie counts by flavor, orders, Fri/Sat split  
- **Merch** via Printify Pop-Up Store (24/7, third-party fulfillment)

## Quick start (Windows)

```powershell
cd $env:USERPROFILE\Documents\scratch-cookie-cottage
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
python app.py
```

Open:

- Storefront: http://127.0.0.1:5000  
- Order: http://127.0.0.1:5000/order  
- Admin: http://127.0.0.1:5000/admin  
- Merch: http://127.0.0.1:5000/merch  

## What you need to provide

### 1. Stripe (card payments + email receipts)

| Item | Where to get it |
|------|-----------------|
| **Secret key** `sk_test_…` / `sk_live_…` | [Stripe Dashboard → Developers → API keys](https://dashboard.stripe.com/apikeys) |
| **Publishable key** `pk_test_…` / `pk_live_…` | Same page |
| **Business details** | Settings → Business (name, support email, address for receipts) |

**Email receipts (yes — Stripe does this):**

1. In the app we set `receipt_email` and `customer_email` on checkout.  
2. In Stripe Dashboard: **Settings → Business → Customer emails** → enable **Successful payments**.  
3. Customers who pay by card get a Stripe receipt email automatically.

Put keys in `.env`:

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
PUBLIC_BASE_URL=http://127.0.0.1:5000
```

Without Stripe keys, the site still works with **pay at pickup** only.

### 2. Admin login

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` before going live.

### 3. Printify merch (optional API)

Merch works **today** by linking to your Pop-Up Store (`PRINTIFY_SHOP_URL`). No API required for that.

For a deeper on-site merch checkout later:

| Item | Where |
|------|--------|
| **API token** | [Printify → Account → API](https://printify.com/app/account/api) (Personal Access Token) |
| **Shop ID** | Printify shop settings / API shops list |

```
PRINTIFY_SHOP_URL=https://scratchcookiecottage.printify.me/
PRINTIFY_API_TOKEN=
PRINTIFY_SHOP_ID=
```

### 4. Salted Caramel photos

Add image URLs in `config.py` under `salted_caramel` (`img_default` / `img_hover`), or place files under `static/images/` and point the paths there. Facebook CDN links expire — host images yourself when you can.

## Ordering & weekly pickup cutoff

Cookie orders are accepted **any day**. Customers pick a **Friday or Saturday** on the calendar.

| When you order | Same-week Fri/Sat | Future weekends |
|----------------|-------------------|-----------------|
| Before Wed 11:59 PM CST | **Available** | Available |
| After Wed 11:59 PM CST | **Greyed out** | Available |

Timezone default: `America/Chicago` (CST/CDT). Change `TIMEZONE` / `CUTOFF_*` / `PICKUP_WEEKS_AHEAD` in `.env`.

Batch week in admin is based on the **chosen pickup date’s weekend**, not the day the order was placed.

## Admin & printing

1. Log in at `/admin`  
2. Pick the batch week  
3. **Cookie counts** — how many of each flavor to bake (singles + 6-pack mix)  
4. **Print order list** — names, Fri/Sat, items, paid vs collect  
5. **Print bake sheet** — totals for the oven  

## Deploy

1. Host on Render, Railway, Fly.io, etc.  
2. Set the same env vars (use **live** Stripe keys in production)  
3. Point `www.scratchcookiecottage.com` DNS at the host  
4. Set `PUBLIC_BASE_URL=https://www.scratchcookiecottage.com`  

Your site is currently on **Google Sites**, which cannot run this Flask app. Options:

- Run this app on a free/cheap host and either replace Google Sites or link **Order Cookies** from Google Sites to your app URL  
- Or put the domain’s DNS on the host that runs Flask  

## Project layout

```
app.py              # Routes: storefront, order, Stripe, admin
config.py           # Catalog, prices, env
db.py               # SQLite orders
order_window.py     # Mon–Wed open / cutoff
templates/          # Pages
static/             # CSS & JS
data/orders.db      # Created automatically
```

## Security

- Change the default admin password before production  
- Never commit `.env` or Stripe secret keys  
- Use HTTPS in production  

"""
Pickup scheduling with a weekly Wednesday cutoff (America/Chicago by default).

Cookie orders are accepted any day. Customers pick a future Saturday or Sunday.
Same-week Sat/Sun stay available only until Wednesday 11:59 PM local.
After that cutoff, those dates are locked; next week (and further) remain open.

Saturday is cottage pickup or local delivery. Sunday is pickup only at the
Triangle Farmers Market, and it shares the Monday batch key with that
weekend's Saturday (Python's weekday() treats Sunday as the end of the week).
"""

from datetime import date, datetime, timedelta
from typing import Any, Optional

import pytz

from config import Config

# Saturday=5, Sunday=6. Friday (4) is no longer offered.
ALLOWED_PICKUP_WEEKDAYS = (5, 6)


def now_local() -> datetime:
    return datetime.now(pytz.timezone(Config.TIMEZONE))


def _tz():
    return pytz.timezone(Config.TIMEZONE)


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_cutoff_end(monday: date) -> datetime:
    """Last instant orders may select Sat/Sun of the week starting at monday."""
    cut_day = monday + timedelta(days=Config.CUTOFF_WEEKDAY)
    naive = datetime(
        cut_day.year,
        cut_day.month,
        cut_day.day,
        Config.CUTOFF_HOUR,
        Config.CUTOFF_MINUTE,
        59,
        999999,
    )
    return _tz().localize(naive)


def sunday_market_start() -> date:
    return date.fromisoformat(Config.SUNDAY_MARKET["starts_iso"])


def is_pickup_date_available(
    pickup: date, at: Optional[datetime] = None
) -> tuple[bool, str]:
    """
    Returns (available, reason_if_not).
    Only Saturdays and Sundays can be selected.
    Sundays before the farmers-market start date are not offered.
    """
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()

    if pickup.weekday() not in ALLOWED_PICKUP_WEEKDAYS:
        return False, "Pickup is only available on Saturdays and Sundays."

    if pickup < today:
        return False, "That date has already passed."

    if pickup.weekday() == 6 and pickup < sunday_market_start():
        market = Config.SUNDAY_MARKET
        return False, (
            f"Sunday market pickup starts {market['starts']} at the {market['name']}."
        )

    monday = monday_of(pickup)
    cutoff = week_cutoff_end(monday)
    if now > cutoff:
        return False, (
            f"Same-week cutoff was {cutoff_display()} — "
            f"please choose a later weekend."
        )

    return True, ""


def batch_week_from_pickup_date(pickup: date | str) -> str:
    """Monday ISO date for the week of the chosen pickup (admin batch key)."""
    if isinstance(pickup, str):
        pickup = date.fromisoformat(pickup)
    return monday_of(pickup).isoformat()


def current_batch_week(at: Optional[datetime] = None) -> str:
    """
    Default admin batch: the next weekend customers can still order for.
    (Earliest week whose Sat/Sun are still available.)
    """
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()
    # Walk forward up to 3 weeks to find first available Sat or Sun
    for i in range(21):
        d = today + timedelta(days=i)
        if d.weekday() in ALLOWED_PICKUP_WEEKDAYS:
            ok, _ = is_pickup_date_available(d, now)
            if ok:
                return batch_week_from_pickup_date(d)
    return monday_of(today).isoformat()


def batch_week_label(batch_week: str) -> str:
    """Human label: Weekend of Month Day, Year (Saturday after Monday key)."""
    try:
        monday = datetime.strptime(batch_week, "%Y-%m-%d")
        saturday = monday + timedelta(days=5)
        return f"Weekend of {saturday.strftime('%B %d, %Y')}"
    except ValueError:
        return batch_week


def batch_pickup_dates(batch_week: str) -> dict[str, str]:
    """Saturday and Sunday labels for a batch week, plus legacy Friday.

    Sunday is the day after that week's Saturday, so it stays on the same
    Monday key. Friday labels remain so older orders still render.
    """
    try:
        monday = datetime.strptime(batch_week, "%Y-%m-%d")
        friday = monday + timedelta(days=4)
        saturday = monday + timedelta(days=5)
        sunday = monday + timedelta(days=6)
        return {
            "friday": friday.strftime("%A, %B %d"),
            "saturday": saturday.strftime("%A, %B %d"),
            "sunday": sunday.strftime("%A, %B %d"),
            "friday_short": friday.strftime("%b %d"),
            "saturday_short": saturday.strftime("%b %d"),
            "sunday_short": sunday.strftime("%b %d"),
            "friday_iso": friday.strftime("%Y-%m-%d"),
            "saturday_iso": saturday.strftime("%Y-%m-%d"),
            "sunday_iso": sunday.strftime("%Y-%m-%d"),
        }
    except ValueError:
        return {
            "friday": "Friday",
            "saturday": "Saturday",
            "sunday": "Sunday",
            "friday_short": "Friday",
            "saturday_short": "Saturday",
            "sunday_short": "Sunday",
            "friday_iso": "",
            "saturday_iso": "",
            "sunday_iso": "",
        }


def list_pickup_slots(
    weeks_ahead: Optional[int] = None, at: Optional[datetime] = None
) -> list[dict[str, Any]]:
    """
    Upcoming Saturday/Sunday slots for the calendar.
    Each: {date, weekday, label, available, reason, batch_week, is_same_week}
    """
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()
    weeks = weeks_ahead if weeks_ahead is not None else Config.PICKUP_WEEKS_AHEAD
    this_monday = monday_of(today)

    slots: list[dict[str, Any]] = []
    # Cover from this week's Saturday through weeks_ahead weekends
    start = this_monday + timedelta(days=5)  # this Saturday
    end = this_monday + timedelta(weeks=weeks, days=6)  # last Sunday

    d = start
    while d <= end:
        if d.weekday() in ALLOWED_PICKUP_WEEKDAYS:
            available, reason = is_pickup_date_available(d, now)
            weekday = "saturday" if d.weekday() == 5 else "sunday"
            slots.append(
                {
                    "date": d.isoformat(),
                    "weekday": weekday,
                    "label": d.strftime("%A, %B %d, %Y"),
                    "short_label": d.strftime("%b %d"),
                    "day_num": d.day,
                    "month": d.month,
                    "year": d.year,
                    "available": available,
                    "reason": reason,
                    "batch_week": batch_week_from_pickup_date(d),
                    "is_same_week": monday_of(d) == this_monday,
                    "delivery_ok": weekday == "saturday",
                }
            )
        d += timedelta(days=1)

    return slots


def same_week_status(at: Optional[datetime] = None) -> dict[str, Any]:
    """Messaging for the current calendar week’s Sat/Sun."""
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()
    monday = monday_of(today)
    saturday = monday + timedelta(days=5)
    sunday = monday + timedelta(days=6)
    cutoff = week_cutoff_end(monday)
    sat_ok, _ = is_pickup_date_available(saturday, now)
    sun_ok, _ = is_pickup_date_available(sunday, now)
    open_same = sat_ok or sun_ok

    if open_same:
        msg = (
            f"Order anytime. Same-weekend pickup (Sat/Sun) is available "
            f"through {cutoff_display()} ({Config.TIMEZONE.split('/')[-1]})."
        )
    else:
        msg = (
            f"Same-weekend pickup has closed (cutoff was {cutoff_display()}). "
            f"You can still order for a future Saturday or Sunday."
        )

    return {
        "same_week_open": open_same,
        "message": msg,
        "cutoff": cutoff.isoformat(),
        "saturday": saturday.isoformat(),
        "sunday": sunday.isoformat(),
    }


def window_status(at: Optional[datetime] = None) -> tuple[bool, str]:
    """
    Compatibility helper. Cookie ordering is always open.
    Message explains same-week pickup availability.
    """
    status = same_week_status(at)
    return True, status["message"]


def is_order_window_open(at: Optional[datetime] = None) -> bool:
    """Orders are always accepted."""
    return True


def cutoff_display() -> str:
    h = Config.CUTOFF_HOUR
    m = Config.CUTOFF_MINUTE
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    return f"{days[Config.CUTOFF_WEEKDAY]} {_time_label(h, m)}"


def format_pickup_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return d.strftime("%A, %B %d, %Y")
    except ValueError:
        return iso or "—"


def _time_label(h: int, m: int) -> str:
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"

"""
Pickup scheduling with a weekly Wednesday cutoff (America/Chicago by default).

Cookie orders are accepted any day. Customers pick a future Friday or Saturday.
Same-week Fri/Sat stay available only until Wednesday 11:59 PM local.
After that cutoff, those dates are locked; next week (and further) remain open.
"""

from datetime import date, datetime, timedelta
from typing import Any, Optional

import pytz

from config import Config


def now_local() -> datetime:
    return datetime.now(pytz.timezone(Config.TIMEZONE))


def _tz():
    return pytz.timezone(Config.TIMEZONE)


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_cutoff_end(monday: date) -> datetime:
    """Last instant orders may select Fri/Sat of the week starting at monday."""
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


def is_pickup_date_available(
    pickup: date, at: Optional[datetime] = None
) -> tuple[bool, str]:
    """
    Returns (available, reason_if_not).
    Only Fridays and Saturdays can be selected.
    """
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()

    if pickup.weekday() not in (4, 5):  # Friday=4, Saturday=5
        return False, "Pickup is only available on Fridays and Saturdays."

    if pickup < today:
        return False, "That date has already passed."

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
    (Earliest week whose Fri/Sat are still available.)
    """
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()
    # Walk forward up to 3 weeks to find first available Fri or Sat
    for i in range(21):
        d = today + timedelta(days=i)
        if d.weekday() in (4, 5):
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
    """Friday and Saturday labels for a batch week (Monday key)."""
    try:
        monday = datetime.strptime(batch_week, "%Y-%m-%d")
        friday = monday + timedelta(days=4)
        saturday = monday + timedelta(days=5)
        return {
            "friday": friday.strftime("%A, %B %d"),
            "saturday": saturday.strftime("%A, %B %d"),
            "friday_short": friday.strftime("%b %d"),
            "saturday_short": saturday.strftime("%b %d"),
            "friday_iso": friday.strftime("%Y-%m-%d"),
            "saturday_iso": saturday.strftime("%Y-%m-%d"),
        }
    except ValueError:
        return {
            "friday": "Friday",
            "saturday": "Saturday",
            "friday_short": "Friday",
            "saturday_short": "Saturday",
            "friday_iso": "",
            "saturday_iso": "",
        }


def list_pickup_slots(
    weeks_ahead: Optional[int] = None, at: Optional[datetime] = None
) -> list[dict[str, Any]]:
    """
    Upcoming Friday/Saturday slots for the calendar.
    Each: {date, weekday, label, available, reason, batch_week, is_same_week}
    """
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()
    weeks = weeks_ahead if weeks_ahead is not None else Config.PICKUP_WEEKS_AHEAD
    this_monday = monday_of(today)

    slots: list[dict[str, Any]] = []
    # Cover from this week's Friday through weeks_ahead weekends
    start = this_monday + timedelta(days=4)  # this Friday
    end = this_monday + timedelta(weeks=weeks, days=5)  # last Saturday

    d = start
    while d <= end:
        if d.weekday() in (4, 5):
            available, reason = is_pickup_date_available(d, now)
            slots.append(
                {
                    "date": d.isoformat(),
                    "weekday": "friday" if d.weekday() == 4 else "saturday",
                    "label": d.strftime("%A, %B %d, %Y"),
                    "short_label": d.strftime("%b %d"),
                    "day_num": d.day,
                    "month": d.month,
                    "year": d.year,
                    "available": available,
                    "reason": reason,
                    "batch_week": batch_week_from_pickup_date(d),
                    "is_same_week": monday_of(d) == this_monday,
                }
            )
        d += timedelta(days=1)

    return slots


def same_week_status(at: Optional[datetime] = None) -> dict[str, Any]:
    """Messaging for the current calendar week’s Fri/Sat."""
    now = at.astimezone(_tz()) if at else now_local()
    today = now.date()
    monday = monday_of(today)
    friday = monday + timedelta(days=4)
    saturday = monday + timedelta(days=5)
    cutoff = week_cutoff_end(monday)
    fri_ok, _ = is_pickup_date_available(friday, now)
    sat_ok, _ = is_pickup_date_available(saturday, now)
    open_same = fri_ok or sat_ok

    if open_same:
        msg = (
            f"Order anytime. Same-weekend pickup (Fri/Sat) is available "
            f"through {cutoff_display()} ({Config.TIMEZONE.split('/')[-1]})."
        )
    else:
        msg = (
            f"Same-weekend pickup has closed (cutoff was {cutoff_display()}). "
            f"You can still order for a future Friday or Saturday."
        )

    return {
        "same_week_open": open_same,
        "message": msg,
        "cutoff": cutoff.isoformat(),
        "friday": friday.isoformat(),
        "saturday": saturday.isoformat(),
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

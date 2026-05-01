from datetime import datetime, timedelta
from core.state import NotschoolState
from tools.calendar_client import create_calendar_event


# Default daily start hour (local time) for day/week-based cadences.
DEFAULT_START_HOUR = 10


VALID_UNITS = ("min", "hour", "day", "week")


def timeframe_to_timedelta(amount: int, unit: str) -> timedelta:
    """Convert an (amount, unit) cadence into a timedelta.
    Falls back to 1 day for unknown units so existing data keeps working.
    """
    try:
        n = max(1, int(amount))
    except (TypeError, ValueError):
        n = 1
    u = (unit or "day").lower()
    if u == "min":
        return timedelta(minutes=n)
    if u == "hour":
        return timedelta(hours=n)
    if u == "week":
        return timedelta(weeks=n)
    return timedelta(days=n)


def compute_module_slot(
    now: datetime,
    module_index: int,
    timeframe_amount: int,
    timeframe_unit: str,
) -> datetime:
    """Pick the start time for a given module (0-indexed).

    For day/week cadences we anchor each module to the configured 10:00 local
    slot — the same behaviour as before the timeframe feature.

    For min/hour cadences we want the FIRST module to start almost immediately
    so demos and short-cycle reviews are usable. The first module starts ~1
    minute from `now`, then we space subsequent modules by the cadence delta.
    """
    delta = timeframe_to_timedelta(timeframe_amount, timeframe_unit)
    unit = (timeframe_unit or "day").lower()

    if unit in ("min", "hour"):
        # Demo / short-cycle mode — kick off the first session ~1 min out so the
        # user can immediately verify auto-reschedule on the next miss.
        first = now + timedelta(minutes=1)
        return first + delta * module_index

    # Day / week cadence — anchor to the daily 10:00 slot.
    base = (now + delta * (module_index + 1)).replace(
        hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0
    )
    if module_index == 0 and base <= now:
        base = base + delta
    return base


def scheduler_node(state: NotschoolState) -> dict:
    """Creates one calendar event per module. Tracks per-session links + ids."""
    goal = state["goal"]
    curriculum = state.get("curriculum_json") or {}
    timezone = state["user_timezone"]
    access_token = state.get("user_access_token")
    timeframe_amount = state.get("timeframe_amount") or 1
    timeframe_unit = state.get("timeframe_unit") or "day"

    modules = curriculum.get("modules", []) or []

    if not access_token:
        return {
            "calendar_event_id": None,
            "calendar_event_ids": [None] * len(modules),
            "calendar_event_links": [None] * len(modules),
            "messages": [{"role": "system", "content": "Scheduler skipped: User did not link Google Calendar."}],
        }

    first_event_link = None
    all_event_ids = []
    all_event_links = []

    try:
        now = datetime.strptime(state["current_timestamp"], "%Y-%m-%d %H:%M:%S")

        for i, mod in enumerate(modules):
            if not isinstance(mod, dict):
                all_event_ids.append(None)
                all_event_links.append(None)
                continue

            topic = mod.get("topic", f"Module {i+1}")
            try:
                duration = float(mod.get("duration_hours", 1) or 1)
            except (TypeError, ValueError):
                duration = 1.0
            try:
                day_label = int(mod.get("day", i + 1))
            except (TypeError, ValueError):
                day_label = i + 1

            start_time = compute_module_slot(now, i, timeframe_amount, timeframe_unit)
            # Cap each event at one minute below the cadence so consecutive
            # sessions never overlap on Google Calendar — a 60-min cadence with
            # 1h modules would otherwise butt directly into the next event and
            # confuse the user. Day/week cadences are large enough that the
            # raw duration_hours value passes through unchanged.
            cadence_minutes = max(1, int(timeframe_to_timedelta(timeframe_amount, timeframe_unit).total_seconds() / 60))
            max_event = max(1, cadence_minutes - 1)
            event_minutes = max(1, min(int(duration * 60), max_event))
            end_time = start_time + timedelta(minutes=event_minutes)

            summary = f"📚 Notschool · Day {day_label}: {topic}"
            description = (
                f"Goal: {goal}\n\n"
                f"Day {day_label}: {topic}\n\n"
                f"{mod.get('description', '')}\n\n"
                "Scheduled by Notschool OS."
            )

            event_link, event_id = create_calendar_event(
                summary=summary,
                description=description,
                start_time_iso=start_time.isoformat(timespec="seconds"),
                end_time_iso=end_time.isoformat(timespec="seconds"),
                timezone=timezone,
                access_token=access_token,
                color_id="6",  # tangerine — visually distinct on Google Calendar
            )

            all_event_ids.append(event_id)
            all_event_links.append(event_link)

            if event_link and first_event_link is None:
                first_event_link = event_link

        booked = len([e for e in all_event_ids if e])
        if booked == 0:
            msg = (
                "Scheduler could not create any calendar events. "
                "Check that you granted the Google Calendar permission."
            )
        elif booked < len(modules):
            msg = f"Scheduler booked {booked}/{len(modules)} session(s) — some calendar inserts failed."
        else:
            msg = f"Scheduler booked {booked} session(s) across {len(modules)} module(s)."

    except Exception as e:
        print(f"Scheduler Node Error: {e}")
        first_event_link = None
        all_event_ids = []
        all_event_links = []
        msg = f"Scheduler failed: {str(e)}"

    return {
        "calendar_event_id": first_event_link,
        "calendar_event_ids": all_event_ids,
        "calendar_event_links": all_event_links,
        "messages": [{"role": "system", "content": msg}],
    }

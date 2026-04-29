from datetime import datetime, timedelta
from core.state import NotschoolState
from tools.calendar_client import create_calendar_event


def scheduler_node(state: NotschoolState) -> dict:
    """Creates one calendar event per module. Tracks per-session links + ids."""
    goal = state["goal"]
    curriculum = state.get("curriculum_json") or {}
    timezone = state["user_timezone"]
    access_token = state.get("user_access_token")

    modules = curriculum.get("modules", []) or []
    mode_tag = "Interview Prep" if state.get("mode") == "interview" else "Study Session"

    first_event_link = None
    all_event_ids = []
    all_event_links = []

    if not access_token:
        # No token → don't burn API calls; just emit empty per-module slots.
        return {
            "calendar_event_id": None,
            "calendar_event_ids": [None] * len(modules),
            "calendar_event_links": [None] * len(modules),
            "messages": [{"role": "system", "content": "Scheduler skipped: User did not link Google Calendar."}],
        }

    try:
        now = datetime.strptime(state["current_timestamp"], "%Y-%m-%d %H:%M:%S")

        for i, mod in enumerate(modules):
            if not isinstance(mod, dict):
                all_event_ids.append(None)
                all_event_links.append(None)
                continue

            topic = mod.get("topic", f"Module {i+1}")
            duration = mod.get("duration_hours", 1)
            day_offset = mod.get("day", i + 1)

            start_time = now + timedelta(days=day_offset)
            end_time = start_time + timedelta(hours=duration)

            summary = f"Notschool {mode_tag} Day {day_offset}: {topic}"
            description = (
                f"Goal: {goal}\n\nDay {day_offset}: {topic}\n\n"
                f"{mod.get('description', '')}\n\nAutomated schedule by Notschool OS."
            )

            event_link, event_id = create_calendar_event(
                summary=summary,
                description=description,
                start_time_iso=start_time.isoformat(),
                end_time_iso=end_time.isoformat(),
                timezone=timezone,
                access_token=access_token,
            )

            all_event_ids.append(event_id)
            all_event_links.append(event_link)

            if event_link and first_event_link is None:
                first_event_link = event_link

        if access_token:
            booked = len([e for e in all_event_ids if e])
            msg = f"Scheduler booked {booked} session(s) across {len(modules)} day(s)."
        else:
            msg = "Scheduler skipped: User did not link Google Calendar."

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
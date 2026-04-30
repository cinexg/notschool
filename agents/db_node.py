from datetime import datetime, timedelta
from core.state import NotschoolState
from db.crud import add_curriculum, add_session
from agents.scheduler_node import compute_module_slot, timeframe_to_timedelta


def db_node(state: NotschoolState) -> dict:
    """
    Persists everything for the logged-in user:
      1. The full curriculum (one row in curricula).
      2. One row per module in study_sessions, with its own video URL,
         calendar event link/id, and scheduled time.
    """
    user_id = state.get("user_id")
    if not user_id:
        # Shouldn't happen — main.py blocks unauthenticated requests
        return {
            "db_record_id": 0,
            "messages": [{"role": "system", "content": "DB Node skipped: no user_id."}],
        }

    goal = state["goal"]
    mode = state.get("mode", "learning")
    curriculum = state.get("curriculum_json") or {}
    modules = curriculum.get("modules", []) or []
    title = curriculum.get("title") or f"Roadmap: {goal}"

    youtube_urls = state.get("youtube_urls", []) or []
    event_ids = state.get("calendar_event_ids", []) or []
    event_links = state.get("calendar_event_links", []) or []
    opportunities = state.get("industry_opportunities", []) or []
    web_trends = state.get("web_trends", []) or []
    timeframe_amount = int(state.get("timeframe_amount") or 1)
    timeframe_unit = (state.get("timeframe_unit") or "day").lower()

    # 1. Persist the curriculum record (with timeframe metadata so the
    #    rescheduler can replay the same cadence on missed sessions).
    curriculum_id = add_curriculum(
        user_id=user_id,
        goal=goal,
        mode=mode,
        title=title,
        curriculum_json=curriculum,
        youtube_urls=youtube_urls,
        opportunities=opportunities,
        web_trends=web_trends,
        timeframe_amount=timeframe_amount,
        timeframe_unit=timeframe_unit,
    )

    saved = 0
    try:
        now = datetime.strptime(state["current_timestamp"], "%Y-%m-%d %H:%M:%S")

        for i, mod in enumerate(modules):
            if not isinstance(mod, dict):
                continue

            topic = mod.get("topic", f"Module {i+1}")
            description = mod.get("description", "")
            try:
                day_label = int(mod.get("day", i + 1))
            except (TypeError, ValueError):
                day_label = i + 1
            try:
                duration = float(mod.get("duration_hours", 1) or 1)
            except (TypeError, ValueError):
                duration = 1.0
            # Match the scheduler exactly so the DB row's scheduled_time agrees
            # with the actual Google Calendar event start.
            start_time = compute_module_slot(now, i, timeframe_amount, timeframe_unit)

            event_id = event_ids[i] if i < len(event_ids) else None
            event_link = event_links[i] if i < len(event_links) else None
            video_url = youtube_urls[i] if i < len(youtube_urls) else None

            add_session(
                user_id=user_id,
                curriculum_id=curriculum_id,
                goal=goal,
                module_name=topic,
                module_description=description,
                module_day=day_label,
                duration_hours=duration,
                scheduled_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                event_link=event_link or None,
                event_id=event_id,
                youtube_url=video_url or None,
            )
            saved += 1

        msg = f"DB Node saved curriculum #{curriculum_id} with {saved} session(s)."
    except Exception as e:
        print(f"Database Error: {e}")
        msg = f"DB Node partial save: {e}"

    return {
        "curriculum_id": curriculum_id,
        "db_record_id": saved,
        "messages": [{"role": "system", "content": msg}],
    }

from datetime import datetime, timedelta
from core.state import NotschoolState
from tools.calendar_client import create_calendar_event

def scheduler_node(state: NotschoolState) -> dict:
    """
    Acts as the Study Planner.
    Schedules the first learning module precisely 24 hours from the current context time.
    """
    goal = state["goal"]
    curriculum = state.get("curriculum_json", {})
    timezone = state["user_timezone"]
    
    # Extract the first module name to make the calendar event specific
    modules = curriculum.get("modules", [])
    first_module = modules[0] if modules else "Introduction to Topic"

    summary = f"Notschool Session: {first_module}"
    description = f"Goal: {goal}\n\nAutomated study session prepared by Notschool OS."

    try:
        # Parse the exact time the request was made from the LangGraph state
        now = datetime.strptime(state["current_timestamp"], "%Y-%m-%d %H:%M:%S")
        
        # Schedule the session for exactly 24 hours from now
        start_time = now + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        # The Google Calendar API requires strict ISO 8601 formatting
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        # Call the isolated API tool
        event_link = create_calendar_event(
            summary=summary,
            description=description,
            start_time_iso=start_iso,
            end_time_iso=end_iso,
            timezone=timezone
        )
        
        msg = f"Scheduler booked session for {start_time.strftime('%b %d at %H:%M')}."

    except Exception as e:
        print(f"Scheduler Node Error: {e}")
        event_link = None
        msg = f"Scheduler failed to book calendar event: {str(e)}"

    return {
        "calendar_event_id": event_link,
        "messages": [{"role": "system", "content": msg}]
    }
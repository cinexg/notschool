from datetime import datetime, timedelta
from core.state import NotschoolState
from tools.calendar_client import create_calendar_event

def scheduler_node(state: NotschoolState) -> dict:
    """
    Schedules the first learning session on Google Calendar 
    based on the Architect's curriculum.
    """
    goal = state["goal"]
    curriculum = state.get("curriculum_json", {})
    timezone = state.get("user_timezone", "Asia/Kolkata")
    
    # We grab the title of the first module to make the calendar event specific
    modules = curriculum.get("modules", [])
    first_module = modules[0] if modules else "Introduction"

    summary = f"Notschool Session: {first_module}"
    description = f"Goal: {goal}\n\nPrepared by Notschool OS."

    # For hackathon simplicity, schedule the first session for exactly 24 hours from now
    try:
        now = datetime.strptime(state["current_timestamp"], "%Y-%m-%d %H:%M:%S")
        start_time = now + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        # Convert to ISO 8601 format required by Google Calendar
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
        
        msg = f"Scheduled session for {start_time.strftime('%b %d at %H:%M')}."

    except Exception as e:
        event_link = None
        msg = f"Scheduling failed: {str(e)}"

    return {
        "calendar_event_id": event_link,
        "messages": [{"role": "system", "content": msg}]
    }
from datetime import datetime, timedelta
from core.state import NotschoolState
from tools.calendar_client import create_calendar_event

def scheduler_node(state: NotschoolState) -> dict:
    """Acts as the Study Planner."""
    goal = state["goal"]
    curriculum = state.get("curriculum_json", {})
    timezone = state["user_timezone"]
    access_token = state.get("user_access_token") 
    
    modules = curriculum.get("modules", [])
    
    # Extract the topic name safely from the new JSON object structure
    first_module_name = modules[0].get("topic", "Introduction") if modules and isinstance(modules[0], dict) else "Introduction"

    # Adapt summary based on mode
    mode_tag = "Interview Prep" if state.get("mode") == "interview" else "Study Session"
    summary = f"Notschool {mode_tag}: {first_module_name}"
    description = f"Goal: {goal}\n\nAutomated schedule prepared by Notschool OS."

    try:
        now = datetime.strptime(state["current_timestamp"], "%Y-%m-%d %H:%M:%S")
        start_time = now + timedelta(days=1)
        
        # Use dynamic duration_hours if available, otherwise default to 1 hour
        duration = modules[0].get("duration_hours", 1) if modules and isinstance(modules[0], dict) else 1
        end_time = start_time + timedelta(hours=duration)

        event_link = create_calendar_event(
            summary=summary,
            description=description,
            start_time_iso=start_time.isoformat(),
            end_time_iso=end_time.isoformat(),
            timezone=timezone,
            access_token=access_token 
        )
        
        if event_link:
            msg = f"Scheduler booked session for {start_time.strftime('%b %d at %H:%M')}."
        else:
            msg = "Scheduler skipped: User did not link Google Calendar."

    except Exception as e:
        print(f"Scheduler Node Error: {e}")
        event_link = None
        msg = f"Scheduler failed to book calendar event: {str(e)}"

    return {
        "calendar_event_id": event_link,
        "messages": [{"role": "system", "content": msg}]
    }
from core.state import NotschoolState
from db.crud import add_session
from datetime import datetime, timedelta

def db_node(state: NotschoolState) -> dict:
    """Acts as the Memory/Database Writer."""
    goal = state["goal"]
    curriculum = state.get("curriculum_json", {})
    event_link = state.get("calendar_event_id")
    
    modules = curriculum.get("modules", [])
    
    # Extract the topic name safely from the new JSON object structure
    first_module_name = modules[0].get("topic", "Introduction") if modules and isinstance(modules[0], dict) else "Introduction"
    
    # Calculate the exact time the scheduler used
    now = datetime.strptime(state["current_timestamp"], "%Y-%m-%d %H:%M:%S")
    start_time = now + timedelta(days=1)
    
    try:
        record_id = add_session(
            goal=goal,
            module_name=first_module_name,
            scheduled_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
            event_link=event_link if event_link else "No Link"
        )
        msg = f"DB Node saved session tracking ID: {record_id}."
    except Exception as e:
        print(f"Database Error: {e}")
        record_id = None
        msg = "DB Node failed to save."

    return {
        "db_record_id": record_id,
        "messages": [{"role": "system", "content": msg}]
    }
from core.state import NotschoolState
from db.crud import save_learning_path

def db_node(state: NotschoolState) -> dict:
    """
    Extracts the finalized learning path from the state and persists it to SQLite.
    """
    goal = state["goal"]
    curriculum = state.get("curriculum_json", {})
    resources = state.get("youtube_urls", [])

    try:
        record_id = save_learning_path(goal, curriculum, resources)
        msg = f"Successfully saved state to database with ID: {record_id}"
    except Exception as e:
        print(f"Database Node Error: {e}")
        record_id = None
        msg = f"Database save failed: {e}"

    return {
        "db_record_id": record_id,
        "messages": [{"role": "system", "content": msg}]
    }
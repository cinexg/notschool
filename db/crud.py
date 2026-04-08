import sqlite3
from db.schema import DB_FILE

def add_session(goal: str, module_name: str, scheduled_time: str, event_link: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO study_sessions (goal, module_name, scheduled_time, event_link) VALUES (?, ?, ?, ?)",
        (goal, module_name, scheduled_time, event_link)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def get_missed_sessions(current_time: str):
    """Fetches sessions where the scheduled time is in the past and status is pending."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, goal, module_name, scheduled_time FROM study_sessions WHERE scheduled_time < ? AND status = 'pending'",
        (current_time,)
    )
    missed = cursor.fetchall()
    conn.close()
    return missed

def update_session_status(session_id: int, new_time: str, new_link: str, status: str = 'rescheduled'):
    """Updates a session after it has been shifted to a new day."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE study_sessions SET scheduled_time = ?, event_link = ?, status = ? WHERE id = ?",
        (new_time, new_link, status, session_id)
    )
    conn.commit()
    conn.close()
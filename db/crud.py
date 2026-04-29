import sqlite3
import json
from datetime import datetime, timezone
from db.schema import DB_FILE


def _utc_now() -> str:
    """Timezone-aware UTC timestamp formatted to match SQLite's CURRENT_TIMESTAMP."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- USERS ----------------

def upsert_user(user_id: str, email: str, name: str = None, picture: str = None):
    """Create user if missing, update last_login otherwise."""
    conn = _conn()
    cur = conn.cursor()
    now = _utc_now()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE users SET last_login = ?, name = COALESCE(?, name), picture = COALESCE(?, picture) WHERE user_id = ?",
            (now, name, picture, user_id),
        )
    else:
        cur.execute(
            "INSERT INTO users (user_id, email, name, picture, created_at, last_login) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email, name, picture, now, now),
        )
    conn.commit()
    conn.close()


def get_user(user_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------- CURRICULA ----------------

def add_curriculum(user_id: str, goal: str, mode: str, title: str,
                   curriculum_json: dict, youtube_urls: list,
                   opportunities: list, web_trends: list) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO curricula
           (user_id, goal, mode, title, curriculum_json, youtube_urls_json, opportunities_json, web_trends_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id, goal, mode, title,
            json.dumps(curriculum_json or {}),
            json.dumps(youtube_urls or []),
            json.dumps(opportunities or []),
            json.dumps(web_trends or []),
        ),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def get_curriculum(curriculum_id: int):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM curricula WHERE id = ?", (curriculum_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["curriculum_json"] = json.loads(d.get("curriculum_json") or "{}")
    d["youtube_urls"] = json.loads(d.get("youtube_urls_json") or "[]")
    d["opportunities"] = json.loads(d.get("opportunities_json") or "[]")
    d["web_trends"] = json.loads(d.get("web_trends_json") or "[]")
    return d


def get_user_curricula(user_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, goal, mode, title, created_at FROM curricula WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_curriculum(curriculum_id: int, user_id: str) -> bool:
    """Cascade-delete a curriculum and all related sessions, quizzes, doubts (user-scoped)."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM curricula WHERE id = ? AND user_id = ?", (curriculum_id, user_id))
    deleted = cur.rowcount > 0
    cur.execute("DELETE FROM study_sessions WHERE curriculum_id = ? AND user_id = ?", (curriculum_id, user_id))
    cur.execute("DELETE FROM quizzes WHERE curriculum_id = ? AND user_id = ?", (curriculum_id, user_id))
    cur.execute("DELETE FROM doubts WHERE curriculum_id = ? AND user_id = ?", (curriculum_id, user_id))
    conn.commit()
    conn.close()
    return deleted


# ---------------- STUDY SESSIONS ----------------

def add_session(user_id: str, curriculum_id: int, goal: str, module_name: str,
                module_description: str, module_day: int, duration_hours: float,
                scheduled_time: str, event_link: str = None, event_id: str = None,
                youtube_url: str = None) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO study_sessions
           (user_id, curriculum_id, goal, module_name, module_description, module_day,
            duration_hours, scheduled_time, event_link, event_id, youtube_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, curriculum_id, goal, module_name, module_description, module_day,
         duration_hours, scheduled_time, event_link, event_id, youtube_url),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def get_user_sessions(user_id: str, curriculum_id: int = None):
    conn = _conn()
    cur = conn.cursor()
    if curriculum_id is not None:
        cur.execute(
            "SELECT * FROM study_sessions WHERE user_id = ? AND curriculum_id = ? ORDER BY scheduled_time ASC",
            (user_id, curriculum_id),
        )
    else:
        cur.execute(
            "SELECT * FROM study_sessions WHERE user_id = ? ORDER BY scheduled_time ASC",
            (user_id,),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def mark_session_complete(session_id: int, user_id: str) -> bool:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE study_sessions SET status = 'completed' WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def get_all_event_ids(user_id: str = None) -> list[str]:
    conn = _conn()
    cur = conn.cursor()
    if user_id:
        cur.execute("SELECT event_id FROM study_sessions WHERE event_id IS NOT NULL AND user_id = ?", (user_id,))
    else:
        cur.execute("SELECT event_id FROM study_sessions WHERE event_id IS NOT NULL")
    ids = [r[0] for r in cur.fetchall()]
    conn.close()
    return ids


def get_missed_sessions(current_time: str, user_id: str = None):
    conn = _conn()
    cur = conn.cursor()
    if user_id:
        cur.execute(
            "SELECT id, goal, module_name, scheduled_time FROM study_sessions WHERE scheduled_time < ? AND status = 'pending' AND user_id = ?",
            (current_time, user_id),
        )
    else:
        cur.execute(
            "SELECT id, goal, module_name, scheduled_time FROM study_sessions WHERE scheduled_time < ? AND status = 'pending'",
            (current_time,),
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def update_session_status(session_id: int, new_time: str, new_link: str, status: str = 'rescheduled'):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE study_sessions SET scheduled_time = ?, event_link = ?, status = ? WHERE id = ?",
        (new_time, new_link, status, session_id),
    )
    conn.commit()
    conn.close()


def reset_user_data(user_id: str):
    """Clears all of a user's data."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM study_sessions WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM quizzes WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM doubts WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM curricula WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ---------------- QUIZZES ----------------

def add_quiz(user_id: str, curriculum_id: int, module_day: int, module_topic: str, questions: list) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO quizzes (user_id, curriculum_id, module_day, module_topic, questions_json, total)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, curriculum_id, module_day, module_topic, json.dumps(questions), len(questions)),
    )
    qid = cur.lastrowid
    conn.commit()
    conn.close()
    return qid


def get_quiz(quiz_id: int, user_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM quizzes WHERE id = ? AND user_id = ?", (quiz_id, user_id))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["questions"] = json.loads(d.get("questions_json") or "[]")
    return d


def get_quiz_for_module(user_id: str, curriculum_id: int, module_day: int):
    """Return the most recent quiz for this module, if any."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM quizzes WHERE user_id = ? AND curriculum_id = ? AND module_day = ? ORDER BY created_at DESC LIMIT 1",
        (user_id, curriculum_id, module_day),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["questions"] = json.loads(d.get("questions_json") or "[]")
    return d


def submit_quiz_score(quiz_id: int, user_id: str, score: int) -> bool:
    conn = _conn()
    cur = conn.cursor()
    now = _utc_now()
    cur.execute(
        "UPDATE quizzes SET score = ?, attempted_at = ? WHERE id = ? AND user_id = ?",
        (score, now, quiz_id, user_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


# ---------------- DOUBTS ----------------

def add_doubt(user_id: str, question: str, answer: str,
              curriculum_id: int = None, module_day: int = None) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO doubts (user_id, curriculum_id, module_day, question, answer) VALUES (?, ?, ?, ?, ?)",
        (user_id, curriculum_id, module_day, question, answer),
    )
    did = cur.lastrowid
    conn.commit()
    conn.close()
    return did


def get_user_doubts(user_id: str, curriculum_id: int = None, limit: int = 50):
    conn = _conn()
    cur = conn.cursor()
    if curriculum_id is not None:
        cur.execute(
            "SELECT * FROM doubts WHERE user_id = ? AND curriculum_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, curriculum_id, limit),
        )
    else:
        cur.execute(
            "SELECT * FROM doubts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
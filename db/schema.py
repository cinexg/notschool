import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "notschool.db")


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _add_column_if_missing(cursor, table: str, column_def: str):
    column_name = column_def.split()[0]
    if not _column_exists(cursor, table, column_name):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
        except Exception as e:
            print(f"Migration warning ({table}.{column_name}): {e}")


def init_db():
    """Initializes SQLite with users, curricula, study_sessions, quizzes, doubts."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            picture TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    ''')

    # Curricula (one per generation)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS curricula (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            goal TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'learning',
            title TEXT,
            curriculum_json TEXT,
            youtube_urls_json TEXT,
            opportunities_json TEXT,
            web_trends_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Study Sessions (per module)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal TEXT NOT NULL,
            module_name TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            event_link TEXT,
            event_id TEXT
        )
    ''')

    # Migrations for study_sessions
    _add_column_if_missing(cursor, "study_sessions", "event_id TEXT")
    _add_column_if_missing(cursor, "study_sessions", "user_id TEXT")
    _add_column_if_missing(cursor, "study_sessions", "curriculum_id INTEGER")
    _add_column_if_missing(cursor, "study_sessions", "module_day INTEGER")
    _add_column_if_missing(cursor, "study_sessions", "module_description TEXT")
    _add_column_if_missing(cursor, "study_sessions", "duration_hours REAL")
    _add_column_if_missing(cursor, "study_sessions", "youtube_url TEXT")

    # Quizzes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            curriculum_id INTEGER NOT NULL,
            module_day INTEGER NOT NULL,
            module_topic TEXT,
            questions_json TEXT NOT NULL,
            score INTEGER,
            total INTEGER,
            attempted_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (curriculum_id) REFERENCES curricula(id)
        )
    ''')

    # Doubts (Q&A history)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doubts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            curriculum_id INTEGER,
            module_day INTEGER,
            question TEXT NOT NULL,
            answer TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Useful indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_curricula_user ON curricula(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON study_sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_curriculum ON study_sessions(curriculum_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quizzes_curriculum ON quizzes(curriculum_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doubts_user ON doubts(user_id)")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
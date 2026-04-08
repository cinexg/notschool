import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "notschool.db")

def init_db():
    """Initializes the SQLite database with session tracking."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create the core table for tracking study/interview schedules
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal TEXT NOT NULL,
            module_name TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            status TEXT DEFAULT 'pending', 
            event_link TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
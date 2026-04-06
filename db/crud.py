import sqlite3
import json
from typing import Dict, Any

DB_PATH = "notschool.db"

def init_db():
    """Run this once to establish the schema."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                curriculum JSON,
                resources JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_learning_path(goal: str, curriculum: Dict[str, Any], resources: list[str]) -> int:
    """
    Pure database insert function. 
    Can be tested completely independently of the LLM pipeline.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO learning_paths (goal, curriculum, resources) 
            VALUES (?, ?, ?)
            """, 
            (goal, json.dumps(curriculum), json.dumps(resources))
        )
        conn.commit()
        return cursor.lastrowid
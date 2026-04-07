import sqlite3
import json
from typing import Dict, Any, List
from db.schema import CREATE_LEARNING_PATHS_TABLE

DB_PATH = "notschool.db"

def init_db():
    """Initializes the SQLite schema on startup."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_LEARNING_PATHS_TABLE)
        conn.commit()

def save_learning_path(goal: str, curriculum: Dict[str, Any], resources: List[str]) -> int:
    """
    Inserts a newly generated curriculum into the SQLite database.
    Returns the primary key ID of the inserted row.
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
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timedelta
import pytz
import os
import json
from db.crud import get_missed_sessions, update_session_status
from tools.calendar_client import create_calendar_event

# 1. LOAD CONFIG FIRST: This reads the .env file into memory
from core.config import validate_environment
validate_environment()

# 2. THEN IMPORT GRAPH: Now the agents can safely find the API keys
from core.graph import notschool_app

app = FastAPI(title="Notschool OS Backend", version="1.0.0")

# Allow the frontend (index.html) to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the frontend UI"""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    return FileResponse(frontend_path)

@app.post("/api/generate")
async def generate_learning_path(
    goal: str = Form(...),
    mode: str = Form("learning"), # Defaults to learning mode
    access_token: str = Form(None), # Dynamic OAuth token from the user
    image: UploadFile = File(None)
):
    """Main entry point. Triggers the Notschool LangGraph multi-agent system."""
    try:
        image_bytes = await image.read() if image else None
        image_mime_type = image.content_type if image and image.content_type else "image/jpeg"
        local_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

        # Initialize the updated strict LangGraph state
        initial_state = {
            "goal": goal,
            "mode": mode,
            "user_access_token": access_token,
            "image_bytes": image_bytes,
            "image_mime_type": image_mime_type,
            "curriculum_json": None,
            "youtube_urls": [],
            "web_trends": [],
            "calendar_event_id": None,
            "db_record_id": None,
            "messages": [{"role": "user", "content": goal}],
            "user_timezone": "Asia/Kolkata",
            "current_timestamp": current_time
        }

        final_state = notschool_app.invoke(initial_state)
        final_state.pop("image_bytes", None) 
        
        return {"status": "success", "data": final_state}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reschedule")
async def auto_reschedule_missed(access_token: str = Form(...)):
    """Scans DB for missed sessions and shifts them forward by 1 day."""
    if not access_token:
        raise HTTPException(status_code=400, detail="Google Access Token required")

    local_tz = pytz.timezone('Asia/Kolkata')
    current_time_obj = datetime.now(local_tz)
    current_time_str = current_time_obj.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Check DB for missed sessions
    missed_sessions = get_missed_sessions(current_time_str)
    
    if not missed_sessions:
        return {"status": "success", "message": "You are all caught up! No missed sessions."}

    rescheduled_count = 0
    
    # 2. Iterate through missed sessions and shift them
    for session in missed_sessions:
        session_id, goal, module_name, old_time_str = session
        
        # Shift the schedule to tomorrow
        new_start_time = current_time_obj + timedelta(days=1)
        new_end_time = new_start_time + timedelta(hours=1)
        
        summary = f"Notschool Rescheduled: {module_name}"
        description = f"Goal: {goal}\n\nYou missed this session yesterday. Notschool OS has automatically rescheduled it for you so you don't fall behind!"
        
        # Create new calendar event
        new_event_link = create_calendar_event(
            summary=summary,
            description=description,
            start_time_iso=new_start_time.isoformat(),
            end_time_iso=new_end_time.isoformat(),
            timezone="Asia/Kolkata",
            access_token=access_token
        )
        
        if new_event_link:
            # Update the DB record with the new time and status
            update_session_status(
                session_id=session_id, 
                new_time=new_start_time.strftime("%Y-%m-%d %H:%M:%S"), 
                new_link=new_event_link
            )
            rescheduled_count += 1

    return {
        "status": "success", 
        "message": f"Successfully restructured and rescheduled {rescheduled_count} missed sessions!"
    }

@app.post("/api/reset")
async def reset_database():
    """Clears the study sessions table for a fresh hackathon demo."""
    import sqlite3
    from db.schema import DB_FILE
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM study_sessions")
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Demo reset successfully! All local progress cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from db.schema import init_db; init_db()
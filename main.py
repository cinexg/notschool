from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime
import pytz
import os

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

@app.get("/")
async def serve_frontend():
    """Serve the frontend UI"""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    return FileResponse(frontend_path)

@app.post("/api/generate")
async def generate_learning_path(
    goal: str = Form(...),
    image: UploadFile = File(None)
):
    """
    Main entry point. Triggers the Notschool LangGraph multi-agent system.
    """
    try:
        # 1. Read raw bytes (No need for heavy image libraries here)
        image_bytes = await image.read() if image else None

        # 2. Setup precise temporal context for the Scheduler agent
        local_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

        # 3. Initialize the strict LangGraph state
        initial_state = {
            "goal": goal,
            "image_bytes": image_bytes,
            "curriculum_json": None,
            "youtube_urls": [],
            "calendar_event_id": None,
            "db_record_id": None,
            "messages": [{"role": "user", "content": goal}],
            "user_timezone": "Asia/Kolkata",
            "current_timestamp": current_time
        }

        # 4. Execute the Graph
        final_state = notschool_app.invoke(initial_state)
        
        # 5. Clean the response (Frontend doesn't need the image bytes back)
        final_state.pop("image_bytes", None) 
        
        return {"status": "success", "data": final_state}

    except Exception as e:
        # Catch orchestration errors and return a clean HTTP response
        raise HTTPException(status_code=500, detail=str(e))
    
from db.crud import init_db; init_db()
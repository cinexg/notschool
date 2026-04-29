from fastapi import FastAPI, Form, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timedelta
from typing import Optional
import pytz
import os

# 1. LOAD CONFIG FIRST
from core.config import validate_environment
validate_environment()

# 2. THEN IMPORT GRAPH
from core.graph import notschool_app

from db.schema import init_db, DB_FILE
from db import crud
from tools.auth_client import verify_google_token
from tools.calendar_client import create_calendar_event, delete_calendar_event
from tools.quiz_generator import generate_quiz, QuizGenerationError
from tools.doubt_resolver import resolve_doubt, DoubtResolverError


app = FastAPI(title="Notschool OS Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# ---------------- AUTH HELPERS ----------------

def _require_user(authorization: Optional[str]) -> dict:
    """
    Verifies the Bearer token and returns the user info dict.
    Raises 401 on failure.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    info = verify_google_token(token)
    if not info:
        raise HTTPException(status_code=401, detail="Invalid or expired Google access token")
    crud.upsert_user(
        user_id=info["sub"],
        email=info["email"],
        name=info.get("name"),
        picture=info.get("picture"),
    )
    return {**info, "access_token": token}


# ---------------- ROUTES ----------------

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/api/health")
async def health_check():
    """Cheap readiness probe — does NOT call any external API."""
    return {
        "status": "ok",
        "service": "notschool-os",
        "version": app.version,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "youtube_configured": bool(os.getenv("YOUTUBE_API_KEY")),
    }


@app.post("/api/auth/verify")
async def auth_verify(authorization: Optional[str] = Header(None)):
    """Frontend calls this right after Google OAuth to register the user."""
    user = _require_user(authorization)
    return {
        "status": "success",
        "user": {
            "user_id": user["sub"],
            "email": user["email"],
            "name": user.get("name"),
            "picture": user.get("picture"),
        },
    }


@app.post("/api/generate")
async def generate_learning_path(
    goal: str = Form(...),
    mode: str = Form("learning"),
    image: UploadFile = File(None),
    authorization: Optional[str] = Header(None),
):
    """Triggers the full multi-agent pipeline. Requires login."""
    user = _require_user(authorization)
    try:
        image_bytes = await image.read() if image else None
        image_mime_type = image.content_type if image and image.content_type else "image/jpeg"
        local_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

        initial_state = {
            "goal": goal,
            "mode": mode,
            "user_id": user["sub"],
            "user_access_token": user["access_token"],
            "image_bytes": image_bytes,
            "image_mime_type": image_mime_type,
            "curriculum_json": None,
            "youtube_urls": [],
            "web_trends": [],
            "industry_opportunities": [],
            "calendar_event_id": None,
            "calendar_event_ids": [],
            "calendar_event_links": [],
            "db_record_id": None,
            "curriculum_id": None,
            "messages": [{"role": "user", "content": goal}],
            "user_timezone": "Asia/Kolkata",
            "current_timestamp": current_time,
        }

        final_state = notschool_app.invoke(initial_state)
        final_state.pop("image_bytes", None)
        final_state.pop("user_access_token", None)

        return {"status": "success", "data": final_state}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard")
async def get_dashboard(authorization: Optional[str] = Header(None)):
    """Returns the user's curricula list + aggregate stats."""
    user = _require_user(authorization)
    user_id = user["sub"]

    curricula = crud.get_user_curricula(user_id)

    # Per-curriculum stats
    enriched = []
    total_sessions = 0
    completed_sessions = 0
    for c in curricula:
        sessions = crud.get_user_sessions(user_id, c["id"])
        total = len(sessions)
        done = sum(1 for s in sessions if s.get("status") == "completed")
        total_sessions += total
        completed_sessions += done
        enriched.append({
            **c,
            "total_modules": total,
            "completed_modules": done,
            "progress_pct": round((done / total) * 100) if total else 0,
        })

    return {
        "status": "success",
        "user": {
            "user_id": user_id,
            "email": user["email"],
            "name": user.get("name"),
            "picture": user.get("picture"),
        },
        "curricula": enriched,
        "stats": {
            "total_curricula": len(curricula),
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_pct": round((completed_sessions / total_sessions) * 100) if total_sessions else 0,
        },
    }


@app.get("/api/curriculum/{curriculum_id}")
async def get_curriculum_detail(curriculum_id: int, authorization: Optional[str] = Header(None)):
    """Returns the full curriculum + sessions + quiz status."""
    user = _require_user(authorization)
    user_id = user["sub"]

    curr = crud.get_curriculum(curriculum_id)
    if not curr or curr["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    sessions = crud.get_user_sessions(user_id, curriculum_id)

    # Attach quiz status to each session
    for s in sessions:
        q = crud.get_quiz_for_module(user_id, curriculum_id, s.get("module_day") or 0)
        if q:
            s["quiz_id"] = q["id"]
            s["quiz_score"] = q.get("score")
            s["quiz_total"] = q.get("total")
        else:
            s["quiz_id"] = None
            s["quiz_score"] = None
            s["quiz_total"] = None

    return {
        "status": "success",
        "curriculum": curr,
        "sessions": sessions,
    }


@app.post("/api/session/complete")
async def complete_session(session_id: int = Form(...), authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    ok = crud.mark_session_complete(session_id, user["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "session_id": session_id}


@app.post("/api/quiz/generate")
async def quiz_generate(
    curriculum_id: int = Form(...),
    module_day: int = Form(...),
    force: Optional[bool] = Form(False),
    authorization: Optional[str] = Header(None),
):
    """Generate or fetch the quiz for a specific module.

    Pass `force=true` to bypass the cache and produce a brand-new quiz —
    used by the 'Generate fresh quiz' button after a learner has retaken it.
    """
    user = _require_user(authorization)
    user_id = user["sub"]

    curr = crud.get_curriculum(curriculum_id)
    if not curr or curr["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    if not force:
        existing = crud.get_quiz_for_module(user_id, curriculum_id, module_day)
        if existing:
            return {"status": "success", "quiz": existing, "cached": True}

    # Find module by day number — tolerate the day being stored as either int or str
    modules = (curr.get("curriculum_json") or {}).get("modules", []) or []

    def _day_of(m):
        try:
            return int(m.get("day"))
        except (TypeError, ValueError):
            return None

    module = next((m for m in modules if isinstance(m, dict) and _day_of(m) == module_day), None)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    try:
        questions = generate_quiz(
            goal=curr["goal"],
            module_topic=module.get("topic", ""),
            module_description=module.get("description", ""),
            num_questions=5,
        )
    except QuizGenerationError as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            detail = "AI quiz service is rate-limited (free-tier quota hit). Please wait a minute and try again."
        else:
            detail = "Quiz unavailable right now — please retry."
        raise HTTPException(status_code=503, detail=detail)

    quiz_id = crud.add_quiz(user_id, curriculum_id, module_day, module.get("topic", ""), questions)
    quiz = crud.get_quiz(quiz_id, user_id)
    return {"status": "success", "quiz": quiz, "cached": False}


@app.post("/api/quiz/submit")
async def quiz_submit(
    quiz_id: int = Form(...),
    score: int = Form(...),
    authorization: Optional[str] = Header(None),
):
    user = _require_user(authorization)
    ok = crud.submit_quiz_score(quiz_id, user["sub"], score)
    if not ok:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return {"status": "success", "quiz_id": quiz_id, "score": score}


@app.post("/api/doubt/ask")
async def ask_doubt(
    question: str = Form(...),
    curriculum_id: Optional[int] = Form(None),
    module_day: Optional[int] = Form(None),
    authorization: Optional[str] = Header(None),
):
    user = _require_user(authorization)
    user_id = user["sub"]

    q = (question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    goal = ""
    module_topic = ""
    module_description = ""
    if curriculum_id:
        curr = crud.get_curriculum(curriculum_id)
        if curr and curr["user_id"] == user_id:
            goal = curr.get("goal", "")
            if module_day:
                modules = (curr.get("curriculum_json") or {}).get("modules", []) or []
                def _day_of(x):
                    try:
                        return int(x.get("day"))
                    except (TypeError, ValueError):
                        return None
                m = next((x for x in modules if isinstance(x, dict) and _day_of(x) == module_day), None)
                if m:
                    module_topic = m.get("topic", "")
                    module_description = m.get("description", "")

    try:
        answer = resolve_doubt(q, goal, module_topic, module_description)
    except DoubtResolverError as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            detail = "AI tutor is rate-limited (free-tier quota hit). Please wait a minute and try again."
        else:
            detail = "AI tutor is temporarily unavailable. Please retry in a moment."
        raise HTTPException(status_code=503, detail=detail)

    crud.add_doubt(user_id, q, answer, curriculum_id, module_day)
    return {"status": "success", "answer": answer}


@app.get("/api/doubts")
async def get_doubts(
    curriculum_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    user = _require_user(authorization)
    rows = crud.get_user_doubts(user["sub"], curriculum_id)
    return {"status": "success", "doubts": rows}


@app.post("/api/reschedule")
async def auto_reschedule_missed(authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    user_id = user["sub"]
    access_token = user["access_token"]

    local_tz = pytz.timezone('Asia/Kolkata')
    current_time_obj = datetime.now(local_tz)
    current_time_str = current_time_obj.strftime("%Y-%m-%d %H:%M:%S")

    missed_sessions = crud.get_missed_sessions(current_time_str, user_id=user_id)
    if not missed_sessions:
        return {"status": "success", "message": "You are all caught up! No missed sessions."}

    rescheduled_count = 0
    for session in missed_sessions:
        session_id, goal, module_name, _ = session

        new_start_time = current_time_obj + timedelta(days=1)
        new_end_time = new_start_time + timedelta(hours=1)

        summary = f"Notschool Rescheduled: {module_name}"
        description = f"Goal: {goal}\n\nThis session was rescheduled by Notschool OS."

        new_event_link, _ = create_calendar_event(
            summary=summary,
            description=description,
            start_time_iso=new_start_time.isoformat(),
            end_time_iso=new_end_time.isoformat(),
            timezone="Asia/Kolkata",
            access_token=access_token,
        )

        if new_event_link:
            crud.update_session_status(
                session_id=session_id,
                new_time=new_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                new_link=new_event_link,
            )
            rescheduled_count += 1

    return {
        "status": "success",
        "message": f"Successfully rescheduled {rescheduled_count} missed session(s)!",
    }


@app.post("/api/reset")
async def reset_user(authorization: Optional[str] = Header(None)):
    """Wipes the *logged-in user's* data + their calendar events."""
    user = _require_user(authorization)
    user_id = user["sub"]
    access_token = user["access_token"]

    deleted_events = 0
    event_ids = crud.get_all_event_ids(user_id=user_id)
    for eid in event_ids:
        if delete_calendar_event(eid, access_token):
            deleted_events += 1

    crud.reset_user_data(user_id)

    return {
        "status": "success",
        "message": f"Cleared your data. Removed {deleted_events} calendar event(s).",
    }


@app.delete("/api/curriculum/{curriculum_id}")
async def delete_curriculum_endpoint(curriculum_id: int, authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    user_id = user["sub"]
    access_token = user["access_token"]

    sessions = crud.get_user_sessions(user_id, curriculum_id)
    for s in sessions:
        if s.get("event_id"):
            delete_calendar_event(s["event_id"], access_token)

    ok = crud.delete_curriculum(curriculum_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return {"status": "success", "message": "Roadmap deleted."}


# Init DB on import
init_db()
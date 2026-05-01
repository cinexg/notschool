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
from tools.guest_auth import issue_guest_token, verify_guest_token, is_guest_token
from tools.calendar_client import (
    create_calendar_event,
    delete_calendar_event,
    update_calendar_event,
)
from agents.scheduler_node import timeframe_to_timedelta, VALID_UNITS
from tools.quiz_generator import generate_quiz, QuizGenerationError
from tools.doubt_resolver import resolve_doubt, DoubtResolverError, summarize_for_title


app = FastAPI(title="Notschool OS Backend", version="2.1.0")

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

    Accepts two token shapes:
      - Google OAuth access tokens (full features, including Calendar sync).
      - HMAC-signed guest tokens issued by /api/auth/guest (no Calendar; lets
        evaluators try the product without a Google account).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()

    if is_guest_token(token):
        info = verify_guest_token(token)
        if not info:
            raise HTTPException(status_code=401, detail="Invalid or expired guest token")
        crud.upsert_user(
            user_id=info["sub"],
            email=info["email"],
            name=info.get("name"),
            picture=info.get("picture"),
        )
        # Empty access_token signals "no Google scope" to downstream callers
        # (calendar_client treats it as a no-op).
        return {**info, "access_token": "", "is_guest": True}

    info = verify_google_token(token)
    if not info:
        raise HTTPException(status_code=401, detail="Invalid or expired Google access token")
    crud.upsert_user(
        user_id=info["sub"],
        email=info["email"],
        name=info.get("name"),
        picture=info.get("picture"),
    )
    return {**info, "access_token": token, "is_guest": False}


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
    profile = crud.get_user(user["sub"]) or {}
    return {
        "status": "success",
        "user": {
            "user_id": user["sub"],
            "email": user["email"],
            "name": user.get("name"),
            "picture": user.get("picture"),
            "is_guest": bool(user.get("is_guest")),
            "profile": _profile_payload(profile),
        },
    }


@app.post("/api/auth/guest")
async def auth_guest():
    """Issue a fresh guest identity. Lets evaluators explore Notschool without
    a Google account — Calendar sync is disabled for guests, but generation,
    quizzes, doubts, and the dashboard all work end-to-end.

    No request body is required. We deliberately avoid `Form(None)` here because
    fetch() sending an empty FormData() produces a multipart body with zero
    parts, which python-multipart rejects as "There was an error parsing the
    body".
    """
    info = issue_guest_token(name=None)
    crud.upsert_user(
        user_id=info["user_id"],
        email=info["email"],
        name=info["name"],
        picture=None,
    )
    profile = crud.get_user(info["user_id"]) or {}
    return {
        "status": "success",
        "token": info["token"],
        "user": {
            "user_id": info["user_id"],
            "email": info["email"],
            "name": info["name"],
            "picture": None,
            "is_guest": True,
            "profile": _profile_payload(profile),
        },
    }


def _profile_payload(profile: dict) -> dict:
    """Strip non-profile DB columns and shape the response for the frontend."""
    if not profile:
        return {
            "display_name": None,
            "age": None,
            "skills": [],
            "interests": [],
            "learning_style": None,
        }
    return {
        "display_name": profile.get("display_name") or None,
        "age": profile.get("age"),
        "skills": profile.get("skills") or [],
        "interests": profile.get("interests") or [],
        "learning_style": profile.get("learning_style") or None,
    }


@app.get("/api/profile")
async def get_profile(authorization: Optional[str] = Header(None)):
    """Returns the user's personalisation profile."""
    user = _require_user(authorization)
    profile = crud.get_user(user["sub"]) or {}
    return {"status": "success", "profile": _profile_payload(profile)}


@app.put("/api/profile")
async def update_profile(
    display_name: Optional[str] = Form(None),
    age: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    learning_style: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Save personalisation fields. `skills` and `interests` are comma-separated.

    `age` is accepted as a string so an empty form value clears it instead of
    blowing up on int() coercion.
    """
    user = _require_user(authorization)

    age_val = None
    if age is not None and str(age).strip() != "":
        try:
            age_val = int(age)
        except ValueError:
            raise HTTPException(status_code=400, detail="Age must be a whole number.")
        if age_val < 5 or age_val > 120:
            raise HTTPException(status_code=400, detail="Age must be between 5 and 120.")

    refreshed = crud.update_user_profile(
        user_id=user["sub"],
        display_name=display_name,
        age=age_val,
        skills=skills,
        interests=interests,
        learning_style=learning_style,
    )
    if refreshed is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "success", "profile": _profile_payload(refreshed)}


@app.post("/api/generate")
async def generate_learning_path(
    goal: str = Form(...),
    image: UploadFile = File(None),
    timeframe_amount: Optional[str] = Form(None),
    timeframe_unit: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Triggers the full multi-agent pipeline. Requires login.

    `timeframe_amount` and `timeframe_unit` (min/hour/day/week) control the
    spacing between consecutive modules. Defaults to 1 day so omitted values
    behave the same as the original 7-day-roadmap experience.
    """
    user = _require_user(authorization)

    try:
        tf_amount = max(1, int(timeframe_amount)) if timeframe_amount else 1
    except ValueError:
        raise HTTPException(status_code=400, detail="timeframe_amount must be a whole number ≥ 1.")
    tf_unit = (timeframe_unit or "day").strip().lower()
    if tf_unit not in VALID_UNITS:
        raise HTTPException(status_code=400, detail=f"timeframe_unit must be one of {VALID_UNITS}.")

    try:
        image_bytes = await image.read() if image else None
        image_mime_type = image.content_type if image and image.content_type else "image/jpeg"
        local_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

        profile = crud.get_user(user["sub"]) or {}

        initial_state = {
            "goal": goal,
            "mode": "learning",
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
            "user_profile": _profile_payload(profile),
            "timeframe_amount": tf_amount,
            "timeframe_unit": tf_unit,
        }

        final_state = notschool_app.invoke(initial_state)
        final_state.pop("image_bytes", None)
        final_state.pop("user_access_token", None)

        # Surface a calendar status flag so the frontend can warn the user if
        # events failed to schedule (e.g. missing scope).
        booked = sum(1 for e in (final_state.get("calendar_event_ids") or []) if e)
        modules = ((final_state.get("curriculum_json") or {}).get("modules") or [])
        final_state["calendar_status"] = {
            "booked": booked,
            "expected": len(modules),
            "ok": booked == len(modules) and len(modules) > 0,
        }

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

    enriched = []
    total_sessions = 0
    completed_sessions = 0
    next_session = None
    for c in curricula:
        sessions = crud.get_user_sessions(user_id, c["id"])
        total = len(sessions)
        done = sum(1 for s in sessions if s.get("status") == "completed")
        total_sessions += total
        completed_sessions += done
        # Find soonest pending session across all curricula
        for s in sessions:
            if s.get("status") != "completed" and s.get("scheduled_time"):
                if next_session is None or s["scheduled_time"] < next_session["scheduled_time"]:
                    next_session = {
                        **s,
                        "curriculum_title": c.get("title") or c.get("goal"),
                        "timeframe_unit": c.get("timeframe_unit"),
                        "timeframe_amount": c.get("timeframe_amount"),
                    }
        enriched.append({
            **c,
            "total_modules": total,
            "completed_modules": done,
            "progress_pct": round((done / total) * 100) if total else 0,
        })

    quiz_stats = crud.get_quiz_progress(user_id)
    streak = crud.get_learning_streak(user_id)

    return {
        "status": "success",
        "user": {
            "user_id": user_id,
            "email": user["email"],
            "name": user.get("name"),
            "picture": user.get("picture"),
            "is_guest": bool(user.get("is_guest")),
        },
        "curricula": enriched,
        "next_session": next_session,
        "stats": {
            "total_curricula": len(curricula),
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_pct": round((completed_sessions / total_sessions) * 100) if total_sessions else 0,
            "quizzes_attempted": quiz_stats["quizzes_attempted"],
            "quiz_accuracy_pct": quiz_stats["accuracy_pct"],
            "current_streak": streak["current_streak"],
            "best_streak": streak["best_streak"],
            "weekly_completed": streak["weekly_completed"],
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

    quiz_stats = crud.get_quiz_progress(user_id, curriculum_id)

    return {
        "status": "success",
        "curriculum": curr,
        "sessions": sessions,
        "quiz_stats": quiz_stats,
    }


@app.post("/api/session/complete")
async def complete_session(session_id: int = Form(...), authorization: Optional[str] = Header(None)):
    """Mark a session done AND remove the linked Google Calendar event.

    Enforces sequential completion — Day N can only be marked done once every
    earlier module in the same curriculum is already completed. Returning 409
    so the frontend can surface a clean message instead of generic 500.
    """
    user = _require_user(authorization)
    user_id = user["sub"]
    access_token = user["access_token"]

    session = crud.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("status") == "completed":
        return {"status": "success", "session_id": session_id, "calendar_removed": False}

    curriculum_id = session.get("curriculum_id")
    module_day = session.get("module_day")
    if curriculum_id and module_day is not None:
        first_pending_day = crud.get_first_incomplete_module_day(user_id, curriculum_id)
        if first_pending_day is not None and module_day > first_pending_day:
            raise HTTPException(
                status_code=409,
                detail=f"Finish Day {first_pending_day} first — modules must be completed in order.",
            )

    calendar_removed = False
    if session.get("event_id"):
        calendar_removed = delete_calendar_event(session["event_id"], access_token)

    ok = crud.mark_session_complete(session_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "status": "success",
        "session_id": session_id,
        "calendar_removed": calendar_removed,
    }


@app.post("/api/quiz/generate")
async def quiz_generate(
    curriculum_id: int = Form(...),
    module_day: int = Form(...),
    force: Optional[bool] = Form(False),
    authorization: Optional[str] = Header(None),
):
    """Generate or fetch the quiz for a specific module."""
    user = _require_user(authorization)
    user_id = user["sub"]

    curr = crud.get_curriculum(curriculum_id)
    if not curr or curr["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    if not force:
        existing = crud.get_quiz_for_module(user_id, curriculum_id, module_day)
        if existing:
            return {"status": "success", "quiz": existing, "cached": True}

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
    chat_id: Optional[int] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Ask the AI tutor a question. If `chat_id` is provided, the tutor sees the
    full prior conversation; otherwise a fresh chat thread is created and its
    id is returned so the client can continue the conversation."""
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

    history: list[dict] = []
    is_new_chat = False
    if chat_id:
        existing = crud.get_chat(chat_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Chat not found")
        history = [{"question": m["question"], "answer": m.get("answer", "")}
                   for m in existing.get("messages", [])]
    else:
        chat_id = crud.create_chat(
            user_id=user_id,
            curriculum_id=curriculum_id,
            module_day=module_day,
            title=summarize_for_title(q),
        )
        is_new_chat = True

    try:
        profile = _profile_payload(crud.get_user(user_id) or {})
        answer = resolve_doubt(q, goal, module_topic, module_description,
                               history=history, profile=profile)
    except DoubtResolverError as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            detail = "AI tutor is rate-limited (free-tier quota hit). Please wait a minute and try again."
        else:
            detail = "AI tutor is temporarily unavailable. Please retry in a moment."
        raise HTTPException(status_code=503, detail=detail)

    crud.add_doubt(user_id, q, answer, curriculum_id, module_day, chat_id=chat_id)
    crud.touch_chat(chat_id, user_id, title=summarize_for_title(q) if is_new_chat else None)

    return {
        "status": "success",
        "answer": answer,
        "chat_id": chat_id,
        "is_new_chat": is_new_chat,
    }


@app.get("/api/doubts")
async def get_doubts(
    curriculum_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    """Legacy flat list — kept for backward compat with older clients."""
    user = _require_user(authorization)
    rows = crud.get_user_doubts(user["sub"], curriculum_id)
    return {"status": "success", "doubts": rows}


# ---------------- CHAT THREADS (multi-turn AI tutor) ----------------

@app.get("/api/chats")
async def list_chats(
    curriculum_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    """List the user's chat threads (newest first), optionally scoped to a curriculum."""
    user = _require_user(authorization)
    chats = crud.get_user_chats(user["sub"], curriculum_id)
    return {"status": "success", "chats": chats}


@app.post("/api/chats")
async def new_chat(
    curriculum_id: Optional[int] = Form(None),
    module_day: Optional[int] = Form(None),
    title: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Create an empty chat thread. The client gets the id back and can post
    its first question via /api/doubt/ask?chat_id=..."""
    user = _require_user(authorization)
    cid = crud.create_chat(
        user_id=user["sub"],
        curriculum_id=curriculum_id,
        module_day=module_day,
        title=(title or "New chat"),
    )
    return {"status": "success", "chat_id": cid}


@app.get("/api/chat/{chat_id}")
async def get_chat(chat_id: int, authorization: Optional[str] = Header(None)):
    """Full chat thread with ordered messages."""
    user = _require_user(authorization)
    chat = crud.get_chat(chat_id, user["sub"])
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "success", "chat": chat}


@app.delete("/api/chat/{chat_id}")
async def delete_chat_endpoint(chat_id: int, authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    ok = crud.delete_chat(chat_id, user["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "success", "message": "Chat deleted."}


@app.post("/api/chat/{chat_id}/rename")
async def rename_chat_endpoint(
    chat_id: int,
    title: str = Form(...),
    authorization: Optional[str] = Header(None),
):
    user = _require_user(authorization)
    title = (title or "").strip()[:80] or "Untitled chat"
    ok = crud.rename_chat(chat_id, user["sub"], title)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "success", "title": title}


def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _reschedule_curriculum(
    *,
    curriculum: dict,
    user_id: str,
    access_token: str,
    now: datetime,
    timezone: str = "Asia/Kolkata",
) -> int:
    """Push every still-pending session in this curriculum forward by enough
    timeframes that the earliest pending session lands strictly in the future.

    Concretely: if Day 4 was the active module and the user blew past it,
    Day 4 slides into Day 5's old slot, Day 5 slides into Day 6's old slot,
    and so on — preserving the original cadence the user picked at generation
    time. Already-completed sessions are NEVER touched.

    Returns the number of sessions whose times changed.
    """
    pending = crud.get_pending_sessions_for_curriculum(user_id, curriculum["id"])
    if not pending:
        return 0

    delta = timeframe_to_timedelta(
        curriculum.get("timeframe_amount") or 1,
        curriculum.get("timeframe_unit") or "day",
    )

    # The "anchor" is the earliest pending session — the one the user is
    # currently supposed to be working on. We only treat it as missed once its
    # FULL window has elapsed, i.e. `earliest + cadence <= now`. That gives the
    # user the entire cadence (5 min, 1 hour, 1 day, …) to mark done before the
    # rescheduler kicks in. Once a miss is detected, every pending session
    # shifts by the same amount so the original spacing is preserved.
    earliest = min((_parse_dt(s["scheduled_time"]) for s in pending if s.get("scheduled_time")), default=None)
    if not earliest or earliest + delta > now:
        return 0

    # Smallest integer N such that earliest + N*delta > now. We use floor+1
    # (rather than ceil) so the new slot is strictly in the future even when
    # the detection lands exactly on a cadence boundary — otherwise the next
    # poll would re-trigger a redundant reschedule.
    delta_seconds = max(1, delta.total_seconds())
    diff_seconds = max(0, (now - earliest).total_seconds())
    shifts_needed = int(diff_seconds // delta_seconds) + 1

    shift = shifts_needed * delta
    changed = 0

    for s in pending:
        old = _parse_dt(s.get("scheduled_time"))
        if not old:
            continue
        new_start = old + shift
        try:
            duration_hours = float(s.get("duration_hours") or 1)
        except (TypeError, ValueError):
            duration_hours = 1.0
        # Mirror the per-cadence event-length clamp the scheduler applies on
        # initial generation so reschedules don't blow up to 1h slots inside
        # 5-min demos. Cap at cadence - 1 minute so consecutive sessions never
        # overlap on the user's calendar.
        cadence_min = max(1, int(delta.total_seconds() / 60))
        max_event = max(1, cadence_min - 1)
        event_minutes = max(1, min(int(duration_hours * 60), max_event))
        new_end = new_start + timedelta(minutes=event_minutes)

        summary = f"📚 Notschool · Day {s.get('module_day') or '?'}: {s.get('module_name', 'Session')}"
        description = (
            f"Goal: {s.get('goal', '')}\n\n"
            f"{s.get('module_description', '')}\n\n"
            "Rescheduled automatically by Notschool OS."
        )

        new_link = s.get("event_link")
        new_event_id = s.get("event_id")

        if s.get("event_id"):
            # Patch the existing event in-place — keeps reminders and the event
            # ID stable across reschedules.
            updated_link, updated_id = update_calendar_event(
                event_id=s["event_id"],
                summary=summary,
                description=description,
                start_time_iso=new_start.isoformat(timespec="seconds"),
                end_time_iso=new_end.isoformat(timespec="seconds"),
                timezone=timezone,
                access_token=access_token,
            )
            if updated_id:
                new_link, new_event_id = updated_link, updated_id
            else:
                # Patch failed (event was deleted in the user's calendar UI).
                # Recreate it so the next miss has something to update.
                new_link, new_event_id = create_calendar_event(
                    summary=summary,
                    description=description,
                    start_time_iso=new_start.isoformat(timespec="seconds"),
                    end_time_iso=new_end.isoformat(timespec="seconds"),
                    timezone=timezone,
                    access_token=access_token,
                    color_id="6",
                )
        else:
            # No prior event — create one now so Calendar stays in sync.
            new_link, new_event_id = create_calendar_event(
                summary=summary,
                description=description,
                start_time_iso=new_start.isoformat(timespec="seconds"),
                end_time_iso=new_end.isoformat(timespec="seconds"),
                timezone=timezone,
                access_token=access_token,
                color_id="6",
            )

        crud.update_session_status(
            session_id=s["id"],
            new_time=new_start.strftime("%Y-%m-%d %H:%M:%S"),
            new_link=new_link,
            new_event_id=new_event_id,
            status="rescheduled",
        )
        changed += 1

    return changed


@app.post("/api/reschedule")
async def auto_reschedule_missed(authorization: Optional[str] = Header(None)):
    """Sweep every curriculum for missed sessions and push the active module
    plus all later pending modules forward by one cadence step. Already-
    completed modules are left untouched. The cadence is whatever the user
    picked at generation time (min / hour / day / week).
    """
    user = _require_user(authorization)
    user_id = user["sub"]
    access_token = user["access_token"]

    local_tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(local_tz).replace(tzinfo=None)

    rescheduled_total = 0
    for curr in crud.get_user_curricula_with_timeframe(user_id):
        rescheduled_total += _reschedule_curriculum(
            curriculum=curr,
            user_id=user_id,
            access_token=access_token,
            now=now,
        )

    if rescheduled_total == 0:
        return {
            "status": "success",
            "rescheduled": 0,
            "message": "You are all caught up! No missed sessions.",
        }

    return {
        "status": "success",
        "rescheduled": rescheduled_total,
        "message": f"Pushed {rescheduled_total} pending module(s) forward.",
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

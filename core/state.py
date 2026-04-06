import operator
from typing import Annotated, TypedDict, List, Any
from datetime import datetime

class NotschoolState(TypedDict):
    """
    The unified state schema for the Notschool OS orchestrator.
    All agents must conform to this schema when updating state.
    """
    # User Inputs
    goal: str
    image_bytes: bytes | None

    # Architect Output
    curriculum_json: dict[str, Any] | None

    # Librarian Output
    youtube_urls: List[str]

    # Scheduler Output
    calendar_event_id: str | None

    # Database Output
    db_record_id: int | None

    # Context & Orchestration
    # Using operator.add allows LangGraph to append messages rather than overwrite them
    messages: Annotated[List[dict], operator.add]
    
    # Crucial for the Scheduler Agent to book accurately
    user_timezone: str 
    current_timestamp: str
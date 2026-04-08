import operator
from typing import Annotated, TypedDict, List, Any, Optional

class NotschoolState(TypedDict):
    """
    The unified state schema for the Notschool OS orchestrator.
    """
    # User Inputs
    goal: str
    mode: str  # "learning" or "interview"
    image_bytes: Optional[bytes]
    image_mime_type: Optional[str]  # Actual MIME type of uploaded image
    user_access_token: Optional[str]  # For multi-tenant calendar auth

    # Agent Outputs
    curriculum_json: Optional[dict[str, Any]]
    youtube_urls: List[str]
    web_trends: List[str] # NEW: For storing latest interview trends
    calendar_event_id: Optional[str]
    db_record_id: Optional[int]

    # Orchestration & Audit Logging
    messages: Annotated[List[dict[str, str]], operator.add]
    
    # Context
    user_timezone: str 
    current_timestamp: str
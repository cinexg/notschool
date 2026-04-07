import operator
from typing import Annotated, TypedDict, List, Any, Optional

class NotschoolState(TypedDict):
    """
    The unified state schema for the Notschool OS orchestrator.
    If a variable is not defined here, no agent can access or return it.
    """
    # User Inputs
    goal: str
    image_bytes: Optional[bytes]

    # Agent Outputs
    curriculum_json: Optional[dict[str, Any]]
    youtube_urls: List[str]
    calendar_event_id: Optional[str]
    db_record_id: Optional[int]

    # Orchestration & Audit Logging
    # operator.add ensures nodes append to the list rather than overwrite
    messages: Annotated[List[dict[str, str]], operator.add]
    
    # Context (Crucial for the Scheduler Agent)
    user_timezone: str 
    current_timestamp: str
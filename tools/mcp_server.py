# notschool/tools/mcp_server.py
import os
from mcp.server.fastmcp import FastMCP
from typing import List

# Import your existing logic
from tools.youtube_client import search_youtube_videos
from tools.calendar_client import create_calendar_event
from duckduckgo_search import DDGS

# Initialize FastMCP
mcp = FastMCP("Notschool")

@mcp.tool()
def find_video_tutorials(queries: List[str], max_results: int = 1) -> List[str]:
    """
    Search YouTube for educational video tutorials based on specific queries.
    """
    return search_youtube_videos(queries, max_results)

@mcp.tool()
def schedule_study_session(summary: str, description: str, start_time_iso: str, end_time_iso: str, timezone: str, access_token: str = None) -> str:
    """
    Create a Google Calendar event for a study or interview prep session.
    Returns the event URL.
    """
    link = create_calendar_event(summary, description, start_time_iso, end_time_iso, timezone, access_token)
    return link if link else "Failed to schedule event."

@mcp.tool()
def search_web_for_trends(query: str, num_results: int = 3) -> List[str]:
    """
    Search the web for the latest interview trends, tech stacks, or required certifications.
    """
    try:
        with DDGS() as ddgs:
            results = [r["href"] for r in ddgs.text(query, max_results=num_results)]
        return results
    except Exception as e:
        return [f"Search failed: {str(e)}"]

if __name__ == "__main__":
    # This allows the server to run via standard input/output (stdio)
    mcp.run(transport='stdio')
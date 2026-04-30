# notschool/tools/mcp_server.py
import os
from mcp.server.fastmcp import FastMCP
from typing import List

# Import your existing logic
from tools.youtube_client import search_youtube_videos
from tools.calendar_client import create_calendar_event

# `duckduckgo_search` was renamed to `ddgs` in 2025 — prefer the new module name,
# fall back to the old name on older installs so neither breaks the import.
try:
    from ddgs import DDGS  # type: ignore
except ImportError:  # pragma: no cover
    from duckduckgo_search import DDGS  # type: ignore

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

@mcp.tool()
def search_industry_opportunities(goal: str, num_results: int = 5) -> List[dict]:
    """
    Search the web for real-world industry programs, cohorts, bootcamps, hackathons,
    and certifications matching the user's learning goal.
    Returns structured results with title, url, and description.
    """
    try:
        query = f"{goal} 2026 cohort Google Amazon Microsoft bootcamp certification program apply"
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=num_results)) or []
            results = []
            for r in raw:
                url = r.get("href", "") or ""
                title = (r.get("title") or "Initiative").strip()
                provider = ""
                low = (url + " " + title).lower()
                if "google" in low or "deepmind" in low: provider = "Google"
                elif "amazon" in low or "aws" in low: provider = "Amazon"
                elif "microsoft" in low or "azure" in low or "github.com" in low: provider = "Microsoft"
                results.append({
                    "title": title,
                    "url": url,
                    "description": (r.get("body", "") or "")[:160].strip(),
                    "provider": provider,
                    "source": "live",
                })
        return results
    except Exception as e:
        return [{"title": "Search unavailable", "url": "", "description": str(e), "source": "error"}]

if __name__ == "__main__":
    # This allows the server to run via standard input/output (stdio)
    mcp.run(transport='stdio')
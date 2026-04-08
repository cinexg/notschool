from core.state import NotschoolState
from tools.youtube_client import search_youtube_videos

# Import the web search function we added to our MCP Server file
from tools.mcp_server import search_web_for_trends

def librarian_node(state: NotschoolState) -> dict:
    """
    Acts as the Resource Curator. 
    Fetches YouTube videos, and if in interview mode, fetches web trends.
    """
    curriculum = state.get("curriculum_json")
    mode = state.get("mode", "learning")
    goal = state["goal"]
    
    # 1. Fetch YouTube URLs (Standard)
    if not curriculum or not curriculum.get("search_queries"):
        queries = [goal]
    else:
        queries = curriculum["search_queries"]

    youtube_urls = search_youtube_videos(queries=queries, max_results_per_query=1)
    
    # 2. Fetch Web Trends (Interview Mode Only)
    web_trends = []
    if mode == "interview":
        # Create a highly targeted Google Search query
        search_query = f"Latest interview questions, tech stack trends, and certifications for {goal} 2026"
        web_trends = search_web_for_trends(query=search_query, num_results=3)

    return {
        "youtube_urls": youtube_urls,
        "web_trends": web_trends,
        "messages": [{"role": "system", "content": f"Librarian fetched {len(youtube_urls)} videos and {len(web_trends)} trends."}]
    }
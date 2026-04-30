from core.state import NotschoolState
from tools.youtube_client import search_youtube_videos
from tools.mcp_server import search_industry_opportunities


def librarian_node(state: NotschoolState) -> dict:
    """
    Resource Curator. Maps one YouTube video per module (1:1 with modules).
    Also fetches live industry opportunities.
    """
    curriculum = state.get("curriculum_json") or {}
    goal = state["goal"]

    modules = curriculum.get("modules", []) or []

    queries = []
    for mod in modules:
        if not isinstance(mod, dict):
            queries.append(f"{goal} tutorial for beginners")
            continue
        topic = mod.get("topic") or "Module"
        queries.append(f"{topic} tutorial {goal} explained")

    if not queries:
        queries = curriculum.get("search_queries") or [goal]

    youtube_urls = search_youtube_videos(queries=queries, max_results_per_query=1)

    while len(youtube_urls) < len(modules):
        youtube_urls.append("")

    industry_opportunities = search_industry_opportunities(goal=goal, num_results=5)

    return {
        "youtube_urls": youtube_urls,
        "web_trends": [],
        "industry_opportunities": industry_opportunities,
        "messages": [{"role": "system", "content": f"Librarian fetched {len(youtube_urls)} videos, {len(industry_opportunities)} opportunities."}]
    }

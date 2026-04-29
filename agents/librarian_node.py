from core.state import NotschoolState
from tools.youtube_client import search_youtube_videos
from tools.mcp_server import search_web_for_trends, search_industry_opportunities


def librarian_node(state: NotschoolState) -> dict:
    """
    Resource Curator. Maps one YouTube video per module (1:1 with modules).
    Also fetches web trends (interview mode) and live industry opportunities (all modes).
    """
    curriculum = state.get("curriculum_json") or {}
    mode = state.get("mode", "learning")
    goal = state["goal"]

    modules = curriculum.get("modules", []) or []

    # Build per-module YouTube search queries (1:1 with modules)
    queries = []
    for mod in modules:
        if not isinstance(mod, dict):
            queries.append(f"{goal} tutorial for beginners")
            continue
        topic = mod.get("topic") or "Module"
        # Lead with the specific module topic — that's the strongest relevance signal —
        # then add the goal context and an explicit tutorial keyword.
        queries.append(f"{topic} tutorial {goal} explained")

    if not queries:
        queries = curriculum.get("search_queries") or [goal]

    # 1 video per query → parallel to modules
    youtube_urls = search_youtube_videos(queries=queries, max_results_per_query=1)

    # Pad to match modules length (in case a query failed)
    while len(youtube_urls) < len(modules):
        youtube_urls.append("")

    # Web Trends (Interview Mode)
    web_trends = []
    if mode == "interview":
        search_query = f"Latest interview questions, tech stack trends, and certifications for {goal} 2026"
        web_trends = search_web_for_trends(query=search_query, num_results=3)

    # Industry Opportunities (All Modes)
    industry_opportunities = search_industry_opportunities(goal=goal, num_results=5)

    return {
        "youtube_urls": youtube_urls,
        "web_trends": web_trends,
        "industry_opportunities": industry_opportunities,
        "messages": [{"role": "system", "content": f"Librarian fetched {len(youtube_urls)} videos, {len(web_trends)} trends, {len(industry_opportunities)} opportunities."}]
    }
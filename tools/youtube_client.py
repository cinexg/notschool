import os
import re
from googleapiclient.discovery import build
from typing import List


_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _iso_duration_seconds(iso: str) -> int:
    """Parse ISO 8601 YouTube duration (e.g. 'PT1H23M45S') to seconds."""
    if not iso:
        return 0
    m = _DURATION_RE.fullmatch(iso)
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


_QUALITY_KEYWORDS = (
    "tutorial", "course", "crash course", "explained", "guide",
    "for beginners", "full course", "masterclass", "step by step",
    "complete", "learn", "introduction",
)
_BAD_KEYWORDS = (
    "#shorts", "shorts", "tiktok", "compilation", "reaction",
    "in 60 seconds", "in 1 minute",
)
# Channels well-known for high-quality programming/learning content.
_TRUSTED_CHANNELS = {
    "freecodecamp.org", "the net ninja", "traversy media", "academind",
    "fireship", "web dev simplified", "programming with mosh",
    "codewithharry", "javascript mastery", "techworld with nana",
    "google developers", "microsoft developer", "mit opencourseware",
    "harvard university", "cs50", "kevin powell", "theo - t3.gg",
    "ben awad", "sentdex", "corey schafer", "tech with tim",
    "computerphile", "3blue1brown", "two minute papers",
}


def _score_video(item: dict, query: str) -> float:
    """Heuristic ranking — favors substantive, popular, on-topic videos."""
    snippet = item.get("snippet", {}) or {}
    stats = item.get("statistics", {}) or {}
    content = item.get("contentDetails", {}) or {}

    title = (snippet.get("title") or "").lower()
    channel = (snippet.get("channelTitle") or "").lower()
    description = (snippet.get("description") or "").lower()

    seconds = _iso_duration_seconds(content.get("duration", ""))
    # Reject shorts and absurdly long streams outright.
    if seconds < 240 or seconds > 4 * 3600:
        return -1.0

    try:
        views = int(stats.get("viewCount", "0") or 0)
    except (TypeError, ValueError):
        views = 0
    try:
        likes = int(stats.get("likeCount", "0") or 0)
    except (TypeError, ValueError):
        likes = 0

    # Base score: square-root of views dampens runaway popularity bias.
    score = views ** 0.5

    # Engagement bonus.
    if views > 0:
        score *= 1.0 + min(0.5, (likes / max(views, 1)) * 20)

    # Sweet-spot duration (8–45 min) is ideal for tutorials.
    if 8 * 60 <= seconds <= 45 * 60:
        score *= 1.25
    elif seconds > 90 * 60:
        score *= 0.75  # very long courses still useful but less likely a fit

    # Title quality signals.
    if any(k in title for k in _QUALITY_KEYWORDS):
        score *= 1.4
    if any(k in title for k in _BAD_KEYWORDS):
        score *= 0.3

    # Trusted educator bonus.
    if channel in _TRUSTED_CHANNELS or any(c in channel for c in _TRUSTED_CHANNELS):
        score *= 1.5

    # On-topic bonus: how many query tokens appear in title/description.
    q_tokens = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    if q_tokens:
        hits = sum(1 for t in q_tokens if t in title or t in description)
        score *= 1.0 + (hits / len(q_tokens)) * 0.6

    return score


def search_youtube_videos(queries: List[str], max_results_per_query: int = 1) -> List[str]:
    """
    Search YouTube and return high-quality video URLs (one URL per query, in order).
    Filters out Shorts/clickbait, prefers trusted educational channels and tutorial-shaped titles,
    and ranks by view count + engagement + relevance.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("Warning: YOUTUBE_API_KEY not found.")
        return ["" for _ in queries]

    youtube = build("youtube", "v3", developerKey=api_key)
    out: List[str] = []

    for query in queries:
        picked = ""
        try:
            search_resp = youtube.search().list(
                part="snippet",
                maxResults=10,
                q=query,
                type="video",
                videoEmbeddable="true",
                relevanceLanguage="en",
                safeSearch="strict",
                order="relevance",
                videoDuration="medium",  # 4–20 min — good for tutorials
            ).execute()

            ids = [
                it.get("id", {}).get("videoId")
                for it in search_resp.get("items", [])
                if it.get("id", {}).get("videoId")
            ]

            # Backfill with longer-form results if medium gave us nothing.
            if len(ids) < 3:
                long_resp = youtube.search().list(
                    part="snippet",
                    maxResults=8,
                    q=query,
                    type="video",
                    videoEmbeddable="true",
                    relevanceLanguage="en",
                    safeSearch="strict",
                    order="relevance",
                    videoDuration="long",
                ).execute()
                for it in long_resp.get("items", []):
                    vid = it.get("id", {}).get("videoId")
                    if vid and vid not in ids:
                        ids.append(vid)

            if ids:
                details = youtube.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=",".join(ids[:15]),
                ).execute()

                ranked = []
                for v in details.get("items", []):
                    s = _score_video(v, query)
                    if s > 0:
                        ranked.append((s, v["id"]))
                ranked.sort(reverse=True)

                if ranked:
                    picked = f"https://www.youtube.com/watch?v={ranked[0][1]}"
                else:
                    # Last-resort: take the first search result even if it failed our filters.
                    picked = f"https://www.youtube.com/watch?v={ids[0]}"
        except Exception as e:
            print(f"YouTube API error for query '{query}': {e}")

        # We currently return one URL per query; pad to keep 1:1 mapping.
        out.append(picked)
        for _ in range(max_results_per_query - 1):
            out.append("")

    return out

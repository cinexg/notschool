import os
from googleapiclient.discovery import build
from typing import List

def search_youtube_videos(queries: List[str], max_results_per_query: int = 1) -> List[str]:
    """
    Pure tool function to hit the YouTube Data API v3.
    Isolated from any LangGraph state logic.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("Warning: YOUTUBE_API_KEY not found.")
        return []

    youtube = build('youtube', 'v3', developerKey=api_key)
    video_urls = []

    for query in queries:
        try:
            request = youtube.search().list(
                part="snippet",
                maxResults=max_results_per_query,
                q=query,
                type="video"
            )
            response = request.execute()

            for item in response.get('items', []):
                video_id = item['id']['videoId']
                video_urls.append(f"[https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=){video_id}")
                
        except Exception as e:
            print(f"YouTube API Error for query '{query}': {e}")
            continue

    return video_urls
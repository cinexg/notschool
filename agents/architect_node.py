import os
import json
import re
import time
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from core.state import NotschoolState


def _is_transient(exc: Exception) -> bool:
    msg = str(exc)
    return "503" in msg or "UNAVAILABLE" in msg or "429" in msg

def architect_node(state: NotschoolState) -> dict:
    """Acts as the Principal Curriculum Designer."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from the environment!")
        
    client = genai.Client(api_key=api_key)

    goal = state["goal"]
    mode = state.get("mode", "learning")
    image_bytes = state.get("image_bytes")
    image_mime_type = state.get("image_mime_type", "image/jpeg")

    # Supercharged Prompts for Hackathon "Wow" Factor
    if mode == "interview":
        prompt = f"""
        You are an elite Tech Career Coach. The user is doing INTERVIEW PREP for: "{goal}".
        Design a highly actionable, structured prep curriculum. If an image was provided (like a job description), tailor it strictly to that.
        
        You MUST return EXACTLY this JSON structure and nothing else. Give me a full 7-DAY curriculum:
        {{
            "title": "Learning Roadmap: {goal}",
            "modules": [
                {{"day": 1, "topic": "Fundamentals", "description": "Specific details", "duration_hours": 2}},
                {{"day": 2, "topic": "Deep Dive", "description": "Specific details", "duration_hours": 3}},
                {{"day": 3, "topic": "Practice", "description": "Specific details", "duration_hours": 2}},
                {{"day": 4, "topic": "Advanced Concepts", "description": "Specific details", "duration_hours": 3}},
                {{"day": 5, "topic": "Real-world Application", "description": "Specific details", "duration_hours": 4}},
                {{"day": 6, "topic": "Project Building", "description": "Specific details", "duration_hours": 4}},
                {{"day": 7, "topic": "Review & Next Steps", "description": "Specific details", "duration_hours": 2}}
            ],
            "search_queries": ["{goal} basics tutorial full course", "{goal} project tutorial", "Advanced {goal} concepts"],
            "trends": ["Current industry use case 1", "Current industry use case 2"],
            "certifications": ["Relevant Cert to aim for"]
        }}
        """
    else:
        prompt = f"""
        You are an elite AI Professor. The user wants to learn: "{goal}".
        Design a highly actionable, structured learning roadmap. If an image of a syllabus/book index is provided, extract the topics from it!
        
        You MUST return EXACTLY this JSON structure and nothing else. Give me a full 7-DAY curriculum:
        {{
            "title": "Learning Roadmap: {goal}",
            "modules": [
                {{"day": 1, "topic": "Fundamentals", "description": "Specific details", "duration_hours": 2}},
                {{"day": 2, "topic": "Deep Dive", "description": "Specific details", "duration_hours": 3}},
                {{"day": 3, "topic": "Practice", "description": "Specific details", "duration_hours": 2}},
                {{"day": 4, "topic": "Advanced Concepts", "description": "Specific details", "duration_hours": 3}},
                {{"day": 5, "topic": "Real-world Application", "description": "Specific details", "duration_hours": 4}},
                {{"day": 6, "topic": "Project Building", "description": "Specific details", "duration_hours": 4}},
                {{"day": 7, "topic": "Review & Next Steps", "description": "Specific details", "duration_hours": 2}}
            ],
            "search_queries": ["{goal} basics tutorial full course", "{goal} project tutorial", "Advanced {goal} concepts"],
            "trends": ["Current industry use case 1", "Current industry use case 2"],
            "certifications": ["Relevant Cert to aim for"]
        }}
        """

    if image_bytes:
        contents = types.Content(
            role="user",
            parts=[
                types.Part(text=prompt),
                types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type)
            ]
        )
    else:
        contents = prompt

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        reraise=True,
    )
    def _call_gemini():
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        raw_text = response.text
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw_text)

    curriculum = None
    try:
        curriculum = _call_gemini()
    except Exception as e:
        print(f"All retries exhausted or fatal error: {e}. Triggering Fallback.")
        curriculum = {
            "title": f"Fallback Plan for {goal}",
            "modules": [
                {"day": 1, "topic": "Fundamentals", "description": "Review basics", "duration_hours": 2},
                {"day": 2, "topic": "Core Concepts", "description": "Deep dive", "duration_hours": 3},
                {"day": 3, "topic": "Practice", "description": "Hands-on", "duration_hours": 2},
                {"day": 4, "topic": "Advanced Topics", "description": "Complex areas", "duration_hours": 3},
                {"day": 5, "topic": "Project", "description": "Build something", "duration_hours": 4},
                {"day": 6, "topic": "Review", "description": "Test knowledge", "duration_hours": 2},
                {"day": 7, "topic": "Next Steps", "description": "Plan future", "duration_hours": 1},
            ],
            "search_queries": [f"{goal} full course 2026", f"Advanced {goal} tutorial"],
            "trends": ["AI Integration", "Cloud Native Architectures"],
            "certifications": ["Industry Standard Certification"],
        }

    return {
        "curriculum_json": curriculum,
        "messages": [{"role": "system", "content": f"Architect designed a {mode} plan with rich metadata."}]
    }
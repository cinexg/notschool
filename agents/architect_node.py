import json
import re
from google.genai import types
from core.state import NotschoolState
from tools.gemini_client import generate_with_fallback


def architect_node(state: NotschoolState) -> dict:
    """Acts as the Principal Curriculum Designer."""
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
            "certifications": ["Relevant Cert to aim for"],
            "opportunities": [
                {{"title": "Real program or cohort name relevant to {goal}", "description": "One-line description of what it offers", "type": "cohort", "url": "https://example.com"}},
                {{"title": "Another real bootcamp, hackathon, or certification program", "description": "One-line description", "type": "bootcamp", "url": "https://example.com"}}
            ]
        }}

        For the "opportunities" field: list 3-5 REAL, well-known industry programs, cohorts, bootcamps, hackathons, or certification programs that are highly relevant to "{goal}". Include actual names like Google ML Bootcamp, DeepLearning.AI specializations, Google Gen AI APAC, fast.ai, Kaggle competitions, AWS/GCP/Azure certifications, major hackathons, etc. Type must be one of: cohort, bootcamp, certification, hackathon, program.
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
            "certifications": ["Relevant Cert to aim for"],
            "opportunities": [
                {{"title": "Real program or cohort name relevant to {goal}", "description": "One-line description of what it offers", "type": "cohort", "url": "https://example.com"}},
                {{"title": "Another real bootcamp, hackathon, or certification program", "description": "One-line description", "type": "bootcamp", "url": "https://example.com"}}
            ]
        }}

        For the "opportunities" field: list 3-5 REAL, well-known industry programs, cohorts, bootcamps, hackathons, or certification programs that are highly relevant to "{goal}". Include actual names like Google ML Bootcamp, DeepLearning.AI specializations, Google Gen AI APAC, fast.ai, Kaggle competitions, AWS/GCP/Azure certifications, major hackathons, etc. Type must be one of: cohort, bootcamp, certification, hackathon, program.
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

    curriculum = None
    try:
        raw_text = generate_with_fallback(
            contents,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        curriculum = json.loads(match.group(0)) if match else json.loads(raw_text)
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
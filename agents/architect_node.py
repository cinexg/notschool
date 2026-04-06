import json
import os
from google import genai
from google.genai import types
from core.state import NotschoolState

# The client automatically picks up GEMINI_API_KEY from the environment
client = genai.Client()

def architect_node(state: NotschoolState) -> dict:
    """
    Acts as the Principal Curriculum Designer for the skills and studies platform.
    Uses Gemini 1.5 Pro to process text and images into a structured JSON syllabus.
    """
    goal = state["goal"]
    image_bytes = state.get("image_bytes")

    prompt = f"""
    You are an expert curriculum architect for an elite coaching platform.
    Design a 3-step learning curriculum for the following goal: {goal}
    
    You must return a raw JSON object with the following schema:
    {{
        "title": "Course Title",
        "modules": ["Module 1", "Module 2", "Module 3"],
        "search_queries": ["query 1", "query 2", "query 3"]
    }}
    Do not include markdown formatting like ```json.
    """

    contents = [prompt]
    
    # If the user uploaded a syllabus or diagram, append it to the multimodal prompt
    if image_bytes:
        contents.append(
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        )

    # We use Gemini 1.5 Pro for complex reasoning and schema adherence
    response = client.models.generate_content(
        model='gemini-1.5-pro',
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.2, # Low temperature for structured output
        )
    )

    try:
        curriculum = json.loads(response.text.strip())
    except json.JSONDecodeError:
        # Fallback error handling for the hackathon
        curriculum = {"title": "Error generating curriculum", "modules": [], "search_queries": [goal]}

    # LangGraph automatically merges this dictionary into the NotschoolState
    return {
        "curriculum_json": curriculum,
        "messages": [{"role": "system", "content": "Architect completed the curriculum design."}]
    }
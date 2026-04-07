import os
import json
from google import genai
from google.genai import types
from core.state import NotschoolState
from db.schema import CurriculumModel

def architect_node(state: NotschoolState) -> dict:
    """
    Acts as the Principal Curriculum Designer.
    Uses Gemini 1.5 Pro to process text and images into a structured JSON syllabus.
    """
    # 1. Initialize the client INSIDE the function (Lazy Initialization)
    # This ensures the .env file is 100% loaded before the SDK looks for the key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from the environment!")
        
    client = genai.Client(api_key=api_key)

    # 2. Extract state
    goal = state["goal"]
    image_bytes = state.get("image_bytes")

    # 3. Define the system instructions context
    prompt = f"""
        You are the Principal Architect for Notschool, an elite coaching platform dedicated to skills and studies.
        Your task is to design a highly actionable, 3-step learning curriculum for the following goal: "{goal}"
        
        If the user provided an image (like a syllabus or diagram), analyze it deeply and base your curriculum on its contents.
        
        You MUST return EXACTLY this JSON structure and nothing else:
        {{
            "title": "The Course Title",
            "modules": ["Module 1 string", "Module 2 string", "Module 3 string"],
            "search_queries": ["Specific YouTube search 1", "Specific YouTube search 2", "Specific YouTube search 3"]
        }}
        """

    contents = [prompt]
    
    # If the user uploaded an image, append it to the multimodal prompt
    if image_bytes:
        contents.append(
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg") 
        )

    try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.2, 
                    response_mime_type="application/json",
                )
            )

            curriculum = json.loads(response.text)

    except Exception as e:
        print(f"Architect Node Error: {e}")
        curriculum = {
            "title": "Fallback: Error generating curriculum", 
            "modules": ["Understand the basics", "Practice concepts", "Build a project"], 
            "search_queries": [f"{goal} tutorial for beginners"]
        }

    return {
        "curriculum_json": curriculum,
        "messages": [{"role": "system", "content": "Architect successfully designed the skills and studies curriculum."}]
    }
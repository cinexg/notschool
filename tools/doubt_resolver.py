"""Gemini-powered Q&A helper for the 'Ask a Doubt' feature."""
from google.genai import types
from tools.gemini_client import generate_with_fallback, GeminiUnavailableError


class DoubtResolverError(RuntimeError):
    """Raised when the AI tutor can't be reached."""


def resolve_doubt(question: str, goal: str = "", module_topic: str = "",
                  module_description: str = "") -> str:
    """
    Returns a focused, friendly tutor-style answer.
    Raises DoubtResolverError when Gemini is fully unavailable so the API layer
    can return a 503 instead of silently masking the failure as a "success".
    """
    if not question or not question.strip():
        raise DoubtResolverError("Please type a question first.")

    context = ""
    if goal:
        context += f"The student is learning: {goal}.\n"
    if module_topic:
        context += f"They are currently on the module: {module_topic}.\n"
    if module_description:
        context += f"Module description: {module_description}\n"

    prompt = f"""
    You are an expert AI tutor. Be patient, clear, and concise.
    {context}
    Student's question:
    {question}

    Rules:
    - Answer in 4-8 sentences max unless the question demands depth.
    - Use plain language. Use a code block (```) only if code is required.
    - If the question is off-topic from learning, politely redirect.
    - End with one short follow-up suggestion if helpful.
    """

    try:
        answer = generate_with_fallback(
            prompt,
            config=types.GenerateContentConfig(temperature=0.5),
        ).strip()
    except GeminiUnavailableError as e:
        raise DoubtResolverError(str(e)) from e
    except Exception as e:
        print(f"Doubt resolver failed: {e}")
        raise DoubtResolverError(f"AI tutor unreachable: {e}") from e

    if not answer:
        raise DoubtResolverError("The AI returned an empty answer. Try rephrasing.")
    return answer

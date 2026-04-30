"""Gemini-powered Q&A helper for the 'Ask a Doubt' / AI tutor feature.

Supports multi-turn conversations: pass a `history` list of prior
{question, answer} dicts and the model will keep continuity across turns.
"""
from typing import Iterable
from google.genai import types
from tools.gemini_client import generate_with_fallback, GeminiUnavailableError


class DoubtResolverError(RuntimeError):
    """Raised when the AI tutor can't be reached."""


def _format_history(history: Iterable[dict]) -> str:
    """Render past turns as a compact transcript so the model has context."""
    lines = []
    for turn in history or []:
        q = (turn.get("question") or "").strip()
        a = (turn.get("answer") or "").strip()
        if q:
            lines.append(f"Student: {q}")
        if a:
            lines.append(f"Tutor: {a}")
    return "\n".join(lines)


def resolve_doubt(question: str, goal: str = "", module_topic: str = "",
                  module_description: str = "",
                  history: list[dict] | None = None,
                  profile: dict | None = None) -> str:
    """
    Returns a focused, friendly tutor-style answer with conversational memory.
    `history` is the prior turns of the same chat (oldest → newest), each a
    dict with `question` + `answer` keys. The model is instructed to treat the
    conversation as continuous.
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

    profile = profile or {}
    profile_lines = []
    if profile.get("display_name"):
        profile_lines.append(f"Name: {profile['display_name']}")
    if profile.get("age"):
        profile_lines.append(f"Age: {profile['age']}")
    if profile.get("skills"):
        profile_lines.append(f"Existing skills: {', '.join(profile['skills'][:8])}")
    if profile.get("interests"):
        profile_lines.append(f"Interests: {', '.join(profile['interests'][:8])}")
    if profile.get("learning_style"):
        profile_lines.append(f"Preferred style: {profile['learning_style']}")
    if profile_lines:
        context += "Learner profile — use this to pitch the answer at the right level and weave in their interests when natural:\n- " + "\n- ".join(profile_lines) + "\n"

    transcript = _format_history(history)
    transcript_block = (
        f"\nPrior conversation (most recent at the bottom):\n{transcript}\n"
        if transcript else ""
    )

    prompt = f"""
You are an expert AI tutor on the Notschool platform. Be patient, clear, and concise.
{context}{transcript_block}
Student's new question:
{question}

Rules:
- Treat the prior conversation as ongoing — if the student says "explain that again", "what about the second one", "expand", etc., resolve the reference using the transcript above.
- Answer in 4-8 sentences max unless the question demands depth.
- Use plain language. Use a fenced code block (```) only if code is required.
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


def summarize_for_title(question: str, max_words: int = 6) -> str:
    """Cheap title generator from the first question — no extra API call."""
    q = (question or "").strip().rstrip("?!.").strip()
    if not q:
        return "New chat"
    words = q.split()
    if len(words) <= max_words:
        return q[:60]
    return " ".join(words[:max_words]) + "…"

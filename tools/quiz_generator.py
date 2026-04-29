"""Gemini-powered quiz generator. Returns 5-question MCQs as structured data."""
import json
import re
from google.genai import types
from tools.gemini_client import generate_with_fallback, GeminiUnavailableError


class QuizGenerationError(RuntimeError):
    """Raised when the quiz generator can't produce a usable quiz."""


def _extract_json(raw: str) -> dict:
    """Pull a JSON object out of an LLM response, tolerating markdown fences and prose."""
    if not raw:
        raise ValueError("empty response")
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", raw, re.DOTALL)
    body = fenced.group(1) if fenced else raw
    start = body.find("{")
    end = body.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(body[start : end + 1])
    return json.loads(body)


def _clean_questions(questions, num_questions: int) -> list[dict]:
    cleaned = []
    for q in questions or []:
        if not isinstance(q, dict):
            continue
        opts = q.get("options", [])
        if not isinstance(opts, list) or len(opts) != 4:
            continue
        try:
            ci = int(q.get("correct_index", 0))
        except (TypeError, ValueError):
            ci = 0
        if ci < 0 or ci > 3:
            ci = 0
        question_text = str(q.get("question", "")).strip()
        if not question_text:
            continue
        cleaned.append({
            "question": question_text,
            "options": [str(o) for o in opts],
            "correct_index": ci,
            "explanation": str(q.get("explanation", "")).strip(),
        })
    return cleaned[:num_questions]


def generate_quiz(goal: str, module_topic: str, module_description: str = "", num_questions: int = 5) -> list[dict]:
    """
    Returns a list of MCQ dicts: [{question, options: [4 strings], correct_index: int, explanation}, ...]
    Raises QuizGenerationError if the LLM cannot produce a usable quiz.

    Quiz content is generated purely from the goal + module topic/description —
    it does not depend on any video being available.
    """
    prompt = f"""You are an expert educator. Generate exactly {num_questions} high-quality multiple-choice
questions to test a learner's understanding of the topic below.

Learner's Goal: {goal}
Module Topic: {module_topic}
Module Details: {module_description}

Return ONLY valid JSON that matches this structure (no markdown, no commentary):
{{
  "questions": [
    {{
      "question": "Clear, specific question text",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_index": 0,
      "explanation": "Why this is the correct answer (1-2 sentences)"
    }}
  ]
}}

Rules:
- Exactly 4 options per question.
- correct_index is the 0-based index (0-3) of the correct option.
- Mix difficulty: 2 easy, 2 medium, 1 hard.
- Test conceptual understanding, not memorized trivia.
- Questions must stand alone — never reference "the module", "the video", or "as discussed".
- All four options must be plausible-looking; avoid obvious throwaways.
"""

    try:
        cfg = types.GenerateContentConfig(
            temperature=0.4,
            response_mime_type="application/json",
        )
    except TypeError:
        cfg = types.GenerateContentConfig(temperature=0.4)

    try:
        raw = generate_with_fallback(prompt, config=cfg)
        data = _extract_json(raw)
    except GeminiUnavailableError as e:
        raise QuizGenerationError(str(e)) from e
    except Exception as e:
        raise QuizGenerationError(f"Quiz generator failed: {e}") from e

    cleaned = _clean_questions(data.get("questions", []), num_questions)
    if not cleaned:
        raise QuizGenerationError("Quiz generator returned no usable questions.")
    return cleaned

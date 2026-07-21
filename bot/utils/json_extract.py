import json


def extract_json(text: str) -> dict | None:
    """Extrae el primer objeto JSON de un texto de Claude, tolerando backticks/markdown."""
    if not text:
        return None
    cleaned = text.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end])
    except json.JSONDecodeError:
        return None

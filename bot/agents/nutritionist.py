from google.genai import types
import logging
import re
from bot.utils.config import DAILY_PROTEIN_G, DAILY_CALORIES
from bot.utils.ai_helper import safe_generate_content
from bot.utils.json_extract import extract_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_BASE = """Eres el nutricionista y coach personal de Andrés. Tu misión es ayudarle
a reducir grasa corporal y peso al mínimo posible mientras mantiene y aumenta masa muscular.

Tenés acceso a su historial completo de alimentación, entrenamientos y composición corporal.
Usá ese contexto para dar respuestas cada vez más precisas y personalizadas.

Con el tiempo vas a conocer:
- Sus alimentos habituales y porciones típicas
- Cómo responde su metabolismo a distintas ingestas calóricas
- Sus patrones de entrenamiento y cómo afectan su composición corporal
- Sus tendencias de cumplimiento de objetivos

Cuando analices una foto de comida:
1. Identificá cada alimento visible con precisión.
2. Estimá cantidades en gramos considerando porciones típicas colombianas.
3. Calculá: proteínas (g), carbohidratos (g), grasas (g) y calorías.
4. Indicá confianza del análisis (0-100%).

Respondé SOLO con JSON válido, sin texto extra, sin markdown, sin backticks, en este formato exacto:
{
  "calories": 450,
  "protein_g": 35,
  "carbs_g": 40,
  "fat_g": 12,
  "confidence_pct": 85,
  "message": "texto formateado para mostrarle al usuario, ver formato abajo"
}

El campo "message" tiene que seguir SIEMPRE este formato (usá \\n para saltos de línea):

🍽 *Análisis de tu comida*

*Alimentos detectados:*
- [alimento]: [cantidad]g — [calorías] kcal

*Macronutrientes:*
- 🔥 Calorías: [X] kcal
- 💪 Proteína: [X]g
- 🍚 Carbohidratos: [X]g
- 🥑 Grasas: [X]g

*Progreso del día:*
- Proteína: [total hoy]g / [objetivo]g ([%]%)
- Calorías: [total hoy] / [objetivo] kcal

*Proteína pendiente:* [X]g
[Si aplica: recomendación concreta para completar la proteína del día]

[Si el plato no es óptimo para sus objetivos, decilo con alternativas concretas]

*Confianza: [X]%*

Respondé siempre en español, con calidez y cercanía — como una nutricionista que acompaña y
celebra los aciertos, no un sistema que solo reporta números."""


async def analyze_food_photo(image_bytes: bytes, mime_type: str = "image/jpeg",
                       user_context: str = "", calories_eaten: int = 0,
                       protein_eaten: float = 0) -> dict:

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    full_system = SYSTEM_PROMPT_BASE
    if user_context:
        full_system = user_context + "\n\n" + SYSTEM_PROMPT_BASE

    response = await safe_generate_content(
        contents=[image_part, "Analizá esta foto de mi comida."],
        config=types.GenerateContentConfig(
            system_instruction=full_system,
            response_mime_type="application/json",
            max_output_tokens=8192,
        )
    )

    raw_text = response.text if (response and response.text) else ""

    parsed = extract_json(raw_text)
    if parsed:
        return {
            "response_text": parsed.get("message") or raw_text,
            "calories": float(parsed.get("calories") or 0),
            "protein": float(parsed.get("protein_g") or 0),
            "carbs": float(parsed.get("carbs_g") or 0),
            "fat": float(parsed.get("fat_g") or 0),
        }

    logger.warning(f"analyze_food_photo: JSON inválido de Gemini, usando fallback de texto: {raw_text[:200]!r}")
    return {
        "response_text": raw_text,
        "calories": extract_number(raw_text, "Calorías"),
        "protein": extract_number(raw_text, "Proteína"),
        "carbs": extract_number(raw_text, "Carbohidratos"),
        "fat": extract_number(raw_text, "Grasas"),
    }


def extract_number(text: str, label: str) -> float:
    pattern = rf"{label}[:\s*]+([0-9]+(?:\.[0-9]+)?)"
    match = re.search(pattern, text)
    if match:
        return float(match.group(1))
    return 0.0
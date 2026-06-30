import anthropic
import base64
from bot.utils.config import ANTHROPIC_API_KEY, DAILY_PROTEIN_G, DAILY_CALORIES

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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
5. Respondé SIEMPRE con este formato:

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

Respondé siempre en español, tono directo y práctico."""


def analyze_food_photo(image_bytes: bytes, mime_type: str = "image/jpeg",
                       user_context: str = "", calories_eaten: int = 0,
                       protein_eaten: float = 0) -> dict:

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    full_system = SYSTEM_PROMPT_BASE
    if user_context:
        full_system = user_context + "\n\n" + SYSTEM_PROMPT_BASE

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=full_system,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Analizá esta foto de mi comida."
                    }
                ],
            }
        ],
    )

    response_text = response.content[0].text

    result = {
        "response_text": response_text,
        "calories": extract_number(response_text, "Calorías"),
        "protein": extract_number(response_text, "Proteína"),
        "carbs": extract_number(response_text, "Carbohidratos"),
        "fat": extract_number(response_text, "Grasas"),
    }

    return result


def extract_number(text: str, label: str) -> float:
    import re
    pattern = rf"{label}[:\s*]+([0-9]+(?:\.[0-9]+)?)"
    match = re.search(pattern, text)
    if match:
        return float(match.group(1))
    return 0.0
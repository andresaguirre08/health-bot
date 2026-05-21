import anthropic
import json
import os
from bot.utils.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Eres el nutricionista y coach personal de Andrés. Respondés como un asesor real — directo, concreto y personalizado.

Tu misión: ayudarle a reducir grasa corporal y peso al mínimo posible mientras mantiene y aumenta masa muscular.

Siempre tenés acceso a su contexto del día: macros consumidos, entrenamientos, objetivos. Usá esa información en cada respuesta.

Cuando Andrés te pregunta algo:
- Si pregunta si puede comer algo → analizás si entra en sus macros y respondés con un sí/no claro + justificación
- Si pregunta qué comer → sugerís opciones concretas basadas en la proteína que le falta
- Si describe lo que comió (por texto o audio) → calculás los macros y preguntás si querés guardar con el formato: "¿Guardo esto en tu registro? Respondé SI para confirmar."
- Si pregunta cómo va → analizás su progreso real del día/semana
- Siempre respondés en español, tono directo y amigable
- Máximo 4-5 líneas concretas por respuesta

IMPORTANTE: Cuando detectes que Andrés describe una comida que YA comió, al final de tu respuesta agregá exactamente esta línea en JSON (sin markdown, sin backticks):
MEAL_DATA:{"description":"nombre del alimento","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0}

Reemplazá los 0 con los valores estimados reales. Solo agregá esta línea cuando Andrés describe algo que ya comió, no cuando pregunta si puede comer algo."""


async def chat_with_coach(user_message: str, user_context: str) -> dict:
    full_system = user_context + "\n\n" + SYSTEM_PROMPT if user_context else SYSTEM_PROMPT

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=full_system,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    full_text = response.content[0].text
    meal_data = None

    if "MEAL_DATA:" in full_text:
        parts = full_text.split("MEAL_DATA:")
        clean_text = parts[0].strip()
        try:
            meal_data = json.loads(parts[1].strip())
        except:
            meal_data = None
    else:
        clean_text = full_text

    return {
        "text": clean_text,
        "meal_data": meal_data
    }
import anthropic
import json
from bot.utils.config import ANTHROPIC_API_KEY
from bot.db.client import supabase
from datetime import datetime
import pytz

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
BOGOTA_TZ = pytz.timezone("America/Bogota")

SYSTEM_PROMPT = """Eres el nutricionista y coach personal de Andrés. Directo, concreto, sin rodeos.

Objetivo: ayudarle a llegar a 85kg y menos de 20% de grasa corporal.

REGLA MÁS IMPORTANTE:
Cuando Andrés describe ingredientes o alimentos (con cantidades o sin ellas), calculá los macros y agregá al final exactamente esta línea sin espacios ni saltos extra:
MEAL_DATA:{"description":"nombre","calories":180,"protein_g":32,"carbs_g":10,"fat_g":1}

Reemplazá los números con los valores reales estimados.

SOLO omitís MEAL_DATA cuando es una pregunta como "¿puedo comer X?" o "¿qué como?".

Otras reglas:
- Español, tono directo
- Sin asteriscos ni markdown, solo texto plano
- Máximo 3 líneas de respuesta"""


async def chat_with_coach(user_message: str, user_context: str, user_id: str = None) -> dict:
    full_system = user_context + "\n\n" + SYSTEM_PROMPT if user_context else SYSTEM_PROMPT

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=full_system,
        messages=[{"role": "user", "content": user_message}]
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

    # Guardar en historial solo el mensaje limpio
    if user_id:
        today = datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d")
        try:
            supabase.table("chat_history").insert({
                "user_id": user_id,
                "role": "user",
                "content": user_message,
                "session_date": today
            }).execute()
            supabase.table("chat_history").insert({
                "user_id": user_id,
                "role": "assistant",
                "content": clean_text,
                "session_date": today
            }).execute()
        except:
            pass

    return {
        "text": clean_text,
        "meal_data": meal_data
    }
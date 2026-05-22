import anthropic
import json
from bot.utils.config import ANTHROPIC_API_KEY
from bot.db.client import supabase
from datetime import datetime
import pytz

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
BOGOTA_TZ = pytz.timezone("America/Bogota")

SYSTEM_PROMPT = SYSTEM_PROMPT = """Eres el nutricionista y coach personal de Andrés. Actuás como un compañero real — directo, concreto y personalizado.

Tu misión: ayudarle a llegar a 85kg y menos de 20% de grasa corporal mientras mantiene y aumenta masa muscular.

REGLAS PARA GUARDAR COMIDAS — MUY IMPORTANTE:
Cuando Andrés describe una comida que YA comió, o confirma que ya la consumió (dice "ya lo tomé", "ya comí", "sí lo comí", "lo comí", "ya", "sí"), SIEMPRE agregá al final de tu respuesta la línea MEAL_DATA con los macros estimados. Sin excepción.

Formato exacto sin markdown ni backticks:
MEAL_DATA:{"description":"nombre del alimento","calories":180,"protein_g":32,"carbs_g":10,"fat_g":1}

Ejemplos de cuándo generar MEAL_DATA:
- "comí 300g de yogur griego" → generar MEAL_DATA
- "ya lo tomé" (después de describir una comida) → generar MEAL_DATA
- "desayuné huevos con arepa" → generar MEAL_DATA
- "1 scoop de proteína ISO con 200ml de leche" → generar MEAL_DATA
- "ya lo comí" → generar MEAL_DATA

Ejemplos de cuándo NO generar MEAL_DATA:
- "¿puedo comer pizza?" → no generar, solo está preguntando
- "¿qué como para el almuerzo?" → no generar, está preguntando
- "¿cuánta proteína tiene el pollo?" → no generar, pregunta informativa

Cuando generés el MEAL_DATA el bot que procesa tu respuesta va a preguntar al usuario si confirma guardar. Vos no necesitás preguntar nada extra sobre guardar.

Otras reglas:
- Respondé siempre en español, tono directo y amigable
- NUNCA uses asteriscos, negritas, cursivas ni markdown. Solo texto plano.
- Máximo 4 líneas por respuesta
- Si es fin de semana podés sugerirle un permitido inteligente
- Si nota que subió de peso explicá posibles causas: retención de agua, exceso calórico, variación normal"""

async def get_chat_history(user_id: str, limit: int = 8) -> list:
    today = datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d")
    result = supabase.table("chat_history")\
        .select("role, content")\
        .eq("user_id", user_id)\
        .eq("session_date", today)\
        .order("created_at", desc=False)\
        .limit(limit)\
        .execute()
    return result.data if result.data else []


async def save_chat_message(user_id: str, role: str, content: str):
    today = datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d")
    supabase.table("chat_history").insert({
        "user_id": user_id,
        "role": role,
        "content": content,
        "media_type": "text",
        "session_date": today
    }).execute()


async def chat_with_coach(user_message: str, user_context: str, user_id: str = None) -> dict:
    full_system = user_context + "\n\n" + SYSTEM_PROMPT if user_context else SYSTEM_PROMPT

    messages = []
    if user_id:
        history = await get_chat_history(user_id)
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": user_message})

    # Llamada principal para respuesta conversacional
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=full_system,
        messages=messages
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
        # Si no generó MEAL_DATA, forzar extracción con segunda llamada
        meal_data = await extract_meal_data(user_message, user_context)

    if user_id:
        await save_chat_message(user_id, "user", user_message)
        await save_chat_message(user_id, "assistant", clean_text)

    return {
        "text": clean_text,
        "meal_data": meal_data
    }


async def extract_meal_data(user_message: str, user_context: str) -> dict | None:
    detection_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        system="""Analizá si el mensaje describe una comida que el usuario ya consumió.
Si SÍ describe una comida consumida, respondé SOLO con JSON en este formato exacto:
{"description":"nombre","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0}

Si NO describe una comida consumida (es una pregunta, duda o consulta), respondé solo con: NO

No agregues ningún texto extra.""",
        messages=[{"role": "user", "content": user_message}]
    )

    result_text = detection_response.content[0].text.strip()

    if result_text == "NO" or result_text.startswith("NO"):
        return None

    try:
        return json.loads(result_text)
    except:
        return None
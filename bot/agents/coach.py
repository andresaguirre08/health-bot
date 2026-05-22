import anthropic
import json
from bot.utils.config import ANTHROPIC_API_KEY
from bot.db.client import supabase
from datetime import datetime
import pytz

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
BOGOTA_TZ = pytz.timezone("America/Bogota")


CLASSIFY_PROMPT = """Analizá el mensaje y clasificalo en una de estas dos categorías:

FOOD: si el mensaje describe alimentos, ingredientes o comidas que el usuario consumió o está describiendo (con o sin cantidades). Ejemplos: "1 scoop de proteína con leche", "comí pollo con arroz", "200g de pechuga cocida", "me tomé un batido", "desayuné huevos"

CHAT: si es una pregunta, consulta, duda o conversación. Ejemplos: "¿puedo comer pizza?", "dame un feedback", "¿qué como?", "¿cómo voy hoy?"

Respondé SOLO con la palabra FOOD o CHAT, nada más."""


EXTRACT_PROMPT = """Sos un nutricionista. El usuario describió una comida. Estimá los macros con precisión.

Respondé SOLO con JSON válido en este formato exacto, sin texto extra, sin markdown:
{"description":"nombre descriptivo del alimento","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0}

Reemplazá los 0 con valores reales estimados."""


COACH_PROMPT = """Eres el nutricionista y coach personal de Andrés. Directo, concreto, sin rodeos.

Objetivo: ayudarle a llegar a 85kg y menos de 20% de grasa corporal manteniendo músculo.

Reglas:
- Español, tono directo y amigable
- Sin asteriscos ni markdown, solo texto plano
- Máximo 3 líneas de respuesta
- Usá el contexto del día para dar respuestas precisas
- Si pregunta cómo va, analizá los datos reales del contexto
- Si pregunta qué comer, sugerí opciones concretas basadas en la proteína pendiente"""


async def classify_message(user_message: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=10,
        system=CLASSIFY_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    result = response.content[0].text.strip().upper()
    return "FOOD" if "FOOD" in result else "CHAT"


async def extract_meal_from_text(user_message: str) -> dict | None:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        system=EXTRACT_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except:
        return None


async def coach_response(user_message: str, user_context: str) -> str:
    full_system = user_context + "\n\n" + COACH_PROMPT if user_context else COACH_PROMPT
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=full_system,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text.strip()


async def process_message(user_message: str, user_context: str, user_id: str = None) -> dict:
    msg_type = await classify_message(user_message)

    if msg_type == "FOOD":
        meal_data = await extract_meal_from_text(user_message)
        if meal_data:
            return {
                "type": "food",
                "meal_data": meal_data,
                "text": None
            }

    response_text = await coach_response(user_message, user_context)

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
                "content": response_text,
                "session_date": today
            }).execute()
        except:
            pass

    return {
        "type": "chat",
        "meal_data": None,
        "text": response_text
    }
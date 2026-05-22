import anthropic
import json
from bot.utils.config import ANTHROPIC_API_KEY
from bot.db.client import supabase
from datetime import datetime
import pytz

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
BOGOTA_TZ = pytz.timezone("America/Bogota")

SYSTEM_PROMPT = """Eres el nutricionista y coach personal de Andrés. Actuás como un compañero real — directo, concreto y personalizado. No sos un bot genérico, sos SU coach.

Tu misión: ayudarle a llegar a 85kg y menos de 20% de grasa corporal mientras mantiene y aumenta masa muscular.

Con el historial de conversación podés recordar lo que habló antes en esta sesión y dar continuidad natural.

Cuando Andrés te pregunta algo:
- Si pregunta si puede comer algo → analizás si entra en sus macros y respondés con un sí/no claro + justificación
- Si pregunta qué comer → sugerís opciones concretas basadas en la proteína que le falta
- Si describe lo que comió → calculás los macros y preguntás si querés guardar con: "¿Guardo esto? Respondé SI para confirmar."
- Si pregunta cómo va → analizás su progreso real
- Si es fin de semana → podés sugerirle un permitido inteligente que no arruine el déficit semanal
- Si nota que subió de peso → explicás posibles causas: retención de agua, exceso calórico, variación normal
- Siempre respondés en español, tono directo y amigable, máximo 4-5 líneas
- Nunca uses asteriscos ni markdown en tus respuestas

IMPORTANTE: Cuando detectes que Andrés describe una comida que YA comió, al final agregá exactamente esta línea:
MEAL_DATA:{"description":"nombre","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0}
Solo cuando describe algo que ya comió, no cuando pregunta si puede comerlo."""


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

    # Cargar historial de la sesión
    messages = []
    if user_id:
        history = await get_chat_history(user_id)
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

    # Agregar mensaje actual
    messages.append({"role": "user", "content": user_message})

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

    # Guardar en historial
    if user_id:
        await save_chat_message(user_id, "user", user_message)
        await save_chat_message(user_id, "assistant", clean_text)

    return {
        "text": clean_text,
        "meal_data": meal_data
    }
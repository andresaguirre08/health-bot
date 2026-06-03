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


async def extract_meal_from_text(user_message: str, user_id: str = None) -> dict | None:
    from bot.agents.nutrition_scanner import search_food_database

    db_source = False
    db_product = None

    # Buscar en la base de datos personal primero
    if user_id:
        words = user_message.lower().split()
        for word in words:
            if len(word) > 3:
                results = await search_food_database(user_id, word)
                if results:
                    db_product = results[0]
                    db_source = True
                    break

    if db_source and db_product:
        # Calcular macros basado en la base de datos
        # Intentar detectar cantidad mencionada
        import re
        quantity_match = re.search(r'(\d+)\s*(?:g|gr|gramos|scoop|scoops|porción|porciones)?', user_message.lower())
        multiplier = 1.0

        if quantity_match:
            quantity = float(quantity_match.group(1))
            serving_size = db_product.get("serving_size_g", 33)
            if serving_size and serving_size > 0:
                multiplier = quantity / serving_size

        return {
            "description": db_product.get("product_name"),
            "calories": round((db_product.get("calories_per_serving") or 0) * multiplier),
            "protein_g": round((db_product.get("protein_g") or 0) * multiplier, 1),
            "carbs_g": round((db_product.get("carbs_g") or 0) * multiplier, 1),
            "fat_g": round((db_product.get("fat_g") or 0) * multiplier, 1),
            "source": "database",
            "db_product": db_product.get("product_name")
        }

    # Si no está en la base, estimar con Claude
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        system="""Sos un nutricionista. El usuario describió una comida. Estimá los macros.
Respondé SOLO con JSON válido sin texto extra:
{"description":"nombre","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0,"source":"ai"}""",
        messages=[{"role": "user", "content": user_message}]
    )

    text = response.content[0].text.strip()
    try:
        data = json.loads(text)
        data["source"] = "ai"
        return data
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
        meal_data = await extract_meal_from_text(user_message, user_id)
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
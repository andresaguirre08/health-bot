import anthropic
import json
from bot.utils.config import ANTHROPIC_API_KEY
from bot.db.client import supabase
from datetime import datetime
import pytz

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
BOGOTA_TZ = pytz.timezone("America/Bogota")


CLASSIFY_PROMPT = """Analizá el mensaje y clasificalo en una de estas dos categorías:

FOOD: si el mensaje describe alimentos, ingredientes o comidas que el usuario consumió o está describiendo (con o sin cantidades). Ejemplos: "1 scoop de proteína con leche", "comí pollo con arroz", "200g de pechuga cocida", "me tomé un batido", "desayuné huevos", "230 gramos de solomo de res con sopa", "arroz con pollo y ensalada", "me comí una pizza"

CHAT: si es una pregunta, consulta, duda o conversación. Ejemplos: "¿puedo comer pizza?", "dame un feedback", "¿qué como?", "¿cómo voy hoy?", "guardar", "hola"

REGLA PRINCIPAL: Si el mensaje menciona alimentos con o sin cantidades y NO tiene signo de pregunta, es FOOD.

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
    import re

    db_matches = []
    remaining_text = user_message

    if user_id:
        ingredients = re.split(r',|\sy\s', user_message.lower())

        for ingredient in ingredients:
            ingredient = ingredient.strip()
            if len(ingredient) < 3:
                continue

            words = [w for w in ingredient.split() if len(w) > 3]
            for word in words:
                results = await search_food_database(user_id, word)
                if results:
                    db_product = results[0]

                    quantity_match = re.search(
                        r'(\d+(?:\.\d+)?)\s*(g|gr|gramos|ml|kg)?'
                        r'(?:\s*(?:de\s+)?(?:scoop|scoops|cuchara\s+medidora|cucharas\s+medidoras|'
                        r'unidad|unidades|lonja|lonjas|taza|tazas|cdas?|porcion|porciones|'
                        r'vaso|vasos|tajada|tajadas|rebanada|rebanadas|sobre|sobres))?',
                        ingredient
                    )
                    multiplier = 1.0
                    if quantity_match:
                        quantity = float(quantity_match.group(1))
                        unit = (quantity_match.group(2) or "").lower()
                        serving_size = db_product.get("serving_size_g") or 1

                        if unit in ("g", "gr", "gramos", "ml", "kg"):
                            if unit == "kg":
                                quantity *= 1000
                            multiplier = quantity / serving_size if serving_size > 0 else 1.0
                        else:
                            multiplier = quantity

                    db_matches.append({
                        "product": db_product,
                        "multiplier": multiplier,
                        "ingredient_text": ingredient
                    })
                    remaining_text = remaining_text.replace(ingredient, "")
                    break

    if db_matches:
        total = {
            "calories": 0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0
        }
        names = []

        for match in db_matches:
            p = match["product"]
            m = match["multiplier"]
            total["calories"] += round((p.get("calories_per_serving") or 0) * m)
            total["protein_g"] += round((p.get("protein_g") or 0) * m, 1)
            total["carbs_g"] += round((p.get("carbs_g") or 0) * m, 1)
            total["fat_g"] += round((p.get("fat_g") or 0) * m, 1)
            names.append(p.get("product_name"))

        remaining_text = remaining_text.strip().strip(",").strip()
        if remaining_text and len(remaining_text) > 5:
            ai_result = await _estimate_with_ai(remaining_text)
            if ai_result:
                total["calories"] += ai_result.get("calories", 0)
                total["protein_g"] += ai_result.get("protein_g", 0)
                total["carbs_g"] += ai_result.get("carbs_g", 0)
                total["fat_g"] += ai_result.get("fat_g", 0)
                source_msg = f"📦 Base: {', '.join(names)} + 🤖 IA para el resto"
            else:
                source_msg = f"📦 Datos de tu base: {', '.join(names)}"

            return {
                "description": user_message[:100],
                "calories": total["calories"],
                "protein_g": total["protein_g"],
                "carbs_g": total["carbs_g"],
                "fat_g": total["fat_g"],
                "source": "mixed",
                "db_product": source_msg
            }

        return {
            "description": user_message[:100],
            "calories": total["calories"],
            "protein_g": total["protein_g"],
            "carbs_g": total["carbs_g"],
            "fat_g": total["fat_g"],
            "source": "database",
            "db_product": f"📦 Base: {', '.join(names)}"
        }

    ai_result = await _estimate_with_ai(user_message)
    if ai_result:
        ai_result["source"] = "ai"
        return ai_result
    return None

async def _estimate_with_ai(text: str) -> dict | None:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        system="""Sos un nutricionista. Estimá los macros de esta comida.
Respondé SOLO con JSON válido sin texto extra, sin markdown, sin backticks:
{"description":"nombre","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0}""",
        messages=[{"role": "user", "content": text}]
    )
    try:
        raw = response.content[0].text.strip()
        # Limpiar posibles backticks o texto extra
        raw = raw.replace("```json", "").replace("```", "").strip()
        # Encontrar el JSON en el texto
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return None
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
        return {
            "type": "confirm_food",
            "meal_text": user_message,
            "text": "¿Ya comiste esto o estás preguntando si podés comerlo?\n\n1️⃣ Respondé REGISTRAR para guardarlo\n2️⃣ Respondé CONSULTA para que te asesore"
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
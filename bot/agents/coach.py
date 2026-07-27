from google.genai import types
from bot.utils.ai_helper import safe_generate_content
from bot.db.client import supabase
from bot.utils.json_extract import extract_json
from datetime import datetime
import pytz

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


COACH_PROMPT = """Eres la nutricionista y coach personal de Andrés — su compañera de todos los
días en esta meta, no un sistema que solo contesta preguntas. Objetivo: ayudarlo a llegar a 85kg
y menos de 20% de grasa corporal manteniendo músculo.

Reglas estrictas de respuesta:
- IDIOMA: Respondé SIEMPRE en español. Jamás uses inglés.
- FORMATO: Escribí en texto claro y fluido. No uses asteriscos dobles o formateos raros de markdown. Usá guiones simples "- " para listas.
- Cálida, cercana y con personalidad — hablás con él directamente. Podés usar emojis con naturalidad.
- Proactiva: si el contexto muestra un patrón, comentalo aunque no te lo pregunte directamente.
- Das recomendaciones concretas y porciones estimadas en gramos o tazas basadas en los números reales del contexto.
- Completa la idea sin cortar oraciones a la mitad.
- CRÍTICO: nunca inventes qué comió o qué entrenó si no está en el contexto. Si te pregunta por comidas o entrenos puntuales y el detalle no aparece explícitamente ahí, decile que no tenés ese registro específico."""


async def classify_message(user_message: str) -> str:
    response = await safe_generate_content(
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=CLASSIFY_PROMPT,
            max_output_tokens=10,
        )
    )
    result = (response.text or "").strip().upper() if response else ""
    return "FOOD" if "FOOD" in result else "CHAT"


async def extract_meal_from_text(user_message: str, user_id: str = None) -> dict | None:
    from bot.agents.nutrition_scanner import search_food_database
    import re

    # Limpiar prefijos de comando antes de procesar ingredientes
    clean_text = re.sub(r'^(?:listo\s+guardar|guardar|registrar)\s*[:;-]?\s*', '', user_message, flags=re.IGNORECASE).strip()

    db_matches = []
    remaining_parts = []

    if user_id:
        ingredients = re.split(r',|\s+con\s+|\s+más\s+|\s+mas\s+|\s+y\s+|\s*\+\s*', clean_text.lower())

        for ingredient in ingredients:
            ingredient = ingredient.strip()
            if len(ingredient) < 3:
                continue

            found = False
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
                    })
                    found = True
                    break

            if not found:
                remaining_parts.append(ingredient)
    else:
        remaining_parts.append(clean_text.lower())

    remaining_text = ", ".join(remaining_parts).strip()

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

        if remaining_text and len(remaining_text) > 3:
            ai_result = await _estimate_with_ai(remaining_text)
            if ai_result:
                total["calories"] += round(float(ai_result.get("calories") or 0))
                total["protein_g"] = round(total["protein_g"] + float(ai_result.get("protein_g") or 0), 1)
                total["carbs_g"] = round(total["carbs_g"] + float(ai_result.get("carbs_g") or 0), 1)
                total["fat_g"] = round(total["fat_g"] + float(ai_result.get("fat_g") or 0), 1)
                source_msg = f"📦 Base: {', '.join(names)} + 🤖 IA para el resto"
            else:
                source_msg = f"📦 Base: {', '.join(names)}"
        else:
            source_msg = f"📦 Base: {', '.join(names)}"

        return {
            "description": clean_text[:100],
            "calories": total["calories"],
            "protein_g": total["protein_g"],
            "carbs_g": total["carbs_g"],
            "fat_g": total["fat_g"],
            "source": "mixed" if (remaining_text and len(remaining_text) > 3) else "database",
            "db_product": source_msg
        }

    ai_result = await _estimate_with_ai(clean_text)
    if ai_result:
        ai_result["source"] = "ai"
        return ai_result
    return None


async def _estimate_with_ai(text: str) -> dict | None:
    system_prompt = """Sos un nutricionista. Estimá los macros totales de esta comida.
Respondé SOLO con JSON válido en este formato exacto:
{"description":"nombre descriptivo","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0}"""
    response = await safe_generate_content(
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            max_output_tokens=1024,
        )
    )
    raw = response.text if (response and response.text) else ""
    return extract_json(raw)


async def coach_response(user_message: str, user_context: str) -> str:
    full_system = user_context + "\n\n" + COACH_PROMPT if user_context else COACH_PROMPT
    response = await safe_generate_content(
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=full_system,
            max_output_tokens=2048,
        )
    )
    return (response.text or "").strip() if (response and response.text) else ""


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
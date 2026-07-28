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
- IDIOMA: Respondé SIEMPRE en español latino. Jamás uses inglés.
- FORMATO: Escribí en texto claro y fluido. NO uses asteriscos dobles (**). Usá guiones simples "- " para listas.
- Cálida, cercana y con personalidad — hablás con él directamente. Podés usar emojis con naturalidad.

CUANDO PIDA RECOMENDACIÓN DE CENA O COMIDA (CRÍTICO):
1. Leé atentamente el contexto: las calorías consumidas hoy, las calorías quemadas en sus entrenamientos de hoy, y sus macronutrientes restantes (proteína, carbohidratos y grasas pendientes).
2. Si te menciona qué ingredientes tiene disponibles (ej: yogurt griego, banano, pan lactal, jamón, queso, etc.), armale una propuesta usando ESOS ingredientes exactos.
3. Indicale LAS CANTIDADES EXACTAS RECOMENDADAS para cada ingrediente (en gramos, lonjas, rebanadas o unidades) para cubrir sus macronutrientes pendientes de hoy.
4. Muestra un resumen claro del aporte total de la cena recomendada (Calorías, Proteína, Carbohidratos y Grasas).
5. Mantené la respuesta completa y directa (entre 12 y 18 líneas en total) para cerrar limpiamente todas las ideas.
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
    from bot.agents.nutrition_scanner import get_all_products
    import re

    # Limpiar prefijos de comandos comunes
    clean_text = re.sub(
        r'^(?:almorc[eé]|desayun[eé]|cen[eé]|com[ií]|listo\s+guardar|guardar|registrar)\s*[:;-]?\s*',
        '',
        user_message,
        flags=re.IGNORECASE
    ).strip()

    db_products = []
    if user_id:
        try:
            db_products = await get_all_products(user_id)
        except Exception:
            db_products = []

    ai_result = await _estimate_meal_with_context(clean_text, db_products)
    if ai_result:
        ai_result["source"] = "ai"
        return ai_result
    return None


async def _estimate_meal_with_context(text: str, db_products: list = None) -> dict | None:
    db_info = ""
    if db_products:
        db_info = "\n\nProductos preferidos de la base de datos personal del usuario (usá sus valores exactos si los menciona explícitamente):\n"
        for p in db_products:
            db_info += f"- {p.get('product_name')}: {p.get('calories_per_serving')} kcal, {p.get('protein_g')}g proteína por porción de {p.get('serving_description') or str(p.get('serving_size_g')) + 'g'}\n"

    system_prompt = f"""Sos un nutricionista experto. El usuario describió una comida o receta.
Tu trabajo es analizar TODOS los ingredientes mencionados con sus porciones reales y calcular los macronutrientes totales.{db_info}

Reglas estrictas:
1. Analizá CADA ingrediente mencionado (carnes, huevos, caldos, vegetales, fideos, aceites, mantecas, salsas, etc.).
2. "manteca de leche" o "mantequilla" es grasa para cocinar (~100 kcal, ~11g grasa por cucharada). NO es leche líquida ni leche descremada.
3. "caldo de res sin grasa" es caldo de res (~15-20 kcal por 400ml).
4. Sumá con precisión nutricional real las calorías, proteínas, carbohidratos y grasas de TODOS los ingredientes.

Respondé SOLO con JSON válido en este formato exacto:
{{"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "description": "resumen breve de todos los alimentos detectados"}}"""

    response = await safe_generate_content(
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            max_output_tokens=1000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
    )
    raw = response.text if (response and response.text) else ""
    parsed = extract_json(raw)
    if parsed:
        return {
            "description": parsed.get("description") or text[:100],
            "calories": round(float(parsed.get("calories") or 0)),
            "protein_g": round(float(parsed.get("protein_g") or 0), 1),
            "carbs_g": round(float(parsed.get("carbs_g") or 0), 1),
            "fat_g": round(float(parsed.get("fat_g") or 0), 1),
        }
    return None


async def coach_response(user_message: str, user_context: str) -> str:
    full_system = user_context + "\n\n" + COACH_PROMPT if user_context else COACH_PROMPT
    response = await safe_generate_content(
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=full_system,
            max_output_tokens=1000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
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
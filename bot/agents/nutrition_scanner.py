import anthropic
import base64
import json
from bot.utils.config import ANTHROPIC_API_KEY
from bot.db.client import supabase

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SCAN_PROMPT = """Analizá esta imagen. Puede ser una tabla nutricional de un producto alimenticio.

Si ES una tabla nutricional respondé SOLO con JSON válido en este formato exacto:
{
  "is_nutrition_label": true,
  "product_name": "nombre del producto",
  "brand": "marca si se ve",
  "serving_size_g": 30,
  "serving_description": "1 scoop (30g)",
  "calories_per_serving": 120,
  "protein_g": 24,
  "carbs_g": 3,
  "fat_g": 2,
  "fiber_g": 0,
  "sodium_mg": 150,
  "sugar_g": 1
}

Si NO es una tabla nutricional respondé SOLO con:
{"is_nutrition_label": false}

Sin texto extra, sin markdown, solo JSON."""


async def scan_nutrition_label(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": image_b64
                    }
                },
                {
                    "type": "text",
                    "text": SCAN_PROMPT
                }
            ]
        }]
    )

    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except:
        return {"is_nutrition_label": False}

async def save_to_food_database(user_id: str, data: dict, caption: str = None) -> dict:
    # Caption siempre tiene prioridad absoluta sobre lo que Claude detectó
    product_name = caption.strip() if caption else data.get("product_name", "").strip()
    
    # Si el nombre detectado es genérico, usar caption
    generic_names = ["información nutricional", "informacion nutricional", 
                     "tabla nutricional", "producto", "producto sin nombre", ""]
    if not caption and product_name.lower() in generic_names:
        product_name = "Producto sin nombre"

    # Buscar si ya existe exactamente ese producto
    existing = supabase.table("food_database")\
        .select("id, product_name, times_used")\
        .eq("user_id", user_id)\
        .ilike("product_name", product_name)\
        .execute()

    if existing.data:
        supabase.table("food_database")\
            .update({
                "calories_per_serving": data.get("calories_per_serving"),
                "protein_g": data.get("protein_g"),
                "carbs_g": data.get("carbs_g"),
                "fat_g": data.get("fat_g"),
                "fiber_g": data.get("fiber_g"),
                "sodium_mg": data.get("sodium_mg"),
                "serving_size_g": data.get("serving_size_g"),
                "serving_description": data.get("serving_description"),
                "times_used": existing.data[0]["times_used"] + 1
            })\
            .eq("id", existing.data[0]["id"])\
            .execute()
        return {"action": "updated", "product": product_name}

    result = supabase.table("food_database").insert({
        "user_id": user_id,
        "product_name": product_name,
        "brand": data.get("brand"),
        "serving_size_g": data.get("serving_size_g"),
        "serving_description": data.get("serving_description"),
        "calories_per_serving": data.get("calories_per_serving"),
        "protein_g": data.get("protein_g"),
        "carbs_g": data.get("carbs_g"),
        "fat_g": data.get("fat_g"),
        "fiber_g": data.get("fiber_g"),
        "sodium_mg": data.get("sodium_mg"),
        "sugar_g": data.get("sugar_g"),
        "raw_ai_response": data
    }).execute()

    return {"action": "created", "product": product_name}

async def search_food_database(user_id: str, query: str) -> list:
    result = supabase.table("food_database")\
        .select("*")\
        .eq("user_id", user_id)\
        .ilike("product_name", f"%{query}%")\
        .order("times_used", desc=True)\
        .limit(3)\
        .execute()
    return result.data if result.data else []


async def get_all_products(user_id: str) -> list:
    result = supabase.table("food_database")\
        .select("product_name, brand, calories_per_serving, protein_g, serving_description")\
        .eq("user_id", user_id)\
        .order("times_used", desc=True)\
        .execute()
    return result.data if result.data else []   
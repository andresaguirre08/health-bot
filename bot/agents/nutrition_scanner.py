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
  "product_name": "nombre del producto si se ve en la imagen",
  "brand": "marca si se ve en la imagen",
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
        model="claude-3-5-sonnet-20241022",
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


async def save_to_food_database(user_id: str, data: dict, caption: str = None, brand: str = None) -> dict:
    product_name = caption.strip() if caption else data.get("product_name", "").strip()

    generic_names = ["información nutricional", "informacion nutricional",
                     "tabla nutricional", "producto", "producto sin nombre", ""]
    if not caption and product_name.lower() in generic_names:
        product_name = "Producto sin nombre"

    final_brand = brand or data.get("brand") or None

    if not final_brand and caption and len(caption.strip().split()) >= 2:
        words = caption.strip().split()
        final_brand = words[-1].capitalize()
        product_name = " ".join(words[:-1])

    calories = int(float(data.get("calories_per_serving"))) if data.get("calories_per_serving") else None
    protein = float(data.get("protein_g")) if data.get("protein_g") else None
    carbs = float(data.get("carbs_g")) if data.get("carbs_g") else None
    fat = float(data.get("fat_g")) if data.get("fat_g") else None
    fiber = float(data.get("fiber_g")) if data.get("fiber_g") else None
    sodium = float(data.get("sodium_mg")) if data.get("sodium_mg") else None
    sugar = float(data.get("sugar_g")) if data.get("sugar_g") else None
    serving_size = float(data.get("serving_size_g")) if data.get("serving_size_g") else None

    existing = supabase.table("food_database")\
        .select("id, product_name, times_used")\
        .eq("user_id", user_id)\
        .ilike("product_name", product_name)\
        .execute()

    if existing.data:
        supabase.table("food_database")\
            .update({
                "brand": final_brand,
                "calories_per_serving": calories,
                "protein_g": protein,
                "carbs_g": carbs,
                "fat_g": fat,
                "fiber_g": fiber,
                "sodium_mg": sodium,
                "serving_size_g": serving_size,
                "serving_description": data.get("serving_description"),
                "times_used": existing.data[0]["times_used"] + 1
            })\
            .eq("id", existing.data[0]["id"])\
            .execute()
        return {"action": "updated", "product": product_name, "brand": final_brand}

    supabase.table("food_database").insert({
        "user_id": user_id,
        "product_name": product_name,
        "brand": final_brand,
        "serving_size_g": serving_size,
        "serving_description": data.get("serving_description"),
        "calories_per_serving": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "fiber_g": fiber,
        "sodium_mg": sodium,
        "sugar_g": sugar,
        "raw_ai_response": data
    }).execute()

    return {"action": "created", "product": product_name, "brand": final_brand}


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
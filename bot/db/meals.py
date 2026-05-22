from datetime import date
from bot.db.client import supabase


async def get_or_create_user(telegram_id: int, name: str = "Andrés") -> str:
    result = supabase.table("users").select("id").eq("telegram_id", telegram_id).execute()

    if result.data:
        return result.data[0]["id"]

    new_user = supabase.table("users").insert({
        "telegram_id": telegram_id,
        "name": name,
        "height_cm": 175,
        "daily_calories": 2000,
        "daily_protein_g": 180,
        "daily_carbs_g": 150,
        "daily_fat_g": 60,
        "goal_type": "fat_loss"
    }).execute()

    return new_user.data[0]["id"]


async def save_meal(user_id: str, calories: float, protein: float,
                    carbs: float, fat: float, description: str = "",
                    photo_url: str = None, raw_response: str = "") -> dict:

    meal = supabase.table("meals").insert({
        "user_id": user_id,
        "calories": int(calories),
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "description": description,
        "photo_url": photo_url,
        "raw_ai_response": {"text": raw_response},
        "logged_at": date.today().isoformat()
    }).execute()

    return meal.data[0] if meal.data else {}


async def get_today_totals(user_id: str) -> dict:
    from datetime import datetime
    import pytz
    
    bogota_tz = pytz.timezone("America/Bogota")
    today = datetime.now(bogota_tz).strftime("%Y-%m-%d")
    
    result = supabase.table("meals")\
        .select("calories, protein_g, carbs_g, fat_g")\
        .eq("user_id", user_id)\
        .gte("logged_at", today)\
        .lt("logged_at", today + "T23:59:59-05:00")\
        .execute()

    totals = {"calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for meal in result.data:
        totals["calories"] += meal.get("calories") or 0
        totals["protein"] += float(meal.get("protein_g") or 0)
        totals["carbs"] += float(meal.get("carbs_g") or 0)
        totals["fat"] += float(meal.get("fat_g") or 0)

    return totals
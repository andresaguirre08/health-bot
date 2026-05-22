from datetime import datetime, date
import pytz
from bot.db.client import supabase

BOGOTA_TZ = pytz.timezone("America/Bogota")


def get_meal_type_by_hour() -> str:
    hour = datetime.now(BOGOTA_TZ).hour
    if 5 <= hour < 10:
        return "desayuno"
    elif 10 <= hour < 12:
        return "media_manana"
    elif 12 <= hour < 15:
        return "almuerzo"
    elif 15 <= hour < 19:
        return "media_tarde"
    elif 19 <= hour < 23:
        return "cena"
    elif 23 <= hour <= 23:
        return "merienda_nocturna"
    else:
        return "madrugada"


MEAL_TYPE_LABELS = {
    "desayuno": "🌅 Desayuno",
    "media_manana": "☕ Media mañana",
    "almuerzo": "🍽 Almuerzo",
    "media_tarde": "🍎 Media tarde",
    "cena": "🌙 Cena",
    "merienda_nocturna": "🌛 Merienda nocturna",
    "madrugada": "🌃 Madrugada"
}

# Calorías esperadas por tipo de comida (rango normal)
MEAL_CALORIE_RANGES = {
    "desayuno": (200, 600),
    "media_manana": (100, 300),
    "almuerzo": (400, 900),
    "media_tarde": (100, 400),
    "cena": (300, 700),
    "merienda_nocturna": (100, 300),
    "madrugada": (0, 200)
}


def check_unusual_calories(meal_type: str, calories: int) -> str | None:
    if meal_type not in MEAL_CALORIE_RANGES:
        return None
    min_cal, max_cal = MEAL_CALORIE_RANGES[meal_type]
    label = MEAL_TYPE_LABELS.get(meal_type, meal_type)
    if calories > max_cal:
        return (
            f"⚠️ Registré {calories} kcal para {label} — eso es bastante alto para este horario "
            f"(lo normal es {min_cal}-{max_cal} kcal). ¿Te saltaste alguna comida anterior?"
        )
    return None


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

    meal_type = get_meal_type_by_hour()
    now_bogota = datetime.now(BOGOTA_TZ).isoformat()

    meal = supabase.table("meals").insert({
        "user_id": user_id,
        "calories": int(calories),
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "description": description,
        "meal_type": meal_type,
        "photo_url": photo_url,
        "raw_ai_response": {"text": raw_response},
        "logged_at": now_bogota
    }).execute()

    return meal.data[0] if meal.data else {}


async def get_today_totals(user_id: str) -> dict:
    today = datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d")

    result = supabase.table("meals")\
        .select("calories, protein_g, carbs_g, fat_g, meal_type")\
        .eq("user_id", user_id)\
        .gte("logged_at", today)\
        .lt("logged_at", today + "T23:59:59-05:00")\
        .execute()

    totals = {
        "calories": 0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "meal_count": 0,
        "meals_by_type": {}
    }

    for meal in result.data:
        totals["calories"] += meal.get("calories") or 0
        totals["protein"] += float(meal.get("protein_g") or 0)
        totals["carbs"] += float(meal.get("carbs_g") or 0)
        totals["fat"] += float(meal.get("fat_g") or 0)
        totals["meal_count"] += 1

        meal_type = meal.get("meal_type", "otro")
        if meal_type not in totals["meals_by_type"]:
            totals["meals_by_type"][meal_type] = 0
        totals["meals_by_type"][meal_type] += meal.get("calories") or 0

    return totals
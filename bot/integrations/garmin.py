from datetime import date, timedelta
from garminconnect import Garmin
from bot.db.client import supabase
from bot.utils.config import GARMIN_EMAIL, GARMIN_PASSWORD


def get_garmin_client():
    import time
    client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    try:
        client.login()
    except Exception as e:
        if "429" in str(e):
            time.sleep(60)
            client.login()
        else:
            raise
    return client


async def sync_weight(user_id: str, target_date: str = None):
    if not target_date:
        target_date = date.today().isoformat()

    try:
        client = get_garmin_client()
        data = client.get_body_composition(target_date)

        if not data or not data.get("totalAverage"):
            return None

        stats = data["totalAverage"]
        weight = stats.get("weight")
        if weight:
            weight = weight / 1000

        bf_pct = stats.get("bodyFat")
        muscle_mass = stats.get("muscleMass")
        if muscle_mass:
            muscle_mass = muscle_mass / 1000

        if not weight:
            return None

        # Obtener peso anterior para comparar
        previous = supabase.table("body_measurements")\
            .select("weight_kg, measured_at")\
            .eq("user_id", user_id)\
            .lt("measured_at", target_date)\
            .order("measured_at", desc=True)\
            .limit(1)\
            .execute()

        previous_weight = None
        if previous.data:
            previous_weight = previous.data[0].get("weight_kg")

        existing = supabase.table("body_measurements")\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("measured_at", target_date)\
            .eq("source", "garmin_index")\
            .execute()

        measurement = {
            "user_id": user_id,
            "measured_at": target_date,
            "weight_kg": round(weight, 2),
            "body_fat_pct": round(bf_pct, 1) if bf_pct else None,
            "muscle_mass_kg": round(muscle_mass, 2) if muscle_mass else None,
            "source": "garmin_index"
        }

        if existing.data:
            supabase.table("body_measurements")\
                .update(measurement)\
                .eq("id", existing.data[0]["id"])\
                .execute()
        else:
            supabase.table("body_measurements")\
                .insert(measurement)\
                .execute()

        measurement["previous_weight"] = previous_weight
        return measurement

    except Exception as e:
        raise Exception(f"Error sincronizando peso Garmin: {str(e)}")

async def sync_workouts(user_id: str, target_date: str = None, days_back: int = 7):
    end_date = target_date or date.today().isoformat()
    start_date = (date.today() - timedelta(days=days_back)).isoformat()

    try:
        client = get_garmin_client()
        activities = client.get_activities_by_date(start_date, end_date)

        if not activities:
            return []

        saved = []
        for activity in activities:
            external_id = str(activity.get("activityId", ""))

            existing = supabase.table("workouts")\
                .select("id")\
                .eq("external_id", external_id)\
                .execute()

            if existing.data:
                continue

            duration_sec = activity.get("duration", 0)
            workout_date = activity.get("startTimeLocal", "")[:10] or end_date

            workout = {
                "user_id": user_id,
                "workout_date": workout_date,
                "source": "garmin",
                "activity_type": activity.get("activityType", {}).get("typeKey", "workout").replace("_", " "),
                "duration_min": round(duration_sec / 60) if duration_sec else None,
                "calories_burned": int(activity.get("calories")) if activity.get("calories") else None,
                "avg_heart_rate": int(activity.get("averageHR")) if activity.get("averageHR") else None,
                "max_heart_rate": int(activity.get("maxHR")) if activity.get("maxHR") else None,
                "distance_km": round(activity.get("distance", 0) / 1000, 3) if activity.get("distance") else None,
                "external_id": external_id,
                "raw_data": activity
            }

            supabase.table("workouts").insert(workout).execute()
            saved.append(workout)

        return saved

    except Exception as e:
        raise Exception(f"Error sincronizando entrenamientos Garmin: {str(e)}")



async def sync_all(user_id: str, target_date: str = None):
    if not target_date:
        target_date = date.today().isoformat()

    results = {"weight": None, "workouts": [], "errors": []}

    try:
        results["weight"] = await sync_weight(user_id, target_date)
    except Exception as e:
        results["errors"].append(str(e))

    try:
        results["workouts"] = await sync_workouts(user_id, days_back=7)
    except Exception as e:
        results["errors"].append(str(e))

    return results
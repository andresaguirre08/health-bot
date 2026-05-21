import httpx
from datetime import date
from bot.db.client import supabase
from bot.utils.config import POLAR_CLIENT_ID, POLAR_CLIENT_SECRET, POLAR_REDIRECT_URL

POLAR_AUTH_URL = "https://flow.polar.com/oauth2/authorization"
POLAR_TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
POLAR_API_URL = "https://www.polaraccesslink.com/v3"


def get_auth_url(user_id: str) -> str:
    return (
        f"{POLAR_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={POLAR_CLIENT_ID}"
        f"&redirect_uri={POLAR_REDIRECT_URL}"
        f"&state={user_id}"
    )


async def exchange_code_for_token(code: str) -> dict:
    import base64
    credentials = f"{POLAR_CLIENT_ID}:{POLAR_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            POLAR_TOKEN_URL,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": POLAR_REDIRECT_URL
            }
        )
        return response.json()


async def register_user_polar(access_token: str, polar_user_id: str) -> bool:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{POLAR_API_URL}/users",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json={"member-id": polar_user_id}
        )
        return response.status_code in [200, 201, 409]


async def get_polar_token(user_id: str) -> dict | None:
    result = supabase.table("users")\
        .select("polar_access_token, polar_user_id")\
        .eq("id", user_id)\
        .execute()

    if result.data and result.data[0].get("polar_access_token"):
        return {
            "access_token": result.data[0]["polar_access_token"],
            "polar_user_id": result.data[0]["polar_user_id"]
        }
    return None


async def save_polar_token(user_id: str, token_data: dict):
    supabase.table("users").update({
        "polar_access_token": token_data.get("access_token"),
        "polar_user_id": str(token_data.get("x_user_id", ""))
    }).eq("id", user_id).execute()


async def sync_polar_workouts(user_id: str) -> list:
    token_data = await get_polar_token(user_id)
    if not token_data:
        raise Exception("No hay token de Polar. Usá /polar para conectar tu cuenta.")

    access_token = token_data["access_token"]

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{POLAR_API_URL}/exercises",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )

        if response.status_code == 404:
            return []

        if response.status_code != 200:
            raise Exception(f"Error obteniendo ejercicios: {response.status_code} — {response.text}")

        exercises = response.json()
        if not exercises:
            return []

        saved = []
        for ex in exercises:
            external_id = str(ex.get("id", ""))

            existing = supabase.table("workouts")\
                .select("id")\
                .eq("external_id", f"polar_{external_id}")\
                .execute()

            if existing.data:
                continue

            duration_str = ex.get("duration", "PT0S")
            duration_min = parse_duration_minutes(duration_str)
            workout_date = ex.get("start_time", "")[:10] or date.today().isoformat()

            workout = {
                "user_id": user_id,
                "workout_date": workout_date,
                "source": "polar",
                "activity_type": ex.get("detailed_sport_info", ex.get("sport", "workout")).lower(),
                "duration_min": duration_min,
                "calories_burned": ex.get("calories"),
                "avg_heart_rate": ex.get("heart_rate", {}).get("average"),
                "max_heart_rate": ex.get("heart_rate", {}).get("maximum"),
                "distance_km": round(ex.get("distance", 0) / 1000, 3) if ex.get("distance") else None,
                "external_id": f"polar_{external_id}",
                "raw_data": ex
            }

            supabase.table("workouts").insert(workout).execute()
            saved.append(workout)

        return saved


async def sync_polar_activity(user_id: str, target_date: str = None) -> dict:
    if not target_date:
        target_date = date.today().isoformat()

    token_data = await get_polar_token(user_id)
    if not token_data:
        raise Exception("No hay token de Polar.")

    access_token = token_data["access_token"]
    polar_user_id = token_data["polar_user_id"]

    async with httpx.AsyncClient() as client:
        trans_response = await client.post(
            f"{POLAR_API_URL}/users/{polar_user_id}/activity-transactions",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )

        if trans_response.status_code == 204:
            return {}

        if trans_response.status_code != 201:
            raise Exception(f"Error activity transaction: {trans_response.status_code} — {trans_response.text}")

        transaction = trans_response.json()
        transaction_id = transaction.get("transaction-id")

        list_response = await client.get(
            f"{POLAR_API_URL}/users/{polar_user_id}/activity-transactions/{transaction_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )

        if list_response.status_code != 200:
            return {}

        activity_list = list_response.json()
        activity_urls = activity_list.get("activity-log", [])

        result = {}
        for activity_url in activity_urls:
            act_response = await client.get(
                activity_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
            )

            if act_response.status_code != 200:
                continue

            activity = act_response.json()
            activity_date = activity.get("date", target_date)

            if activity_date == target_date:
                result = {
                    "date": activity_date,
                    "calories": activity.get("calories"),
                    "active_calories": activity.get("active-calories"),
                    "steps": activity.get("steps"),
                    "active_time": activity.get("active-time"),
                    "activity_goal_pct": activity.get("activity-goal"),
                }

        await client.put(
            f"{POLAR_API_URL}/users/{polar_user_id}/activity-transactions/{transaction_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        return result


def parse_duration_minutes(duration_str: str) -> int:
    import re
    if not duration_str:
        return 0
    hours = re.search(r'(\d+)H', duration_str)
    minutes = re.search(r'(\d+)M', duration_str)
    seconds = re.search(r'(\d+(?:\.\d+)?)S', duration_str)
    total_seconds = 0
    if hours:
        total_seconds += int(hours.group(1)) * 3600
    if minutes:
        total_seconds += int(minutes.group(1)) * 60
    if seconds:
        total_seconds += float(seconds.group(1))
    return round(total_seconds / 60)
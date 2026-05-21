from garminconnect import Garmin
from bot.utils.config import GARMIN_EMAIL, GARMIN_PASSWORD
from datetime import date, timedelta

client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
client.login()

start = (date.today() - timedelta(days=7)).isoformat()
end = date.today().isoformat()

activities = client.get_activities_by_date(start, end)
print(f"Total actividades: {len(activities)}")
for a in activities:
    tipo = a.get("activityType", {}).get("typeKey", "unknown")
    fecha = a.get("startTimeLocal", "")[:10]
    duracion = int(a.get("duration", 0) // 60)
    activity_id = a.get("activityId")
    print(f"- {tipo} | {fecha} | {duracion} min | ID: {activity_id}")
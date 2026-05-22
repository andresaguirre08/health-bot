from datetime import datetime, timedelta
import pytz
from bot.db.client import supabase

BOGOTA_TZ = pytz.timezone("America/Bogota")


def get_today_bogota():
    return datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d")


async def build_user_context(user_id: str) -> str:
    today = get_today_bogota()
    week_ago = (datetime.now(BOGOTA_TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now(BOGOTA_TZ) - timedelta(days=30)).strftime("%Y-%m-%d")

    # Perfil del usuario
    user = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        return ""
    u = user.data[0]

    # Última medición corporal
    last_measurement = supabase.table("body_measurements")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("measured_at", desc=True)\
        .limit(1)\
        .execute()

    # Medición de hace 30 días para comparar
    prev_measurement = supabase.table("body_measurements")\
        .select("*")\
        .eq("user_id", user_id)\
        .lte("measured_at", month_ago)\
        .order("measured_at", desc=True)\
        .limit(1)\
        .execute()

    # Comidas de hoy
    today_meals = supabase.table("meals")\
    .select("calories, protein_g, carbs_g, fat_g, description, logged_at")\
    .eq("user_id", user_id)\
    .gte("logged_at", today + "T00:00:00-05:00")\
    .lte("logged_at", today + "T23:59:59-05:00")\
    .execute()

    # Promedio nutricional últimos 7 días
    week_meals = supabase.table("meals")\
        .select("calories, protein_g, carbs_g, fat_g")\
        .eq("user_id", user_id)\
        .gte("logged_at", week_ago)\
        .execute()

    # Entrenamientos última semana
    week_workouts = supabase.table("workouts")\
        .select("activity_type, duration_min, calories_burned, workout_date")\
        .eq("user_id", user_id)\
        .gte("workout_date", week_ago)\
        .execute()

    # Calcular totales de hoy
    today_calories = sum(m.get("calories") or 0 for m in today_meals.data)
    today_protein = sum(float(m.get("protein_g") or 0) for m in today_meals.data)
    today_carbs = sum(float(m.get("carbs_g") or 0) for m in today_meals.data)
    today_fat = sum(float(m.get("fat_g") or 0) for m in today_meals.data)
    today_meal_count = len(today_meals.data)

    # Calcular promedios semanales
    if week_meals.data:
        days_with_data = 7
        avg_calories = sum(m.get("calories") or 0 for m in week_meals.data) / days_with_data
        avg_protein = sum(float(m.get("protein_g") or 0) for m in week_meals.data) / days_with_data
        avg_carbs = sum(float(m.get("carbs_g") or 0) for m in week_meals.data) / days_with_data
        avg_fat = sum(float(m.get("fat_g") or 0) for m in week_meals.data) / days_with_data
    else:
        avg_calories = avg_protein = avg_carbs = avg_fat = 0

    # Construir sección de composición corporal
    body_section = ""
    if last_measurement.data:
        m = last_measurement.data[0]
        body_section = f"""
Última medición corporal ({m.get('measured_at')}):
- Peso: {m.get('weight_kg')} kg
- % Grasa corporal: {m.get('body_fat_pct')}%
- Masa muscular: {m.get('muscle_mass_kg')} kg
- Cintura: {m.get('waist_cm')} cm"""

        if prev_measurement.data:
            p = prev_measurement.data[0]
            weight_change = (m.get('weight_kg') or 0) - (p.get('weight_kg') or 0)
            bf_change = (m.get('body_fat_pct') or 0) - (p.get('body_fat_pct') or 0)
            muscle_change = (m.get('muscle_mass_kg') or 0) - (p.get('muscle_mass_kg') or 0)
            body_section += f"""

Cambios vs hace 30 días:
- Peso: {weight_change:+.1f} kg
- % Grasa: {bf_change:+.1f}%
- Masa muscular: {muscle_change:+.1f} kg
- Tendencia: {'✅ perdiendo grasa' if bf_change < 0 else '⚠️ subiendo grasa'}"""

    # Construir sección de entrenamientos
    workout_section = ""
    if week_workouts.data:
        total_workouts = len(week_workouts.data)
        total_burned = sum(w.get("calories_burned") or 0 for w in week_workouts.data)
        types = [w.get("activity_type", "") for w in week_workouts.data]
        workout_section = f"""
Entrenamientos esta semana: {total_workouts} sesiones
- Calorías quemadas: {total_burned} kcal
- Actividades: {', '.join(types)}"""

    # Calcular proteína pendiente
    protein_remaining = max(0, u.get("daily_protein_g", 180) - today_protein)
    calories_remaining = max(0, u.get("daily_calories", 2000) - today_calories)
    protein_pct = round((today_protein / u.get("daily_protein_g", 180)) * 100) if u.get("daily_protein_g") else 0

    context = f"""=== CONTEXTO PERSONALIZADO DE ANDRÉS ===

PERFIL:
- Nombre: {u.get('name')}
- Altura: {u.get('height_cm')} cm
- Objetivo: {u.get('goal_type')} (reducir grasa y peso al mínimo, mantener músculo)
{body_section}

OBJETIVOS DIARIOS:
- Calorías: {u.get('daily_calories')} kcal
- Proteína: {u.get('daily_protein_g')} g
- Carbohidratos: {u.get('daily_carbs_g')} g
- Grasas: {u.get('daily_fat_g')} g

HOY ({today}):
- Comidas registradas: {today_meal_count}
- Calorías consumidas: {today_calories} / {u.get('daily_calories')} kcal
- Proteína consumida: {today_protein:.1f}g / {u.get('daily_protein_g')}g ({protein_pct}%)
- Carbohidratos: {today_carbs:.1f}g
- Grasas: {today_fat:.1f}g
- ⚡ Proteína pendiente: {protein_remaining:.1f}g
- 🔥 Calorías restantes: {calories_remaining}

PROMEDIOS ÚLTIMOS 7 DÍAS:
- Calorías/día: {avg_calories:.0f} kcal
- Proteína/día: {avg_protein:.1f}g
- Carbohidratos/día: {avg_carbs:.1f}g
- Grasas/día: {avg_fat:.1f}g
- Cumplimiento proteína: {'✅ bien' if avg_protein >= u.get('daily_protein_g', 180) * 0.8 else '⚠️ bajo, necesita mejorar'}
{workout_section}

=== FIN CONTEXTO ==="""

    return context


async def get_today_totals(user_id: str) -> dict:
    today = get_today_bogota()
    result = supabase.table("meals")\
    .select("calories, protein_g, carbs_g, fat_g, meal_type")\
    .eq("user_id", user_id)\
    .gte("logged_at", today + "T00:00:00-05:00")\
    .lte("logged_at", today + "T23:59:59-05:00")\
    .execute()

    totals = {"calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for meal in result.data:
        totals["calories"] += meal.get("calories") or 0
        totals["protein"] += float(meal.get("protein_g") or 0)
        totals["carbs"] += float(meal.get("carbs_g") or 0)
        totals["fat"] += float(meal.get("fat_g") or 0)

    return totals
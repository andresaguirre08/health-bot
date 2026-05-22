import logging
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Bogota")


def start_scheduler(app):
    scheduler.add_job(
        remind_vitamins,
        CronTrigger(hour=8, minute=0),
        args=[app],
        id="vitamins",
        replace_existing=True
    )
    scheduler.add_job(
        remind_creatine,
        CronTrigger(hour=12, minute=0),
        args=[app],
        id="creatine",
        replace_existing=True
    )
    scheduler.add_job(
        check_protein_midday,
        CronTrigger(hour=14, minute=0),
        args=[app],
        id="protein_midday",
        replace_existing=True
    )
    scheduler.add_job(
        check_protein_evening,
        CronTrigger(hour=19, minute=0),
        args=[app],
        id="protein_evening",
        replace_existing=True
    )
    scheduler.add_job(
        daily_summary,
        CronTrigger(hour=23, minute=30),
        args=[app],
        id="daily_summary",
        replace_existing=True
    )
    scheduler.add_job(
        sync_garmin_auto,
        CronTrigger(hour=23, minute=0),
        args=[app],
        id="garmin_sync",
        replace_existing=True
    )
    scheduler.add_job(
    weekend_message,
    CronTrigger(day_of_week="fri", hour=18, minute=0),
    args=[app],
    id="weekend_message",
    replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler iniciado con zona horaria America/Bogota")


async def get_user_info():
    from bot.db.client import supabase
    result = supabase.table("users").select("id, telegram_id, daily_protein_g, daily_calories").execute()
    return result.data if result.data else []


async def remind_vitamins(app):
    try:
        users = await get_user_info()
        for user in users:
            await app.bot.send_message(
                chat_id=user["telegram_id"],
                text="💊 Recordatorio: tomá tus vitaminas\n- Vitamina D\n- Omega 3\n- Zinc"
            )
    except Exception as e:
        logger.error(f"Error recordatorio vitaminas: {e}")


async def remind_creatine(app):
    try:
        users = await get_user_info()
        for user in users:
            await app.bot.send_message(
                chat_id=user["telegram_id"],
                text="💪 Recordatorio: tomá tu creatina (5g)\nMejor momento: después del entreno o con la comida."
            )
    except Exception as e:
        logger.error(f"Error recordatorio creatina: {e}")


async def check_protein_midday(app):
    try:
        from bot.db.client import supabase
        users = await get_user_info()

        for user in users:
            today = date.today().isoformat()
            meals = supabase.table("meals")\
                .select("protein_g")\
                .eq("user_id", user["id"])\
                .gte("logged_at", today)\
                .execute()

            protein_eaten = sum(float(m.get("protein_g") or 0) for m in meals.data)
            protein_goal = user.get("daily_protein_g", 180)
            protein_remaining = max(0, protein_goal - protein_eaten)
            protein_pct = round((protein_eaten / protein_goal) * 100) if protein_goal else 0

            if protein_pct < 40:
                msg = (
                    f"⚡ Alerta proteína — 2pm\n\n"
                    f"Llevas {protein_eaten:.0f}g de {protein_goal}g ({protein_pct}%)\n"
                    f"Te faltan {protein_remaining:.0f}g para hoy\n\n"
                    f"Opciones rápidas:\n"
                    f"- Lata de atún: 25g\n"
                    f"- Pechuga 150g: 45g\n"
                    f"- Huevos x3: 18g\n"
                    f"- Yogurt griego: 15g"
                )
                await app.bot.send_message(chat_id=user["telegram_id"], text=msg)

    except Exception as e:
        logger.error(f"Error check proteína mediodía: {e}")


async def check_protein_evening(app):
    try:
        from bot.db.client import supabase
        users = await get_user_info()

        for user in users:
            today = date.today().isoformat()
            meals = supabase.table("meals")\
                .select("protein_g")\
                .eq("user_id", user["id"])\
                .gte("logged_at", today)\
                .execute()

            protein_eaten = sum(float(m.get("protein_g") or 0) for m in meals.data)
            protein_goal = user.get("daily_protein_g", 180)
            protein_remaining = max(0, protein_goal - protein_eaten)
            protein_pct = round((protein_eaten / protein_goal) * 100) if protein_goal else 0

            if protein_remaining > 20:
                msg = (
                    f"🌙 Última alerta proteína — 7pm\n\n"
                    f"Llevas {protein_eaten:.0f}g de {protein_goal}g ({protein_pct}%)\n"
                    f"Te faltan {protein_remaining:.0f}g\n\n"
                    f"{'⚠️ Estás muy bajo, priorizá proteína en la cena' if protein_pct < 50 else '💡 Completá con la cena y una merienda'}"
                )
                await app.bot.send_message(chat_id=user["telegram_id"], text=msg)

    except Exception as e:
        logger.error(f"Error check proteína noche: {e}")


async def daily_summary(app):
    try:
        from bot.db.client import supabase
        from bot.utils.config import ANTHROPIC_API_KEY
        import anthropic
        from datetime import datetime
        import pytz

        bogota_tz = pytz.timezone("America/Bogota")
        today = datetime.now(bogota_tz).strftime("%Y-%m-%d")

        users = await get_user_info()

        for user in users:
            meals = supabase.table("meals")\
                .select("calories, protein_g, carbs_g, fat_g, meal_type")\
                .eq("user_id", user["id"])\
                .gte("logged_at", today)\
                .lt("logged_at", today + "T23:59:59-05:00")\
                .execute()

            workouts = supabase.table("workouts")\
                .select("activity_type, duration_min, calories_burned")\
                .eq("user_id", user["id"])\
                .eq("workout_date", today)\
                .execute()

            # Medición más reciente
            last_measurement = supabase.table("body_measurements")\
                .select("weight_kg, body_fat_pct")\
                .eq("user_id", user["id"])\
                .order("measured_at", desc=True)\
                .limit(1)\
                .execute()

            total_calories = sum(m.get("calories") or 0 for m in meals.data)
            total_protein = sum(float(m.get("protein_g") or 0) for m in meals.data)
            total_carbs = sum(float(m.get("carbs_g") or 0) for m in meals.data)
            total_fat = sum(float(m.get("fat_g") or 0) for m in meals.data)
            total_burned = sum(w.get("calories_burned") or 0 for w in workouts.data)
            net_calories = total_calories - total_burned

            protein_goal = user.get("daily_protein_g", 180)
            calorie_goal = user.get("daily_calories", 2000)
            protein_pct = round((total_protein / protein_goal) * 100) if protein_goal else 0

            current_weight = last_measurement.data[0].get("weight_kg") if last_measurement.data else None
            current_bf = last_measurement.data[0].get("body_fat_pct") if last_measurement.data else None

            workout_text = ""
            if workouts.data:
                for w in workouts.data:
                    workout_text += f"- {w.get('activity_type')}: {w.get('duration_min')} min — {w.get('calories_burned')} kcal\n"
            else:
                workout_text = "- Sin entrenamientos registrados hoy\n"

            # Generar feedback con Claude
            claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

            prompt = f"""Andrés tuvo este día:
- Calorías consumidas: {total_calories} / {calorie_goal} kcal
- Proteína: {total_protein:.0f}g / {protein_goal}g ({protein_pct}%)
- Carbohidratos: {total_carbs:.0f}g
- Grasas: {total_fat:.0f}g
- Calorías quemadas entrenando: {total_burned} kcal
- Calorías netas: {net_calories} kcal
- Peso actual: {current_weight} kg (objetivo: 85 kg)
- % Grasa actual: {current_bf}% (objetivo: menos de 20%)

Escribí un feedback del día de máximo 3 líneas: qué hizo bien, qué puede mejorar mañana, y una frase de motivación corta y directa para que llegue a su objetivo de 85kg y menos de 20% de grasa. Sin asteriscos ni markdown. Tono directo y personal."""

            feedback_response = claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            feedback = feedback_response.content[0].text

            msg = (
                f"📊 Resumen del día — {today}\n\n"
                f"🍽 Nutrición:\n"
                f"- Calorías: {total_calories} / {calorie_goal} kcal\n"
                f"- Proteína: {total_protein:.0f}g / {protein_goal}g ({protein_pct}%)\n"
                f"- Carbohidratos: {total_carbs:.0f}g\n"
                f"- Grasas: {total_fat:.0f}g\n\n"
                f"🏋 Ejercicio:\n"
                f"{workout_text}"
                f"- Calorías quemadas: {total_burned} kcal\n"
                f"- Calorías netas: {net_calories} kcal\n\n"
                f"🎯 Progreso hacia objetivo:\n"
                f"- Peso: {current_weight} kg → objetivo 85 kg\n"
                f"- Grasa: {current_bf}% → objetivo menos de 20%\n\n"
                f"💬 {feedback}"
            )

            await app.bot.send_message(chat_id=user["telegram_id"], text=msg)

    except Exception as e:
        logger.error(f"Error resumen diario: {e}")

async def sync_garmin_auto(app):
    try:
        from bot.db.client import supabase
        from bot.integrations.garmin import sync_all

        users = await get_user_info()
        for user in users:
            results = await sync_all(user["id"])
            if results.get("weight") or results.get("workouts"):
                msg = "🔄 Sincronización automática Garmin\n"
                if results.get("weight"):
                    w = results["weight"]
                    msg += f"⚖️ Peso: {w.get('weight_kg')} kg"
                    if w.get('body_fat_pct'):
                        msg += f" | Grasa: {w.get('body_fat_pct')}%"
                    msg += "\n"
                if results.get("workouts"):
                    msg += f"🏋 {len(results['workouts'])} entreno(s) descargado(s)\n"
                await app.bot.send_message(chat_id=user["telegram_id"], text=msg)

    except Exception as e:
        logger.error(f"Error sync Garmin automático: {e}")
async def weekend_message(app):
    try:
        from bot.db.client import supabase
        from datetime import datetime, timedelta
        import pytz

        bogota_tz = pytz.timezone("America/Bogota")
        today = datetime.now(bogota_tz).strftime("%Y-%m-%d")
        week_ago = (datetime.now(bogota_tz) - timedelta(days=5)).strftime("%Y-%m-%d")

        users = await get_user_info()

        for user in users:
            # Calorías y proteína de la semana
            meals = supabase.table("meals")\
                .select("calories, protein_g")\
                .eq("user_id", user["id"])\
                .gte("logged_at", week_ago)\
                .execute()

            # Entrenamientos de la semana
            workouts = supabase.table("workouts")\
                .select("calories_burned, workout_date")\
                .eq("user_id", user["id"])\
                .gte("workout_date", week_ago)\
                .execute()

            total_calories = sum(m.get("calories") or 0 for m in meals.data)
            total_protein = sum(float(m.get("protein_g") or 0) for m in meals.data)
            total_burned = sum(w.get("calories_burned") or 0 for w in workouts.data)
            workout_count = len(workouts.data)

            calorie_goal_week = user.get("daily_calories", 2000) * 5
            protein_goal_week = user.get("daily_protein_g", 180) * 5
            calorie_deficit = calorie_goal_week - total_calories + total_burned
            protein_pct = round((total_protein / protein_goal_week) * 100) if protein_goal_week else 0

            # Decidir qué permitido sugerir según la semana
            if calorie_deficit > 1500 and protein_pct >= 80 and workout_count >= 3:
                permitido = "una hamburguesa con papas o una pizza — la tuviste ganada esta semana"
                nivel = "🟢 Semana excelente"
            elif calorie_deficit > 500 and protein_pct >= 60 and workout_count >= 2:
                permitido = "una pizza o hamburguesa, pero controlá el tamaño — una porción, no dos"
                nivel = "🟡 Semana buena"
            elif workout_count >= 2 and protein_pct >= 50:
                permitido = "algo rico pero moderado — un helado, unas empanadas o una comida libre sin excederte"
                nivel = "🟡 Semana regular"
            else:
                permitido = "algo pequeño si querés, pero esta semana estuvo floja — la próxima semana empezá fuerte el lunes"
                nivel = "🔴 Semana difícil"

            msg = (
                f"🎉 Es viernes, Andrés!\n\n"
                f"{nivel}\n"
                f"Resumen de la semana:\n"
                f"- Entrenamientos: {workout_count}\n"
                f"- Proteína: {protein_pct}% del objetivo\n"
                f"- Déficit calórico acumulado: {calorie_deficit:.0f} kcal\n\n"
                f"Tu permitido de fin de semana: {permitido}\n\n"
                f"Si comés el permitido mandame foto y lo registro para que no perdamos el control. "
                f"El lunes retomamos con todo 💪"
            )

            await app.bot.send_message(chat_id=user["telegram_id"], text=msg)

    except Exception as e:
        logger.error(f"Error mensaje fin de semana: {e}")
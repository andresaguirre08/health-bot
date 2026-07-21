import logging
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Bogota")
BOGOTA_TZ = pytz.timezone("America/Bogota")


def get_today_bogota():
    return datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d")


def start_scheduler(app):
    scheduler.add_job(
        remind_vitamins,
        CronTrigger(hour=8, minute=0, timezone="America/Bogota"),
        args=[app],
        id="vitamins",
        replace_existing=True
    )
    scheduler.add_job(
        remind_creatine,
        CronTrigger(hour=12, minute=0, timezone="America/Bogota"),
        args=[app],
        id="creatine",
        replace_existing=True
    )
    scheduler.add_job(
        check_protein_midday,
        CronTrigger(hour=14, minute=0, timezone="America/Bogota"),
        args=[app],
        id="protein_midday",
        replace_existing=True
    )
    scheduler.add_job(
        check_protein_evening,
        CronTrigger(hour=19, minute=0, timezone="America/Bogota"),
        args=[app],
        id="protein_evening",
        replace_existing=True
    )
    scheduler.add_job(
        daily_summary,
        CronTrigger(hour=23, minute=30, timezone="America/Bogota"),
        args=[app],
        id="daily_summary",
        replace_existing=True
    )
    scheduler.add_job(
        sync_garmin_auto,
        CronTrigger(hour=23, minute=0, timezone="America/Bogota"),
        args=[app],
        id="garmin_sync",
        replace_existing=True
    )
    scheduler.add_job(
        weekend_message,
        CronTrigger(day_of_week="fri", hour=18, minute=0, timezone="America/Bogota"),
        args=[app],
        id="weekend_message",
        replace_existing=True
    )
    scheduler.add_job(
        check_anthropic_usage,
        CronTrigger(hour=9, minute=0, timezone="America/Bogota"),
        args=[app],
        id="check_anthropic_usage",
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
    except Exception as e:
        logger.error(f"Error obteniendo usuarios para recordatorio vitaminas: {e}")
        return

    for user in users:
        try:
            await app.bot.send_message(
                chat_id=user["telegram_id"],
                text="💊 Recordatorio: tomá tus vitaminas\n- Vitamina D\n- Omega 3\n- Zinc"
            )
        except Exception as e:
            logger.error(f"Error recordatorio vitaminas para usuario {user.get('id')}: {e}")


async def remind_creatine(app):
    try:
        users = await get_user_info()
    except Exception as e:
        logger.error(f"Error obteniendo usuarios para recordatorio creatina: {e}")
        return

    for user in users:
        try:
            await app.bot.send_message(
                chat_id=user["telegram_id"],
                text="💪 Recordatorio: tomá tu creatina (5g)\nMejor momento: después del entreno o con la comida."
            )
        except Exception as e:
            logger.error(f"Error recordatorio creatina para usuario {user.get('id')}: {e}")


async def check_protein_midday(app):
    from bot.db.client import supabase
    try:
        users = await get_user_info()
    except Exception as e:
        logger.error(f"Error obteniendo usuarios para check proteína mediodía: {e}")
        return

    for user in users:
        try:
            today = get_today_bogota()
            meals = supabase.table("meals")\
                .select("protein_g")\
                .eq("user_id", user["id"])\
                .gte("logged_at", today + "T00:00:00-05:00")\
                .lte("logged_at", today + "T23:59:59-05:00")\
                .execute()

            protein_eaten = sum(float(m.get("protein_g") or 0) for m in meals.data)
            protein_goal = user.get("daily_protein_g") or 180
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
            logger.error(f"Error check proteína mediodía para usuario {user.get('id')}: {e}")


async def check_protein_evening(app):
    from bot.db.client import supabase
    try:
        users = await get_user_info()
    except Exception as e:
        logger.error(f"Error obteniendo usuarios para check proteína noche: {e}")
        return

    for user in users:
        try:
            today = get_today_bogota()
            meals = supabase.table("meals")\
                .select("protein_g")\
                .eq("user_id", user["id"])\
                .gte("logged_at", today + "T00:00:00-05:00")\
                .lte("logged_at", today + "T23:59:59-05:00")\
                .execute()

            protein_eaten = sum(float(m.get("protein_g") or 0) for m in meals.data)
            protein_goal = user.get("daily_protein_g") or 180
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
            logger.error(f"Error check proteína noche para usuario {user.get('id')}: {e}")


async def daily_summary(app):
    from bot.db.client import supabase
    from bot.utils.config import ANTHROPIC_API_KEY
    import anthropic

    claude = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    try:
        today = get_today_bogota()
        users = await get_user_info()
    except Exception as e:
        logger.error(f"Error obteniendo usuarios para resumen diario: {e}")
        return

    for user in users:
        try:
            meals = supabase.table("meals")\
                .select("calories, protein_g, carbs_g, fat_g, meal_type")\
                .eq("user_id", user["id"])\
                .gte("logged_at", today + "T00:00:00-05:00")\
                .lte("logged_at", today + "T23:59:59-05:00")\
                .execute()

            workouts = supabase.table("workouts")\
                .select("activity_type, duration_min, calories_burned")\
                .eq("user_id", user["id"])\
                .eq("workout_date", today)\
                .execute()

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

            protein_goal = user.get("daily_protein_g") or 180
            calorie_goal = user.get("daily_calories") or 2000
            protein_pct = round((total_protein / protein_goal) * 100) if protein_goal else 0

            current_weight = last_measurement.data[0].get("weight_kg") if last_measurement.data else None
            current_bf = last_measurement.data[0].get("body_fat_pct") if last_measurement.data else None

            workout_text = ""
            if workouts.data:
                for w in workouts.data:
                    workout_text += f"- {w.get('activity_type')}: {w.get('duration_min')} min — {w.get('calories_burned')} kcal\n"
            else:
                workout_text = "- Sin entrenamientos registrados hoy\n"

            prompt = f"""Andrés tuvo este día:
- Calorías consumidas: {total_calories} / {calorie_goal} kcal
- Proteína: {total_protein:.0f}g / {protein_goal}g ({protein_pct}%)
- Carbohidratos: {total_carbs:.0f}g
- Grasas: {total_fat:.0f}g
- Calorías quemadas entrenando: {total_burned} kcal
- Calorías netas: {net_calories} kcal
- Peso actual: {current_weight} kg (objetivo: 85 kg)
- % Grasa actual: {current_bf}% (objetivo: menos de 20%)

Escribí un feedback del día de máximo 3 líneas: qué hizo bien, qué puede mejorar mañana, y una frase de motivación corta y directa. Sin asteriscos ni markdown. Tono directo y personal."""

            feedback_response = await claude.messages.create(
                model="claude-opus-4-1-20250805",
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
            logger.error(f"Error resumen diario para usuario {user.get('id')}: {e}")


async def sync_garmin_auto(app):
    from bot.integrations.garmin import sync_all

    try:
        users = await get_user_info()
    except Exception as e:
        logger.error(f"Error obteniendo usuarios para sync Garmin automático: {e}")
        return

    for user in users:
        try:
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
            logger.error(f"Error sync Garmin automático para usuario {user.get('id')}: {e}")


async def weekend_message(app):
    from bot.db.client import supabase

    today = get_today_bogota()
    week_ago = (datetime.now(BOGOTA_TZ) - timedelta(days=5)).strftime("%Y-%m-%d")

    try:
        users = await get_user_info()
    except Exception as e:
        logger.error(f"Error obteniendo usuarios para mensaje fin de semana: {e}")
        return

    for user in users:
        try:
            meals = supabase.table("meals")\
                .select("calories, protein_g")\
                .eq("user_id", user["id"])\
                .gte("logged_at", week_ago + "T00:00:00-05:00")\
                .lte("logged_at", today + "T23:59:59-05:00")\
                .execute()

            workouts = supabase.table("workouts")\
                .select("calories_burned, workout_date")\
                .eq("user_id", user["id"])\
                .gte("workout_date", week_ago)\
                .execute()

            total_calories = sum(m.get("calories") or 0 for m in meals.data)
            total_protein = sum(float(m.get("protein_g") or 0) for m in meals.data)
            total_burned = sum(w.get("calories_burned") or 0 for w in workouts.data)
            workout_count = len(workouts.data)

            calorie_goal_week = (user.get("daily_calories") or 2000) * 5
            protein_goal_week = (user.get("daily_protein_g") or 180) * 5
            calorie_deficit = calorie_goal_week - total_calories + total_burned
            protein_pct = round((total_protein / protein_goal_week) * 100) if protein_goal_week else 0

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
                f"Si comés el permitido mandame foto y lo registro. El lunes retomamos 💪"
            )

            await app.bot.send_message(chat_id=user["telegram_id"], text=msg)

        except Exception as e:
            logger.error(f"Error mensaje fin de semana para usuario {user.get('id')}: {e}")


async def check_anthropic_usage(app):
    try:
        import httpx
        from bot.utils.config import ANTHROPIC_API_KEY

        now = datetime.now(BOGOTA_TZ)
        year = now.year
        month = now.month

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.anthropic.com/v1/usage?year={year}&month={month}",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01"
                }
            )

            if response.status_code != 200:
                return

            data = response.json()
            total_cost = data.get("total_cost_usd", 0)
            limit = 5.0
            pct = (total_cost / limit) * 100

            if pct >= 70:
                users = await get_user_info()
                for user in users:
                    try:
                        await app.bot.send_message(
                            chat_id=user["telegram_id"],
                            text=(
                                f"⚠️ Alerta de tokens Anthropic\n\n"
                                f"Gastaste ${total_cost:.2f} de ${limit:.2f} este mes ({pct:.0f}%)\n"
                                f"Te quedan ${limit - total_cost:.2f}\n\n"
                                f"Revisá en console.anthropic.com"
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error alerta de tokens para usuario {user.get('id')}: {e}")

    except Exception as e:
        logger.error(f"Error chequeando uso Anthropic: {e}")
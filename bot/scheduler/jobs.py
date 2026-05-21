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
        CronTrigger(hour=22, minute=0),
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
        users = await get_user_info()

        for user in users:
            today = date.today().isoformat()

            meals = supabase.table("meals")\
                .select("calories, protein_g, carbs_g, fat_g")\
                .eq("user_id", user["id"])\
                .gte("logged_at", today)\
                .execute()

            workouts = supabase.table("workouts")\
                .select("activity_type, duration_min, calories_burned")\
                .eq("user_id", user["id"])\
                .eq("workout_date", today)\
                .execute()

            total_calories = sum(m.get("calories") or 0 for m in meals.data)
            total_protein = sum(float(m.get("protein_g") or 0) for m in meals.data)
            total_carbs = sum(float(m.get("carbs_g") or 0) for m in meals.data)
            total_fat = sum(float(m.get("fat_g") or 0) for m in meals.data)
            total_burned = sum(w.get("calories_burned") or 0 for w in workouts.data)

            protein_goal = user.get("daily_protein_g", 180)
            calorie_goal = user.get("daily_calories", 2000)
            protein_pct = round((total_protein / protein_goal) * 100) if protein_goal else 0
            protein_remaining = max(0, protein_goal - total_protein)

            workout_text = ""
            if workouts.data:
                workout_text = f"\n🏋 Entrenamientos: {len(workouts.data)}\n"
                for w in workouts.data:
                    workout_text += f"- {w.get('activity_type')}: {w.get('duration_min')} min"
                    if w.get('calories_burned'):
                        workout_text += f" — {w.get('calories_burned')} kcal"
                    workout_text += "\n"
                workout_text += f"- Total quemado: {total_burned} kcal\n"

            status = "✅" if protein_pct >= 90 else "⚠️" if protein_pct >= 60 else "❌"

            msg = (
                f"📊 Resumen del día — {today}\n\n"
                f"Nutrición:\n"
                f"- Calorías: {total_calories} / {calorie_goal} kcal\n"
                f"- Proteína: {total_protein:.0f}g / {protein_goal}g ({protein_pct}%) {status}\n"
                f"- Carbohidratos: {total_carbs:.0f}g\n"
                f"- Grasas: {total_fat:.0f}g\n"
                f"{workout_text}\n"
                f"{'✅ Excelente día, objetivo de proteína cumplido!' if protein_remaining == 0 else f'Proteína pendiente: {protein_remaining:.0f}g'}"
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
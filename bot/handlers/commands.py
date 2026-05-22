from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ContextTypes
from bot.db.meals import get_or_create_user, get_today_totals
from bot.db.client import supabase

BOGOTA_TZ = pytz.timezone("America/Bogota")


def get_today_bogota():
    return datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d")


async def cmd_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        totals = await get_today_totals(user_id)

        user = supabase.table("users").select("*").eq("id", user_id).execute()
        u = user.data[0]

        today = get_today_bogota()
        workouts = supabase.table("workouts")\
            .select("activity_type, duration_min, calories_burned")\
            .eq("user_id", user_id)\
            .eq("workout_date", today)\
            .execute()

        total_burned = sum(w.get("calories_burned") or 0 for w in workouts.data)
        net_calories = totals["calories"] - total_burned

        protein_goal = u.get("daily_protein_g", 180)
        calorie_goal = u.get("daily_calories", 2000)
        protein_pct = round((totals["protein"] / protein_goal) * 100) if protein_goal else 0
        calorie_pct = round((totals["calories"] / calorie_goal) * 100) if calorie_goal else 0
        protein_remaining = max(0, protein_goal - totals["protein"])

        def progress_bar(pct):
            filled = min(int(pct / 10), 10)
            return "█" * filled + "░" * (10 - filled)

        workout_section = ""
        if workouts.data:
            workout_section = "\n*Entrenamientos de hoy:*\n"
            for w in workouts.data:
                workout_section += f"- {w.get('activity_type', 'entreno')}: {w.get('duration_min')} min — {w.get('calories_burned')} kcal\n"
            workout_section += f"- Total quemado: {total_burned} kcal\n"
            workout_section += f"- Calorías netas: {net_calories} kcal\n"
        else:
            workout_section = "\n⚠️ Sin entrenamientos registrados hoy\n"

        msg = f"""📊 *Resumen de hoy — {today}*

*Nutrición:*
- 🔥 Calorías: {totals['calories']} / {calorie_goal} kcal ({calorie_pct}%)
  {progress_bar(calorie_pct)}
- 💪 Proteína: {totals['protein']:.1f} / {protein_goal}g ({protein_pct}%)
  {progress_bar(protein_pct)}
- 🍚 Carbohidratos: {totals['carbs']:.1f}g
- 🥑 Grasas: {totals['fat']:.1f}g
{workout_section}
*Proteína pendiente: {protein_remaining:.1f}g*
{'✅ Objetivo de proteína cumplido!' if protein_remaining == 0 else f'⚡ Necesitás {protein_remaining:.1f}g más de proteína hoy'}"""

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cmd_progreso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        measurements = supabase.table("body_measurements")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("measured_at", desc=True)\
            .limit(5)\
            .execute()

        if not measurements.data:
            await update.message.reply_text(
                "📏 No tenés mediciones registradas todavía.\n"
                "Usá /peso para registrar tu peso y medidas."
            )
            return

        latest = measurements.data[0]
        msg = "📈 *Tu progreso*\n\n"
        msg += f"*Última medición ({latest.get('measured_at')}):*\n"
        msg += f"- ⚖️ Peso: {latest.get('weight_kg')} kg\n"
        msg += f"- 📊 % Grasa: {latest.get('body_fat_pct')}%\n"
        msg += f"- 💪 Masa muscular: {latest.get('muscle_mass_kg')} kg\n"
        msg += f"- 📏 Cintura: {latest.get('waist_cm')} cm\n"

        if len(measurements.data) > 1:
            oldest = measurements.data[-1]
            weight_change = (latest.get('weight_kg') or 0) - (oldest.get('weight_kg') or 0)
            bf_change = (latest.get('body_fat_pct') or 0) - (oldest.get('body_fat_pct') or 0)
            muscle_change = (latest.get('muscle_mass_kg') or 0) - (oldest.get('muscle_mass_kg') or 0)

            msg += f"\n*Cambios desde {oldest.get('measured_at')}:*\n"
            msg += f"- Peso: {weight_change:+.1f} kg {'✅' if weight_change < 0 else '⚠️'}\n"
            msg += f"- % Grasa: {bf_change:+.1f}% {'✅' if bf_change < 0 else '⚠️'}\n"
            msg += f"- Masa muscular: {muscle_change:+.1f} kg {'✅' if muscle_change > 0 else '⚠️'}\n"

        msg += "\n*Historial:*\n"
        for m in measurements.data:
            msg += f"- {m.get('measured_at')}: {m.get('weight_kg')}kg | {m.get('body_fat_pct')}% grasa\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cmd_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚖️ *Registrar medición*\n\n"
        "Enviame tus datos en este formato:\n\n"
        "`peso cintura grasa musculo`\n\n"
        "Ejemplo:\n"
        "`84.5 95 30.2 35.8`\n\n"
        "Si no tenés algún dato usá 0:\n"
        "`84.5 0 0 0`",
        parse_mode="Markdown"
    )
    context.user_data["waiting_for_measurement"] = True


async def handle_measurement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_measurement"):
        return False

    try:
        parts = update.message.text.strip().split()
        if len(parts) < 1:
            return False

        values = [float(p) for p in parts]
        weight = values[0] if len(values) > 0 else None
        waist = values[1] if len(values) > 1 and values[1] > 0 else None
        bf_pct = values[2] if len(values) > 2 and values[2] > 0 else None
        muscle = values[3] if len(values) > 3 and values[3] > 0 else None

        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        measurement = {
            "user_id": user_id,
            "measured_at": get_today_bogota(),
            "weight_kg": weight,
            "waist_cm": waist,
            "body_fat_pct": bf_pct,
            "muscle_mass_kg": muscle,
            "source": "manual"
        }

        supabase.table("body_measurements").insert(measurement).execute()
        context.user_data["waiting_for_measurement"] = False

        msg = "✅ *Medición registrada*\n\n"
        if weight:
            msg += f"- ⚖️ Peso: {weight} kg\n"
        if waist:
            msg += f"- 📏 Cintura: {waist} cm\n"
        if bf_pct:
            msg += f"- 📊 % Grasa: {bf_pct}%\n"
        if muscle:
            msg += f"- 💪 Masa muscular: {muscle} kg\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
        return True

    except Exception as e:
        context.user_data["waiting_for_measurement"] = False
        await update.message.reply_text(f"❌ Error al guardar: {str(e)}")
        return True


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Sincronizando con Garmin Connect... ⏳")

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        from bot.integrations.garmin import sync_all
        results = await sync_all(user_id)

        msg = "✅ *Sincronización Garmin completada*\n\n"

        if results["weight"]:
            w = results["weight"]
            msg += "⚖️ *Peso registrado:*\n"
            msg += f"- Peso: {w.get('weight_kg')} kg\n"
            if w.get('body_fat_pct'):
                msg += f"- % Grasa: {w.get('body_fat_pct')}%\n"
            if w.get('muscle_mass_kg'):
                msg += f"- Masa muscular: {w.get('muscle_mass_kg')} kg\n"
        else:
            msg += "⚖️ Sin datos de peso para hoy\n"

        if results["workouts"]:
            msg += f"\n🏋 *Entrenamientos descargados: {len(results['workouts'])}*\n"
            for w in results["workouts"]:
                msg += f"- {w.get('activity_type')}: {w.get('duration_min')} min"
                if w.get('calories_burned'):
                    msg += f" — {w.get('calories_burned')} kcal"
                msg += "\n"
        else:
            msg += "\n🏋 Sin entrenamientos nuevos para hoy\n"

        if results["errors"]:
            msg += f"\n⚠️ Errores: {', '.join(results['errors'])}"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cmd_polar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        from bot.integrations.polar import get_auth_url, get_polar_token

        token = await get_polar_token(user_id)
        if token:
            await update.message.reply_text(
                "✅ Polar ya está conectado.\n"
                "Usá /sync_polar para sincronizar entrenamientos."
            )
            return

        auth_url = get_auth_url(user_id)
        await update.message.reply_text(
            f"🔗 Conectar Polar Flow\n\n"
            f"1. Abrí este enlace en tu navegador:\n{auth_url}\n\n"
            f"2. Autorizá el acceso\n"
            f"3. Copiá el código de la URL de callback\n"
            f"4. Enviame el código con: /polar_code TU_CODIGO"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cmd_polar_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text(
                "Enviame el código así:\n`/polar_code TU_CODIGO`",
                parse_mode="Markdown"
            )
            return

        code = context.args[0]
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        await update.message.reply_text("⏳ Conectando con Polar...")

        from bot.integrations.polar import exchange_code_for_token, save_polar_token, register_user_polar

        token_data = await exchange_code_for_token(code)

        if "access_token" not in token_data:
            await update.message.reply_text(f"❌ Error obteniendo token: {token_data}")
            return

        await save_polar_token(user_id, token_data)
        polar_user_id = str(token_data.get("x_user_id", user_id))
        await register_user_polar(token_data["access_token"], polar_user_id)

        await update.message.reply_text(
            "✅ Polar conectado exitosamente\n\n"
            "Ahora podés usar /sync_polar para sincronizar tus entrenamientos."
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cmd_sync_polar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Sincronizando con Polar... ⏳")

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        from bot.integrations.polar import sync_polar_workouts, sync_polar_activity

        workouts = await sync_polar_workouts(user_id)
        activity = await sync_polar_activity(user_id)

        msg = "✅ Sincronización Polar completada\n\n"

        if workouts:
            msg += f"🏋 Entrenamientos nuevos: {len(workouts)}\n"
            for w in workouts:
                msg += f"- {w.get('activity_type')}: {w.get('duration_min')} min"
                if w.get('calories_burned'):
                    msg += f" — {w.get('calories_burned')} kcal"
                if w.get('avg_heart_rate'):
                    msg += f" — FC: {w.get('avg_heart_rate')} bpm"
                msg += "\n"
        else:
            msg += "🏋 Sin entrenamientos nuevos\n"

        if activity:
            msg += "\n📊 Actividad del día:\n"
            if activity.get('calories'):
                msg += f"- Calorías totales: {activity.get('calories')} kcal\n"
            if activity.get('active_calories'):
                msg += f"- Calorías activas: {activity.get('active_calories')} kcal\n"
            if activity.get('steps'):
                msg += f"- Pasos: {activity.get('steps')}\n"
            if activity.get('activity_goal_pct'):
                msg += f"- Objetivo actividad: {activity.get('activity_goal_pct')}%\n"
        else:
            msg += "\n📊 Sin datos de actividad nuevos hoy\n"

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
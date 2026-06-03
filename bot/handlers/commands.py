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

        await update.message.reply_text(msg)

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

        await update.message.reply_text(msg)

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

        await update.message.reply_text(msg)
        return True

    except Exception as e:
        context.user_data["waiting_for_measurement"] = False
        await update.message.reply_text(f"❌ Error al guardar: {str(e)}")
        return True
async def analyze_weight_change(user_id: str, diff: float, current_weight: float) -> str:
    from datetime import datetime, timedelta
    import pytz

    bogota_tz = pytz.timezone("America/Bogota")
    today = datetime.now(bogota_tz).strftime("%Y-%m-%d")
    three_days_ago = (datetime.now(bogota_tz) - timedelta(days=3)).strftime("%Y-%m-%d")

    # Calorías promedio últimos 3 días
    meals = supabase.table("meals")\
        .select("calories, logged_at")\
        .eq("user_id", user_id)\
        .gte("logged_at", three_days_ago)\
        .execute()

    # Entrenamientos últimos 3 días
    workouts = supabase.table("workouts")\
        .select("calories_burned, workout_date")\
        .eq("user_id", user_id)\
        .gte("workout_date", three_days_ago)\
        .execute()

    total_calories = sum(m.get("calories") or 0 for m in meals.data)
    total_burned = sum(w.get("calories_burned") or 0 for w in workouts.data)
    avg_daily_calories = total_calories / 3 if meals.data else 0
    avg_daily_burned = total_burned / 3 if workouts.data else 0
    net_avg = avg_daily_calories - avg_daily_burned

    # Lógica de análisis sin tokens
    if diff > 0:
        if diff <= 0.5:
            return "Subida menor a 0.5kg — variación normal por agua, sal o digestión. No es grasa real."
        elif diff > 0.5 and net_avg > 2200:
            return f"Subiste {diff}kg. Promedio de {avg_daily_calories:.0f} kcal/día los últimos 3 días con {avg_daily_burned:.0f} kcal quemadas. El exceso calórico explica la subida. Bajá las porciones de carbohidratos."
        elif diff > 0.5 and net_avg <= 2200:
            return f"Subiste {diff}kg pero estuviste en déficit calórico ({net_avg:.0f} kcal netas/día). Probable retención de agua — puede ser por sodio alto, poco sueño o estrés. No es grasa."
        else:
            return f"Subiste {diff}kg. Revisá el sodio de lo que comiste ayer — embutidos, enlatados y salsas retienen agua."
    elif diff < 0:
        if abs(diff) <= 0.5:
            return f"Bajaste {abs(diff)}kg — buen progreso. Seguí así."
        else:
            return f"Bajaste {abs(diff)}kg en un día — excelente. Vas camino a los 85kg."
    return ""


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Sincronizando con Garmin Connect... ⏳")

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        from bot.integrations.garmin import sync_all
        results = await sync_all(user_id)

        msg = "✅ Sincronización Garmin completada\n\n"

        if results["weight"]:
            w = results["weight"]
            current_weight = w.get("weight_kg")
            previous_weight = w.get("previous_weight")

            msg += "⚖️ Peso registrado:\n"
            msg += f"- Peso: {current_weight} kg\n"
            if w.get("body_fat_pct"):
                msg += f"- % Grasa: {w.get('body_fat_pct')}%\n"
            if w.get("muscle_mass_kg"):
                msg += f"- Masa muscular: {w.get('muscle_mass_kg')} kg\n"

            # Análisis de cambio de peso
            if previous_weight and current_weight:
                diff = round(current_weight - previous_weight, 2)
                if diff != 0:
                    msg += f"\n{'📈' if diff > 0 else '📉'} Cambio vs ayer: {diff:+.2f} kg\n"
                    analysis = await analyze_weight_change(user_id, diff, current_weight)
                    if analysis:
                        msg += f"\n{analysis}"
        else:
            msg += "⚖️ Sin datos de peso para hoy\n"

        if results["workouts"]:
            msg += f"\n🏋 Entrenamientos descargados: {len(results['workouts'])}\n"
            for w in results["workouts"]:
                msg += f"- {w.get('activity_type')}: {w.get('duration_min')} min"
                if w.get("calories_burned"):
                    msg += f" — {w.get('calories_burned')} kcal"
                msg += "\n"
        else:
            msg += "\n🏋 Sin entrenamientos nuevos\n"

        if results["errors"]:
            msg += f"\n⚠️ Errores: {', '.join(results['errors'])}"

        await update.message.reply_text(msg)

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

async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        today = get_today_bogota()

        # Obtener la última comida del día
        result = supabase.table("meals")\
            .select("id, description, calories, protein_g, meal_type, logged_at")\
            .eq("user_id", user_id)\
            .gte("logged_at", today + "T00:00:00-05:00")\
            .lte("logged_at", today + "T23:59:59-05:00")\
            .order("logged_at", desc=True)\
            .limit(1)\
            .execute()

        if not result.data:
            await update.message.reply_text("No encontré comidas registradas hoy para borrar.")
            return

        meal = result.data[0]
        context.user_data["pending_delete_id"] = meal["id"]

        await update.message.reply_text(
            f"La última comida registrada es:\n\n"
            f"- {meal.get('description', 'sin descripción')}\n"
            f"- {meal.get('calories')} kcal\n"
            f"- {meal.get('protein_g')}g proteína\n\n"
            f"¿Confirmás que querés borrarla? Respondé SI para confirmar."
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def cmd_mialimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        from bot.agents.nutrition_scanner import get_all_products
        products = await get_all_products(user_id)

        if not products:
            await update.message.reply_text(
                "No tenés productos guardados todavía.\n"
                "Enviame una foto de la tabla nutricional de cualquier producto para agregarlo."
            )
            return

        msg = f"📦 Tu base de alimentos ({len(products)} productos)\n\n"
        for p in products:
            msg += f"- {p.get('product_name')}"
            if p.get('brand'):
                msg += f" ({p.get('brand')})"
            msg += f": {p.get('calories_per_serving')} kcal | {p.get('protein_g')}g proteína"
            if p.get('serving_description'):
                msg += f" por {p.get('serving_description')}"
            msg += "\n"

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def cmd_tabla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        today = get_today_bogota()

        meals = supabase.table("meals")\
            .select("description, calories, protein_g, carbs_g, fat_g, meal_type, logged_at")\
            .eq("user_id", user_id)\
            .gte("logged_at", today + "T00:00:00-05:00")\
            .lte("logged_at", today + "T23:59:59-05:00")\
            .order("logged_at", desc=False)\
            .execute()

        if not meals.data:
            await update.message.reply_text("No registraste comidas hoy todavía.")
            return

        from bot.db.meals import MEAL_TYPE_LABELS
        msg = f"🗒 Comidas de hoy — {today}\n\n"

        total_cal = 0
        total_prot = 0
        total_carbs = 0
        total_fat = 0

        for m in meals.data:
            label = MEAL_TYPE_LABELS.get(m.get("meal_type", ""), m.get("meal_type", ""))
            hora = m.get("logged_at", "")[11:16]
            desc = m.get("description", "sin descripción")
            cal = m.get("calories") or 0
            prot = float(m.get("protein_g") or 0)
            carbs = float(m.get("carbs_g") or 0)
            fat = float(m.get("fat_g") or 0)

            msg += f"{label} ({hora})\n"
            msg += f"  {desc}\n"
            msg += f"  🔥 {cal} kcal | 💪 {prot:.1f}g prot | 🍚 {carbs:.1f}g carbs | 🥑 {fat:.1f}g grasas\n\n"

            total_cal += cal
            total_prot += prot
            total_carbs += carbs
            total_fat += fat

        msg += f"─────────────────\n"
        msg += f"TOTAL: 🔥 {total_cal} kcal | 💪 {total_prot:.1f}g | 🍚 {total_carbs:.1f}g | 🥑 {total_fat:.1f}g"

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
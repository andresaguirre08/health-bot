from telegram import Update
from telegram.ext import ContextTypes
from bot.agents.nutritionist import analyze_food_photo
from bot.agents.nutrition_scanner import scan_nutrition_label, save_to_food_database
from bot.db.meals import (
    get_or_create_user,
    save_meal,
    get_today_totals,
    get_meal_type_by_hour,
    check_unusual_calories,
    MEAL_TYPE_LABELS
)
from bot.utils.context_builder import build_user_context


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Analizando imagen... ⏳")

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        # Caption del mensaje tiene prioridad como nombre del producto
        caption = update.message.caption or None

        # Detectar si es tabla nutricional
        scan_result = await scan_nutrition_label(bytes(image_bytes))

        if scan_result.get("is_nutrition_label"):
            save_result = await save_to_food_database(user_id, scan_result, caption)
            action = save_result["action"]
            product = save_result["product"]

            msg = (
                f"{'✅ Producto guardado' if action == 'created' else '🔄 Producto actualizado'} en tu base de datos\n\n"
                f"📦 {product}"
            )
            if scan_result.get("brand"):
                msg += f" — {scan_result.get('brand')}"
            msg += "\n\n"
            msg += f"Por porción ({scan_result.get('serving_description', '')}):\n"
            msg += f"🔥 Calorías: {scan_result.get('calories_per_serving')} kcal\n"
            msg += f"💪 Proteína: {scan_result.get('protein_g')}g\n"
            msg += f"🍚 Carbohidratos: {scan_result.get('carbs_g')}g\n"
            msg += f"🥑 Grasas: {scan_result.get('fat_g')}g\n"
            if scan_result.get("fiber_g"):
                msg += f"🌾 Fibra: {scan_result.get('fiber_g')}g\n"
            if scan_result.get("sodium_mg"):
                msg += f"🧂 Sodio: {scan_result.get('sodium_mg')}mg\n"
            msg += f"\nAhora cuando me digas que comiste {product} voy a usar estos datos exactos."

            await update.message.reply_text(msg)
            return

        # Es una foto de comida — analizar macros
        meal_type = get_meal_type_by_hour()
        label = MEAL_TYPE_LABELS.get(meal_type, meal_type)
        await update.message.reply_text(f"📷 Analizando tu {label}... ⏳")

        user_context = await build_user_context(user_id)
        totals = await get_today_totals(user_id)

        # Si hay caption, usarlo como descripción adicional para el análisis
        extra_context = f"El usuario dice que esto es: {caption}" if caption else ""

        result = analyze_food_photo(
            image_bytes=bytes(image_bytes),
            mime_type="image/jpeg",
            user_context=user_context + extra_context,
            calories_eaten=totals["calories"],
            protein_eaten=totals["protein"]
        )

        await save_meal(
            user_id=user_id,
            calories=result["calories"],
            protein=result["protein"],
            carbs=result["carbs"],
            fat=result["fat"],
            description=caption or f"foto - {label}",
            raw_response=result["response_text"]
        )

        await update.message.reply_text(
            result["response_text"],
            parse_mode="Markdown"
        )

        alert = check_unusual_calories(meal_type, int(result["calories"]))
        if alert:
            await update.message.reply_text(alert)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
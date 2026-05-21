from telegram import Update
from telegram.ext import ContextTypes
from bot.agents.nutritionist import analyze_food_photo
from bot.db.meals import get_or_create_user, save_meal, get_today_totals
from bot.utils.context_builder import build_user_context


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Analizando tu comida... ⏳")

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name
        user_id = await get_or_create_user(telegram_id, name)

        # Construir contexto completo con historial
        user_context = await build_user_context(user_id)
        totals = await get_today_totals(user_id)

        # Descargar foto
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        # Analizar con Claude + contexto acumulado
        result = analyze_food_photo(
            image_bytes=bytes(image_bytes),
            mime_type="image/jpeg",
            user_context=user_context,
            calories_eaten=totals["calories"],
            protein_eaten=totals["protein"]
        )

        # Guardar en DB
        await save_meal(
            user_id=user_id,
            calories=result["calories"],
            protein=result["protein"],
            carbs=result["carbs"],
            fat=result["fat"],
            description="foto",
            raw_response=result["response_text"]
        )

        await update.message.reply_text(
            result["response_text"],
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
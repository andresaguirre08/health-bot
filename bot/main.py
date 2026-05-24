import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from bot.utils.config import TELEGRAM_TOKEN
from bot.handlers.food import handle_photo
from bot.handlers.commands import (
    cmd_hoy,
    cmd_progreso,
    cmd_peso,
    cmd_sync,
    cmd_polar,
    cmd_polar_code,
    cmd_sync_polar,
    handle_measurement
)

from bot.handlers.commands import (
    cmd_hoy,
    cmd_progreso,
    cmd_peso,
    cmd_sync,
    cmd_polar,
    cmd_polar_code,
    cmd_sync_polar,
    cmd_borrar,
    handle_measurement
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hola {user.first_name} 💪\n\n"
        f"Soy tu agente personal de nutrición y entrenamiento.\n\n"
        f"Podés:\n"
        f"📷 Enviarme una foto de tu comida\n"
        f"🎙 Mandarme un audio con lo que comiste\n"
        f"💬 Describir tu comida por texto\n"
        f"❓ Preguntarme cualquier cosa sobre tu dieta o entreno\n\n"
        f"Comandos:\n"
        f"  /hoy — resumen del día\n"
        f"  /progreso — composición corporal\n"
        f"  /peso — registrar peso y medidas\n"
        f"  /sync — sincronizar Garmin\n"
        f"  /sync_polar — sincronizar Polar\n\n"
        f"Arrancamos 🚀"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handled = await handle_measurement(update, context)
    if handled:
        return

    # Confirmar borrado de comida
    if context.user_data.get("pending_delete_id"):
        if update.message.text.upper().strip() == "SI":
            try:
                from bot.db.client import supabase
                meal_id = context.user_data["pending_delete_id"]
                supabase.table("meals").delete().eq("id", meal_id).execute()
                context.user_data["pending_delete_id"] = None
                await update.message.reply_text("✅ Comida borrada. Podés registrarla de nuevo.")
            except Exception as e:
                await update.message.reply_text(f"❌ Error borrando: {str(e)}")
        else:
            context.user_data["pending_delete_id"] = None
            await update.message.reply_text("Ok, no borré nada.")
        return

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name

        from bot.db.meals import get_or_create_user, save_meal, get_meal_type_by_hour, MEAL_TYPE_LABELS
        from bot.utils.context_builder import build_user_context
        from bot.agents.coach import process_message

        user_id = await get_or_create_user(telegram_id, name)
        user_context = await build_user_context(user_id)

        result = await process_message(update.message.text, user_context, user_id)

        if result["type"] == "food" and result["meal_data"]:
            meal = result["meal_data"]
            meal_type = get_meal_type_by_hour()
            label = MEAL_TYPE_LABELS.get(meal_type, meal_type)

            await save_meal(
                user_id=user_id,
                calories=meal.get("calories", 0),
                protein=meal.get("protein_g", 0),
                carbs=meal.get("carbs_g", 0),
                fat=meal.get("fat_g", 0),
                description=meal.get("description", ""),
                raw_response=meal.get("description", "")
            )

            await update.message.reply_text(
                f"✅ {label} guardado\n\n"
                f"🔥 Calorías: {meal.get('calories')} kcal\n"
                f"💪 Proteína: {meal.get('protein_g')}g\n"
                f"🍚 Carbohidratos: {meal.get('carbs_g')}g\n"
                f"🥑 Grasas: {meal.get('fat_g')}g"
            )
        else:
            await update.message.reply_text(result["text"])

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙 Escuchando... ⏳")

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name

        from bot.db.meals import get_or_create_user, save_meal, get_meal_type_by_hour, MEAL_TYPE_LABELS
        from bot.utils.context_builder import build_user_context
        from bot.agents.coach import process_message
        from groq import Groq

        user_id = await get_or_create_user(telegram_id, name)
        user_context = await build_user_context(user_id)

        file = await update.message.voice.get_file()
        audio_bytes = await file.download_as_bytearray()

        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        transcription = groq_client.audio.transcriptions.create(
            file=("audio.ogg", bytes(audio_bytes)),
            model="whisper-large-v3",
            language="es"
        )

        audio_text = transcription.text
        result = await process_message(audio_text, user_context, user_id)

        if result["type"] == "food" and result["meal_data"]:
            meal = result["meal_data"]
            meal_type = get_meal_type_by_hour()
            label = MEAL_TYPE_LABELS.get(meal_type, meal_type)

            await save_meal(
                user_id=user_id,
                calories=meal.get("calories", 0),
                protein=meal.get("protein_g", 0),
                carbs=meal.get("carbs_g", 0),
                fat=meal.get("fat_g", 0),
                description=meal.get("description", ""),
                raw_response=meal.get("description", "")
            )

            await update.message.reply_text(
                f"🎙 Escuché: {audio_text}\n\n"
                f"✅ {label} guardado\n\n"
                f"🔥 Calorías: {meal.get('calories')} kcal\n"
                f"💪 Proteína: {meal.get('protein_g')}g\n"
                f"🍚 Carbohidratos: {meal.get('carbs_g')}g\n"
                f"🥑 Grasas: {meal.get('fat_g')}g"
            )
        else:
            await update.message.reply_text(
                f"🎙 Escuché: {audio_text}\n\n{result['text']}"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def post_init(app):
    from bot.scheduler.jobs import start_scheduler
    start_scheduler(app)
    logger.info("Scheduler iniciado con zona horaria America/Bogota")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hoy", cmd_hoy))
    app.add_handler(CommandHandler("progreso", cmd_progreso))
    app.add_handler(CommandHandler("peso", cmd_peso))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler("polar", cmd_polar))
    app.add_handler(CommandHandler("polar_code", cmd_polar_code))
    app.add_handler(CommandHandler("sync_polar", cmd_sync_polar))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler("borrar", cmd_borrar))

    logger.info("Bot iniciado...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
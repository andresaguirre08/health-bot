import logging
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
        f"📷 Enviarme una foto de tu comida para calcular macros\n"
        f"🎙 Mandarme un audio con lo que comiste\n"
        f"💬 Preguntarme cualquier cosa sobre tu dieta o entreno\n"
        f"⌨️ Comandos disponibles:\n"
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

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name

        from bot.db.meals import get_or_create_user
        from bot.utils.context_builder import build_user_context
        from bot.agents.coach import chat_with_coach

        user_id = await get_or_create_user(telegram_id, name)
        user_context = await build_user_context(user_id)

        response = await chat_with_coach(update.message.text, user_context)
        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙 Escuchando... ⏳")

    try:
        telegram_id = update.effective_user.id
        name = update.effective_user.first_name

        from bot.db.meals import get_or_create_user
        from bot.utils.context_builder import build_user_context
        from bot.agents.coach import chat_with_coach

        user_id = await get_or_create_user(telegram_id, name)
        user_context = await build_user_context(user_id)

        file = await update.message.voice.get_file()
        audio_bytes = await file.download_as_bytearray()

        import base64
        import anthropic
        from bot.utils.config import ANTHROPIC_API_KEY

        audio_b64 = base64.standard_b64encode(bytes(audio_bytes)).decode("utf-8")
        claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        transcription = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribí exactamente lo que dice este audio. Solo devolvé el texto transcripto, sin comentarios."
                    },
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "audio/ogg",
                            "data": audio_b64
                        }
                    }
                ]
            }]
        )

        audio_text = transcription.content[0].text
        response = await chat_with_coach(audio_text, user_context)

        await update.message.reply_text(
            f"🎙 Escuché:_{audio_text}_\n\n{response}",
            parse_mode="Markdown"
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

    logger.info("Bot iniciado...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
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
        f"⌨️ Comandos disponibles:\n"
        f"  /hoy — resumen del día\n"
        f"  /progreso — composición corporal\n"
        f"  /peso — registrar peso y medidas\n"
        f"  /suplementos — estado de suplementos\n\n"
        f"Arrancamos 🚀"
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎙 Audio recibido. Procesando...\n"
        "(Módulo de audio en construcción)"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Primero verificar si está esperando una medición
    handled = await handle_measurement(update, context)
    if handled:
        return

    text = update.message.text
    await update.message.reply_text(
        f"Recibí tu mensaje: '{text}'\n"
        f"(Módulo de respuesta en construcción)"
    )


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
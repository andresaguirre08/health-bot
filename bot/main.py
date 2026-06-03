import logging
import os
import re
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
    cmd_borrar,
    cmd_mialimentos,
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
        f"📷 Enviarme una foto de tu comida o tabla nutricional\n"
        f"🎙 Mandarme un audio con lo que comiste\n"
        f"💬 Describir tu comida por texto\n"
        f"❓ Preguntarme cualquier cosa sobre tu dieta o entreno\n\n"
        f"Comandos:\n"
        f"  /hoy — resumen del día\n"
        f"  /progreso — composición corporal\n"
        f"  /peso — registrar peso y medidas\n"
        f"  /sync — sincronizar Garmin\n"
        f"  /sync_polar — sincronizar Polar\n"
        f"  /borrar — borrar última comida\n"
        f"  /mialimentos — ver base de alimentos\n\n"
        f"Arrancamos 🚀"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handled = await handle_measurement(update, context)
    if handled:
        return

    # Confirmación y corrección de tabla nutricional desde Supabase
    telegram_id_check = update.effective_user.id
    from bot.db.client import supabase as supa
    pending_scan = supa.table("pending_scans")\
        .select("*")\
        .eq("telegram_id", telegram_id_check)\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()

    if pending_scan.data:
        from bot.agents.nutrition_scanner import save_to_food_database
        pending = pending_scan.data[0]
        scan_result = pending["scan_result"]
        product_name = pending["product_name"]
        user_id = pending["user_id"]
        pending_id = pending["id"]
        user_input = update.message.text.strip()
        user_input_lower = user_input.lower()

        if user_input_lower == "si":
            supa.table("pending_scans").delete().eq("id", pending_id).execute()
            save_result = await save_to_food_database(user_id, scan_result, product_name)
            action = save_result["action"]
            product = save_result["product"]
            final_brand = save_result.get("brand")

            msg = f"{'✅ Producto guardado' if action == 'created' else '🔄 Producto actualizado'} en tu base de datos\n\n"
            msg += f"📦 Producto: {product}\n"
            if final_brand:
                msg += f"🏷 Marca: {final_brand}\n"
            msg += f"\nCuando me digas que comiste {product} voy a usar estos datos exactos."
            await update.message.reply_text(msg)
            return

        corrections = {
            "proteina": "protein_g",
            "proteína": "protein_g",
            "calorias": "calories_per_serving",
            "calorías": "calories_per_serving",
            "carbohidratos": "carbs_g",
            "grasas": "fat_g",
            "fibra": "fiber_g",
            "sodio": "sodium_mg"
        }

        corrected = False
        parts = user_input.split("/")
        for part in parts:
            part = part.strip()
            part_lower = part.lower()
            for keyword, field in corrections.items():
                if keyword in part_lower:
                    match = re.search(r'(\d+(?:\.\d+)?)', part)
                    if match:
                        scan_result[field] = float(match.group(1))
                        corrected = True
                        break

        if corrected:
            import json
            supa.table("pending_scans")\
                .update({"scan_result": json.loads(json.dumps(scan_result))})\
                .eq("id", pending_id)\
                .execute()
            msg = (
                f"✏️ Datos corregidos:\n\n"
                f"🔥 Calorías: {scan_result.get('calories_per_serving')} kcal\n"
                f"💪 Proteína: {scan_result.get('protein_g')}g\n"
                f"🍚 Carbohidratos: {scan_result.get('carbs_g')}g\n"
                f"🥑 Grasas: {scan_result.get('fat_g')}g\n\n"
                f"¿Ahora están correctos? Respondé SI para guardar o seguí corrigiendo."
            )
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(
                "No entendí la corrección. Usá el formato:\n"
                "proteina 11 / calorias 139 / carbohidratos 9 / grasas 5\n\n"
                "O respondé SI para guardar los datos actuales."
            )
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

            source = meal.get("source", "ai")
            if source == "database":
                source_msg = f"📦 Datos de tu base: {meal.get('db_product')}"
            elif source == "mixed":
                source_msg = f"{meal.get('db_product')}"
            else:
                source_msg = "🤖 Estimado por IA"

            await update.message.reply_text(
                f"✅ {label} guardado\n\n"
                f"🔥 Calorías: {meal.get('calories')} kcal\n"
                f"💪 Proteína: {meal.get('protein_g')}g\n"
                f"🍚 Carbohidratos: {meal.get('carbs_g')}g\n"
                f"🥑 Grasas: {meal.get('fat_g')}g\n\n"
                f"{source_msg}"
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

            source = meal.get("source", "ai")
            if source == "database":
                source_msg = f"📦 Datos de tu base: {meal.get('db_product')}"
            elif source == "mixed":
                source_msg = f"{meal.get('db_product')}"
            else:
                source_msg = "🤖 Estimado por IA"

            await update.message.reply_text(
                f"🎙 Escuché: {audio_text}\n\n"
                f"✅ {label} guardado\n\n"
                f"🔥 Calorías: {meal.get('calories')} kcal\n"
                f"💪 Proteína: {meal.get('protein_g')}g\n"
                f"🍚 Carbohidratos: {meal.get('carbs_g')}g\n"
                f"🥑 Grasas: {meal.get('fat_g')}g\n\n"
                f"{source_msg}"
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
    app.add_handler(CommandHandler("borrar", cmd_borrar))
    app.add_handler(CommandHandler("mialimentos", cmd_mialimentos))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot iniciado...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
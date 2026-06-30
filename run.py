import sys
import logging
from bot.main import main
from bot.utils.config_validator import validate_config

# Configurar logging básico
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("🤖 Iniciando Health Bot...")
    
    # Validar configuración antes de iniciar
    is_valid, errors = validate_config()
    
    if not is_valid:
        logger.error("❌ Configuración inválida - No se puede iniciar el bot")
        sys.exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⛔ Bot detenido por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}", exc_info=True)
        sys.exit(1)
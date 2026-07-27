import asyncio
import logging
from google import genai
from google.genai import types
from bot.utils.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)

FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-pro-latest",
]


async def safe_generate_content(contents, config=None):
    """
    Ejecuta llamadas a la API de Gemini de forma segura, con reintentos y
    fallback a modelos alternativos en caso de errores 503 (alta demanda),
    429 (límite de peticiones) o 404 (modelo no disponible).
    """
    last_exception = None

    for model_name in FALLBACK_MODELS:
        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                if response and response.text:
                    return response
            except Exception as e:
                last_exception = e
                err_text = str(e)
                if "503" in err_text or "429" in err_text or "high demand" in err_text.lower() or "UNAVAILABLE" in err_text:
                    logger.warning(
                        f"Límite/Demanda en modelo '{model_name}' (intento {attempt + 1}). Reintentando en 1s..."
                    )
                    await asyncio.sleep(1)
                elif "404" in err_text or "NOT_FOUND" in err_text:
                    logger.warning(
                        f"Modelo '{model_name}' retornó 404, probando modelo de respaldo..."
                    )
                    break
                else:
                    logger.error(f"Error con modelo {model_name}: {e}")
                    break

    if last_exception:
        raise last_exception
    return None

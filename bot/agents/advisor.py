from google.genai import types
import logging
from bot.utils.ai_helper import safe_generate_content
from bot.utils.json_extract import extract_json

logger = logging.getLogger(__name__)

ADVISOR_PROMPT = """Sos la nutricionista personal de Andrés. Te paso su contexto completo:
perfil, objetivos diarios actuales, composición corporal y su tendencia, promedios de
alimentación de los últimos 7 días y sus entrenamientos de la semana.

Tu trabajo es analizar ese historial como lo haría una nutricionista real en una consulta de
seguimiento, y decidir si conviene ajustar sus objetivos diarios (calorías, proteína,
carbohidratos, grasas) o si están bien como están.

Pensá en cosas como:
- ¿El déficit calórico es demasiado agresivo o demasiado suave para su objetivo?
- ¿Está cumpliendo la proteína de forma consistente o crónicamente baja?
- ¿Hay estancamiento o cambios raros en la tendencia de peso/grasa corporal?
- ¿El volumen de entrenamiento sugiere que necesita más o menos energía?

Si con los datos disponibles no hay suficiente historial para opinar con confianza, decilo
honestamente en el mensaje y no cambies nada (changed: false).

Respondé SOLO con JSON válido, sin texto extra, sin markdown, sin backticks, en este formato
exacto:
{
  "changed": true,
  "calories": 2000,
  "protein_g": 180,
  "carbs_g": 150,
  "fat_g": 60,
  "message": "explicación cálida y concreta en español de qué cambia y por qué (o de por qué está bien dejarlo como está)"
}

Si "changed" es false, "calories"/"protein_g"/"carbs_g"/"fat_g" tienen que ser los mismos valores
que ya tenía (los objetivos actuales del contexto), no valores nuevos.

El "message" tiene que sonar como una nutricionista hablándole directamente a Andrés, con
calidez y cercanía, no como un reporte técnico. Máximo 6 líneas."""


async def recommend_diet_adjustment(user_context: str) -> dict | None:
    response = await safe_generate_content(
        contents=user_context,
        config=types.GenerateContentConfig(
            system_instruction=ADVISOR_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=8192,
        )
    )

    raw_text = response.text if (response and response.text) else ""
    parsed = extract_json(raw_text)

    if not parsed:
        logger.warning(f"recommend_diet_adjustment: JSON inválido de Gemini: {raw_text[:200]!r}")
        return None

    return parsed

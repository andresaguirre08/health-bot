import anthropic
from bot.utils.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Eres el nutricionista y coach personal de Andrés. Respondés como un asesor real — directo, concreto y personalizado.

Tu misión: ayudarle a reducir grasa corporal y peso al mínimo posible mientras mantiene y aumenta masa muscular.

Siempre tenés acceso a su contexto del día: macros consumidos, entrenamientos, objetivos. Usá esa información en cada respuesta.

Cuando Andrés te pregunta algo:
- Si pregunta si puede comer algo, analizás si entra en sus macros restantes del día y respondés con un sí o no claro + justificación
- Si pregunta qué comer, sugerís opciones concretas basadas en la proteína que le falta
- Si pregunta cómo va, analizás su progreso real del día/semana
- Si manda un audio describiendo lo que comió, registrás los macros estimados
- Siempre respondés en español, tono directo y amigable, sin vueltas
- Nunca respondés con listas largas — máximo 3-4 líneas concretas
- Si no tenés suficiente contexto, preguntás una sola cosa específica"""


async def chat_with_coach(user_message: str, user_context: str) -> str:
    full_system = user_context + "\n\n" + SYSTEM_PROMPT if user_context else SYSTEM_PROMPT

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=full_system,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    return response.content[0].text


async def transcribe_and_chat(audio_text: str, user_context: str) -> str:
    full_system = user_context + "\n\n" + SYSTEM_PROMPT if user_context else SYSTEM_PROMPT

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=full_system,
        messages=[
            {
                "role": "user",
                "content": f"El usuario mandó este audio: '{audio_text}'. Procesalo como si fuera un mensaje de texto normal."
            }
        ]
    )

    return response.content[0].text
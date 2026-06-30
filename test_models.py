#!/usr/bin/env python3
"""Test para verificar qué modelos de Claude están disponibles."""

import anthropic
from bot.utils.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Modelos a probar (en orden de preferencia)
models_to_test = [
    "claude-opus-4-1-20250805",
    "claude-opus-4-1",
    "claude-4-opus-20250805",
    "claude-opus",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4",
    "claude-3-5-sonnet-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
]

print("🔍 Probando modelos disponibles...\n")

for model in models_to_test:
    try:
        print(f"⏳ Probando: {model}")
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )
        print(f"✅ ¡FUNCIONA! Modelo disponible: {model}\n")
        break
    except anthropic.NotFoundError as e:
        print(f"❌ No disponible\n")
    except anthropic.AuthenticationError as e:
        print(f"🔐 Error de autenticación: {e}\n")
        break
    except Exception as e:
        print(f"⚠️ Error: {str(e)[:60]}\n")

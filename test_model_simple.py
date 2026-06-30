#!/usr/bin/env python3
"""Test directo de la API sin dependencias externas."""

import anthropic
from bot.utils.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

print("🧪 Testing claude-opus-4-1-20250805\n")

try:
    print("1️⃣ Enviar mensaje de prueba...")
    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=50,
        messages=[{"role": "user", "content": "Hola! ¿Cómo estás?"}]
    )
    
    print(f"✅ ¡ÉXITO! Modelo funcionando correctamente\n")
    print(f"Respuesta: {response.content[0].text[:100]}")
    
except anthropic.NotFoundError as e:
    print(f"❌ Modelo no encontrado: {e}")
except anthropic.AuthenticationError as e:
    print(f"🔐 Error de autenticación: {e}")
except Exception as e:
    print(f"⚠️ Error: {e}")

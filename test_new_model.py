#!/usr/bin/env python3
"""Test rápido para verificar que el nuevo modelo funciona."""

import asyncio
from bot.agents.coach import classify_message, extract_meal_from_text, coach_response

async def test_api():
    print("🧪 Testing nuevo modelo claude-opus-4-1-20250805\n")
    
    # Test 1: Clasificación
    print("1️⃣ Test clasificación:")
    try:
        result = await classify_message("Comí 250g de pollo con arroz")
        print(f"   ✅ Resultado: {result}\n")
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:80]}\n")
    
    # Test 2: Coach response
    print("2️⃣ Test coach response:")
    try:
        result = await coach_response("Hola, ¿cómo me veo hoy?", "")
        print(f"   ✅ Resultado: {result[:100]}...\n")
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:80]}\n")
    
    print("✨ Tests completados")

if __name__ == "__main__":
    asyncio.run(test_api())

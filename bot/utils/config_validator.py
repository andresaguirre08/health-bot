"""
Validador de configuración y variables de entorno.
Asegura que todas las variables necesarias estén presentes.
"""

import os
import sys
from typing import List, Tuple
from bot.utils.config import (
    TELEGRAM_TOKEN,
    ANTHROPIC_API_KEY,
    SUPABASE_URL,
    SUPABASE_KEY,
    GARMIN_EMAIL,
    GARMIN_PASSWORD,
    POLAR_CLIENT_ID,
    POLAR_CLIENT_SECRET,
    GROQ_API_KEY,
)

def validate_config() -> Tuple[bool, List[str]]:
    """
    Valida que todas las variables de entorno críticas estén configuradas.
    
    Returns:
        Tuple[bool, List[str]]: (es_válido, lista_de_errores)
    """
    errors = []
    warnings = []
    
    # Variables críticas (sin estas no funciona el bot)
    critical_vars = {
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "GROQ_API_KEY": GROQ_API_KEY,
    }
    
    # Variables opcionales (funcionan sin estas pero con funcionalidad limitada)
    optional_vars = {
        "GARMIN_EMAIL": GARMIN_EMAIL,
        "GARMIN_PASSWORD": GARMIN_PASSWORD,
        "POLAR_CLIENT_ID": POLAR_CLIENT_ID,
        "POLAR_CLIENT_SECRET": POLAR_CLIENT_SECRET,
    }
    
    # Validar variables críticas
    print("🔍 Validando configuración crítica...")
    for var_name, var_value in critical_vars.items():
        if not var_value:
            errors.append(f"❌ CRÍTICO: {var_name} no configurada")
        else:
            print(f"   ✅ {var_name}")
    
    # Validar variables opcionales
    print("\n🔍 Validando integraciones opcionales...")
    for var_name, var_value in optional_vars.items():
        if not var_value:
            warnings.append(f"⚠️  OPCIONAL: {var_name} no configurada (funcionalidad limitada)")
        else:
            print(f"   ✅ {var_name}")
    
    # Imprimir resumen
    print("\n" + "="*50)
    
    if errors:
        print("❌ ERRORES CRÍTICOS ENCONTRADOS:")
        for error in errors:
            print(f"   {error}")
        print("\nConfigura estas variables en el archivo .env")
        print("Usa .env.example como referencia")
        return False, errors
    
    if warnings:
        print("⚠️  ADVERTENCIAS (funcionalidad limitada):")
        for warning in warnings:
            print(f"   {warning}")
    
    if not errors:
        print("✅ Configuración válida - Bot listo para iniciar")
    
    print("="*50 + "\n")
    
    return len(errors) == 0, errors


if __name__ == "__main__":
    is_valid, errors = validate_config()
    sys.exit(0 if is_valid else 1)

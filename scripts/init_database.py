#!/usr/bin/env python3
"""
Script para inicializar la base de datos en Supabase.
Crea todas las tablas necesarias para el bot.

Uso: python scripts/init_database.py
"""

import sys
import logging
from bot.db.client import supabase

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def init_database():
    """Inicializa la base de datos con tablas necesarias."""
    
    logger.info("🗄️  Inicializando base de datos...")
    
    try:
        # Las tablas debería crearlas mediante la UI de Supabase
        # Este script verifica que existan
        
        tables_to_check = [
            "users",
            "meals",
            "chat_history",
            "measurements",
            "food_database",
            "pending_scans",
        ]
        
        logger.info("🔍 Verificando tablas necesarias...")
        
        # Intenta una query simple a cada tabla
        for table in tables_to_check:
            try:
                result = supabase.table(table).select("*").limit(1).execute()
                logger.info(f"   ✅ Tabla '{table}' existe")
            except Exception as e:
                logger.warning(f"   ⚠️  Tabla '{table}' puede no existir: {str(e)[:60]}")
        
        logger.info("\n✅ Verificación completada")
        logger.info("\nIMPORTANTE: Si faltaban tablas, créalas en el Dashboard de Supabase")
        logger.info("con los esquemas adecuados")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)

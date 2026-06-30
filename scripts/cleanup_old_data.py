#!/usr/bin/env python3
"""
Script para limpiar datos antiguos de la base de datos.
Elimina registros de más de 30 días.

Uso: python scripts/cleanup_old_data.py
"""

import sys
from datetime import datetime, timedelta
from bot.db.client import supabase
import logging

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def cleanup_old_data(days=30):
    """Elimina datos más antiguos que N días."""
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    logger.info(f"🗑️  Limpiando datos más antiguos a {cutoff_date}...")
    
    try:
        # Limpiar chat history
        logger.info("📝 Limpiando chat_history...")
        result = supabase.table("chat_history")\
            .delete()\
            .lt("created_at", cutoff_date)\
            .execute()
        
        chat_deleted = len(result.data) if result.data else 0
        logger.info(f"   ✅ {chat_deleted} registros eliminados de chat_history")
        
        # Limpiar meals
        logger.info("🍽️  Limpiando meals...")
        result = supabase.table("meals")\
            .delete()\
            .lt("created_at", cutoff_date)\
            .execute()
        
        meals_deleted = len(result.data) if result.data else 0
        logger.info(f"   ✅ {meals_deleted} registros eliminados de meals")
        
        # Limpiar measurements
        logger.info("📊 Limpiando measurements...")
        result = supabase.table("measurements")\
            .delete()\
            .lt("created_at", cutoff_date)\
            .execute()
        
        measurements_deleted = len(result.data) if result.data else 0
        logger.info(f"   ✅ {measurements_deleted} registros eliminados de measurements")
        
        total = chat_deleted + meals_deleted + measurements_deleted
        logger.info(f"\n✨ Limpieza completada - Total: {total} registros eliminados")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante limpieza: {e}", exc_info=True)
        return False

def cleanup_pending_scans():
    """Elimina scans pendientes de más de 1 día."""
    
    cutoff_date = (datetime.now() - timedelta(days=1)).isoformat()
    
    logger.info(f"🔍 Limpiando pending_scans más antiguos a {cutoff_date}...")
    
    try:
        result = supabase.table("pending_scans")\
            .delete()\
            .lt("created_at", cutoff_date)\
            .execute()
        
        deleted = len(result.data) if result.data else 0
        logger.info(f"✅ {deleted} pending_scans eliminados")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("🤖 Health Bot - Limpieza de datos")
    logger.info("="*50)
    
    # Limpiar datos antiguos
    success = cleanup_old_data(days=30)
    
    # Limpiar pending scans
    cleanup_pending_scans()
    
    if success:
        logger.info("\n✅ Limpieza exitosa")
        sys.exit(0)
    else:
        logger.error("\n❌ Limpieza con errores")
        sys.exit(1)

#!/usr/bin/env python3
"""
Auto-commit script que sube todos los cambios a GitHub automáticamente.
Uso: python auto_commit.py
"""

import subprocess
import os
from datetime import datetime

def run_command(cmd, show_output=False):
    """Ejecuta un comando y retorna el resultado."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=not show_output,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def auto_commit():
    """Detecta cambios pendientes, hace commit y push automático."""
    
    print("🔍 Verificando cambios pendientes...")
    
    # Verificar si hay cambios sin stagear
    success, output = run_command("git status --porcelain")
    
    if output.strip():
        # Si hay cambios, agregarlos y commitear
        print(f"📝 Cambios detectados:\n{output}")
        
        print("\n📦 Agregando cambios...")
        success, _ = run_command("git add -A")
        if not success:
            print("❌ Error al agregar cambios")
            return False
        
        # Crear mensaje de commit con fecha/hora
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_message = f"🤖 Auto-commit: {timestamp}"
        
        # Hacer commit
        print(f"\n💾 Haciendo commit: {commit_message}")
        success, output = run_command(f'git commit -m "{commit_message}"')
        if not success:
            print(f"⚠️  Commit falló: {output}")
            return False
    else:
        print("✅ Sin cambios locales nuevos.")
    
    # Verificar si hay commits para pushear
    print("\n🔍 Verificando commits pendientes...")
    success, output = run_command("git log origin/HEAD..HEAD --oneline")
    
    if not output.strip():
        print("✅ Todo está sincronizado con GitHub.")
        return True
    
    print(f"📤 Commits a subir:\n{output}")
    
    # Hacer push
    print("\n🚀 Subiendo a GitHub...")
    success, output = run_command("git push")
    if not success:
        print(f"❌ Error al subir: {output}")
        return False
    
    print("✅ ¡Cambios subidos exitosamente!")
    return True

if __name__ == "__main__":
    auto_commit()

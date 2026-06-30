#!/usr/bin/env python3
"""
Setup script para configurar auto-commit automático.
Ejecuta esto una sola vez para activar el sistema.
"""

import os
import shutil
import sys
from pathlib import Path

def setup_hooks():
    """Configura los git hooks automáticamente."""
    
    project_root = Path(__file__).parent
    git_hooks_dir = project_root / ".git" / "hooks"
    
    # Crear directorio si no existe
    git_hooks_dir.mkdir(parents=True, exist_ok=True)
    
    # Crear post-commit hook
    post_commit_hook = git_hooks_dir / "post-commit"
    
    # Script para Windows (batch) y Unix (bash)
    if sys.platform == "win32":
        hook_content = f"""@echo off
REM Auto-push después de commit en Windows
cd /d "{project_root}"
python auto_commit.py
"""
        hook_file = git_hooks_dir / "post-commit.bat"
    else:
        hook_content = f"""#!/bin/bash
# Auto-push después de commit en Unix/Mac
cd "{project_root}"
python3 auto_commit.py
"""
        hook_file = post_commit_hook
    
    # Escribir el hook
    with open(hook_file, "w") as f:
        f.write(hook_content)
    
    # Hacer ejecutable en Unix/Mac
    if sys.platform != "win32":
        os.chmod(hook_file, 0o755)
        print(f"✅ Hook configurado: {hook_file}")
    else:
        print(f"✅ Hook configurado: {hook_file}")
    
    print("\n📋 Configuración completada:")
    print("   • Auto-commit activado")
    print("   • Se ejecutará después de cada commit local")
    print("   • Los cambios se subirán automáticamente a GitHub")
    print("\n💡 Para desactivar, simplemente elimina el archivo hook")

if __name__ == "__main__":
    setup_hooks()

#!/usr/bin/env python3
"""
Watch and Auto-Commit: Monitorea cambios en tiempo real y hace commit+push automático
Uso: python watch_and_commit.py
"""

import subprocess
import os
import time
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

class ChangeHandler(FileSystemEventHandler):
    """Maneja cambios de archivos y triggeriza commits automáticos."""
    
    def __init__(self, debounce_seconds=5):
        self.debounce_seconds = debounce_seconds
        self.last_commit_time = 0
        self.pending_changes = False
        self.commit_timer = None
        
        # Carpetas y extensiones a ignorar
        self.ignored_dirs = {'.git', '__pycache__', '.pytest_cache', 'venv', '.venv', 'node_modules', '.idea', '.vscode'}
        self.ignored_extensions = {'.pyc', '.pyo', '.log', '.tmp', '.swp', '.swo'}
    
    def should_ignore(self, path):
        """Determina si debe ignorar este archivo/directorio."""
        path_obj = Path(path)
        
        # Ignorar directorios
        for part in path_obj.parts:
            if part.startswith('.') and part in self.ignored_dirs:
                return True
        
        # Ignorar extensiones
        if path_obj.suffix in self.ignored_extensions:
            return True
        
        # Ignorar archivos temporales
        if path_obj.name.startswith('~') or path_obj.name.endswith('~'):
            return True
        
        return False
    
    def on_modified(self, event):
        if not event.is_directory and not self.should_ignore(event.src_path):
            print(f"📝 Cambio detectado: {event.src_path}")
            self.schedule_commit()
    
    def on_created(self, event):
        if not event.is_directory and not self.should_ignore(event.src_path):
            print(f"✨ Archivo nuevo: {event.src_path}")
            self.schedule_commit()
    
    def on_deleted(self, event):
        if not event.is_directory and not self.should_ignore(event.src_path):
            print(f"🗑️  Archivo eliminado: {event.src_path}")
            self.schedule_commit()
    
    def schedule_commit(self):
        """Programa un commit con debouncing."""
        self.pending_changes = True
        
        # Cancelar timer anterior si existe
        if self.commit_timer:
            self.commit_timer.cancel()
        
        # Crear nuevo timer
        self.commit_timer = threading.Timer(
            self.debounce_seconds,
            self.perform_commit
        )
        self.commit_timer.daemon = True
        self.commit_timer.start()
        
        print(f"⏰ Commit programado en {self.debounce_seconds}s...")
    
    def perform_commit(self):
        """Ejecuta el commit y push."""
        if not self.pending_changes:
            return
        
        # Verificar si hay cambios
        result = subprocess.run(
            "git status --porcelain",
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )
        
        if not result.stdout.strip():
            print("✅ Sin cambios para commitear")
            self.pending_changes = False
            return
        
        print(f"\n📦 Cambios pendientes:\n{result.stdout}")
        
        # Agregar cambios
        subprocess.run("git add -A", shell=True, cwd=str(Path(__file__).parent))
        
        # Hacer commit
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"🤖 Auto-commit: {timestamp}"
        
        result = subprocess.run(
            f'git commit -m "{commit_msg}"',
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )
        
        if result.returncode == 0:
            print(f"✅ Commit realizado: {commit_msg}")
            
            # Hacer push
            result = subprocess.run(
                "git push",
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent)
            )
            
            if result.returncode == 0:
                print("🚀 Push exitoso ✨")
            else:
                print(f"⚠️ Error en push: {result.stderr}")
        else:
            if "nothing to commit" not in result.stdout.lower():
                print(f"⚠️ Error en commit: {result.stderr}")
        
        self.pending_changes = False


def watch_repository():
    """Inicia el observador de cambios."""
    
    project_root = Path(__file__).parent
    
    print(f"""
╔════════════════════════════════════════╗
║  🤖 HEALTH-BOT AUTO-COMMIT MONITOR    ║
╚════════════════════════════════════════╝

📍 Monitoreo: {project_root}
⏱️  Debounce: 5 segundos
📤 Destino: GitHub

🟢 Sistema activo - Esperando cambios...
(Presiona Ctrl+C para salir)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    event_handler = ChangeHandler(debounce_seconds=5)
    observer = Observer()
    
    # Monitorear carpetas importantes
    paths_to_watch = [
        project_root / "bot",
        project_root / "migrations",
        project_root,
    ]
    
    for path in paths_to_watch:
        if path.exists():
            observer.schedule(event_handler, str(path), recursive=True)
            print(f"👀 Monitoreando: {path}")
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⛔ Parando monitor...")
        observer.stop()
    
    observer.join()
    print("✅ Monitor finalizado\n")


if __name__ == "__main__":
    watch_repository()

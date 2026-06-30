# 🤖 Auto-Commit a GitHub

Configura auto-commit automático para subir cambios a GitHub sin intervención manual.

## Opciones de instalación:

### Opción 1: Script Manual (Más simple)
```bash
# Ejecuta esto manualmente cuando quieras subir cambios:
python auto_commit.py
```

### Opción 2: Ejecutar periódicamente con Windows Task Scheduler
1. Abre **Task Scheduler**
2. Crea nueva tarea: "Health Bot Auto Commit"
3. Trigger: Repetir cada 30 minutos (o el intervalo que quieras)
4. Acción: 
   - Program: `C:\Python\python.exe` (o tu Python path)
   - Arguments: `c:\proyectos\health-bot\auto_commit.py`
   - Start in: `c:\proyectos\health-bot\`

### Opción 3: Git Hook automático (Requiere activación manual)
```bash
# Desde la carpeta del proyecto:
python setup_hooks.py
```

## Cómo verificar

```bash
# Ver estado del repositorio
git status

# Ver últimos commits
git log --oneline -5

# Ver si el push llegó a GitHub
git log --oneline -5 --all
```

## Notas

- **No requiere credenciales** si ya tienes SSH configurado o GitHub CLI autenticado
- **Seguro**: Solo sube cambios existentes, no modifica nada
- **Reversible**: Todos los commits son reversibles con `git revert` o `git reset`

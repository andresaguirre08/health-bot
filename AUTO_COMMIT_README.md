# 🤖 Auto-Commit a GitHub

Configura auto-commit automático para subir cambios a GitHub sin intervención manual.

## ⚡ OPCIÓN RECOMENDADA: Monitor en tiempo real

### ✨ Monitoreo Automático (Opción B)
Detecta cambios mientras trabajas y hace commit+push automáticamente en segundos.

**Inicio rápido:**
```bash
# Opción 1: Ejecutar directamente
python watch_and_commit.py

# Opción 2: Hacer doble-click en START_MONITOR.bat
# (más fácil en Windows)
```

**¿Qué hace?**
- 👀 Monitorea cambios en `bot/`, `migrations/` y raíz
- ⏱️ Espera 5 segundos de inactividad (debounce)
- 💾 Hace commit automático
- 🚀 Hace push a GitHub
- 📊 Muestra logs de cada acción

**Ventajas:**
- ✅ Cambios en GitHub **casi instantáneamente**
- ✅ Cero intervención manual
- ✅ Logs en tiempo real
- ✅ Ignora archivos temporales y caché

---

## Otras Opciones:

### Opción 1: Script Manual (Simple)
```bash
# Ejecuta esto manualmente cuando quieras subir cambios:
python auto_commit.py
```

### Opción 2: Git Hook post-commit
```bash
# Ejecuta una sola vez:
python setup_hooks.py

# Luego, cada commit local hace push automático
```

### Opción 3: Windows Task Scheduler (Cada N minutos)
1. Abre **Task Scheduler**
2. Crea nueva tarea: "Health Bot Auto Commit"
3. Trigger: Repetir cada 30 minutos
4. Acción: 
   - Program: `python.exe`
   - Arguments: `c:\proyectos\health-bot\auto_commit.py`
   - Start in: `c:\proyectos\health-bot\`

---

## 📊 Verificación

```bash
# Ver estado del repositorio
git status

# Ver últimos commits
git log --oneline -5

# Ver si cambios llegaron a GitHub
git log --oneline -5 --all
```

## 🔒 Seguridad & Notas

- **No requiere credenciales** si tienes SSH o GitHub CLI autenticado
- **Seguro**: Solo sube cambios existentes, no modifica nada
- **Reversible**: Todos los commits son reversibles con `git revert` o `git reset`
- **Para detener el monitor**: Presiona `Ctrl+C` en la terminal

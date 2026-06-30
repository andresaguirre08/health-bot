# 📋 HEALTH BOT - DEPLOYMENT GUIDE

## 🚀 Despliegue Local

### 1. Configuración Inicial
```bash
# Clonar repositorio
git clone https://github.com/andresaguirre08/health-bot.git
cd health-bot

# Crear entorno virtual
python -m venv venv

# Activar entorno
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Variables de Entorno
```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar con tus credenciales
nano .env  # o usa tu editor favorito
```

### 3. Ejecutar Bot
```bash
# Opción 1: Directo
python run.py

# Opción 2: Con auto-commit a GitHub
python watch_and_commit.py  # En otra terminal

# Opción 3: Con supervisor (producción)
supervisord -c supervisord.conf
```

---

## 🐳 Despliegue con Docker

### 1. Construir imagen
```bash
docker build -t health-bot:latest .
```

### 2. Crear archivo .env (importante)
```bash
# Crear archivo .env en el directorio raíz con todas las variables
cat > .env << 'EOF'
TELEGRAM_TOKEN=your_token
ANTHROPIC_API_KEY=your_key
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
# ... resto de variables
EOF
```

### 3. Ejecutar contenedor
```bash
# Despliegue simple
docker run -d \
  --name health-bot \
  --env-file .env \
  --restart unless-stopped \
  health-bot:latest

# Con volúmenes (para persistencia)
docker run -d \
  --name health-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  health-bot:latest
```

### 4. Ver logs
```bash
docker logs -f health-bot
```

---

## ☁️ Despliegue en Heroku

### 1. Inicializar Heroku
```bash
heroku login
heroku create health-bot
```

### 2. Configurar variables de entorno
```bash
heroku config:set TELEGRAM_TOKEN=xxx
heroku config:set ANTHROPIC_API_KEY=xxx
# ... resto de variables
```

### 3. Desplegar
```bash
git push heroku main
```

### 4. Ver logs
```bash
heroku logs --tail
```

---

## 📊 Monitoreo y Mantenimiento

### Health Check
```bash
# Verificar que el bot está funcionando
curl http://localhost:8000/health  # Si está disponible

# O simplemente verificar logs
docker logs health-bot
```

### Limpieza de datos antiguos
```bash
# Script para limpiar datos de más de 30 días
python scripts/cleanup_old_data.py
```

### Actualizar código
```bash
# Con git
git pull origin main
git push heroku main  # Si usas Heroku

# Con Docker
docker stop health-bot
docker rm health-bot
docker build -t health-bot:latest .
docker run -d --name health-bot --env-file .env health-bot:latest
```

---

## 🔧 Troubleshooting

### Bot no responde
1. Verificar TELEGRAM_TOKEN en .env
2. Ver logs: `docker logs health-bot` o `heroku logs --tail`
3. Validar conexión a Supabase

### Error en Claude API
1. Verificar ANTHROPIC_API_KEY válida
2. Chequear cuota disponible en Anthropic
3. Revisar modelo configurado en código

### Database connection error
1. Verificar SUPABASE_URL y SUPABASE_KEY
2. Chequear que la base de datos está online
3. Validar que las tablas existen

---

## 📈 Actualizaciones y Mejoras

- [x] Validación de configuración al iniciar
- [x] Mejor error handling
- [x] Auto-commit a GitHub
- [x] Dockerfile optimizado
- [x] Health checks
- [ ] Métricas de rendimiento
- [ ] Dashboard de estadísticas

---

## 📞 Support

Para reportar problemas, abre un issue en GitHub:
https://github.com/andresaguirre08/health-bot/issues

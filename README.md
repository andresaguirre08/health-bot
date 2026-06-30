# 🤖 Health Bot - Personal AI Nutrition & Fitness Coach

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-andresaguirre08%2Fhealth--bot-black.svg)](https://github.com/andresaguirre08/health-bot)

Un bot de Telegram impulsado por IA que actúa como tu entrenador personal de nutrición y fitness. Registra comidas, sincroniza datos de Garmin/Polar, y recibe recomendaciones personalizadas.

## ✨ Características

### 📷 Análisis de Alimentos
- **OCR de Etiquetas Nutricionales**: Fotografía etiquetas y extrae macros automáticamente
- **Descripción por Texto**: "Comí 250g de pollo con arroz" → macros calculados
- **Audio/Voz**: Dictado en español con transcripción automática
- **Base de Datos Personal**: Guarda alimentos frecuentes para uso rápido

### 📊 Seguimiento de Progreso
- **Resumen Diario**: Calorías, proteína, carbohidratos, grasas consumidas
- **Composición Corporal**: Peso, % grasa, músculo, medidas
- **Historial Completo**: Seguimiento de tendencias a lo largo del tiempo
- **Objetivos Personalizados**: Configurables según tu meta

### 🔄 Integraciones de Fitness
- **Garmin Connect**: Sincroniza actividades, calorías quemadas, datos de entrenamiento
- **Polar**: Conecta deportivos Polar para métricas de cardio
- **Automático**: Sync cada 6 horas

### 🤖 IA Inteligente
- **Claude AI (Anthropic)**: Asesoría nutricional y fitness personalizada
- **Contexto Adaptativo**: Recomienda basado en tu día, macros pendientes, objetivos
- **Lenguaje Natural**: Entiende descripciones complejas de comidas
- **Groq Whisper**: Transcripción de audio en tiempo real

## 🚀 Quick Start

### Requisitos
- Python 3.11+
- Cuenta en Telegram
- API keys: Anthropic, Supabase, Groq
- Opcional: Garmin/Polar para sincronización

### Instalación Local

```bash
# Clonar repo
git clone https://github.com/andresaguirre08/health-bot.git
cd health-bot

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales

# Ejecutar bot
python run.py
```

### Con Docker

```bash
docker build -t health-bot .
docker run -d --env-file .env --name health-bot health-bot:latest
```

## 📖 Guía de Uso

### Comandos Disponibles

| Comando | Descripción |
|---------|------------|
| `/start` | Mensaje de bienvenida |
| `/hoy` | Resumen nutricional del día |
| `/progreso` | Composición corporal actual |
| `/peso` | Registrar peso y medidas |
| `/sync` | Sincronizar Garmin |
| `/sync_polar` | Sincronizar Polar |
| `/borrar` | Eliminar última comida registrada |
| `/mialimentos` | Ver base de datos personal |
| `/tabla` | Ver tabla con datos del día |

### Ejemplos de Uso

**Registrar comida por texto:**
```
Usuario: Comí 200g de pechuga de pollo, arroz y ensalada
Bot: ✅ Almuerzo guardado
🔥 Calorías: 450 kcal
💪 Proteína: 45g
🍚 Carbohidratos: 42g
🥑 Grasas: 8g
```

**Foto de etiqueta nutricional:**
```
Usuario: [Envía foto de etiqueta]
Bot: Vi esta etiqueta... ¿Estos datos son correctos?
Usuario: Si
Bot: ✅ Producto guardado en tu base de datos
```

**Consultar sobre comida:**
```
Usuario: ¿Puedo comer pizza hoy?
Bot: [Análisis basado en tus macros restantes, objetivos, y progreso]
```

## 🛠️ Configuración

### Variables de Entorno Requeridas
```env
# Telegram
TELEGRAM_TOKEN=your_token_here

# Claude AI
ANTHROPIC_API_KEY=your_key_here

# Supabase (Database)
SUPABASE_URL=your_url_here
SUPABASE_KEY=your_key_here

# Groq (Audio transcription)
GROQ_API_KEY=your_key_here

# Garmin (Optional)
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_password_here

# Polar (Optional)
POLAR_CLIENT_ID=your_id_here
POLAR_CLIENT_SECRET=your_secret_here
POLAR_REDIRECT_URL=http://localhost:8000/auth/polar/callback
```

Mira [.env.example](.env.example) para más detalles.

## 📚 Documentación

- [**DEPLOYMENT.md**](DEPLOYMENT.md) - Guía completa de despliegue (local, Docker, Heroku)
- [**AUTO_COMMIT_README.md**](AUTO_COMMIT_README.md) - Configuración de auto-sync a GitHub

## 📁 Estructura del Proyecto

```
health-bot/
├── bot/
│   ├── agents/
│   │   ├── coach.py           # Agente principal de coach/nutrición
│   │   ├── nutrition_scanner.py # OCR y análisis de etiquetas
│   │   └── nutritionist.py     # Respuestas nutricionales con IA
│   ├── db/
│   │   ├── client.py           # Cliente de Supabase
│   │   └── meals.py            # Funciones de comidas
│   ├── handlers/
│   │   ├── commands.py         # Comandos del bot
│   │   └── food.py             # Manejo de fotos de comida
│   ├── integrations/
│   │   ├── garmin.py           # Sincronización Garmin
│   │   └── polar.py            # Sincronización Polar
│   ├── scheduler/
│   │   └── jobs.py             # Jobs programados (sync, feedback)
│   ├── utils/
│   │   ├── config.py           # Configuración global
│   │   └── context_builder.py  # Contexto para IA
│   └── main.py                 # Punto de entrada
├── scripts/
│   ├── cleanup_old_data.py     # Limpiar datos antiguos
│   └── init_database.py        # Inicializar DB
├── migrations/                 # Cambios de base de datos
├── requirements.txt            # Dependencias Python
├── run.py                      # Script para ejecutar bot
├── dockerfile                  # Configuración Docker
├── Procfile                    # Configuración Heroku
└── README.md                   # Este archivo
```

## 🔧 Desarrollo

### Configurar dev environment
```bash
pip install -r requirements.txt

# Ejecutar con auto-reload
python watch_and_commit.py  # Auto-sync a GitHub
```

### Tests
```bash
# Validar configuración
python run.py

# Tests específicos
python -m pytest tests/
```

## 🐛 Troubleshooting

### El bot no responde
1. Verificar `TELEGRAM_TOKEN` en `.env`
2. Ver logs: `docker logs health-bot`
3. Validar conexión a Supabase

### Error "Model not found"
- Verificar que `ANTHROPIC_API_KEY` es válido
- El modelo actualmente es `claude-opus-4-1-20250805`
- Revisar cuota disponible en Anthropic

### Errores de base de datos
- Validar `SUPABASE_URL` y `SUPABASE_KEY`
- Verificar que las tablas existen
- Ejecutar: `python scripts/init_database.py`

## 🚀 Roadmap

- [ ] Dashboard web con estadísticas
- [ ] Exportar datos (CSV, PDF)
- [ ] Recomendaciones de ejercicios
- [ ] Integración con más wearables
- [ ] Planes de comidas personalizados
- [ ] Recetas sugeridas basadas en objetivos
- [ ] Modo offline básico

## 📄 Licencia

MIT License - mira [LICENSE](LICENSE)

## 👤 Autor

**Andrés Aguirre**
- GitHub: [@andresaguirre08](https://github.com/andresaguirre08)

## 🙏 Agradecimientos

- Telegram Bot API
- Anthropic Claude AI
- Supabase
- Groq API
- Garmin Connect
- Polar Sport

## 📞 Soporte

¿Problemas? Abre un issue:
https://github.com/andresaguirre08/health-bot/issues

---

**Versión**: 1.0.0  
**Última actualización**: 2026-06-29

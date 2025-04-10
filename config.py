import os
from dotenv import load_dotenv

load_dotenv() # Загружает переменные из .env файла

# Токен Telegram бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")

# Параметры подключения к Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL_HERE")
# Ключ ANON (может понадобиться для других целей, но НЕ для основного бота)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY_HERE") 
# Ключ SERVICE_ROLE (для серверных операций бота)
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "YOUR_SUPABASE_SERVICE_KEY_HERE")

# --- Параметры SQLite (если используется) ---
# SQLITE_DB_NAME = "game_data.db"

# Параметры игры (можно добавить позже)
# Например, начальные значения ресурсов
INITIAL_SUPPORT = 50
INITIAL_TREASURY = 1000
INITIAL_ARMY = "medium"
INITIAL_PEASANTS = "medium"

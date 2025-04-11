import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart

import config
from bot.handlers import router as main_router # Импортируем роутер из handlers.py
from data.database import init_supabase_client # Импортируем только функцию инициализации

async def main():
    """Основная функция для запуска бота."""
    # Настройка логирования (изменено на INFO)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # --- Инициализация клиента Supabase --- 
    db_client = await init_supabase_client()
    if not db_client:
        logging.critical("Failed to initialize Supabase client. Bot cannot start.")
        return # Не запускаем бота, если нет подключения к БД
    # --------------------------------------

    # Создание объектов бота и диспетчера
    bot = Bot(token=config.TELEGRAM_TOKEN)
    dp = Dispatcher()

    # --- Передаем клиент Supabase в контекст --- 
    # Это стандартный способ aiogram передавать данные в хендлеры
    dp["db_client"] = db_client
    # Передаем и объект bot, если он нужен в хендлерах не через аргумент
    # dp["bot"] = bot # <- Кажется, это было сделано ранее, проверим, нужно ли

    # Подключаем роутер
    dp.include_router(main_router)

    # Запуск polling
    logging.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logging.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot execution stopped manually.")

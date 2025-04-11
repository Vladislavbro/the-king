import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart

import config
from bot.handlers import router as main_router # Импортируем роутер из handlers.py
from data.database import init_supabase_client # Импортируем функцию инициализации БД

async def main():
    """Основная функция для запуска бота."""
    # Настройка логирования (базовая)
    logging.basicConfig(level=logging.INFO)

    # --- Инициализация клиента Supabase --- 
    await init_supabase_client()
    # --------------------------------------

    # Создание объектов бота и диспетчера
    bot = Bot(token=config.TELEGRAM_TOKEN)
    dp = Dispatcher()

    # Передаем объект bot в роутер, чтобы он был доступен в хендлерах
    dp.include_router(main_router)
    dp["bot"] = bot # Стандартный способ передать bot в хендлеры через Dispatcher

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

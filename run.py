#!/usr/bin/env python3
"""
Простой запуск бота. Точка входа приложения.
"""

import os
import sys
import asyncio
import logging
import signal

# Создаем директорию для логов
log_dir = '/app/logs'
os.makedirs(log_dir, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'{log_dir}/skufobot.log')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Основная асинхронная функция"""
    # Импортируем внутри, чтобы избежать проблем с циклическими импортами
    # и гарантировать, что логирование инициализируется первым.
    from bot import SkufBot

    logger.info("🤖 Создаю экземпляр бота...")
    bot = SkufBot()

    # --- Настройка Graceful Shutdown для Docker ---
    # Docker отправляет SIGTERM при остановке контейнера.
    loop = asyncio.get_running_loop()

    def handle_stop_signal(sig_name):
        logger.info(f"🛑 Получен системный сигнал {sig_name}. Инициирую мягкую остановку...")
        # Сообщаем боту, что пора сворачиваться (он сам вызовет свой shutdown())
        bot.stop_event.set()

    # Регистрируем обработчики для Linux/Docker (SIGTERM и SIGINT)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: handle_stop_signal(s.name))
        except NotImplementedError:
            pass

    # --- Запуск бота ---
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"💥 Ошибка при работе бота: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("👋 Процесс завершен.")

#!/usr/bin/env python3
"""
Простой запуск бота.
"""

import os
import sys
import asyncio
import logging

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
    # Импортируем здесь, чтобы логгирование было настроено
    from bot import SkufBot

    logger.info("🤖 Создаю экземпляр бота...")
    bot = SkufBot()

    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("⌨️ Получен KeyboardInterrupt, завершаю работу...")
    except Exception as e:
        logger.error(f"💥 Ошибка при работе бота: {e}")
        raise


if __name__ == "__main__":
    # Простой запуск
    asyncio.run(main())

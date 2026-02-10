"""
Упрощенный планировщик задач без зависимости от внешней базы данных.
Использует встроенные средства Python для планирования задач.
"""

import asyncio
import logging
import time
from datetime import datetime, time as dt_time
from typing import Callable

from config import settings
from services import subscriber_service, gif_service
from telegram_utils import send_text_message, send_gif_message
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

class SimpleScheduler:
    """Упрощенный планировщик задач с использованием asyncio"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.is_running = False
        self.tasks = []
        self.debug_mode = settings.debug  # Сохраняем режим отладки
        self.last_gif_sent_time = {}  # Кэш времени отправки гифок по chat_id
        self.request_delay = settings.scheduler_min_interval    # Минимальная задержка между запросами (сек)
        self._scheduled_tasks = []

    def _get_today_day_of_week(self) -> int:
        """Возвращает номер дня недели (1=понедельник, 7=воскресенье)"""
        return datetime.now().isoweekday()

    def _get_day_name(self, day: int) -> str:
        """Возвращает название дня недели"""
        days = {
            1: "Понедельник",
            2: "Вторник",
            3: "Среда",
            4: "Четверг",
            5: "Пятница",
            6: "Суббота",
            7: "Воскресенье"
        }
        return days.get(day, f"День {day}")

    async def send_daily_text_message(self):
        """Ежедневная рассылка текстовых сообщений в 8:30 утра"""
        try:
            logger.info("🚀 Начинаю ежедневную текстовую рассылку...")

            chat_ids = await subscriber_service.get_all_subscriber_ids()
            message = "Доброе утро! Хорошего дня! 🎉"

            sent_count = 0
            failed_count = 0

            for chat_id in chat_ids:
                try:
                    await send_text_message(self.bot, chat_id, message)
                    sent_count += 1
                    logger.debug(f"📨 Сообщение отправлено в чат {chat_id}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Ошибка отправки в чат {chat_id}: {e}")

            logger.info(f"✅ Ежедневная текстовая рассылка завершена. "
                        f"Успешно: {sent_count}, Ошибок: {failed_count}")

        except Exception as e:
            logger.error(f"❌ Ошибка в ежедневной текстовой рассылке: {e}")

    async def send_daily_gif_message(self):
        """Ежедневная рассылка GIF в 8:30 утра"""
        try:
            logger.info("🚀 Начинаю ежедневную GIF рассылку...")

            today = self._get_today_day_of_week()
            day_name_genitive = self._get_day_name_genitive(today)  # Изменено на родительный падеж
            chat_ids = await subscriber_service.get_all_subscriber_ids()

            # Ищем случайный GIF для сегодняшнего дня
            gif = await gif_service.find_random_gif_by_day(today)

            sent_count = 0
            failed_count = 0

            for chat_id in chat_ids:
                try:
                    if gif:
                        await send_gif_message(self.bot, chat_id, gif.file_id, f"Хорошего {day_name_genitive}! 😊")
                    else:
                        await send_text_message(self.bot, chat_id, "😔 Гифки на сегодня закончились")

                    sent_count += 1
                    logger.debug(f"🎬 GIF отправлен в чат {chat_id}")
                except BadRequest as e:
                    if "Chat not found" in str(e) or "chat not found" in str(e).lower():
                        logger.error(f"❌ Чат {chat_id} не найден")
                    else:
                        logger.error(f"❌ Ошибка запроса при отправке в чат {chat_id}: {e}")
                    failed_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Ошибка отправки в чат {chat_id}: {e}")

            logger.info(f"✅ Ежедневная GIF рассылка завершена. "
                        f"Успешно: {sent_count}, Ошибок: {failed_count}")

        except Exception as e:
            logger.error(f"❌ Ошибка в ежедневной GIF рассылке: {e}")

    async def send_test_short_interval_message(self):
        """Тестовая задача с коротким интервалом (только в debug-режиме)"""
        if not self.debug_mode:
            return

        try:
            logger.debug("🔧 Тестовая задача с коротким интервалом...")

            # В режиме отладки отправляем только в первый чат (или в тестовый)
            chat_ids = await subscriber_service.get_all_subscriber_ids()
            if not chat_ids:
                logger.debug("ℹ️ Нет подписчиков для тестовой отправки")
                return

            # Используем первый чат из списка
            chat_id = chat_ids[0]

            # Проверяем, не слишком ли рано отправляем
            now = time.time()
            last_sent = self.last_gif_sent_time.get(chat_id, 0)
            if now - last_sent < self.request_delay:
                logger.debug(f"⏳ Пропускаю отправку в чат {chat_id}, слишком рано")
                return

            # Обновляем время последней отправки
            self.last_gif_sent_time[chat_id] = now

            # Получаем текущий день недели
            today = self._get_today_day_of_week()
            day_name = self._get_day_name(today)

            # Получаем случайную гифку
            gif = await gif_service.find_random_gif_by_day(today)

            if gif:
                timestamp = datetime.now().strftime("%H:%M:%S")
                await send_gif_message(self.bot, chat_id, gif.file_id,
                                       f"[Тест] {day_name} - {timestamp}\n"
                                       f"Тест планировщика с интервалом 30 сек")
                logger.debug(f"✅ Тестовая гифка отправлена в {chat_id} в {timestamp}")
            else:
                await send_text_message(self.bot, chat_id,
                                        f"[Тест {day_name}] Нет гифок для этого дня\n"
                                        f"Время: {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"❌ Ошибка в тестовой задаче: {e}")
            # При ошибке увеличиваем задержку
            self.request_delay = min(self.request_delay + 5, 60)

    def schedule_daily_tasks(self):
        """Планирует ежедневные задачи"""

        daily_gif_task = asyncio.create_task(self._schedule_daily_task(
            dt_time(5, 30), self.send_daily_gif_message, "Ежедневная GIF рассылка в 8:30 по UTC+3"
        ))

        self._scheduled_tasks.extend([daily_gif_task])

        logger.info("📅 Запланированы ежедневные задачи на 8:30 по UTC+3")

    async def _schedule_daily_task(self, target_time: dt_time, coro_func: Callable, description: str):
        """Планирует задачу на определенное время каждый день"""
        logger.info(f"⏰ Запланирована задача: {description}")

        while self.is_running:
            now = datetime.now()
            target_datetime = datetime.combine(now.date(), target_time)

            # Если время уже прошло сегодня, планируем на завтра
            if target_datetime < now:
                target_datetime = datetime.combine(
                    now.date() + timedelta(days=1),
                    target_time
                )

            # Вычисляем время ожидания
            wait_seconds = (target_datetime - now).total_seconds()

            if wait_seconds > 0:
                logger.info(f"⏰ Задача '{description}' запланирована на {target_datetime.strftime('%H:%M')} (через {wait_seconds/60:.1f} минут)")
                await asyncio.sleep(wait_seconds)

            # Выполняем задачу
            try:
                await coro_func()
            except Exception as e:
                logger.error(f"❌ Ошибка выполнения задачи '{description}': {e}")

            # Ждем до следующего дня
            await asyncio.sleep(60)  # Небольшая задержка перед планированием следующего дня

    async def send_test_minute_interval_message(self):
        """Тестовая задача с минутным интервалом"""
        if not self.debug_mode:
            return

        try:
            logger.info("⏱️ Тестовая задача с минутным интервалом...")

            chat_ids = await subscriber_service.get_all_subscriber_ids()
            if not chat_ids:
                return

            # Используем первый чат
            chat_id = chat_ids[0]
            today = self._get_today_day_of_week()
            timestamp = datetime.now().strftime("%H:%M:%S")

            await send_text_message(self.bot, chat_id,
                                    f"⏱️ Тест планировщика\n"
                                    f"Минутная проверка\n"
                                    f"Время: {timestamp}\n"
                                    f"День недели: {self._get_day_name(today)}")

            logger.debug(f"✅ Минутная проверка отправлена в {chat_id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в минутной задаче: {e}")

    async def run_pending_tasks(self):
        """Запускает запланированные задачи (для совместимости)"""
        # В этой версии мы не используем aioschedule
        while self.is_running:
            await asyncio.sleep(1)

    async def start(self):
        """Запускает планировщик"""
        if not self.is_running:
            self.is_running = True

            # Планируем ежедневные задачи
            self.schedule_daily_tasks()

            # В debug-режиме добавляем тестовые задачи
            if self.debug_mode:
                debug_task = asyncio.create_task(self._run_debug_tasks())
                self._scheduled_tasks.append(debug_task)
                logger.info("🔧 Включен debug-режим: добавлены тестовые задачи")

            logger.info("🚀 Планировщик запущен")

    async def _run_debug_tasks(self):
        """Запускает тестовые задачи в debug-режиме"""
        while self.is_running and self.debug_mode:
            try:
                # Тестовая задача каждые 30 секунд
                await self.send_test_short_interval_message()
                await asyncio.sleep(30)

                # Тестовая задача каждые 2 минуты
                await self.send_daily_gif_message()
                await asyncio.sleep(120)  # 2 минуты

            except Exception as e:
                logger.error(f"❌ Ошибка в отладочных задачах: {e}")
                await asyncio.sleep(30)

    def stop(self):
        """Останавливает планировщик"""
        self.is_running = False
        for task in self._scheduled_tasks:
            task.cancel()
        self._scheduled_tasks.clear()
        logger.info("🛑 Планировщик остановлен")

    async def send_test_gif(self, chat_id: int, day: int):
        """Отправляет тестовый GIF в указанный чат"""
        try:
            day_name = self._get_day_name(day)
            gif = await gif_service.find_random_gif_by_day(day)

            if gif:
                await send_gif_message(self.bot, chat_id, gif.file_id, f"[Тест] {day_name}")
                logger.info(f"✅ Тестовый GIF отправлен в чат {chat_id} для дня {day}")
                return True
            else:
                await send_text_message(self.bot, chat_id, f"[Тест {day_name}] В базе нет гифок для этого дня")
                logger.info(f"ℹ️ GIF для дня {day} не найден для чата {chat_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового GIF в чат {chat_id}: {e}")
            await send_text_message(self.bot, chat_id, "❌ Произошла ошибка при отправке теста")
            return False

    def _get_day_name_genitive(self, day_num: int) -> str:
        """
        Возвращает название дня недели в родительном падеже
        (для фраз типа "Хорошего понедельника!")

        Args:
            day_num: номер дня недели (0-6)

        Returns:
            str: день недели в родительном падеже
        """
        day_names_genitive = {
            0: "понедельника",
            1: "вторника",
            2: "среды",
            3: "четверга",
            4: "пятницы",
            5: "субботы",
            6: "воскресенья"
        }
        return day_names_genitive.get(day_num, "дня")

    def add_custom_task(self, interval_seconds: int, callback):
        """Добавляет пользовательскую задачу с заданным интервалом"""
        if interval_seconds <= 0:
            raise ValueError("Интервал должен быть положительным числом")

        async def wrapped_task():
            while self.is_running:
                await callback()
                await asyncio.sleep(interval_seconds)

        task = asyncio.create_task(wrapped_task())
        self._scheduled_tasks.append(task)
        logger.info(f"➕ Добавлена пользовательская задача с интервалом {interval_seconds} сек")

# Добавьте импорт timedelta в начало файла
from datetime import timedelta
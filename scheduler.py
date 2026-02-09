"""
Упрощенный планировщик задач без зависимости от внешней базы данных.
Использует встроенные средства Python для планирования задач.
"""

import asyncio
import logging
import time
from datetime import datetime
import aioschedule as schedule
from telegram.error import BadRequest

from config import settings
from services import subscriber_service, gif_service
from telegram_utils import send_text_message, send_gif_message

logger = logging.getLogger(__name__)


class SimpleScheduler:
    """Упрощенный планировщик задач с использованием aioschedule"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.is_running = False
        self.tasks = []
        self.debug_mode = settings.debug  # Сохраняем режим отладки
        self.last_gif_sent_time = {}  # Кэш времени отправки гифок по chat_id
        self.request_delay = settings.scheduler_min_interval    # Минимальная задержка между запросами (сек)

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

    async def send_daily_gif_message(self):
        """Ежедневная рассылка GIF в 8:30 утра"""
        try:
            logger.info("🚀 Начинаю ежедневную GIF рассылку...")

            today = self._get_today_day_of_week()
            day_name = self._get_day_name(today)
            chat_ids = await subscriber_service.get_all_subscriber_ids()

            # Ищем случайный GIF для сегодняшнего дня
            gif = await gif_service.find_random_gif_by_day(today)

            sent_count = 0
            failed_count = 0

            for chat_id in chat_ids:
                try:
                    if gif:
                        await send_gif_message(self.bot, chat_id, gif.file_id, f"Хорошего {day_name}! 😊")
                    else:
                        await send_text_message(self.bot, chat_id, "😔 Гифки на сегодня закончились")

                    sent_count += 1
                    logger.debug(f"🎬 GIF отправлен в чат {chat_id}")
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

        # scheduler.py - исправьте блок try-except в функции send_test_short_interval_message
        except BadRequest as e:
            if "Chat not found" in str(e) or "chat not found" in str(e).lower():
                logger.error(f"❌ Чат {chat_id} не найден")
                # Удаляем из кэша
                if chat_id in self.last_gif_sent_time:
                    del self.last_gif_sent_time[chat_id]
            else:
                logger.error(f"❌ Ошибка запроса при отправке тестового GIF в чат {chat_id}: {e}")

    def schedule_daily_tasks(self):
        """Планирует ежедневные задачи"""

        # Ежедневная GIF рассылка в 8:30
        schedule.every().day.at("08:31").do(
            lambda: asyncio.create_task(self.send_daily_gif_message())
        )

        logger.info("📅 Запланированы ежедневные задачи на 8:30")

        # В debug-режиме добавляем тестовые задачи с короткими интервалами
        if self.debug_mode:
            # Тестовая задача каждые 30 секунд (вместо 5)
            schedule.every(settings.scheduler_debug_interval).seconds.do(
                lambda: asyncio.create_task(self.send_test_short_interval_message())
            )

            logger.info("🔧 Включен debug-режим: добавлены тестовые задачи")

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
        """Запускает запланированные задачи"""
        while self.is_running:
            try:
                # Запускаем все задачи, которые должны быть выполнены
                await schedule.run_pending()

                # В debug-режиме логируем оставшиеся задачи
                if self.debug_mode and schedule.jobs:
                    logger.debug(f"🔍 Активных задач в очереди: {len(schedule.jobs)}")

            except Exception as e:
                logger.error(f"❌ Ошибка в run_pending: {e}")

            # Ждем 1 секунду перед следующей проверкой
            await asyncio.sleep(1)

    async def start(self):
        """Запускает планировщик"""
        if not self.is_running:
            self.is_running = True
            self.schedule_daily_tasks()

            # Запускаем фоновую задачу для проверки расписания
            asyncio.create_task(self.run_pending_tasks())
            logger.info("🚀 Упрощенный планировщик запущен")

            # Показываем запланированные задачи
            jobs = schedule.jobs
            logger.info(f"📋 Запланировано задач: {len(jobs)}")
            for i, job in enumerate(jobs, 1):
                logger.info(f"  {i:2d}. {job}")

            # Логируем расписание для debug-режима
            if self.debug_mode:
                self.log_schedule_details()
        else:
            logger.warning("⚠️ Планировщик уже запущен")

    def log_schedule_details(self):
        """Логирует детали расписания (только в debug)"""
        logger.debug("🔍 Детали расписания планировщика:")
        for i, job in enumerate(schedule.jobs, 1):
            logger.debug(f"  Задача {i}:")
            logger.debug(f"    - Функция: {job.job_func}")
            logger.debug(f"    - Интервал: {job.interval} {job.unit}")
            logger.debug(f"    - Следующий запуск: {job.next_run}")
            logger.debug(f"    - Последний запуск: {job.last_run}")

    def stop(self):
        """Останавливает планировщик"""
        self.is_running = False
        schedule.clear()
        logger.info("🛑 Упрощенный планировщик остановлен")

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

    def add_custom_task(self, interval_seconds: int, callback):
        """Добавляет пользовательскую задачу с заданным интервалом"""
        if interval_seconds <= 0:
            raise ValueError("Интервал должен быть положительным числом")

        # Преобразуем секунды в соответствующую единицу
        if interval_seconds >= 86400:  # больше или равно дню
            days = interval_seconds // 86400
            schedule.every(days).days.do(lambda: asyncio.create_task(callback()))
        elif interval_seconds >= 3600:  # больше или равно часу
            hours = interval_seconds // 3600
            schedule.every(hours).hours.do(lambda: asyncio.create_task(callback()))
        elif interval_seconds >= 60:  # больше или равно минуте
            minutes = interval_seconds // 60
            schedule.every(minutes).minutes.do(lambda: asyncio.create_task(callback()))
        else:
            schedule.every(interval_seconds).seconds.do(lambda: asyncio.create_task(callback()))

        logger.info(f"➕ Добавлена пользовательская задача с интервалом {interval_seconds} сек")


async def test_scheduler(bot_instance):
    """Тестирование планировщика"""
    scheduler = SimpleScheduler(bot_instance)
    await scheduler.start()

    # Тест: немедленная отправка
    await scheduler.send_daily_gif_message()

    return scheduler

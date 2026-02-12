"""
Упрощенный планировщик задач без зависимости от внешней базы данных.
Использует встроенные средства Python для планирования задач.
"""

import asyncio
import logging
import time
from datetime import datetime
from datetime import timedelta

import pytz

from config import settings
from services import subscriber_service, gif_service
from telegram_utils import send_text, send_gif
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone("Europe/Moscow")

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

    async def start(self):
        """Запускает планировщик"""
        if not self.is_running:
            self.is_running = True

            # Сразу проверяем в логах, когда он хочет запустить 8:30
            self._log_next_run_info(8, 30)

            # Планируем ежедневные задачи
            # self.schedule_daily_tasks()
            main_task = asyncio.create_task(self._daily_loop())
            self._scheduled_tasks.append(main_task)

            # В debug-режиме добавляем тестовые задачи
            if self.debug_mode:
                logger.warning("🔧 Включен DEBUG-режим: запущен тестовый цикл сообщений")

                # Вариант А: Отладочный цикл
                # debug_task = asyncio.create_task(self._debug_loop())
                # self._scheduled_tasks.append(debug_task)

                # Вариант Б: Тест "Умного ожидания"
                smart_test_task = asyncio.create_task(self._test_smart_loop())
                self._scheduled_tasks.append(smart_test_task)

            logger.info("🚀 Планировщик запущен")

    async def stop(self):
        """Останавливает планировщик"""
        self.is_running = False
        for task in self._scheduled_tasks:
            task.cancel()

        # Ждем завершения задач
        await asyncio.gather(*self._scheduled_tasks, return_exceptions=True)
        self._scheduled_tasks.clear()
        logger.info("🛑 Планировщик остановлен")

    async def run_daily_mailing(self):
        """Логика ежедневной рассылки"""
        logger.info("🚀 Начинаю ежедневную рассылку...")

        # 1. Получаем данные
        # isoweekday: 1 (Пн) - 7 (Вс)
        today_idx = datetime.now(TIMEZONE).isoweekday()
        gif = await gif_service.find_random_gif_by_day(today_idx)
        subscribers = await subscriber_service.get_all_subscriber_ids()

        if not subscribers:
            logger.warning("⚠️ Нет подписчиков для рассылки.")
            return

        greeting = self._get_greeting(today_idx)

        # 2. Рассылаем
        success_count = 0
        for chat_id in subscribers:
            try:
                if gif:
                    await send_gif(self.bot, chat_id, gif.file_id, greeting)
                else:
                    # Если гифки нет, шлем просто текст, чтобы не молчать
                    await send_text(self.bot, chat_id, f"{greeting}\n(Гифки на сегодня закончились 😔)")

                success_count += 1
                # Небольшая пауза, чтобы не словить лимиты Telegram при большой базе
                await asyncio.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ Не удалось отправить рассылку в {chat_id}: {e}")

        logger.info(f"✅ Рассылка завершена. Отправлено: {success_count}/{len(subscribers)}")

    async def send_daily_gif_message(self):
        """Ежедневная рассылка GIF в 8:30 утра"""
        try:
            logger.info("🚀 Начинаю ежедневную GIF рассылку...")

            today = self._get_today_day_of_week()
            chat_ids = await subscriber_service.get_all_subscriber_ids()

            # Ищем случайный GIF для сегодняшнего дня
            gif = await gif_service.find_random_gif_by_day(today)

            sent_count = 0
            failed_count = 0

            for chat_id in chat_ids:
                try:
                    if gif:
                        await send_gif(self.bot, chat_id, gif.file_id, self._get_greeting(today))
                    else:
                        await send_text(self.bot, chat_id, "😔 Гифки на сегодня закончились")

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

    async def send_debug_short_interval_message(self):
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
                await send_gif(self.bot, chat_id, gif.file_id,
                                       f"[Тест] {day_name} - {timestamp}\n"
                                       f"Тест планировщика с интервалом 30 сек")
                logger.debug(f"✅ Тестовая гифка отправлена в {chat_id} в {timestamp}")
            else:
                await send_text(self.bot, chat_id,
                                        f"[Тест {day_name}] Нет гифок для этого дня\n"
                                        f"Время: {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"❌ Ошибка в тестовой задаче: {e}")
            # При ошибке увеличиваем задержку
            self.request_delay = min(self.request_delay + 5, 60)

    async def send_test_gif(self, chat_id: int, day: int):
        """Отправляет тестовый GIF в указанный чат"""
        try:
            day_name = self._get_day_name(day)
            gif = await gif_service.find_random_gif_by_day(day)

            if gif:
                await send_gif(self.bot, chat_id, gif.file_id, f"[Тест] {day_name}")
                logger.info(f"✅ Тестовый GIF отправлен в чат {chat_id} для дня {day}. Время: {datetime.now(TIMEZONE)}")
                return True
            else:
                await send_text(self.bot, chat_id, f"[Тест {day_name}] В базе нет гифок для этого дня")
                logger.info(f"ℹ️ GIF для дня {day} не найден для чата {chat_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового GIF в чат {chat_id}: {e}")
            await send_text(self.bot, chat_id, "❌ Произошла ошибка при отправке теста")
            return False

    def _log_next_run_info(self, hour, minute):
        """
        Просто выводит в лог, когда планируется следующая задача.
        Помогает сразу понять, верно ли время сервера и часовой пояс.
        """
        wait_seconds = self._get_seconds_until_target_time(hour, minute)
        run_time = datetime.now(TIMEZONE) + timedelta(seconds=wait_seconds)

        logger.info(
            f"📊 [TEST INFO] Сейчас: {datetime.now(TIMEZONE).strftime('%H:%M:%S')}. "
            f"Задача запланирована на: {run_time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"(через {int(wait_seconds)} сек)"
        )

    async def _daily_loop(self):
        """
        Главный цикл. Вычисляет время до следующей рассылки и спит.
        """
        while self.is_running:
            # 1. Вычисляем секунды до следующего запуска (например, 08:30)
            wait_seconds = self._get_seconds_until_target_time(hour=8, minute=30)

            hours = int(wait_seconds // 3600)
            minutes = int((wait_seconds % 3600) // 60)
            logger.info(f"💤 Следующая рассылка через {hours}ч {minutes}мин")

            try:
                # 2. Спим до нужного времени
                await asyncio.sleep(wait_seconds)

                # 3. Выполняем рассылку
                if self.is_running:
                    await self.run_daily_mailing()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле планировщика: {e}")
                # Если произошла ошибка, ждем немного, чтобы не уйти в бесконечный цикл ошибок
                await asyncio.sleep(60)

    async def _debug_loop(self):
        """Запускает тестовые задачи в debug-режиме"""
        while self.is_running and self.debug_mode:
            try:
                # Тестовая задача каждые 30 секунд
                await self.send_debug_short_interval_message()
                await asyncio.sleep(30)

                # Тестовая задача каждые 2 минуты
                await self.send_daily_gif_message() # используется в debug целях
                await asyncio.sleep(120)  # 2 минуты

            except Exception as e:
                logger.error(f"❌ Ошибка в отладочных задачах: {e}")
                await asyncio.sleep(30)

    async def _test_smart_loop(self):
        """
        Тестовый цикл, который использует 'умное ожидание',
        но целится в начало каждой следующей минуты.
        """
        logger.warning("⏱ Запущен тест УМНОГО планировщика (срабатывает каждую минуту в :00)")

        while self.is_running and self.debug_mode:
            # 1. Вычисляем время: "Следующая минута, 00 секунд"
            now = datetime.now(TIMEZONE)
            next_run = now + timedelta(minutes=1)
            target_hour = next_run.hour
            target_minute = next_run.minute

            wait_seconds = self._get_seconds_until_target_time(target_hour, target_minute)

            logger.info(f"🧪 Тест: Жду {wait_seconds:.1f} сек до {target_hour:02d}:{target_minute:02d}:00")

            try:
                # 2. Спим (тестируем asyncio.sleep)
                await asyncio.sleep(wait_seconds)

                # 3. Выполняем рассылку (тестируем отправку)
                logger.info("🧪 Тест: Время пришло! Запускаю рассылку...")

                chat_ids = await subscriber_service.get_all_subscriber_ids()
                if chat_ids:
                    await self.send_test_gif(chat_ids[0], day=self._get_today_day_of_week())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в тестовом цикле: {e}")
                await asyncio.sleep(10)

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

    def _get_greeting(self, day_idx: int) -> str:
        """Текстовки для дней недели"""
        greetings = {
            1: "Тяжелый понедельник? Терпи.",
            2: "Вторник - это почти среда! 🌭",
            3: "Среда - маленькая пятница! 🐸",
            4: "Четверг - рыбный день (или пивной)! 🐟",
            5: "УРА! ПЯТНИЦА! 🎉",
            6: "Суббота! Отдыхаем! 📺",
            7: "Воскресенье... Завтра на завод 😢"
        }
        return greetings.get(day_idx, "Хорошего дня! 👋")

    def _get_seconds_until_target_time(self, hour: int, minute: int) -> float:
        """Считает разницу в секундах между 'сейчас' и следующим 'hour:minute'"""
        now = datetime.now(TIMEZONE)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if target <= now:
            # Если время на сегодня уже прошло, планируем на завтра
            target += timedelta(days=1)

        return (target - now).total_seconds()
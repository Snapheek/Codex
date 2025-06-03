"""
Telegram бот для отправки уведомлений о новых проектах Kwork.ru
Асинхронная реализация с группировкой сообщений и retry логикой
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
import traceback

from telegram import Bot
from telegram.error import TelegramError, BadRequest, TimedOut, NetworkError, RetryAfter
from loguru import logger

from core.models import Project, ProjectStatus
from utils import (
    retry_async, 
    RetryConfig, 
    STANDARD_RETRY,
    get_rate_limiter, 
    RateLimitConfig,
    get_logger
)
from config.settings import Settings, get_settings
from .formatter import TelegramMessageFormatter
from .templates import MessageTemplates


class TelegramNotifier:
    """
    Класс для отправки уведомлений в Telegram о новых проектах
    """
    
    def __init__(
        self, 
        bot_token: str,
        settings: Optional[Settings] = None,
        retry_config: Optional[RetryConfig] = None
    ):
        """
        Инициализация Telegram бота
        
        Args:
            bot_token: Токен Telegram бота
            settings: Настройки приложения
            retry_config: Конфигурация retry логики
        """
        self.bot_token = bot_token
        self.settings = settings or get_settings()
        self.logger = get_logger("telegram_bot")
        
        # Инициализируем бота
        self.bot = Bot(token=bot_token)
        
        # Конфигурации
        self.retry_config = retry_config or STANDARD_RETRY
        
        # Rate limiter для Telegram API (30 сообщений в секунду максимум)
        telegram_rate_config = RateLimitConfig(
            requests_per_second=20.0,  # Немного меньше лимита для безопасности
            requests_per_minute=600.0,
            requests_per_hour=10000.0,
            min_delay=0.05,  # 50мс между запросами
            max_delay=30.0
        )
        self.rate_limiter = get_rate_limiter("telegram.org", telegram_rate_config)
        
        # Форматтер сообщений
        self.formatter = TelegramMessageFormatter()
        self.templates = MessageTemplates()
        
        # Статистика отправки
        self.stats = {
            "messages_sent": 0,
            "messages_failed": 0,
            "grouped_messages": 0,
            "total_projects_sent": 0,
            "start_time": time.time(),
            "last_send_time": None
        }
        
        # Настройки группировки
        self.max_projects_per_message = 5
        self.group_timeout = 30  # секунд для накопления проектов перед отправкой
        
        # Кэш для группировки сообщений
        self._pending_projects: Dict[str, List[Project]] = {}
        self._pending_tasks: Dict[str, asyncio.Task] = {}
        
        self.logger.info(f"Telegram бот инициализирован. Token: {bot_token[:10]}...")
    
    async def verify_connection(self) -> bool:
        """
        Проверка подключения к Telegram API
        
        Returns:
            bool: True если подключение успешно
        """
        try:
            await self.rate_limiter.acquire()
            me = await self.bot.get_me()
            self.logger.success(f"Telegram бот подключен: @{me.username}")
            await self.rate_limiter.report_success()
            return True
            
        except Exception as e:
            await self.rate_limiter.report_error()
            self.logger.error(f"Ошибка подключения к Telegram API: {e}")
            return False
    
    async def _send_message_with_retry(
        self, 
        chat_id: Union[str, int], 
        text: str,
        parse_mode: str = "MarkdownV2",
        disable_web_page_preview: bool = True
    ) -> bool:
        """
        Отправка сообщения с retry логикой
        
        Args:
            chat_id: ID чата или username
            text: Текст сообщения
            parse_mode: Режим парсинга (Markdown V2)
            disable_web_page_preview: Отключить превью ссылок
            
        Returns:
            bool: True если сообщение отправлено успешно
        """
        async def _send():
            # Rate limiting
            await self.rate_limiter.acquire()
            
            try:
                # Отправляем сообщение
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                
                await self.rate_limiter.report_success()
                self.stats["messages_sent"] += 1
                self.stats["last_send_time"] = time.time()
                
                self.logger.debug(f"Сообщение отправлено в чат {chat_id}")
                return True
                
            except RetryAfter as e:
                # Telegram просит подождать
                wait_time = e.retry_after + 1
                self.logger.warning(f"Rate limit от Telegram. Ждем {wait_time} секунд")
                await asyncio.sleep(wait_time)
                await self.rate_limiter.report_error(429)
                raise e
                
            except (TimedOut, NetworkError) as e:
                # Сетевые ошибки - можно повторить
                await self.rate_limiter.report_error()
                self.logger.warning(f"Сетевая ошибка Telegram: {e}")
                raise e
                
            except BadRequest as e:
                # Ошибки в запросе - не повторяем
                await self.rate_limiter.report_error(400)
                self.logger.error(f"Некорректный запрос к Telegram: {e}")
                return False
                
            except TelegramError as e:
                # Другие ошибки Telegram
                await self.rate_limiter.report_error()
                self.logger.error(f"Ошибка Telegram API: {e}")
                raise e
        
        try:
            return await retry_async(_send, config=self.retry_config)
        except Exception as e:
            self.stats["messages_failed"] += 1
            self.logger.error(f"Не удалось отправить сообщение после всех попыток: {e}")
            return False
    
    async def send_project_notification(
        self, 
        project: Project, 
        chat_id: Union[str, int],
        use_grouping: bool = True
    ) -> bool:
        """
        Отправка уведомления о новом проекте
        
        Args:
            project: Объект проекта
            chat_id: ID чата для отправки
            use_grouping: Использовать группировку сообщений
            
        Returns:
            bool: True если уведомление отправлено успешно
        """
        try:
            if use_grouping:
                # Добавляем проект в очередь группировки
                return await self._add_to_group(project, chat_id)
            else:
                # Отправляем сразу
                message_text = self.formatter.format_single_project(project)
                success = await self._send_message_with_retry(chat_id, message_text)
                
                if success:
                    self.stats["total_projects_sent"] += 1
                    self.logger.info(f"Отправлено уведомление о проекте: {project.title[:50]}...")
                
                return success
                
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления о проекте {project.external_id}: {e}")
            return False
    
    async def _add_to_group(self, project: Project, chat_id: Union[str, int]) -> bool:
        """
        Добавление проекта в группу для отправки
        
        Args:
            project: Проект для добавления
            chat_id: ID чата
            
        Returns:
            bool: True если проект добавлен в группу
        """
        chat_key = str(chat_id)
        
        # Инициализируем группу если нужно
        if chat_key not in self._pending_projects:
            self._pending_projects[chat_key] = []
        
        # Добавляем проект
        self._pending_projects[chat_key].append(project)
        
        # Проверяем нужно ли отправить группу
        should_send = (
            len(self._pending_projects[chat_key]) >= self.max_projects_per_message
        )
        
        if should_send:
            # Отправляем группу немедленно
            await self._send_grouped_projects(chat_id)
        else:
            # Планируем отправку через таймаут
            await self._schedule_group_send(chat_id)
        
        return True
    
    async def _schedule_group_send(self, chat_id: Union[str, int]) -> None:
        """
        Планирование отправки группы проектов через таймаут
        
        Args:
            chat_id: ID чата
        """
        chat_key = str(chat_id)
        
        # Отменяем предыдущую задачу если есть
        if chat_key in self._pending_tasks:
            self._pending_tasks[chat_key].cancel()
        
        # Создаем новую задачу
        async def delayed_send():
            await asyncio.sleep(self.group_timeout)
            await self._send_grouped_projects(chat_id)
        
        self._pending_tasks[chat_key] = asyncio.create_task(delayed_send())
    
    async def _send_grouped_projects(self, chat_id: Union[str, int]) -> bool:
        """
        Отправка сгруппированных проектов
        
        Args:
            chat_id: ID чата
            
        Returns:
            bool: True если группа отправлена успешно
        """
        chat_key = str(chat_id)
        
        # Получаем проекты для отправки
        projects = self._pending_projects.get(chat_key, [])
        if not projects:
            return True
        
        # Очищаем очередь
        self._pending_projects[chat_key] = []
        
        # Отменяем задачу отложенной отправки
        if chat_key in self._pending_tasks:
            self._pending_tasks[chat_key].cancel()
            del self._pending_tasks[chat_key]
        
        try:
            # Форматируем групповое сообщение
            if len(projects) == 1:
                message_text = self.formatter.format_single_project(projects[0])
            else:
                message_text = self.formatter.format_grouped_projects(projects)
            
            # Отправляем сообщение
            success = await self._send_message_with_retry(chat_id, message_text)
            
            if success:
                self.stats["grouped_messages"] += 1
                self.stats["total_projects_sent"] += len(projects)
                self.logger.info(f"Отправлена группа из {len(projects)} проектов в чат {chat_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки группы проектов в чат {chat_id}: {e}")
            return False
    
    async def send_grouped_notifications(
        self,
        projects: List[Project],
        chat_id: Union[str, int]
    ) -> bool:
        """
        Отправка группы проектов одним сообщением
        
        Args:
            projects: Список проектов
            chat_id: ID чата
            
        Returns:
            bool: True если уведомления отправлены успешно
        """
        if not projects:
            return True
        
        try:
            # Разбиваем на группы по max_projects_per_message
            project_groups = [
                projects[i:i + self.max_projects_per_message]
                for i in range(0, len(projects), self.max_projects_per_message)
            ]
            
            success_count = 0
            
            for group in project_groups:
                if len(group) == 1:
                    message_text = self.formatter.format_single_project(group[0])
                else:
                    message_text = self.formatter.format_grouped_projects(group)
                
                success = await self._send_message_with_retry(chat_id, message_text)
                
                if success:
                    success_count += 1
                    self.stats["total_projects_sent"] += len(group)
                
                # Небольшая задержка между группами
                if len(project_groups) > 1:
                    await asyncio.sleep(1)
            
            self.logger.info(f"Отправлено {success_count}/{len(project_groups)} групп проектов")
            return success_count == len(project_groups)
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки групповых уведомлений: {e}")
            return False
    
    async def send_stats(
        self,
        chat_id: Union[str, int],
        parsing_stats: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Отправка статистики работы парсера
        
        Args:
            chat_id: ID чата
            parsing_stats: Статистика парсинга
            
        Returns:
            bool: True если статистика отправлена
        """
        try:
            message_text = self.formatter.format_stats_message(self.stats, parsing_stats)
            return await self._send_message_with_retry(chat_id, message_text)
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки статистики: {e}")
            return False
    
    async def send_error_notification(
        self,
        chat_id: Union[str, int],
        error_message: str,
        error_details: Optional[str] = None
    ) -> bool:
        """
        Отправка уведомления об ошибке
        
        Args:
            chat_id: ID чата
            error_message: Сообщение об ошибке
            error_details: Детали ошибки
            
        Returns:
            bool: True если уведомление отправлено
        """
        try:
            message_text = self.formatter.format_error_message(error_message, error_details)
            return await self._send_message_with_retry(chat_id, message_text)
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления об ошибке: {e}")
            return False
    
    async def send_startup_notification(self, chat_id: Union[str, int]) -> bool:
        """
        Отправка уведомления о запуске парсера
        
        Args:
            chat_id: ID чата
            
        Returns:
            bool: True если уведомление отправлено
        """
        try:
            message_text = self.formatter.format_startup_message()
            return await self._send_message_with_retry(chat_id, message_text)
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления о запуске: {e}")
            return False
    
    async def flush_pending_groups(self) -> None:
        """
        Принудительная отправка всех ожидающих групп
        """
        tasks = []
        
        for chat_id in list(self._pending_projects.keys()):
            if self._pending_projects[chat_id]:
                task = asyncio.create_task(self._send_grouped_projects(chat_id))
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self.logger.info(f"Принудительно отправлено {len(tasks)} ожидающих групп")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики работы бота
        
        Returns:
            Dict: Статистика отправки сообщений
        """
        stats = self.stats.copy()
        
        # Добавляем информацию о времени работы
        if stats["start_time"]:
            stats["uptime"] = time.time() - stats["start_time"]
        
        # Добавляем информацию о pending группах
        stats["pending_groups"] = len(self._pending_projects)
        stats["pending_projects"] = sum(len(projects) for projects in self._pending_projects.values())
        
        # Добавляем статистику rate limiter
        stats["rate_limiter"] = self.rate_limiter.get_stats()
        
        return stats
    
    async def close(self) -> None:
        """Закрытие бота и отправка всех ожидающих сообщений"""
        try:
            # Отправляем все ожидающие группы
            await self.flush_pending_groups()
            
            # Отменяем все pending задачи
            for task in self._pending_tasks.values():
                task.cancel()
            
            self._pending_tasks.clear()
            self._pending_projects.clear()
            
            self.logger.info("Telegram бот закрыт")
            
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии Telegram бота: {e}")


# Утилитарные функции для быстрого использования

async def send_telegram_notification(
    bot_token: str,
    chat_id: Union[str, int],
    projects: List[Project],
    settings: Optional[Settings] = None
) -> bool:
    """
    Быстрая отправка уведомлений в Telegram
    
    Args:
        bot_token: Токен бота
        chat_id: ID чата
        projects: Список проектов
        settings: Настройки приложения
        
    Returns:
        bool: True если все уведомления отправлены
    """
    notifier = TelegramNotifier(bot_token, settings)
    
    try:
        # Проверяем подключение
        if not await notifier.verify_connection():
            return False
        
        # Отправляем уведомления
        return await notifier.send_grouped_notifications(projects, chat_id)
        
    finally:
        await notifier.close()


async def send_telegram_error(
    bot_token: str,
    chat_id: Union[str, int],
    error_message: str,
    error_details: Optional[str] = None
) -> bool:
    """
    Быстрая отправка уведомления об ошибке
    
    Args:
        bot_token: Токен бота
        chat_id: ID чата
        error_message: Сообщение об ошибке
        error_details: Детали ошибки
        
    Returns:
        bool: True если уведомление отправлено
    """
    notifier = TelegramNotifier(bot_token)
    
    try:
        return await notifier.send_error_notification(chat_id, error_message, error_details)
    finally:
        await notifier.close() 
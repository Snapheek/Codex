"""
Форматирование сообщений для Telegram
Создание красивых уведомлений с эмодзи и Markdown разметкой
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from core.models import Project, PriceType
from .templates import MessageTemplates


class TelegramMessageFormatter:
    """
    Класс для форматирования сообщений для отправки в Telegram
    """
    
    def __init__(self):
        self.templates = MessageTemplates()
    
    def _escape_markdown_v2(self, text: str) -> str:
        """
        Экранирование специальных символов для Markdown V2
        
        Args:
            text: Исходный текст
            
        Returns:
            str: Экранированный текст
        """
        if not text:
            return ""
        
        # Символы, которые нужно экранировать в Markdown V2
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        escaped_text = str(text)
        for char in escape_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        
        return escaped_text
    
    def _format_price(self, project: Project) -> str:
        """
        Форматирование цены проекта
        
        Args:
            project: Объект проекта
            
        Returns:
            str: Отформатированная цена
        """
        if project.price is None:
            if project.price_type == PriceType.NEGOTIABLE:
                return "💬 Договорная"
            else:
                return "💬 Не указана"
        
        # Форматируем число с разделителями тысяч
        formatted_price = f"{int(project.price):,}".replace(",", " ")
        currency_symbol = "₽" if project.currency == "RUB" else project.currency
        
        price_emoji = self._get_price_emoji(project.price)
        type_text = self._get_price_type_text(project.price_type)
        
        return f"{price_emoji} **{formatted_price} {currency_symbol}**{type_text}"
    
    def _get_price_emoji(self, price: Optional[float]) -> str:
        """Получение эмодзи в зависимости от цены"""
        if price is None:
            return "💬"
        elif price < 5000:
            return "💵"
        elif price < 20000:
            return "💰"
        elif price < 50000:
            return "💎"
        else:
            return "🏆"
    
    def _get_price_type_text(self, price_type: PriceType) -> str:
        """Получение текста типа цены"""
        type_mapping = {
            PriceType.FIXED: "",
            PriceType.HOURLY: " /час",
            PriceType.RANGE: " \\(диапазон\\)",
            PriceType.NEGOTIABLE: ""
        }
        return type_mapping.get(price_type, "")
    
    def _format_date(self, date_created: datetime) -> str:
        """
        Форматирование даты создания проекта
        
        Args:
            date_created: Дата создания
            
        Returns:
            str: Отформатированная дата
        """
        now = datetime.utcnow()
        diff = now - date_created
        
        if diff.total_seconds() < 3600:  # Меньше часа
            minutes = int(diff.total_seconds() / 60)
            if minutes < 1:
                return "📅 Только что"
            elif minutes == 1:
                return "📅 1 минуту назад"
            elif minutes < 5:
                return f"📅 {minutes} минуты назад"
            else:
                return f"📅 {minutes} минут назад"
        
        elif diff.total_seconds() < 86400:  # Меньше дня
            hours = int(diff.total_seconds() / 3600)
            if hours == 1:
                return "📅 1 час назад"
            elif hours < 5:
                return f"📅 {hours} часа назад"
            else:
                return f"📅 {hours} часов назад"
        
        elif diff.days == 1:
            return "📅 Вчера"
        
        elif diff.days < 7:
            return f"📅 {diff.days} дня назад"
        
        else:
            return f"📅 {date_created.strftime('%d.%m.%Y')}"
    
    def _format_stats(self, project: Project) -> str:
        """
        Форматирование статистики проекта
        
        Args:
            project: Объект проекта
            
        Returns:
            str: Отформатированная статистика
        """
        stats_parts = []
        
        # Количество откликов
        if project.responses_count > 0:
            if project.responses_count == 1:
                stats_parts.append(f"👥 {project.responses_count} отклик")
            elif project.responses_count < 5:
                stats_parts.append(f"👥 {project.responses_count} отклика")
            else:
                stats_parts.append(f"👥 {project.responses_count} откликов")
        else:
            stats_parts.append("👥 Нет откликов")
        
        # Количество просмотров
        if project.views_count > 0:
            stats_parts.append(f"👀 {project.views_count}")
        
        return " • ".join(stats_parts) if stats_parts else ""
    
    def _format_description(self, description: str, max_length: int = 200) -> str:
        """
        Форматирование описания проекта
        
        Args:
            description: Описание проекта
            max_length: Максимальная длина
            
        Returns:
            str: Отформатированное описание
        """
        if not description:
            return "📄 Описание не указано"
        
        # Очищаем и обрезаем описание
        clean_desc = re.sub(r'\s+', ' ', description.strip())
        
        if len(clean_desc) <= max_length:
            return f"📄 {self._escape_markdown_v2(clean_desc)}"
        
        # Обрезаем по словам
        words = clean_desc.split()
        truncated = ""
        
        for word in words:
            if len(truncated + word + " ") <= max_length - 3:
                truncated += word + " "
            else:
                break
        
        truncated = truncated.strip()
        if truncated:
            return f"📄 {self._escape_markdown_v2(truncated)}\\.\\.\\."
        else:
            return f"📄 {self._escape_markdown_v2(clean_desc[:max_length-3])}\\.\\.\\."
    
    def _format_category_and_tags(self, project: Project) -> str:
        """
        Форматирование категории и тегов
        
        Args:
            project: Объект проекта
            
        Returns:
            str: Отформатированная категория и теги
        """
        parts = []
        
        # Категория
        if project.category:
            parts.append(f"🏷️ {self._escape_markdown_v2(project.category)}")
        
        # Теги (показываем только первые 3)
        if project.tags:
            visible_tags = project.tags[:3]
            tag_text = ", ".join(self._escape_markdown_v2(tag) for tag in visible_tags)
            
            if len(project.tags) > 3:
                tag_text += f" \\+{len(project.tags) - 3}"
            
            parts.append(f"🔖 {tag_text}")
        
        return " • ".join(parts) if parts else ""
    
    def _create_project_link(self, project: Project) -> str:
        """
        Создание ссылки на проект
        
        Args:
            project: Объект проекта
            
        Returns:
            str: Markdown ссылка
        """
        if project.link:
            return f"[🔗 Открыть проект]({project.link})"
        else:
            return "🔗 Ссылка недоступна"
    
    def format_single_project(self, project: Project) -> str:
        """
        Форматирование одного проекта
        
        Args:
            project: Объект проекта
            
        Returns:
            str: Отформатированное сообщение
        """
        # Заголовок
        title = self._escape_markdown_v2(project.title[:100])
        header = f"🆕 **Новый проект на Kwork\\!**\n\n"
        
        # Основная информация
        project_title = f"📝 **{title}**\n"
        price_info = f"{self._format_price(project)}\n"
        date_info = f"{self._format_date(project.date_created)}\n"
        
        # Статистика
        stats = self._format_stats(project)
        stats_line = f"{stats}\n" if stats else ""
        
        # Описание
        description = self._format_description(project.description)
        description_line = f"{description}\n"
        
        # Категория и теги
        category_tags = self._format_category_and_tags(project)
        category_line = f"{category_tags}\n" if category_tags else ""
        
        # Автор
        author_line = ""
        if project.author:
            escaped_author = self._escape_markdown_v2(project.author)
            author_line = f"👤 **Автор:** {escaped_author}\n"
        
        # Ссылка
        link = self._create_project_link(project)
        link_line = f"\n{link}"
        
        # Собираем сообщение
        message = (
            header +
            project_title +
            price_info +
            date_info +
            stats_line +
            description_line +
            category_line +
            author_line +
            link_line
        )
        
        return message
    
    def format_grouped_projects(self, projects: List[Project]) -> str:
        """
        Форматирование группы проектов
        
        Args:
            projects: Список проектов
            
        Returns:
            str: Отформатированное сообщение
        """
        if not projects:
            return ""
        
        if len(projects) == 1:
            return self.format_single_project(projects[0])
        
        # Заголовок группы
        count = len(projects)
        if count < 5:
            header = f"🆕 **{count} новых проекта на Kwork\\!**\n\n"
        else:
            header = f"🆕 **{count} новых проектов на Kwork\\!**\n\n"
        
        # Форматируем каждый проект кратко
        project_lines = []
        
        for i, project in enumerate(projects, 1):
            title = self._escape_markdown_v2(project.title[:80])
            price = self._format_price(project).replace("**", "*")  # Убираем жирный шрифт для компактности
            
            # Создаем компактную строку
            line = f"{i}\\. **{title}**\n"
            line += f"   {price}"
            
            if project.responses_count > 0:
                line += f" • 👥 {project.responses_count}"
            
            if project.link:
                line += f" • [🔗 Открыть]({project.link})"
            
            project_lines.append(line)
        
        # Собираем сообщение
        message = header + "\n\n".join(project_lines)
        
        # Добавляем общую статистику
        total_responses = sum(p.responses_count for p in projects)
        avg_price = sum(p.price for p in projects if p.price) / len([p for p in projects if p.price])
        
        stats_line = f"\n\n📊 **Статистика:**"
        if total_responses > 0:
            stats_line += f" {total_responses} откликов"
        
        if avg_price:
            formatted_avg = f"{int(avg_price):,}".replace(",", " ")
            stats_line += f" • средняя цена {formatted_avg} ₽"
        
        message += stats_line
        
        return message
    
    def format_stats_message(
        self, 
        bot_stats: Dict[str, Any], 
        parsing_stats: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Форматирование сообщения со статистикой
        
        Args:
            bot_stats: Статистика бота
            parsing_stats: Статистика парсинга
            
        Returns:
            str: Отформатированное сообщение
        """
        message = "📊 **Статистика работы парсера Kwork**\n\n"
        
        # Статистика бота
        if bot_stats:
            message += "🤖 **Telegram бот:**\n"
            message += f"• Сообщений отправлено: {bot_stats.get('messages_sent', 0)}\n"
            message += f"• Проектов отправлено: {bot_stats.get('total_projects_sent', 0)}\n"
            message += f"• Групповых сообщений: {bot_stats.get('grouped_messages', 0)}\n"
            
            if bot_stats.get('messages_failed', 0) > 0:
                message += f"• Ошибок: {bot_stats['messages_failed']}\n"
            
            uptime = bot_stats.get('uptime', 0)
            if uptime > 0:
                hours = int(uptime / 3600)
                minutes = int((uptime % 3600) / 60)
                message += f"• Время работы: {hours}ч {minutes}м\n"
            
            message += "\n"
        
        # Статистика парсинга
        if parsing_stats:
            message += "🔍 **Парсер:**\n"
            message += f"• Страниц обработано: {parsing_stats.get('pages_parsed', 0)}\n"
            message += f"• Проектов найдено: {parsing_stats.get('projects_found', 0)}\n"
            message += f"• Новых проектов: {parsing_stats.get('projects_new', 0)}\n"
            
            if parsing_stats.get('errors', 0) > 0:
                message += f"• Ошибок: {parsing_stats['errors']}\n"
            
            avg_time = parsing_stats.get('avg_page_time', 0)
            if avg_time > 0:
                message += f"• Среднее время страницы: {avg_time:.1f}с\n"
        
        # Время генерации отчета
        current_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M")
        message += f"\n🕐 Отчет сгенерирован: {current_time}"
        
        return message
    
    def format_error_message(self, error_message: str, error_details: Optional[str] = None) -> str:
        """
        Форматирование сообщения об ошибке
        
        Args:
            error_message: Основное сообщение об ошибке
            error_details: Детали ошибки
            
        Returns:
            str: Отформатированное сообщение
        """
        message = "🚨 **Ошибка в парсере Kwork**\n\n"
        
        # Основное сообщение
        escaped_error = self._escape_markdown_v2(error_message)
        message += f"❌ {escaped_error}\n"
        
        # Детали ошибки
        if error_details:
            escaped_details = self._escape_markdown_v2(error_details[:500])  # Ограничиваем длину
            message += f"\n📝 **Детали:**\n`{escaped_details}`\n"
        
        # Время ошибки
        current_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M:%S")
        message += f"\n🕐 Время: {current_time}"
        
        return message
    
    def format_startup_message(self) -> str:
        """
        Форматирование сообщения о запуске
        
        Returns:
            str: Отформатированное сообщение
        """
        current_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M:%S")
        
        message = "🚀 **Парсер Kwork запущен\\!**\n\n"
        message += "✅ Система инициализирована\n"
        message += "🔍 Мониторинг новых проектов активен\n"
        message += "📨 Уведомления включены\n\n"
        message += f"🕐 Время запуска: {current_time}"
        
        return message
    
    def format_shutdown_message(self) -> str:
        """
        Форматирование сообщения о завершении работы
        
        Returns:
            str: Отформатированное сообщение
        """
        current_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M:%S")
        
        message = "🛑 **Парсер Kwork остановлен**\n\n"
        message += "📴 Мониторинг приостановлен\n"
        message += "💾 Данные сохранены\n\n"
        message += f"🕐 Время остановки: {current_time}"
        
        return message 
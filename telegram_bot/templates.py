"""
Шаблоны сообщений для Telegram бота
Предустановленные шаблоны для различных типов уведомлений
"""

from typing import Dict, Any


class MessageTemplates:
    """
    Коллекция шаблонов сообщений для Telegram бота
    """
    
    # Основные шаблоны проектов
    single_project_template = """🆕 **Новый проект на Kwork!**

📝 **{title}**
{price}
📅 **{date}**
👥 **{responses}**
📄 **{description}**
🔗 [Открыть проект]({link})"""
    
    grouped_projects_header = "🆕 **{count} новых проектов на Kwork!**\n\n"
    
    grouped_project_item = """{index}. **{title}**
   {price} • 👥 {responses} • [🔗 Открыть]({link})"""
    
    # Шаблоны уведомлений системы
    startup_template = """🚀 **Парсер Kwork запущен!**

✅ Система инициализирована
🔍 Мониторинг новых проектов активен  
📨 Уведомления включены

🕐 Время запуска: {timestamp}"""
    
    shutdown_template = """🛑 **Парсер Kwork остановлен**

📴 Мониторинг приостановлен
💾 Данные сохранены

🕐 Время остановки: {timestamp}"""
    
    error_template = """🚨 **Ошибка в парсере Kwork**

❌ {error_message}

🕐 Время: {timestamp}"""
    
    error_with_details_template = """🚨 **Ошибка в парсере Kwork**

❌ {error_message}

📝 **Детали:**
`{error_details}`

🕐 Время: {timestamp}"""
    
    # Шаблоны статистики
    stats_template = """📊 **Статистика работы парсера Kwork**

🤖 **Telegram бот:**
• Сообщений отправлено: {messages_sent}
• Проектов отправлено: {projects_sent}  
• Групповых сообщений: {grouped_messages}
• Время работы: {uptime}

🔍 **Парсер:**
• Страниц обработано: {pages_parsed}
• Проектов найдено: {projects_found}
• Новых проектов: {projects_new}
• Среднее время страницы: {avg_time}с

🕐 Отчет сгенерирован: {timestamp}"""
    
    # Шаблоны для различных типов проектов
    urgent_project_template = """🔥 **СРОЧНЫЙ проект на Kwork!**

📝 **{title}**
{price}
📅 **{date}** ⏰ **СРОЧНО!**
👥 **{responses}**
📄 **{description}**
🔗 [Открыть проект]({link})"""
    
    high_budget_template = """💎 **ДОРОГОЙ проект на Kwork!**

📝 **{title}**
{price} 💰💰💰
📅 **{date}**
👥 **{responses}**
📄 **{description}**
🔗 [Открыть проект]({link})"""
    
    # Шаблоны для разных ценовых категорий
    price_templates = {
        "low": "💵 **{price} {currency}**",
        "medium": "💰 **{price} {currency}**", 
        "high": "💎 **{price} {currency}**",
        "premium": "🏆 **{price} {currency}**",
        "negotiable": "💬 **Договорная**"
    }
    
    # Шаблоны для разных категорий
    category_emojis = {
        "программирование": "💻",
        "дизайн": "🎨", 
        "тексты": "📝",
        "маркетинг": "📈",
        "видео": "🎬",
        "аудио": "🎵",
        "фото": "📷",
        "переводы": "🌐",
        "продвижение": "🚀",
        "консультации": "💡",
        "другое": "📋"
    }
    
    # Шаблоны времени публикации
    time_templates = {
        "just_now": "📅 Только что",
        "minutes_ago": "📅 {minutes} минут назад",
        "hour_ago": "📅 1 час назад", 
        "hours_ago": "📅 {hours} часов назад",
        "yesterday": "📅 Вчера",
        "days_ago": "📅 {days} дней назад",
        "date": "📅 {date}"
    }
    
    # Шаблоны статуса откликов
    responses_templates = {
        "no_responses": "👥 Нет откликов",
        "one_response": "👥 1 отклик",
        "few_responses": "👥 {count} отклика", 
        "many_responses": "👥 {count} откликов",
        "hot_project": "🔥 {count} откликов (популярно!)"
    }
    
    # Кнопки и действия
    button_templates = {
        "view_project": "🔗 Открыть проект",
        "view_author": "👤 Профиль автора",
        "similar_projects": "🔍 Похожие проекты",
        "save_project": "💾 Сохранить",
        "share_project": "📤 Поделиться"
    }
    
    # Шаблоны для уведомлений о состоянии
    health_check_templates = {
        "healthy": "✅ **Парсер работает нормально**\n🕐 {timestamp}",
        "warning": "⚠️ **Парсер работает с предупреждениями**\n📝 {details}\n🕐 {timestamp}",
        "critical": "🔥 **Критическая ошибка парсера**\n❌ {details}\n🕐 {timestamp}",
        "recovering": "🔄 **Парсер восстанавливается**\n📝 {details}\n🕐 {timestamp}"
    }
    
    # Шаблоны для периодических отчетов
    daily_report_template = """📊 **Ежедневный отчет парсера Kwork**

📅 **{date}**

🔍 **За сегодня:**
• Найдено проектов: {projects_today}
• Новых проектов: {new_projects}
• Отправлено уведомлений: {notifications_sent}

💰 **Статистика цен:**
• Средняя цена: {avg_price} ₽
• Максимальная цена: {max_price} ₽
• Договорных проектов: {negotiable_count}

📈 **Популярные категории:**
{top_categories}

🕐 Отчет сгенерирован: {timestamp}"""
    
    weekly_report_template = """📊 **Недельный отчет парсера Kwork**

📅 **{week_period}**

🔍 **За неделю:**
• Найдено проектов: {projects_week}
• Новых проектов: {new_projects}
• Среднее в день: {avg_per_day}

💰 **Ценовая статистика:**
• Общая сумма проектов: {total_budget} ₽
• Средняя цена: {avg_price} ₽
• Самый дорогой проект: {max_price} ₽

📈 **Тренды:**
• Самый активный день: {most_active_day}
• Самая популярная категория: {top_category}

🕐 Отчет сгенерирован: {timestamp}"""
    
    # Шаблоны для предупреждений
    warning_templates = {
        "rate_limit": "⚠️ **Rate limit достигнут**\nПарсер замедлен до {delay} секунд между запросами",
        "too_many_errors": "⚠️ **Много ошибок парсинга**\nОшибок за последний час: {error_count}",
        "site_changed": "⚠️ **Возможные изменения на сайте**\nСелекторы могут требовать обновления",
        "connection_issues": "⚠️ **Проблемы с подключением**\nПроверьте интернет соединение",
        "disk_space": "⚠️ **Мало места на диске**\nСвободно: {free_space} MB"
    }
    
    # Специальные шаблоны для фильтрации
    filter_match_template = """🎯 **Проект подходит под ваши фильтры!**

📝 **{title}**
{price}
📅 **{date}**
🏷️ **Категория:** {category}
👥 **{responses}**
📄 **{description}**

✅ **Соответствует фильтрам:**
{matching_criteria}

🔗 [Открыть проект]({link})"""
    
    # Шаблоны для настроек
    settings_template = """⚙️ **Настройки парсера Kwork**

🔔 **Уведомления:**
• Групповые сообщения: {grouping_enabled}
• Максимум проектов в группе: {max_per_group}
• Таймаут группировки: {group_timeout}с

🎯 **Фильтры:**
• Минимальная цена: {min_price} ₽
• Максимальная цена: {max_price} ₽
• Категории: {categories}

⏱️ **Интервалы:**
• Проверка новых проектов: {check_interval}мин
• Отчеты: {report_interval}

🕐 Последнее обновление: {timestamp}"""


def get_category_emoji(category: str) -> str:
    """
    Получение эмодзи для категории проекта
    
    Args:
        category: Название категории
        
    Returns:
        str: Эмодзи для категории
    """
    templates = MessageTemplates()
    category_lower = category.lower() if category else ""
    
    # Ищем точное совпадение
    if category_lower in templates.category_emojis:
        return templates.category_emojis[category_lower]
    
    # Ищем частичное совпадение
    for key, emoji in templates.category_emojis.items():
        if key in category_lower or category_lower in key:
            return emoji
    
    # По умолчанию
    return templates.category_emojis["другое"]


def get_price_template(price: float) -> str:
    """
    Получение шаблона для цены в зависимости от суммы
    
    Args:
        price: Сумма проекта
        
    Returns:
        str: Шаблон цены
    """
    templates = MessageTemplates()
    
    if price < 5000:
        return templates.price_templates["low"]
    elif price < 20000:
        return templates.price_templates["medium"]
    elif price < 50000:
        return templates.price_templates["high"]
    else:
        return templates.price_templates["premium"]


def get_responses_template(count: int) -> str:
    """
    Получение шаблона для количества откликов
    
    Args:
        count: Количество откликов
        
    Returns:
        str: Шаблон для откликов
    """
    templates = MessageTemplates()
    
    if count == 0:
        return templates.responses_templates["no_responses"]
    elif count == 1:
        return templates.responses_templates["one_response"]
    elif count < 5:
        return templates.responses_templates["few_responses"].format(count=count)
    elif count < 10:
        return templates.responses_templates["many_responses"].format(count=count)
    else:
        return templates.responses_templates["hot_project"].format(count=count) 
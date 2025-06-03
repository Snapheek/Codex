"""
Модуль Telegram бота для уведомлений о проектах Kwork.ru

Содержит:
- TelegramNotifier - основной класс бота
- TelegramMessageFormatter - форматирование сообщений
- MessageTemplates - шаблоны сообщений
- Утилитарные функции для быстрой отправки
"""

from .bot import (
    TelegramNotifier,
    send_telegram_notification,
    send_telegram_error
)

from .formatter import TelegramMessageFormatter

from .templates import (
    MessageTemplates,
    get_category_emoji,
    get_price_template,
    get_responses_template
)

__all__ = [
    # Основной бот
    'TelegramNotifier',
    
    # Форматирование
    'TelegramMessageFormatter',
    
    # Шаблоны
    'MessageTemplates',
    'get_category_emoji',
    'get_price_template',
    'get_responses_template',
    
    # Утилитарные функции
    'send_telegram_notification',
    'send_telegram_error'
] 
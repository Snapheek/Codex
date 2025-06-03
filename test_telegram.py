#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы Telegram бота
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from core.models import Project, ProjectStatus, PriceType
from telegram_bot import TelegramNotifier, TelegramMessageFormatter, MessageTemplates
from utils import setup_logging, DEBUG_CONFIG, get_logger


def create_test_projects():
    """Создание тестовых проектов для отправки"""
    projects = []
    
    # Проект 1 - обычный
    project1 = Project(
        external_id="test_1",
        title="Разработка интернет-магазина на Django",
        description="Требуется создать современный интернет-магазин с каталогом товаров, корзиной, оплатой и админкой.",
        price=75000.0,
        price_type=PriceType.FIXED,
        currency="RUB",
        author="WebDeveloper123",
        category="Программирование",
        date_created=datetime.utcnow() - timedelta(minutes=15),
        responses_count=3,
        views_count=45,
        link="https://kwork.ru/projects/12345",
        tags=["Django", "Python", "Web"],
        skills_required=["Django", "PostgreSQL", "Bootstrap"],
        status=ProjectStatus.NEW
    )
    projects.append(project1)
    
    # Проект 2 - дорогой
    project2 = Project(
        external_id="test_2", 
        title="Создание мобильного приложения iOS/Android",
        description="Нужно разработать кроссплатформенное мобильное приложение для доставки еды с геолокацией.",
        price=250000.0,
        price_type=PriceType.FIXED,
        currency="RUB",
        author="MobileDevPro",
        category="Программирование",
        date_created=datetime.utcnow() - timedelta(minutes=5),
        responses_count=8,
        views_count=120,
        link="https://kwork.ru/projects/12346",
        tags=["React Native", "Mobile", "iOS", "Android"],
        skills_required=["React Native", "Firebase", "Maps API"],
        status=ProjectStatus.NEW
    )
    projects.append(project2)
    
    # Проект 3 - договорная цена
    project3 = Project(
        external_id="test_3",
        title="Дизайн логотипа и фирменного стиля",
        description="Ищу креативного дизайнера для создания логотипа стартапа в сфере IT.",
        price=None,
        price_type=PriceType.NEGOTIABLE,
        currency="RUB",
        author="StartupFounder",
        category="Дизайн",
        date_created=datetime.utcnow() - timedelta(hours=2),
        responses_count=15,
        views_count=200,
        link="https://kwork.ru/projects/12347",
        tags=["Логотип", "Брендинг", "Фирменный стиль"],
        skills_required=["Adobe Illustrator", "Photoshop"],
        status=ProjectStatus.NEW
    )
    projects.append(project3)
    
    # Проект 4 - почасовая оплата
    project4 = Project(
        external_id="test_4",
        title="Настройка рекламы в Google Ads",
        description="Нужен специалист для настройки и оптимизации рекламных кампаний.",
        price=3500.0,
        price_type=PriceType.HOURLY,
        currency="RUB",
        author="MarketingAgency",
        category="Маркетинг",
        date_created=datetime.utcnow() - timedelta(minutes=30),
        responses_count=1,
        views_count=25,
        link="https://kwork.ru/projects/12348",
        tags=["Google Ads", "PPC", "Контекстная реклама"],
        skills_required=["Google Ads", "Analytics"],
        status=ProjectStatus.NEW
    )
    projects.append(project4)
    
    # Проект 5 - недавний
    project5 = Project(
        external_id="test_5",
        title="Написание статей для блога",
        description="Требуются качественные SEO-статьи для корпоративного блога IT-компании.",
        price=15000.0,
        price_type=PriceType.RANGE,
        currency="RUB",
        author="ContentManager",
        category="Тексты",
        date_created=datetime.utcnow() - timedelta(minutes=2),
        responses_count=0,
        views_count=8,
        link="https://kwork.ru/projects/12349",
        tags=["SEO", "Копирайтинг", "IT-тематика"],
        skills_required=["SEO", "Копирайтинг"],
        status=ProjectStatus.NEW
    )
    projects.append(project5)
    
    return projects


async def test_formatter():
    """Тестирование форматтера сообщений"""
    print("🎨 Тестирование форматтера сообщений...")
    
    try:
        formatter = TelegramMessageFormatter()
        projects = create_test_projects()
        
        # Тестируем форматирование одного проекта
        single_message = formatter.format_single_project(projects[0])
        assert len(single_message) > 0
        assert "Разработка интернет-магазина" in single_message
        print("✅ Форматирование одного проекта работает")
        
        # Тестируем групповое форматирование
        group_message = formatter.format_grouped_projects(projects[:3])
        assert len(group_message) > 0
        assert "3 новых проекта" in group_message
        print("✅ Групповое форматирование работает")
        
        # Тестируем статистику
        bot_stats = {"messages_sent": 10, "total_projects_sent": 25, "uptime": 3600}
        parsing_stats = {"pages_parsed": 5, "projects_found": 25, "errors": 0}
        stats_message = formatter.format_stats_message(bot_stats, parsing_stats)
        assert len(stats_message) > 0
        assert "Статистика работы" in stats_message
        print("✅ Форматирование статистики работает")
        
        # Тестируем сообщения об ошибках
        error_message = formatter.format_error_message("Тестовая ошибка", "Детали ошибки")
        assert len(error_message) > 0
        assert "Ошибка в парсере" in error_message
        print("✅ Форматирование ошибок работает")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в форматтере: {e}")
        return False


async def test_templates():
    """Тестирование шаблонов сообщений"""
    print("📋 Тестирование шаблонов сообщений...")
    
    try:
        from telegram_bot.templates import get_category_emoji, get_price_template, get_responses_template
        
        # Тестируем эмодзи категорий
        emoji = get_category_emoji("Программирование")
        assert emoji == "💻"
        
        emoji = get_category_emoji("Дизайн")
        assert emoji == "🎨"
        
        emoji = get_category_emoji("Неизвестная категория")
        assert emoji == "📋"
        print("✅ Эмодзи категорий работают")
        
        # Тестируем шаблоны цен
        template = get_price_template(3000)
        assert "💵" in template
        
        template = get_price_template(15000)
        assert "💰" in template
        
        template = get_price_template(100000)
        assert "🏆" in template
        print("✅ Шаблоны цен работают")
        
        # Тестируем шаблоны откликов
        template = get_responses_template(0)
        assert "Нет откликов" in template
        
        template = get_responses_template(1)
        assert "1 отклик" in template
        
        template = get_responses_template(15)
        assert "популярно" in template
        print("✅ Шаблоны откликов работают")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в шаблонах: {e}")
        return False


async def test_bot_initialization():
    """Тестирование инициализации бота (без реального API)"""
    print("🤖 Тестирование инициализации бота...")
    
    try:
        # Создаем бота с фейковым токеном
        bot = TelegramNotifier("123456:TEST_TOKEN_FOR_TESTING")
        
        # Проверяем, что бот инициализирован
        assert bot.bot_token == "123456:TEST_TOKEN_FOR_TESTING"
        assert bot.formatter is not None
        assert bot.templates is not None
        assert bot.rate_limiter is not None
        assert bot.max_projects_per_message == 5
        assert bot.group_timeout == 30
        
        # Проверяем статистику
        stats = bot.get_stats()
        assert isinstance(stats, dict)
        assert "messages_sent" in stats
        assert "uptime" in stats
        assert "rate_limiter" in stats
        
        print("✅ Инициализация бота работает")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка инициализации бота: {e}")
        return False


async def test_grouping_logic():
    """Тестирование логики группировки (без отправки)"""
    print("🔄 Тестирование логики группировки...")
    
    try:
        bot = TelegramNotifier("123456:TEST_TOKEN_FOR_TESTING")
        projects = create_test_projects()
        
        # Проверяем, что pending проекты пустые в начале
        assert len(bot._pending_projects) == 0
        
        # Тестируем добавление проектов в группу (мокаем chat_id)
        chat_id = "test_chat"
        
        # Добавляем проекты (не отправляем, только логика)
        bot._pending_projects[chat_id] = []
        bot._pending_projects[chat_id].extend(projects[:3])
        
        assert len(bot._pending_projects[chat_id]) == 3
        
        # Проверяем статистику
        stats = bot.get_stats()
        assert stats["pending_groups"] == 1
        assert stats["pending_projects"] == 3
        
        print("✅ Логика группировки работает")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка логики группировки: {e}")
        return False


async def test_markdown_escaping():
    """Тестирование экранирования Markdown"""
    print("🔤 Тестирование экранирования Markdown...")
    
    try:
        formatter = TelegramMessageFormatter()
        
        # Тестовые строки с специальными символами
        test_strings = [
            "Текст с_подчеркиванием_и*звездочками*",
            "Ссылка: https://example.com/test?param=1&other=2",
            "Цена: 10,000-15,000 руб. (50% предоплата)",
            "Email: test@example.com и телефон: +7(900)123-45-67",
            "[Скобки] и (круглые) символы",
            "Восклицательный знак! И точка."
        ]
        
        for test_string in test_strings:
            escaped = formatter._escape_markdown_v2(test_string)
            
            # Проверяем, что специальные символы экранированы
            assert "\\_" in escaped or "_" not in test_string
            assert "\\*" in escaped or "*" not in test_string
            assert "\\!" in escaped or "!" not in test_string
            assert "\\." in escaped or "." not in test_string
            
        print("✅ Экранирование Markdown работает")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка экранирования Markdown: {e}")
        return False


async def test_message_length():
    """Тестирование длины сообщений (лимит Telegram 4096 символов)"""
    print("📏 Тестирование длины сообщений...")
    
    try:
        formatter = TelegramMessageFormatter()
        projects = create_test_projects()
        
        # Создаем проект с очень длинным описанием
        long_project = Project(
            external_id="test_long",
            title="Проект с очень длинным описанием " * 10,
            description="Очень длинное описание проекта " * 50,  # ~1500 символов
            price=50000.0,
            price_type=PriceType.FIXED,
            currency="RUB",
            author="TestAuthor",
            category="Тест",
            date_created=datetime.utcnow(),
            responses_count=5,
            views_count=100,
            link="https://example.com",
            status=ProjectStatus.NEW
        )
        
        # Форматируем одиночное сообщение
        single_message = formatter.format_single_project(long_project)
        assert len(single_message) < 4096  # Лимит Telegram
        print(f"   Длина одиночного сообщения: {len(single_message)} символов")
        
        # Форматируем групповое сообщение
        group_message = formatter.format_grouped_projects([long_project] * 5)
        assert len(group_message) < 4096  # Лимит Telegram
        print(f"   Длина группового сообщения: {len(group_message)} символов")
        
        print("✅ Длина сообщений в пределах лимитов")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки длины сообщений: {e}")
        return False


async def test_real_telegram_api():
    """Тестирование с реальным Telegram API (если токен предоставлен)"""
    print("📡 Проверка возможности подключения к Telegram API...")
    
    # Проверяем, есть ли токен в переменных окружения
    import os
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("⚠️ Токен бота или chat_id не найдены в переменных окружения")
        print("   Установите TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID для полного тестирования")
        return True  # Не считаем это ошибкой
    
    try:
        bot = TelegramNotifier(bot_token)
        
        # Проверяем подключение
        is_connected = await bot.verify_connection()
        
        if is_connected:
            print("✅ Подключение к Telegram API успешно")
            
            # Отправляем тестовое сообщение
            test_message = "🧪 Тестовое сообщение от парсера Kwork.ru"
            success = await bot._send_message_with_retry(chat_id, test_message)
            
            if success:
                print("✅ Тестовое сообщение отправлено")
            else:
                print("⚠️ Не удалось отправить тестовое сообщение")
        else:
            print("❌ Не удалось подключиться к Telegram API")
            return False
        
        await bot.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Telegram API: {e}")
        return False


async def main():
    """Главная функция тестирования"""
    print("🧪 Начинаем тестирование Telegram бота...")
    print("=" * 60)
    
    # Настраиваем логирование для тестов
    setup_logging(DEBUG_CONFIG)
    logger = get_logger("telegram_test")
    
    tests = [
        ("Форматтер сообщений", test_formatter),
        ("Шаблоны сообщений", test_templates),
        ("Инициализация бота", test_bot_initialization),
        ("Логика группировки", test_grouping_logic),
        ("Экранирование Markdown", test_markdown_escaping),
        ("Длина сообщений", test_message_length),
        ("Подключение к Telegram API", test_real_telegram_api)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"Запуск теста: {test_name}")
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Критическая ошибка в тесте {test_name}: {e}")
            failed += 1
        
        print()  # Пустая строка между тестами
    
    print("=" * 60)
    print(f"📊 Результаты тестирования:")
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"📈 Успешность: {passed / (passed + failed) * 100:.1f}%")
    
    if failed == 0:
        print("🎉 Все тесты пройдены успешно!")
        print("✅ Telegram бот готов к использованию")
        
        # Выводим пример использования
        print("\n📖 Пример использования:")
        print("export TELEGRAM_BOT_TOKEN='ваш_токен_бота'")
        print("export TELEGRAM_CHAT_ID='ваш_chat_id'")
        print("python test_telegram.py")
        
        return True
    else:
        print("⚠️ Некоторые тесты провалены")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
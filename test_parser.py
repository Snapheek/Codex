#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы парсера Kwork.ru
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from core import KworkParser, parse_kwork_single_page
from utils import setup_logging, DEBUG_CONFIG, get_logger


async def test_parser_initialization():
    """Тестирование инициализации парсера"""
    print("🔧 Тестирование инициализации парсера...")
    
    try:
        async with KworkParser(max_concurrent_requests=3) as parser:
            assert parser.session is not None
            assert parser.rate_limiter is not None
            assert parser.user_agent_rotator is not None
            
            stats = parser.get_stats()
            assert isinstance(stats, dict)
            assert "pages_parsed" in stats
            
            print("✅ Парсер успешно инициализирован")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка инициализации парсера: {e}")
        return False


async def test_selector_system():
    """Тестирование системы селекторов"""
    print("🎯 Тестирование системы селекторов...")
    
    try:
        from core.selectors import selector_matcher, get_selector
        from bs4 import BeautifulSoup
        
        # Создаем тестовый HTML
        test_html = """
        <div class="wants-list">
            <div class="want-card">
                <div class="wants-card__header-title">
                    <a href="/project/123">Тестовый проект</a>
                </div>
                <div class="wants-card__price">50000 руб.</div>
                <div class="wants-card__description-text">Описание проекта</div>
                <div class="wants-card__header-username">Тестовый автор</div>
            </div>
        </div>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        
        # Тестируем селекторы
        project_card_selector = selector_matcher.test_selector(soup, 'project_card')
        assert project_card_selector is not None
        
        project_title_selector = selector_matcher.test_selector(soup, 'project_title')
        assert project_title_selector is not None
        
        # Тестируем извлечение элементов
        cards = soup.select(project_card_selector)
        assert len(cards) == 1
        
        title_elements = soup.select(project_title_selector)
        assert len(title_elements) == 1
        assert "Тестовый проект" in title_elements[0].get_text()
        
        print("✅ Система селекторов работает корректно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в системе селекторов: {e}")
        return False


async def test_data_extraction():
    """Тестирование извлечения данных"""
    print("📊 Тестирование извлечения данных...")
    
    try:
        from bs4 import BeautifulSoup
        
        async with KworkParser() as parser:
            # Создаем тестовую карточку проекта
            test_card_html = """
            <div class="want-card" data-want-id="12345">
                <div class="wants-card__header-title">
                    <a href="/project/12345">Разработка веб-приложения</a>
                </div>
                <div class="wants-card__price">75000 руб.</div>
                <div class="wants-card__description-text">
                    Требуется разработать современное веб-приложение на Python
                </div>
                <div class="wants-card__header-username">WebDeveloper123</div>
                <div class="wants-card__category">Программирование</div>
                <div class="wants-card__responses">5 откликов</div>
                <div class="wants-card__views">120 просмотров</div>
                <div class="wants-card__time">2 часа назад</div>
            </div>
            """
            
            soup = BeautifulSoup(test_card_html, 'html.parser')
            card_element = soup.find('div', class_='want-card')
            
            # Извлекаем данные проекта
            project = parser.extract_project_data(card_element, "https://kwork.ru/projects")
            
            assert project is not None
            assert project.external_id == "12345"
            assert "Разработка веб-приложения" in project.title
            assert project.price is not None
            assert project.price > 0
            assert project.author == "WebDeveloper123"
            assert project.category == "Программирование"
            assert project.responses_count == 5
            assert project.views_count == 120
            
            print(f"✅ Извлечен проект: {project.title}")
            print(f"   Цена: {project.price} {project.currency}")
            print(f"   Автор: {project.author}")
            print(f"   Категория: {project.category}")
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка извлечения данных: {e}")
        return False


async def test_price_parsing():
    """Тестирование парсинга цен"""
    print("💰 Тестирование парсинга цен...")
    
    try:
        async with KworkParser() as parser:
            # Тестируем различные форматы цен
            test_cases = [
                ("50000 руб.", 50000.0, "FIXED"),
                ("договорная", None, "NEGOTIABLE"),
                ("от 10000 до 20000", 10000.0, "RANGE"),
                ("1500 руб/час", 1500.0, "HOURLY"),
                ("по договоренности", None, "NEGOTIABLE"),
                ("25 000 руб.", 25000.0, "FIXED")
            ]
            
            for price_text, expected_price, expected_type in test_cases:
                price, price_type = parser._parse_price(price_text)
                
                if expected_price is None:
                    assert price is None
                else:
                    assert abs(price - expected_price) < 0.01
                
                assert price_type.value.upper() == expected_type
                
                print(f"   '{price_text}' -> {price} ({price_type.value})")
            
            print("✅ Парсинг цен работает корректно")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка парсинга цен: {e}")
        return False


async def test_pagination_parsing():
    """Тестирование парсинга пагинации"""
    print("📄 Тестирование парсинга пагинации...")
    
    try:
        from bs4 import BeautifulSoup
        
        async with KworkParser() as parser:
            # Тестовый HTML с пагинацией
            pagination_html = """
            <div class="pagination">
                <a href="?page=1" class="page-numbers">1</a>
                <span class="page-numbers current">2</span>
                <a href="?page=3" class="page-numbers">3</a>
                <a href="?page=4" class="page-numbers">4</a>
                <a href="?page=5" class="page-numbers">5</a>
                <a href="?page=3" class="next">Следующая</a>
            </div>
            <div class="wants-found-count">Найдено: 87 проектов</div>
            """
            
            soup = BeautifulSoup(pagination_html, 'html.parser')
            pagination_info = parser._extract_pagination_info(soup)
            
            assert pagination_info["current_page"] == 2
            assert pagination_info["total_pages"] == 5
            assert pagination_info["has_next"] == True
            assert pagination_info["total_projects"] == 87
            
            print(f"✅ Пагинация: страница {pagination_info['current_page']} из {pagination_info['total_pages']}")
            print(f"   Следующая: {pagination_info['has_next']}")
            print(f"   Всего проектов: {pagination_info['total_projects']}")
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка парсинга пагинации: {e}")
        return False


async def test_error_handling():
    """Тестирование обработки ошибок"""
    print("⚠️ Тестирование обработки ошибок...")
    
    try:
        async with KworkParser() as parser:
            # Тестируем обработку некорректного HTML
            invalid_html = "<html><body><div>Неполный HTML без закрытия"
            projects = await parser.parse_projects_from_page(invalid_html, "test://url")
            
            # Должен вернуть пустой список, не падать
            assert isinstance(projects, list)
            
            # Тестируем извлечение из пустого элемента
            result = parser._extract_text_safe(None, "default")
            assert result == "default"
            
            # Тестируем парсинг некорректной цены
            price, price_type = parser._parse_price("не цена")
            assert price is None
            
            print("✅ Обработка ошибок работает корректно")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка в обработке ошибок: {e}")
        return False


async def test_integration():
    """Интеграционное тестирование"""
    print("🔗 Интеграционное тестирование...")
    
    try:
        # Проверяем интеграцию с утилитами
        from utils import get_rate_limiter, get_user_agent_rotator
        
        # Тестируем создание парсера с кастомными настройками
        rate_limiter = get_rate_limiter("test")
        user_agent_rotator = get_user_agent_rotator()
        
        async with KworkParser(max_concurrent_requests=2) as parser:
            # Проверяем, что утилиты инициализированы
            assert parser.rate_limiter is not None
            assert parser.user_agent_rotator is not None
            
            # Проверяем статистику
            stats = parser.get_stats()
            assert "rate_limiter" in stats
            assert "user_agent" in stats
            
            print("✅ Интеграция с утилитами работает")
            
            # Тестируем полный цикл с mock данными
            mock_html = """
            <html>
            <body>
                <div class="wants-list">
                    <div class="want-card">
                        <div class="wants-card__header-title">
                            <a href="/project/999">Mock проект</a>
                        </div>
                        <div class="wants-card__description-text">Mock описание</div>
                        <div class="wants-card__header-username">MockUser</div>
                        <div class="wants-card__price">1000 руб.</div>
                    </div>
                </div>
                <div class="pagination">
                    <span class="current">1</span>
                </div>
            </body>
            </html>
            """
            
            projects = await parser.parse_projects_from_page(mock_html, "test://mock")
            assert len(projects) == 1
            assert projects[0].title == "Mock проект"
            
            print("✅ Полный цикл парсинга работает")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка интеграционного тестирования: {e}")
        return False


async def main():
    """Главная функция тестирования"""
    print("🧪 Начинаем тестирование парсера Kwork.ru...")
    print("=" * 60)
    
    # Настраиваем логирование для тестов
    setup_logging(DEBUG_CONFIG)
    logger = get_logger("parser_test")
    
    tests = [
        ("Инициализация парсера", test_parser_initialization),
        ("Система селекторов", test_selector_system),
        ("Извлечение данных", test_data_extraction),
        ("Парсинг цен", test_price_parsing),
        ("Парсинг пагинации", test_pagination_parsing),
        ("Обработка ошибок", test_error_handling),
        ("Интеграционные тесты", test_integration)
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
        print("✅ Парсер Kwork.ru готов к использованию")
        return True
    else:
        print("⚠️ Некоторые тесты провалены")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
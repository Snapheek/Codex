"""
Основные компоненты парсера Kwork.ru

Содержит:
- Pydantic модели данных (Project, ProjectFilter, etc.)
- Enums и типы данных
- Валидаторы и бизнес-логика
- CSS селекторы для парсинга
- Основной парсер проектов
"""

from .models import (
    # Основные модели
    Project,
    ProjectFilter,
    ProjectSearchResult,
    DatabaseStats,
    
    # Enums
    ProjectStatus,
    PriceType
)

from .selectors import (
    # Основные селекторы
    KworkSelectors,
    KworkSelectorsAlt,
    SelectorMatcher,
    selector_matcher,
    
    # Функции для работы с селекторами
    get_selector,
    test_selectors,
    
    # Специальные селекторы
    URGENT_PROJECT_SELECTORS,
    PREMIUM_PROJECT_SELECTORS,
    FILTER_SELECTORS,
    NAVIGATION_SELECTORS,
    DETAIL_PAGE_SELECTORS
)

from .parser import (
    # Основной парсер
    KworkParser,
    
    # Утилитарные функции
    parse_kwork_projects,
    parse_kwork_single_page
)

__all__ = [
    # Модели
    'Project',
    'ProjectFilter', 
    'ProjectSearchResult',
    'DatabaseStats',
    
    # Enums
    'ProjectStatus',
    'PriceType',
    
    # Селекторы
    'KworkSelectors',
    'KworkSelectorsAlt', 
    'SelectorMatcher',
    'selector_matcher',
    'get_selector',
    'test_selectors',
    'URGENT_PROJECT_SELECTORS',
    'PREMIUM_PROJECT_SELECTORS',
    'FILTER_SELECTORS',
    'NAVIGATION_SELECTORS',
    'DETAIL_PAGE_SELECTORS',
    
    # Парсер
    'KworkParser',
    'parse_kwork_projects',
    'parse_kwork_single_page'
] 
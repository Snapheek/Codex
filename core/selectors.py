"""
CSS селекторы для парсинга Kwork.ru
Основано на анализе HTML структуры страниц проектов
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class KworkSelectors:
    """
    Коллекция CSS селекторов для парсинга Kwork.ru
    """
    
    # Основные контейнеры
    projects_container: str = ".wants-list"
    project_card: str = ".want-card"
    
    # Заголовки и ссылки
    project_title: str = ".wants-card__header-title a"
    project_link: str = ".wants-card__header-title a"
    
    # Цена проекта
    price_container: str = ".wants-card__price"
    price_value: str = ".wants-card__price .kwork-text-money"
    price_currency: str = ".wants-card__price .currency"
    price_type: str = ".wants-card__price .price-type"  # договорная, фиксированная
    
    # Описание проекта
    description: str = ".wants-card__description-text"
    description_short: str = ".wants-card__description-text p"
    
    # Информация об авторе
    author_name: str = ".wants-card__header-username"
    author_link: str = ".wants-card__header-username a"
    author_avatar: str = ".wants-card__header-user img"
    
    # Категория и теги
    category: str = ".wants-card__category"
    category_link: str = ".wants-card__category a"
    tags: str = ".wants-card__tags .tag"
    skills: str = ".wants-card__skills .skill"
    
    # Статистика проекта
    responses_count: str = ".wants-card__responses"
    views_count: str = ".wants-card__views"
    time_posted: str = ".wants-card__time"
    deadline: str = ".wants-card__deadline"
    
    # Дополнительная информация
    project_type: str = ".wants-card__type"
    experience_level: str = ".wants-card__experience"
    rating: str = ".wants-card__rating"
    location: str = ".wants-card__location"
    
    # Пагинация
    pagination_container: str = ".pagination"
    pagination_next: str = ".pagination .next"
    pagination_pages: str = ".pagination .page-numbers"
    pagination_current: str = ".pagination .current"
    
    # Счетчик проектов
    total_projects: str = ".wants-found-count"
    projects_per_page: str = ".wants-per-page"


# Альтернативные селекторы (fallback)
@dataclass 
class KworkSelectorsAlt:
    """
    Альтернативные селекторы на случай изменения структуры сайта
    """
    
    # Основные (более общие селекторы)
    project_card: str = "[data-want-id]"
    project_title: str = "h3 a, .title a, .project-title a"
    project_link: str = "a[href*='/project/']"
    
    # Цена (более широкий поиск)
    price_container: str = ".price, .cost, .amount, [class*='price']"
    price_value: str = ".price-value, .amount-value, [class*='money']"
    
    # Описание
    description: str = ".description, .content, .text, p"
    
    # Автор
    author_name: str = ".author, .username, .user-name, [class*='user']"
    
    # Статистика
    responses_count: str = "[class*='response'], [class*='offer'], [class*='bid']"
    views_count: str = "[class*='view'], [class*='visit']"
    time_posted: str = "[class*='time'], [class*='date'], .timestamp"


class SelectorMatcher:
    """
    Класс для работы с селекторами и fallback логикой
    """
    
    def __init__(self):
        self.primary = KworkSelectors()
        self.fallback = KworkSelectorsAlt()
        self._cached_selectors = {}
    
    def get_selector(self, field_name: str, use_fallback: bool = False) -> str:
        """
        Получение селектора для поля
        
        Args:
            field_name: Название поля
            use_fallback: Использовать альтернативные селекторы
            
        Returns:
            str: CSS селектор
        """
        selectors = self.fallback if use_fallback else self.primary
        
        if hasattr(selectors, field_name):
            return getattr(selectors, field_name)
        
        raise ValueError(f"Селектор для поля '{field_name}' не найден")
    
    def get_all_selectors(self, field_name: str) -> list[str]:
        """
        Получение всех возможных селекторов для поля
        
        Args:
            field_name: Название поля
            
        Returns:
            list[str]: Список селекторов (основной + fallback)
        """
        selectors = []
        
        # Основной селектор
        try:
            primary_selector = self.get_selector(field_name, use_fallback=False)
            selectors.append(primary_selector)
        except ValueError:
            pass
        
        # Альтернативный селектор
        try:
            fallback_selector = self.get_selector(field_name, use_fallback=True)
            if fallback_selector not in selectors:
                selectors.append(fallback_selector)
        except ValueError:
            pass
        
        return selectors
    
    def test_selector(self, soup, field_name: str) -> Optional[str]:
        """
        Тестирование селекторов для поля и возврат работающего
        
        Args:
            soup: BeautifulSoup объект
            field_name: Название поля
            
        Returns:
            Optional[str]: Работающий селектор или None
        """
        cache_key = f"{field_name}_{id(soup)}"
        
        if cache_key in self._cached_selectors:
            return self._cached_selectors[cache_key]
        
        selectors = self.get_all_selectors(field_name)
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements:  # Если найдены элементы
                    self._cached_selectors[cache_key] = selector
                    return selector
            except Exception:
                continue  # Пробуем следующий селектор
        
        return None


# Глобальный экземпляр
selector_matcher = SelectorMatcher()


def get_selector(field_name: str, use_fallback: bool = False) -> str:
    """
    Быстрый доступ к селектору
    
    Args:
        field_name: Название поля
        use_fallback: Использовать альтернативные селекторы
        
    Returns:
        str: CSS селектор
    """
    return selector_matcher.get_selector(field_name, use_fallback)


def test_selectors(soup, field_name: str) -> Optional[str]:
    """
    Быстрое тестирование селекторов
    
    Args:
        soup: BeautifulSoup объект
        field_name: Название поля
        
    Returns:
        Optional[str]: Работающий селектор или None
    """
    return selector_matcher.test_selector(soup, field_name)


# Специальные селекторы для различных ситуаций
URGENT_PROJECT_SELECTORS = {
    "urgent_marker": ".urgent, .priority, [class*='urgent']",
    "deadline_soon": ".deadline-soon, .expires-soon",
    "hot_project": ".hot, .popular, [class*='hot']"
}

PREMIUM_PROJECT_SELECTORS = {
    "premium_marker": ".premium, .featured, [class*='premium']",
    "verified_author": ".verified, .trusted, [class*='verified']",
    "top_project": ".top, .highlighted, [class*='top']"
}

FILTER_SELECTORS = {
    "category_filter": ".category-filter, #category",
    "price_filter": ".price-filter, #price-range",
    "date_filter": ".date-filter, #date-posted",
    "search_input": ".search-input, #search, input[name='search']"
}

# Навигационные селекторы
NAVIGATION_SELECTORS = {
    "next_page": ".pagination .next, .next-page, [rel='next']",
    "prev_page": ".pagination .prev, .prev-page, [rel='prev']",
    "page_numbers": ".pagination .page, .page-numbers a",
    "load_more": ".load-more, .show-more, #load-more-projects"
}

# Селекторы для детальной страницы проекта
DETAIL_PAGE_SELECTORS = {
    "full_description": ".project-description, .full-description, .content",
    "requirements": ".requirements, .project-requirements",
    "attachments": ".attachments, .files, .project-files",
    "comments": ".comments, .project-comments",
    "similar_projects": ".similar, .related-projects"
} 
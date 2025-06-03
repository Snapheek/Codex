"""
Основной парсер Kwork.ru
Асинхронный парсер проектов с поддержкой пагинации и обработки ошибок
"""

import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, AsyncGenerator, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
import json

import aiohttp
from bs4 import BeautifulSoup, Tag
from loguru import logger

from core.models import Project, ProjectStatus, PriceType
from core.selectors import (
    selector_matcher, 
    NAVIGATION_SELECTORS, 
    URGENT_PROJECT_SELECTORS,
    PREMIUM_PROJECT_SELECTORS
)
from utils import (
    retry_async, 
    RetryConfig, 
    STANDARD_RETRY,
    get_rate_limiter, 
    RateLimitConfig, 
    RATE_STANDARD_CONFIG,
    get_browser_headers, 
    UserAgentRotator, 
    UA_STANDARD_CONFIG,
    get_logger
)
from database import ProjectRepository
from config.settings import Settings, get_settings


class KworkParser:
    """
    Основной парсер проектов Kwork.ru
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        max_concurrent_requests: int = 5,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None
    ):
        """
        Инициализация парсера
        
        Args:
            settings: Настройки приложения
            max_concurrent_requests: Максимальное количество одновременных запросов
            retry_config: Конфигурация retry логики
            rate_limit_config: Конфигурация rate limiting
        """
        self.settings = settings or get_settings()
        self.logger = get_logger("kwork_parser")
        
        # Конфигурации
        self.retry_config = retry_config or STANDARD_RETRY
        self.rate_limit_config = rate_limit_config or RATE_STANDARD_CONFIG
        
        # Сетевые компоненты
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = get_rate_limiter("kwork.ru", self.rate_limit_config)
        self.user_agent_rotator = UserAgentRotator(UA_STANDARD_CONFIG)
        
        # Семафор для контроля одновременных запросов
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Статистика парсинга
        self.stats = {
            "pages_parsed": 0,
            "projects_found": 0,
            "projects_new": 0,
            "errors": 0,
            "start_time": None,
            "last_page_time": None
        }
        
        # Кэш селекторов для оптимизации
        self._selector_cache = {}
        
        # Базовые URL
        self.base_url = "https://kwork.ru"
        self.projects_url = f"{self.base_url}/projects"
        
        self.logger.info(f"Парсер Kwork.ru инициализирован. Макс. запросов: {max_concurrent_requests}")
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        await self.close()
    
    async def start(self) -> None:
        """Запуск парсера"""
        if self.session is None:
            # Создаем HTTP сессию с настройками
            timeout = aiohttp.ClientTimeout(
                total=self.settings.parser.request_timeout,
                connect=10,
                sock_read=30
            )
            
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                trust_env=True
            )
            
            self.logger.info("HTTP сессия создана")
        
        self.stats["start_time"] = time.time()
    
    async def close(self) -> None:
        """Закрытие парсера"""
        if self.session:
            await self.session.close()
            self.session = None
            self.logger.info("HTTP сессия закрыта")
    
    async def fetch_page(
        self, 
        url: str, 
        params: Optional[Dict[str, Any]] = None,
        retry_on_error: bool = True
    ) -> Tuple[str, int]:
        """
        Загрузка HTML страницы
        
        Args:
            url: URL для загрузки
            params: GET параметры
            retry_on_error: Повторять при ошибках
            
        Returns:
            Tuple[str, int]: HTML содержимое и статус код
            
        Raises:
            aiohttp.ClientError: При ошибках сети
        """
        async with self.semaphore:
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Получаем заголовки с User-Agent
            headers = self.user_agent_rotator.get_headers()
            
            # Дополнительные заголовки для Kwork
            headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': self.base_url,
                'X-Requested-With': 'XMLHttpRequest'  # Возможно, поможет избежать блокировок
            })
            
            async def _fetch():
                start_time = time.time()
                
                try:
                    async with self.session.get(url, params=params, headers=headers) as response:
                        response_time = time.time() - start_time
                        
                        # Логируем запрос
                        self.logger.debug(
                            f"GET {url} -> {response.status} ({response_time:.2f}s)",
                            extra={
                                "url": url,
                                "status_code": response.status,
                                "response_time": response_time,
                                "params": params
                            }
                        )
                        
                        # Проверяем статус
                        if response.status == 429:
                            await self.rate_limiter.report_error(429)
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=429,
                                message="Too Many Requests"
                            )
                        
                        if response.status >= 400:
                            await self.rate_limiter.report_error(response.status)
                            response.raise_for_status()
                        
                        # Успешный запрос
                        await self.rate_limiter.report_success()
                        
                        # Читаем содержимое
                        html = await response.text(encoding='utf-8')
                        return html, response.status
                        
                except Exception as e:
                    await self.rate_limiter.report_error()
                    self.stats["errors"] += 1
                    raise e
            
            if retry_on_error:
                return await retry_async(_fetch, config=self.retry_config)
            else:
                return await _fetch()
    
    def _get_working_selector(self, soup: BeautifulSoup, field_name: str) -> Optional[str]:
        """
        Получение работающего селектора для поля
        
        Args:
            soup: BeautifulSoup объект
            field_name: Название поля
            
        Returns:
            Optional[str]: Работающий селектор или None
        """
        cache_key = f"{field_name}_{id(soup)}"
        
        if cache_key in self._selector_cache:
            return self._selector_cache[cache_key]
        
        working_selector = selector_matcher.test_selector(soup, field_name)
        
        if working_selector:
            self._selector_cache[cache_key] = working_selector
        
        return working_selector
    
    def _extract_text_safe(self, element, default: str = "") -> str:
        """
        Безопасное извлечение текста из элемента
        
        Args:
            element: BeautifulSoup элемент или None
            default: Значение по умолчанию
            
        Returns:
            str: Извлеченный и очищенный текст
        """
        if not element:
            return default
        
        try:
            text = element.get_text(strip=True) if hasattr(element, 'get_text') else str(element)
            # Очищаем от лишних пробелов и символов
            text = re.sub(r'\s+', ' ', text).strip()
            return text or default
        except Exception:
            return default
    
    def _extract_link_safe(self, element, base_url: Optional[str] = None) -> Optional[str]:
        """
        Безопасное извлечение ссылки из элемента
        
        Args:
            element: BeautifulSoup элемент
            base_url: Базовый URL для относительных ссылок
            
        Returns:
            Optional[str]: Полная ссылка или None
        """
        if not element:
            return None
        
        try:
            href = element.get('href')
            if not href:
                return None
            
            # Если это относительная ссылка, делаем её абсолютной
            if base_url and not href.startswith(('http://', 'https://')):
                href = urljoin(base_url, href)
            
            return href
        except Exception:
            return None
    
    def _parse_price(self, price_text: str) -> Tuple[Optional[float], PriceType]:
        """
        Парсинг цены проекта
        
        Args:
            price_text: Текст с ценой
            
        Returns:
            Tuple[Optional[float], PriceType]: Цена и тип цены
        """
        if not price_text:
            return None, PriceType.NEGOTIABLE
        
        price_text = price_text.lower().strip()
        
        # Проверяем на договорную цену
        negotiable_keywords = [
            'договорная', 'по договоренности', 'договор', 
            'negotiable', 'tbd', 'обсуждается'
        ]
        
        if any(keyword in price_text for keyword in negotiable_keywords):
            return None, PriceType.NEGOTIABLE
        
        # Ищем числа в тексте
        price_match = re.search(r'[\d\s,\.]+', price_text)
        if not price_match:
            return None, PriceType.NEGOTIABLE
        
        try:
            # Очищаем число от пробелов и заменяем запятые на точки
            price_str = price_match.group().replace(' ', '').replace(',', '.')
            price = float(price_str)
            
            # Определяем тип цены
            if 'час' in price_text or 'hour' in price_text:
                return price, PriceType.HOURLY
            elif '-' in price_text or 'от' in price_text or 'до' in price_text:
                return price, PriceType.RANGE
            else:
                return price, PriceType.FIXED
                
        except ValueError:
            return None, PriceType.NEGOTIABLE
    
    def _parse_datetime(self, time_text: str) -> Optional[datetime]:
        """
        Парсинг даты и времени
        
        Args:
            time_text: Текст с датой/временем
            
        Returns:
            Optional[datetime]: Дата или None
        """
        if not time_text:
            return None
        
        time_text = time_text.lower().strip()
        
        try:
            # Обрабатываем относительные даты
            if 'минут' in time_text:
                minutes = re.search(r'(\d+)', time_text)
                if minutes:
                    return datetime.utcnow() - timedelta(minutes=int(minutes.group(1)))
            
            elif 'час' in time_text:
                hours = re.search(r'(\d+)', time_text)
                if hours:
                    return datetime.utcnow() - timedelta(hours=int(hours.group(1)))
            
            elif 'день' in time_text or 'дня' in time_text:
                days = re.search(r'(\d+)', time_text)
                if days:
                    return datetime.utcnow() - timedelta(days=int(days.group(1)))
            
            elif 'вчера' in time_text:
                return datetime.utcnow() - timedelta(days=1)
            
            elif 'сегодня' in time_text:
                return datetime.utcnow()
            
            # Пробуем парсить абсолютную дату
            # Форматы: "15.01.2024", "15 января 2024", etc.
            date_patterns = [
                r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
                r'(\d{1,2})\s+(\w+)\s+(\d{4})',
                r'(\d{4})-(\d{1,2})-(\d{1,2})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, time_text)
                if match:
                    # Здесь можно добавить более сложную логику парсинга
                    break
            
        except Exception:
            pass
        
        return None
    
    def _parse_number(self, text: str) -> int:
        """
        Извлечение числа из текста
        
        Args:
            text: Текст с числом
            
        Returns:
            int: Извлеченное число или 0
        """
        if not text:
            return 0
        
        # Ищем числа в тексте
        number_match = re.search(r'(\d+)', text.replace(' ', ''))
        if number_match:
            try:
                return int(number_match.group(1))
            except ValueError:
                pass
        
        return 0
    
    def extract_project_data(self, project_element: Tag, page_url: str) -> Optional[Project]:
        """
        Извлечение данных проекта из HTML элемента
        
        Args:
            project_element: BeautifulSoup элемент карточки проекта
            page_url: URL страницы для формирования абсолютных ссылок
            
        Returns:
            Optional[Project]: Объект проекта или None при ошибке
        """
        try:
            # External ID из атрибута элемента или ссылки
            external_id = None
            
            # Пробуем получить ID из data-атрибута
            if project_element.get('data-want-id'):
                external_id = project_element.get('data-want-id')
            
            # Получаем ссылку на проект
            title_selector = self._get_working_selector(project_element, 'project_title')
            title_element = project_element.select_one(title_selector) if title_selector else None
            
            if not title_element:
                self.logger.warning("Не найден заголовок проекта")
                return None
            
            title = self._extract_text_safe(title_element)
            project_link = self._extract_link_safe(title_element, self.base_url)
            
            if not project_link:
                self.logger.warning("Не найдена ссылка на проект")
                return None
            
            # Извлекаем external_id из ссылки если не получили из атрибута
            if not external_id:
                link_match = re.search(r'/(\d+)', project_link)
                if link_match:
                    external_id = link_match.group(1)
                else:
                    # Используем hash от URL как fallback
                    external_id = str(hash(project_link))
            
            # Описание проекта
            desc_selector = self._get_working_selector(project_element, 'description')
            desc_element = project_element.select_one(desc_selector) if desc_selector else None
            description = self._extract_text_safe(desc_element, "Описание отсутствует")
            
            # Цена проекта
            price_selector = self._get_working_selector(project_element, 'price_container')
            price_element = project_element.select_one(price_selector) if price_selector else None
            price_text = self._extract_text_safe(price_element)
            price, price_type = self._parse_price(price_text)
            
            # Автор проекта
            author_selector = self._get_working_selector(project_element, 'author_name')
            author_element = project_element.select_one(author_selector) if author_selector else None
            author = self._extract_text_safe(author_element, "Аноним")
            
            # Категория
            category_selector = self._get_working_selector(project_element, 'category')
            category_element = project_element.select_one(category_selector) if category_selector else None
            category = self._extract_text_safe(category_element)
            
            # Количество откликов
            responses_selector = self._get_working_selector(project_element, 'responses_count')
            responses_element = project_element.select_one(responses_selector) if responses_selector else None
            responses_count = self._parse_number(self._extract_text_safe(responses_element))
            
            # Количество просмотров
            views_selector = self._get_working_selector(project_element, 'views_count')
            views_element = project_element.select_one(views_selector) if views_selector else None
            views_count = self._parse_number(self._extract_text_safe(views_element))
            
            # Время публикации
            time_selector = self._get_working_selector(project_element, 'time_posted')
            time_element = project_element.select_one(time_selector) if time_selector else None
            time_text = self._extract_text_safe(time_element)
            date_created = self._parse_datetime(time_text) or datetime.utcnow()
            
            # Теги и навыки
            tags = []
            skills = []
            
            # Теги
            tags_selector = self._get_working_selector(project_element, 'tags')
            if tags_selector:
                tag_elements = project_element.select(tags_selector)
                tags = [self._extract_text_safe(tag) for tag in tag_elements if self._extract_text_safe(tag)]
            
            # Навыки
            skills_selector = self._get_working_selector(project_element, 'skills')
            if skills_selector:
                skill_elements = project_element.select(skills_selector)
                skills = [self._extract_text_safe(skill) for skill in skill_elements if self._extract_text_safe(skill)]
            
            # Создаем объект проекта
            project = Project(
                external_id=external_id,
                title=title,
                description=description,
                price=price,
                price_type=price_type,
                currency="RUB",  # По умолчанию рубли для Kwork.ru
                author=author,
                category=category,
                date_created=date_created,
                responses_count=responses_count,
                views_count=views_count,
                link=project_link,
                tags=tags,
                skills_required=skills,
                status=ProjectStatus.NEW
            )
            
            self.logger.debug(f"Извлечен проект: {title[:50]}...")
            return project
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения данных проекта: {e}")
            return None
    
    async def parse_projects_from_page(self, html: str, page_url: str) -> List[Project]:
        """
        Парсинг проектов со страницы
        
        Args:
            html: HTML содержимое страницы
            page_url: URL страницы
            
        Returns:
            List[Project]: Список извлеченных проектов
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            projects = []
            
            # Находим контейнер с проектами
            projects_selector = self._get_working_selector(soup, 'projects_container')
            if not projects_selector:
                projects_selector = "body"  # Fallback
            
            container = soup.select_one(projects_selector)
            if not container:
                self.logger.warning("Не найден контейнер с проектами")
                return []
            
            # Находим карточки проектов
            cards_selector = self._get_working_selector(container, 'project_card')
            if not cards_selector:
                self.logger.warning("Не найден селектор карточек проектов")
                return []
            
            project_cards = container.select(cards_selector)
            
            if not project_cards:
                self.logger.warning(f"Проекты не найдены на странице {page_url}")
                return []
            
            self.logger.info(f"Найдено {len(project_cards)} карточек проектов на странице")
            
            # Извлекаем данные из каждой карточки
            for card in project_cards:
                project = self.extract_project_data(card, page_url)
                if project:
                    projects.append(project)
            
            self.stats["projects_found"] += len(projects)
            self.logger.info(f"Успешно извлечено {len(projects)} проектов")
            
            return projects
            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга страницы {page_url}: {e}")
            return []
    
    def _extract_pagination_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Извлечение информации о пагинации
        
        Args:
            soup: BeautifulSoup объект страницы
            
        Returns:
            Dict: Информация о пагинации
        """
        pagination_info = {
            "current_page": 1,
            "total_pages": 1,
            "has_next": False,
            "next_page_url": None,
            "total_projects": 0
        }
        
        try:
            # Ищем текущую страницу
            current_selectors = [".pagination .current", ".active", ".page-current"]
            for selector in current_selectors:
                current_element = soup.select_one(selector)
                if current_element:
                    current_page = self._parse_number(self._extract_text_safe(current_element))
                    if current_page > 0:
                        pagination_info["current_page"] = current_page
                        break
            
            # Ищем общее количество страниц
            page_selectors = [".pagination .page-numbers", ".pagination a", ".page-link"]
            for selector in page_selectors:
                page_elements = soup.select(selector)
                if page_elements:
                    page_numbers = []
                    for el in page_elements:
                        page_num = self._parse_number(self._extract_text_safe(el))
                        if page_num > 0:
                            page_numbers.append(page_num)
                    
                    if page_numbers:
                        pagination_info["total_pages"] = max(page_numbers)
                        break
            
            # Ищем ссылку на следующую страницу
            next_selectors = NAVIGATION_SELECTORS["next_page"].split(", ")
            for selector in next_selectors:
                next_element = soup.select_one(selector)
                if next_element:
                    next_url = self._extract_link_safe(next_element, self.base_url)
                    if next_url:
                        pagination_info["has_next"] = True
                        pagination_info["next_page_url"] = next_url
                        break
            
            # Альтернативная проверка - есть ли следующая страница
            if not pagination_info["has_next"]:
                current = pagination_info["current_page"]
                total = pagination_info["total_pages"]
                pagination_info["has_next"] = current < total
            
            # Ищем общее количество проектов
            count_selectors = [".wants-found-count", ".total-count", ".results-count"]
            for selector in count_selectors:
                count_element = soup.select_one(selector)
                if count_element:
                    total_count = self._parse_number(self._extract_text_safe(count_element))
                    if total_count > 0:
                        pagination_info["total_projects"] = total_count
                        break
            
        except Exception as e:
            self.logger.warning(f"Ошибка извлечения информации о пагинации: {e}")
        
        return pagination_info
    
    async def parse_single_page(
        self, 
        page_number: int = 1, 
        category: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Project], Dict[str, Any]]:
        """
        Парсинг одной страницы проектов
        
        Args:
            page_number: Номер страницы
            category: Категория проектов
            additional_params: Дополнительные параметры запроса
            
        Returns:
            Tuple[List[Project], Dict]: Проекты и информация о пагинации
        """
        start_time = time.time()
        
        # Формируем параметры запроса
        params = {"page": page_number}
        
        if category:
            params["category"] = category
        
        if additional_params:
            params.update(additional_params)
        
        # Формируем URL
        url = self.projects_url
        
        try:
            # Загружаем страницу
            self.logger.info(f"Парсинг страницы {page_number} (категория: {category or 'все'})")
            html, status_code = await self.fetch_page(url, params)
            
            if status_code != 200:
                self.logger.warning(f"Неожиданный статус код: {status_code}")
            
            # Парсим проекты
            projects = await self.parse_projects_from_page(html, url)
            
            # Извлекаем информацию о пагинации
            soup = BeautifulSoup(html, 'html.parser')
            pagination_info = self._extract_pagination_info(soup)
            
            # Обновляем статистику
            parsing_time = time.time() - start_time
            self.stats["pages_parsed"] += 1
            self.stats["last_page_time"] = parsing_time
            
            self.logger.info(
                f"Страница {page_number} обработана: {len(projects)} проектов за {parsing_time:.2f}с"
            )
            
            return projects, pagination_info
            
        except Exception as e:
            self.stats["errors"] += 1
            self.logger.error(f"Ошибка парсинга страницы {page_number}: {e}")
            return [], {}
    
    async def parse_all_pages(
        self, 
        max_pages: Optional[int] = None,
        category: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None,
        project_repository: Optional[ProjectRepository] = None
    ) -> AsyncGenerator[List[Project], None]:
        """
        Парсинг всех страниц проектов с пагинацией
        
        Args:
            max_pages: Максимальное количество страниц (None = без ограничений)
            category: Категория проектов
            additional_params: Дополнительные параметры
            project_repository: Репозиторий для проверки дублирования
            
        Yields:
            List[Project]: Список проектов с каждой страницы
        """
        current_page = 1
        total_projects_found = 0
        
        self.logger.info(f"Начинаем парсинг проектов (макс. страниц: {max_pages or 'без ограничений'})")
        
        while True:
            # Проверяем лимиты
            if max_pages and current_page > max_pages:
                self.logger.info(f"Достигнут лимит страниц: {max_pages}")
                break
            
            try:
                # Парсим страницу
                projects, pagination_info = await self.parse_single_page(
                    page_number=current_page,
                    category=category,
                    additional_params=additional_params
                )
                
                if not projects:
                    self.logger.warning(f"На странице {current_page} не найдено проектов")
                    # Если это первая страница и нет проектов - останавливаемся
                    if current_page == 1:
                        break
                
                # Фильтруем дубликаты если есть репозиторий
                if project_repository:
                    filtered_projects = []
                    for project in projects:
                        if not await project_repository.exists_project(project.external_id):
                            filtered_projects.append(project)
                            self.stats["projects_new"] += 1
                    
                    projects = filtered_projects
                    self.logger.info(f"После фильтрации дубликатов: {len(projects)} новых проектов")
                
                total_projects_found += len(projects)
                
                # Возвращаем проекты
                yield projects
                
                # Проверяем есть ли следующая страница
                if not pagination_info.get("has_next", False):
                    self.logger.info("Больше страниц нет")
                    break
                
                current_page += 1
                
                # Небольшая задержка между страницами
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Критическая ошибка при парсинге страницы {current_page}: {e}")
                break
        
        self.logger.success(f"Парсинг завершен. Обработано страниц: {current_page - 1}, проектов: {total_projects_found}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики парсинга
        
        Returns:
            Dict: Статистика работы парсера
        """
        stats = self.stats.copy()
        
        if stats["start_time"]:
            stats["total_time"] = time.time() - stats["start_time"]
            stats["avg_page_time"] = stats["total_time"] / max(stats["pages_parsed"], 1)
        
        # Добавляем статистику rate limiter
        stats["rate_limiter"] = self.rate_limiter.get_stats()
        
        # Добавляем статистику user agent
        stats["user_agent"] = self.user_agent_rotator.get_stats()
        
        return stats


# Утилитарные функции для быстрого использования

async def parse_kwork_projects(
    max_pages: Optional[int] = None,
    category: Optional[str] = None,
    settings: Optional[Settings] = None
) -> List[Project]:
    """
    Быстрый парсинг проектов Kwork.ru
    
    Args:
        max_pages: Максимальное количество страниц
        category: Категория проектов
        settings: Настройки приложения
        
    Returns:
        List[Project]: Список всех найденных проектов
    """
    all_projects = []
    
    async with KworkParser(settings=settings) as parser:
        async for projects in parser.parse_all_pages(max_pages=max_pages, category=category):
            all_projects.extend(projects)
    
    return all_projects


async def parse_kwork_single_page(
    page_number: int = 1,
    category: Optional[str] = None,
    settings: Optional[Settings] = None
) -> List[Project]:
    """
    Парсинг одной страницы проектов
    
    Args:
        page_number: Номер страницы
        category: Категория проектов
        settings: Настройки приложения
        
    Returns:
        List[Project]: Список проектов со страницы
    """
    async with KworkParser(settings=settings) as parser:
        projects, _ = await parser.parse_single_page(page_number, category)
        return projects 
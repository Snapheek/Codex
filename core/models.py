"""
Pydantic модели данных для парсера Kwork.ru
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Union
from decimal import Decimal

from pydantic import BaseModel, Field, validator, HttpUrl


class ProjectStatus(str, Enum):
    """Статусы проекта"""
    NEW = "new"           # Новый проект
    UPDATED = "updated"   # Обновленный проект
    SENT = "sent"         # Уведомление отправлено
    ARCHIVED = "archived" # Архивный проект


class PriceType(str, Enum):
    """Типы цены проекта"""
    FIXED = "fixed"           # Фиксированная цена
    NEGOTIABLE = "negotiable" # Договорная
    HOURLY = "hourly"         # Почасовая оплата
    RANGE = "range"           # Диапазон цен


class Project(BaseModel):
    """
    Модель проекта с Kwork.ru
    
    Описывает структуру данных проекта для валидации и обработки
    """
    
    # Основные поля
    id: Optional[int] = Field(None, description="ID проекта в нашей БД")
    external_id: str = Field(..., description="Внешний ID проекта на Kwork")
    title: str = Field(..., min_length=1, max_length=500, description="Название проекта")
    description: str = Field(..., min_length=1, description="Описание проекта")
    
    # Ценовая информация
    price: Optional[Union[Decimal, str]] = Field(None, description="Цена проекта")
    price_type: PriceType = Field(default=PriceType.FIXED, description="Тип цены")
    currency: str = Field(default="RUB", max_length=10, description="Валюта")
    
    # Метаданные
    author: str = Field(..., max_length=255, description="Автор проекта")
    category: Optional[str] = Field(None, max_length=255, description="Категория проекта")
    subcategory: Optional[str] = Field(None, max_length=255, description="Подкатегория")
    
    # Временные метки
    date_created: datetime = Field(..., description="Дата создания проекта")
    date_parsed: datetime = Field(default_factory=datetime.utcnow, description="Дата парсинга")
    deadline: Optional[datetime] = Field(None, description="Дедлайн проекта")
    
    # Статистика
    responses_count: int = Field(default=0, ge=0, description="Количество откликов")
    views_count: int = Field(default=0, ge=0, description="Количество просмотров")
    
    # Ссылки и теги
    link: HttpUrl = Field(..., description="Ссылка на проект")
    tags: list[str] = Field(default_factory=list, description="Теги проекта")
    
    # Статус обработки
    status: ProjectStatus = Field(default=ProjectStatus.NEW, description="Статус проекта")
    notification_sent: bool = Field(default=False, description="Отправлено ли уведомление")
    
    # Дополнительные поля
    skills_required: list[str] = Field(default_factory=list, description="Требуемые навыки")
    experience_level: Optional[str] = Field(None, description="Уровень опыта")
    project_type: Optional[str] = Field(None, description="Тип проекта")
    
    class Config:
        """Настройки модели"""
        use_enum_values = True
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }
        schema_extra = {
            "example": {
                "external_id": "proj_123456",
                "title": "Разработка веб-сайта",
                "description": "Необходимо создать современный веб-сайт для компании...",
                "price": "50000",
                "price_type": "fixed",
                "currency": "RUB",
                "author": "john_doe",
                "category": "Программирование",
                "date_created": "2024-01-15T10:30:00Z",
                "responses_count": 5,
                "link": "https://kwork.ru/projects/123456",
                "tags": ["веб-разработка", "python", "django"],
                "skills_required": ["Python", "Django", "HTML", "CSS"]
            }
        }

    @validator('external_id')
    def validate_external_id(cls, v):
        """Валидация внешнего ID"""
        if not v or len(v.strip()) == 0:
            raise ValueError('External ID не может быть пустым')
        return v.strip()

    @validator('title')
    def validate_title(cls, v):
        """Валидация названия проекта"""
        v = v.strip()
        if len(v) < 3:
            raise ValueError('Название проекта должно содержать минимум 3 символа')
        return v

    @validator('description')
    def validate_description(cls, v):
        """Валидация описания проекта"""
        v = v.strip()
        if len(v) < 10:
            raise ValueError('Описание проекта должно содержать минимум 10 символов')
        return v

    @validator('price', pre=True)
    def validate_price(cls, v):
        """Валидация цены проекта"""
        if v is None:
            return None
        
        if isinstance(v, str):
            # Убираем все кроме цифр, точек и запятых
            v = v.replace(' ', '').replace(',', '.')
            if v.lower() in ('договорная', 'по договоренности', 'negotiable'):
                return None
            
            try:
                return Decimal(v)
            except:
                return None
        
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        
        return v

    @validator('author')
    def validate_author(cls, v):
        """Валидация автора проекта"""
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Имя автора должно содержать минимум 2 символа')
        return v

    @validator('tags', 'skills_required', pre=True)
    def validate_lists(cls, v):
        """Валидация списков"""
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(',') if tag.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    def is_duplicate(self, other: 'Project') -> bool:
        """
        Проверка на дублирование проекта
        
        Args:
            other: Другой проект для сравнения
            
        Returns:
            bool: True если проекты дублируются
        """
        if not isinstance(other, Project):
            return False
        
        # Сравниваем по external_id (основной критерий)
        if self.external_id == other.external_id:
            return True
        
        # Дополнительная проверка по названию и автору
        title_similar = self.title.lower().strip() == other.title.lower().strip()
        author_same = self.author.lower().strip() == other.author.lower().strip()
        
        # Проверяем разницу во времени (не более 1 часа)
        time_diff = abs((self.date_created - other.date_created).total_seconds())
        time_close = time_diff < 3600  # 1 час
        
        return title_similar and author_same and time_close

    def to_dict(self) -> dict:
        """
        Конвертация в словарь для экспорта
        
        Returns:
            dict: Словарь с данными проекта
        """
        return {
            'id': self.id,
            'external_id': self.external_id,
            'title': self.title,
            'description': self.description,
            'price': str(self.price) if self.price else None,
            'price_type': self.price_type,
            'currency': self.currency,
            'author': self.author,
            'category': self.category,
            'subcategory': self.subcategory,
            'date_created': self.date_created.isoformat(),
            'date_parsed': self.date_parsed.isoformat(),
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'responses_count': self.responses_count,
            'views_count': self.views_count,
            'link': str(self.link),
            'tags': ', '.join(self.tags),
            'status': self.status,
            'notification_sent': self.notification_sent,
            'skills_required': ', '.join(self.skills_required),
            'experience_level': self.experience_level,
            'project_type': self.project_type
        }


class ProjectFilter(BaseModel):
    """
    Модель для фильтрации проектов
    """
    category: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    author: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status: Optional[ProjectStatus] = None
    has_responses: Optional[bool] = None
    keywords: Optional[list[str]] = None
    exclude_keywords: Optional[list[str]] = None
    
    class Config:
        use_enum_values = True


class ProjectSearchResult(BaseModel):
    """
    Результат поиска проектов
    """
    projects: list[Project]
    total_count: int
    page: int = 1
    page_size: int = 50
    has_next: bool = False
    
    class Config:
        use_enum_values = True


class DatabaseStats(BaseModel):
    """
    Статистика базы данных проектов
    """
    total_projects: int
    new_projects: int
    sent_notifications: int
    categories: dict[str, int]
    date_range: tuple[datetime, datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
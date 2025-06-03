"""
SQLAlchemy модели для базы данных парсера Kwork.ru
Поддерживает как SQLite, так и PostgreSQL
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    DECIMAL, Enum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from core.models import ProjectStatus, PriceType

# Базовый класс для всех моделей
Base = declarative_base()


class ProjectModel(Base):
    """
    SQLAlchemy модель проекта в базе данных
    
    Соответствует Pydantic модели Project с дополнительными полями для БД
    """
    
    __tablename__ = 'projects'
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Уникальный внешний ID (из Kwork)
    external_id = Column(String(255), nullable=False, unique=True, index=True)
    
    # Основная информация
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Ценовая информация
    price = Column(DECIMAL(12, 2), nullable=True)
    price_type = Column(Enum(PriceType, name='price_type_enum'), 
                       default=PriceType.FIXED, nullable=False)
    currency = Column(String(10), default='RUB', nullable=False)
    
    # Метаданные
    author = Column(String(255), nullable=False, index=True)
    category = Column(String(255), nullable=True, index=True)
    subcategory = Column(String(255), nullable=True)
    
    # Временные метки
    date_created = Column(DateTime(timezone=True), nullable=False, index=True)
    date_parsed = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=True)
    
    # Статистика
    responses_count = Column(Integer, default=0, nullable=False)
    views_count = Column(Integer, default=0, nullable=False)
    
    # Ссылки
    link = Column(String(1000), nullable=False)
    
    # Статус обработки
    status = Column(Enum(ProjectStatus, name='project_status_enum'), 
                   default=ProjectStatus.NEW, nullable=False, index=True)
    notification_sent = Column(Boolean, default=False, nullable=False, index=True)
    
    # Дополнительные поля (JSON в строке для совместимости с SQLite)
    tags = Column(Text, nullable=True)  # JSON строка с тегами
    skills_required = Column(Text, nullable=True)  # JSON строка с навыками
    experience_level = Column(String(100), nullable=True)
    project_type = Column(String(100), nullable=True)
    
    # Системные поля
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), 
                       onupdate=func.now(), nullable=False)
    
    # Индексы для оптимизации запросов
    __table_args__ = (
        Index('idx_project_search', 'category', 'status', 'date_created'),
        Index('idx_project_author_date', 'author', 'date_created'),
        Index('idx_project_price_range', 'price', 'price_type'),
        Index('idx_project_notifications', 'notification_sent', 'status'),
        UniqueConstraint('external_id', name='uq_project_external_id'),
    )
    
    def __repr__(self) -> str:
        return f"<ProjectModel(id={self.id}, external_id='{self.external_id}', title='{self.title[:50]}...')>"
    
    def to_pydantic(self) -> 'Project':
        """
        Конвертация SQLAlchemy модели в Pydantic модель
        
        Returns:
            Project: Pydantic модель проекта
        """
        from core.models import Project
        import json
        
        # Парсим JSON поля
        tags = []
        skills_required = []
        
        try:
            if self.tags:
                tags = json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            tags = []
            
        try:
            if self.skills_required:
                skills_required = json.loads(self.skills_required)
        except (json.JSONDecodeError, TypeError):
            skills_required = []
        
        return Project(
            id=self.id,
            external_id=self.external_id,
            title=self.title,
            description=self.description,
            price=self.price,
            price_type=self.price_type,
            currency=self.currency,
            author=self.author,
            category=self.category,
            subcategory=self.subcategory,
            date_created=self.date_created,
            date_parsed=self.date_parsed,
            deadline=self.deadline,
            responses_count=self.responses_count,
            views_count=self.views_count,
            link=self.link,
            tags=tags,
            status=self.status,
            notification_sent=self.notification_sent,
            skills_required=skills_required,
            experience_level=self.experience_level,
            project_type=self.project_type
        )
    
    @classmethod
    def from_pydantic(cls, project: 'Project') -> 'ProjectModel':
        """
        Создание SQLAlchemy модели из Pydantic модели
        
        Args:
            project: Pydantic модель проекта
            
        Returns:
            ProjectModel: SQLAlchemy модель
        """
        import json
        
        return cls(
            external_id=project.external_id,
            title=project.title,
            description=project.description,
            price=project.price,
            price_type=project.price_type,
            currency=project.currency,
            author=project.author,
            category=project.category,
            subcategory=project.subcategory,
            date_created=project.date_created,
            date_parsed=project.date_parsed,
            deadline=project.deadline,
            responses_count=project.responses_count,
            views_count=project.views_count,
            link=str(project.link),
            tags=json.dumps(project.tags, ensure_ascii=False) if project.tags else None,
            status=project.status,
            notification_sent=project.notification_sent,
            skills_required=json.dumps(project.skills_required, ensure_ascii=False) if project.skills_required else None,
            experience_level=project.experience_level,
            project_type=project.project_type
        )


class ParseLogModel(Base):
    """
    Модель для логирования операций парсинга
    """
    
    __tablename__ = 'parse_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Информация о сессии парсинга
    session_id = Column(String(36), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    
    # Статистика парсинга
    pages_parsed = Column(Integer, default=0, nullable=False)
    projects_found = Column(Integer, default=0, nullable=False)
    projects_new = Column(Integer, default=0, nullable=False)
    projects_updated = Column(Integer, default=0, nullable=False)
    
    # Ошибки и статус
    errors_count = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default='running', nullable=False)  # running, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Конфигурация парсинга
    target_url = Column(String(1000), nullable=False)
    max_pages = Column(Integer, nullable=True)
    filters_applied = Column(Text, nullable=True)  # JSON с примененными фильтрами
    
    # Системные поля
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Индексы
    __table_args__ = (
        Index('idx_parse_log_session', 'session_id'),
        Index('idx_parse_log_status', 'status', 'start_time'),
    )
    
    def __repr__(self) -> str:
        return f"<ParseLogModel(id={self.id}, session_id='{self.session_id}', status='{self.status}')>"


class NotificationLogModel(Base):
    """
    Модель для логирования отправленных уведомлений
    """
    
    __tablename__ = 'notification_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Связь с проектом
    project_id = Column(Integer, nullable=False, index=True)
    project_external_id = Column(String(255), nullable=False)
    
    # Информация об уведомлении
    notification_type = Column(String(50), nullable=False)  # telegram, email, webhook
    recipient = Column(String(255), nullable=False)  # chat_id, email, url
    
    # Статус отправки
    status = Column(String(50), nullable=False)  # sent, failed, pending
    attempts_count = Column(Integer, default=1, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Содержимое уведомления
    message_text = Column(Text, nullable=True)
    message_format = Column(String(20), default='text', nullable=False)  # text, markdown, html
    
    # Временные метки
    sent_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Индексы
    __table_args__ = (
        Index('idx_notification_project', 'project_id'),
        Index('idx_notification_status', 'status', 'sent_at'),
        Index('idx_notification_recipient', 'recipient', 'notification_type'),
    )
    
    def __repr__(self) -> str:
        return f"<NotificationLogModel(id={self.id}, project_id={self.project_id}, status='{self.status}')>"


class SystemConfigModel(Base):
    """
    Модель для хранения системных настроек в БД
    """
    
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Ключ и значение настройки
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=True)
    value_type = Column(String(20), default='string', nullable=False)  # string, int, float, bool, json
    
    # Метаданные
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    is_encrypted = Column(Boolean, default=False, nullable=False)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), 
                       onupdate=func.now(), nullable=False)
    
    def __repr__(self) -> str:
        return f"<SystemConfigModel(key='{self.key}', value_type='{self.value_type}')>"
    
    def get_typed_value(self):
        """
        Возвращает значение в правильном типе
        
        Returns:
            Any: Значение в соответствующем типе
        """
        if self.value is None:
            return None
            
        if self.value_type == 'int':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes', 'on')
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        else:
            return self.value
    
    def set_typed_value(self, value):
        """
        Устанавливает значение с автоматическим определением типа
        
        Args:
            value: Значение для установки
        """
        if value is None:
            self.value = None
            return
            
        if isinstance(value, bool):
            self.value_type = 'bool'
            self.value = str(value).lower()
        elif isinstance(value, int):
            self.value_type = 'int'
            self.value = str(value)
        elif isinstance(value, float):
            self.value_type = 'float'
            self.value = str(value)
        elif isinstance(value, (dict, list)):
            self.value_type = 'json'
            import json
            self.value = json.dumps(value, ensure_ascii=False)
        else:
            self.value_type = 'string'
            self.value = str(value) 
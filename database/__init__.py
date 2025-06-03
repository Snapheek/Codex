"""
Модуль работы с базой данных

Предоставляет:
- Pydantic и SQLAlchemy модели данных
- Асинхронное подключение к БД (SQLite/PostgreSQL)
- Репозитории для CRUD операций
- Система миграций и health check
"""

# Модели данных
from .models import (
    Base,
    ProjectModel,
    ParseLogModel,
    NotificationLogModel,
    SystemConfigModel
)

# Подключение к БД
from .connection import (
    DatabaseManager,
    DatabaseHealthCheck,
    get_db_manager,
    init_database,
    close_database,
    get_db_session
)

# Репозитории
from .repository import (
    ProjectRepository,
    ParseLogRepository,
    StatisticsRepository,
    get_project_repository,
    get_parse_log_repository,
    get_statistics_repository
)

__all__ = [
    # Модели
    'Base',
    'ProjectModel',
    'ParseLogModel', 
    'NotificationLogModel',
    'SystemConfigModel',
    
    # Подключение
    'DatabaseManager',
    'DatabaseHealthCheck',
    'get_db_manager',
    'init_database',
    'close_database',
    'get_db_session',
    
    # Репозитории
    'ProjectRepository',
    'ParseLogRepository',
    'StatisticsRepository',
    'get_project_repository',
    'get_parse_log_repository',
    'get_statistics_repository'
] 
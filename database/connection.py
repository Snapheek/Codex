"""
Система подключения к базе данных для парсера Kwork.ru
Поддерживает асинхронные SQLite и PostgreSQL соединения
"""

import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncEngine, 
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy import event, text
from loguru import logger

from config.settings import Settings, get_settings
from database.models import Base


class DatabaseManager:
    """
    Менеджер подключений к базе данных с поддержкой миграций
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._is_initialized = False
    
    def _get_database_url(self) -> str:
        """
        Формирует URL подключения к базе данных
        
        Returns:
            str: URL подключения
        """
        db_config = self.settings.database
        
        if db_config.type == "sqlite":
            # Создаем директорию для SQLite если её нет
            db_path = Path(db_config.sqlite.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # SQLite URL для асинхронности
            return f"sqlite+aiosqlite:///{db_path}"
        
        elif db_config.type == "postgresql":
            pg_config = db_config.postgresql
            if not pg_config:
                raise ValueError("PostgreSQL настройки не найдены в конфигурации")
            
            # PostgreSQL URL для асинхронности
            return (
                f"postgresql+asyncpg://{pg_config.username}:{pg_config.password}"
                f"@{pg_config.host}:{pg_config.port}/{pg_config.database}"
            )
        
        else:
            raise ValueError(f"Неподдерживаемый тип БД: {db_config.type}")
    
    def _create_engine(self) -> AsyncEngine:
        """
        Создает асинхронный engine для базы данных
        
        Returns:
            AsyncEngine: Настроенный engine
        """
        database_url = self._get_database_url()
        db_config = self.settings.database
        
        # Общие настройки engine
        engine_kwargs = {
            "echo": db_config.echo,
            "future": True,
        }
        
        # Специфичные настройки для разных БД
        if db_config.type == "sqlite":
            engine_kwargs.update({
                "poolclass": StaticPool,
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 30
                }
            })
        elif db_config.type == "postgresql":
            engine_kwargs.update({
                "poolclass": QueuePool,
                "pool_size": db_config.pool_size,
                "max_overflow": db_config.max_overflow,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "pool_pre_ping": True
            })
        
        engine = create_async_engine(database_url, **engine_kwargs)
        
        # Настройка SQLite для поддержки внешних ключей
        if db_config.type == "sqlite":
            @event.listens_for(engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA temp_store=memory")
                cursor.execute("PRAGMA mmap_size=134217728")  # 128MB
                cursor.close()
        
        logger.info(f"Создан engine для {db_config.type}: {database_url.split('@')[-1] if '@' in database_url else database_url}")
        return engine
    
    async def initialize(self) -> None:
        """
        Инициализация подключения к базе данных
        """
        if self._is_initialized:
            logger.warning("База данных уже инициализирована")
            return
        
        try:
            # Создаем engine
            self.engine = self._create_engine()
            
            # Создаем фабрику сессий
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True
            )
            
            # Проверяем подключение
            await self._check_connection()
            
            # Создаем таблицы если их нет
            await self.create_tables()
            
            self._is_initialized = True
            logger.success("База данных успешно инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    async def _check_connection(self) -> None:
        """
        Проверка подключения к базе данных
        """
        if not self.engine:
            raise RuntimeError("Engine не инициализирован")
        
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Подключение к базе данных успешно")
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise
    
    async def create_tables(self) -> None:
        """
        Создание всех таблиц в базе данных
        """
        if not self.engine:
            raise RuntimeError("Engine не инициализирован")
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Таблицы базы данных созданы/обновлены")
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise
    
    async def drop_tables(self) -> None:
        """
        Удаление всех таблиц из базы данных (для тестов)
        """
        if not self.engine:
            raise RuntimeError("Engine не инициализирован")
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.warning("Все таблицы удалены из базы данных")
        except Exception as e:
            logger.error(f"Ошибка удаления таблиц: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Контекстный менеджер для получения сессии БД
        
        Yields:
            AsyncSession: Сессия базы данных
        """
        if not self._is_initialized:
            await self.initialize()
        
        if not self.session_factory:
            raise RuntimeError("Session factory не инициализирован")
        
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def execute_raw(self, query: str, params: Optional[dict] = None) -> None:
        """
        Выполнение сырого SQL запроса
        
        Args:
            query: SQL запрос
            params: Параметры запроса
        """
        async with self.get_session() as session:
            await session.execute(text(query), params or {})
    
    async def close(self) -> None:
        """
        Закрытие подключения к базе данных
        """
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._is_initialized = False
            logger.info("Подключение к базе данных закрыто")


# Глобальный экземпляр менеджера БД
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(settings: Optional[Settings] = None) -> DatabaseManager:
    """
    Получение глобального экземпляра менеджера БД (Singleton)
    
    Args:
        settings: Настройки приложения
        
    Returns:
        DatabaseManager: Менеджер базы данных
    """
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager(settings)
    
    return _db_manager


async def init_database(settings: Optional[Settings] = None) -> DatabaseManager:
    """
    Инициализация базы данных
    
    Args:
        settings: Настройки приложения
        
    Returns:
        DatabaseManager: Инициализированный менеджер БД
    """
    db_manager = get_db_manager(settings)
    await db_manager.initialize()
    return db_manager


async def close_database() -> None:
    """
    Закрытие подключения к базе данных
    """
    global _db_manager
    
    if _db_manager:
        await _db_manager.close()
        _db_manager = None


@asynccontextmanager
async def get_db_session(settings: Optional[Settings] = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Удобная функция для получения сессии БД
    
    Args:
        settings: Настройки приложения
        
    Yields:
        AsyncSession: Сессия базы данных
    """
    db_manager = get_db_manager(settings)
    async with db_manager.get_session() as session:
        yield session


class DatabaseHealthCheck:
    """
    Класс для проверки состояния базы данных
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def check_health(self) -> dict:
        """
        Проверка состояния базы данных
        
        Returns:
            dict: Статус БД
        """
        try:
            # Проверка подключения
            start_time = asyncio.get_event_loop().time()
            async with self.db_manager.get_session() as session:
                await session.execute(text("SELECT 1"))
            connection_time = asyncio.get_event_loop().time() - start_time
            
            # Получение статистики таблиц
            tables_info = await self._get_tables_info()
            
            return {
                "status": "healthy",
                "connection_time_ms": round(connection_time * 1000, 2),
                "database_type": self.db_manager.settings.database.type,
                "tables": tables_info,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
    
    async def _get_tables_info(self) -> dict:
        """
        Получение информации о таблицах
        
        Returns:
            dict: Информация о таблицах
        """
        tables_info = {}
        
        try:
            async with self.db_manager.get_session() as session:
                # Получаем количество записей в основных таблицах
                from database.models import ProjectModel, ParseLogModel, NotificationLogModel
                
                # Проекты
                result = await session.execute(text("SELECT COUNT(*) FROM projects"))
                projects_count = result.scalar()
                
                # Логи парсинга
                result = await session.execute(text("SELECT COUNT(*) FROM parse_logs"))
                parse_logs_count = result.scalar()
                
                # Логи уведомлений
                result = await session.execute(text("SELECT COUNT(*) FROM notification_logs"))
                notification_logs_count = result.scalar()
                
                tables_info = {
                    "projects": {"count": projects_count},
                    "parse_logs": {"count": parse_logs_count},
                    "notification_logs": {"count": notification_logs_count}
                }
                
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о таблицах: {e}")
            tables_info = {"error": str(e)}
        
        return tables_info 
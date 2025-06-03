"""
Репозиторий для работы с проектами в базе данных
Предоставляет CRUD операции и бизнес-логику
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from decimal import Decimal

from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from core.models import Project, ProjectFilter, ProjectSearchResult, ProjectStatus, DatabaseStats
from database.models import ProjectModel, ParseLogModel, NotificationLogModel
from database.connection import get_db_session


class ProjectRepository:
    """
    Репозиторий для работы с проектами
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_project(self, project: Project) -> ProjectModel:
        """
        Создание нового проекта в базе данных
        
        Args:
            project: Pydantic модель проекта
            
        Returns:
            ProjectModel: Созданная SQLAlchemy модель
        """
        try:
            # Проверяем на дублирование
            existing = await self.get_project_by_external_id(project.external_id)
            if existing:
                logger.warning(f"Проект с external_id {project.external_id} уже существует")
                return existing
            
            # Создаем новую модель
            db_project = ProjectModel.from_pydantic(project)
            
            self.session.add(db_project)
            await self.session.flush()  # Получаем ID
            await self.session.refresh(db_project)
            
            logger.info(f"Создан проект: {db_project.id} - {db_project.title[:50]}...")
            return db_project
            
        except Exception as e:
            logger.error(f"Ошибка создания проекта: {e}")
            raise
    
    async def get_project_by_id(self, project_id: int) -> Optional[ProjectModel]:
        """
        Получение проекта по ID
        
        Args:
            project_id: ID проекта
            
        Returns:
            ProjectModel: Найденный проект или None
        """
        try:
            result = await self.session.execute(
                select(ProjectModel).where(ProjectModel.id == project_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка получения проекта по ID {project_id}: {e}")
            return None
    
    async def get_project_by_external_id(self, external_id: str) -> Optional[ProjectModel]:
        """
        Получение проекта по внешнему ID
        
        Args:
            external_id: Внешний ID проекта
            
        Returns:
            ProjectModel: Найденный проект или None
        """
        try:
            result = await self.session.execute(
                select(ProjectModel).where(ProjectModel.external_id == external_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка получения проекта по external_id {external_id}: {e}")
            return None
    
    async def exists_project(self, external_id: str) -> bool:
        """
        Проверка существования проекта
        
        Args:
            external_id: Внешний ID проекта
            
        Returns:
            bool: True если проект существует
        """
        try:
            result = await self.session.execute(
                select(func.count(ProjectModel.id)).where(
                    ProjectModel.external_id == external_id
                )
            )
            return result.scalar() > 0
        except Exception as e:
            logger.error(f"Ошибка проверки существования проекта {external_id}: {e}")
            return False
    
    async def update_project(self, project_id: int, **kwargs) -> Optional[ProjectModel]:
        """
        Обновление проекта
        
        Args:
            project_id: ID проекта
            **kwargs: Поля для обновления
            
        Returns:
            ProjectModel: Обновленный проект или None
        """
        try:
            # Добавляем время обновления
            kwargs['updated_at'] = datetime.utcnow()
            
            await self.session.execute(
                update(ProjectModel)
                .where(ProjectModel.id == project_id)
                .values(**kwargs)
            )
            
            # Получаем обновленный проект
            return await self.get_project_by_id(project_id)
            
        except Exception as e:
            logger.error(f"Ошибка обновления проекта {project_id}: {e}")
            return None
    
    async def mark_as_sent(self, project_id: int) -> bool:
        """
        Отметить проект как "уведомление отправлено"
        
        Args:
            project_id: ID проекта
            
        Returns:
            bool: True если успешно
        """
        try:
            result = await self.update_project(
                project_id,
                notification_sent=True,
                status=ProjectStatus.SENT
            )
            return result is not None
        except Exception as e:
            logger.error(f"Ошибка отметки проекта {project_id} как отправленного: {e}")
            return False
    
    async def search_projects(self, filters: ProjectFilter, page: int = 1, page_size: int = 50) -> ProjectSearchResult:
        """
        Поиск проектов с фильтрацией и пагинацией
        
        Args:
            filters: Фильтры поиска
            page: Номер страницы
            page_size: Размер страницы
            
        Returns:
            ProjectSearchResult: Результат поиска
        """
        try:
            # Базовый запрос
            query = select(ProjectModel)
            count_query = select(func.count(ProjectModel.id))
            
            # Применяем фильтры
            conditions = []
            
            if filters.category:
                conditions.append(ProjectModel.category.ilike(f"%{filters.category}%"))
            
            if filters.min_price is not None:
                conditions.append(ProjectModel.price >= filters.min_price)
            
            if filters.max_price is not None:
                conditions.append(ProjectModel.price <= filters.max_price)
            
            if filters.author:
                conditions.append(ProjectModel.author.ilike(f"%{filters.author}%"))
            
            if filters.date_from:
                conditions.append(ProjectModel.date_created >= filters.date_from)
            
            if filters.date_to:
                conditions.append(ProjectModel.date_created <= filters.date_to)
            
            if filters.status:
                conditions.append(ProjectModel.status == filters.status)
            
            if filters.has_responses is not None:
                if filters.has_responses:
                    conditions.append(ProjectModel.responses_count > 0)
                else:
                    conditions.append(ProjectModel.responses_count == 0)
            
            if filters.keywords:
                keyword_conditions = []
                for keyword in filters.keywords:
                    keyword_conditions.append(
                        or_(
                            ProjectModel.title.ilike(f"%{keyword}%"),
                            ProjectModel.description.ilike(f"%{keyword}%")
                        )
                    )
                conditions.extend(keyword_conditions)
            
            if filters.exclude_keywords:
                for keyword in filters.exclude_keywords:
                    conditions.append(
                        and_(
                            ~ProjectModel.title.ilike(f"%{keyword}%"),
                            ~ProjectModel.description.ilike(f"%{keyword}%")
                        )
                    )
            
            # Применяем условия
            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))
            
            # Получаем общее количество
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()
            
            # Применяем сортировку и пагинацию
            query = query.order_by(desc(ProjectModel.date_created))
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            # Выполняем запрос
            result = await self.session.execute(query)
            projects_models = result.scalars().all()
            
            # Конвертируем в Pydantic модели
            projects = [model.to_pydantic() for model in projects_models]
            
            return ProjectSearchResult(
                projects=projects,
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_next=(page * page_size) < total_count
            )
            
        except Exception as e:
            logger.error(f"Ошибка поиска проектов: {e}")
            return ProjectSearchResult(projects=[], total_count=0, page=page, page_size=page_size)
    
    async def get_new_projects(self, limit: int = 100) -> List[ProjectModel]:
        """
        Получение новых проектов (status = NEW)
        
        Args:
            limit: Максимальное количество проектов
            
        Returns:
            List[ProjectModel]: Список новых проектов
        """
        try:
            result = await self.session.execute(
                select(ProjectModel)
                .where(ProjectModel.status == ProjectStatus.NEW)
                .order_by(desc(ProjectModel.date_created))
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка получения новых проектов: {e}")
            return []
    
    async def get_unsent_projects(self, limit: int = 100) -> List[ProjectModel]:
        """
        Получение проектов без отправленных уведомлений
        
        Args:
            limit: Максимальное количество проектов
            
        Returns:
            List[ProjectModel]: Список проектов без уведомлений
        """
        try:
            result = await self.session.execute(
                select(ProjectModel)
                .where(
                    and_(
                        ProjectModel.notification_sent == False,
                        ProjectModel.status.in_([ProjectStatus.NEW, ProjectStatus.UPDATED])
                    )
                )
                .order_by(desc(ProjectModel.date_created))
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка получения неотправленных проектов: {e}")
            return []
    
    async def check_duplicates(self, project: Project) -> List[ProjectModel]:
        """
        Проверка на дублирование проектов
        
        Args:
            project: Проект для проверки
            
        Returns:
            List[ProjectModel]: Список возможных дубликатов
        """
        try:
            # Проверяем по external_id
            exact_match = await self.get_project_by_external_id(project.external_id)
            if exact_match:
                return [exact_match]
            
            # Проверяем по названию и автору
            time_threshold = project.date_created - timedelta(hours=1)
            
            result = await self.session.execute(
                select(ProjectModel)
                .where(
                    and_(
                        ProjectModel.title.ilike(f"%{project.title[:50]}%"),
                        ProjectModel.author == project.author,
                        ProjectModel.date_created >= time_threshold
                    )
                )
                .limit(10)
            )
            
            potential_duplicates = list(result.scalars().all())
            
            # Дополнительная проверка с использованием Pydantic метода
            actual_duplicates = []
            for db_project in potential_duplicates:
                pydantic_project = db_project.to_pydantic()
                if project.is_duplicate(pydantic_project):
                    actual_duplicates.append(db_project)
            
            return actual_duplicates
            
        except Exception as e:
            logger.error(f"Ошибка проверки дубликатов: {e}")
            return []
    
    async def delete_project(self, project_id: int) -> bool:
        """
        Удаление проекта
        
        Args:
            project_id: ID проекта
            
        Returns:
            bool: True если успешно удален
        """
        try:
            result = await self.session.execute(
                delete(ProjectModel).where(ProjectModel.id == project_id)
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления проекта {project_id}: {e}")
            return False


class ParseLogRepository:
    """
    Репозиторий для работы с логами парсинга
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_log(self, session_id: str, target_url: str, max_pages: Optional[int] = None, filters_applied: Optional[dict] = None) -> ParseLogModel:
        """
        Создание лога парсинга
        
        Args:
            session_id: Уникальный ID сессии
            target_url: URL для парсинга
            max_pages: Максимальное количество страниц
            filters_applied: Примененные фильтры
            
        Returns:
            ParseLogModel: Созданный лог
        """
        import json
        
        log = ParseLogModel(
            session_id=session_id,
            start_time=datetime.utcnow(),
            target_url=target_url,
            max_pages=max_pages,
            filters_applied=json.dumps(filters_applied, ensure_ascii=False) if filters_applied else None
        )
        
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        
        return log
    
    async def update_log(self, log_id: int, **kwargs) -> Optional[ParseLogModel]:
        """
        Обновление лога парсинга
        
        Args:
            log_id: ID лога
            **kwargs: Поля для обновления
            
        Returns:
            ParseLogModel: Обновленный лог
        """
        try:
            await self.session.execute(
                update(ParseLogModel)
                .where(ParseLogModel.id == log_id)
                .values(**kwargs)
            )
            
            result = await self.session.execute(
                select(ParseLogModel).where(ParseLogModel.id == log_id)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Ошибка обновления лога {log_id}: {e}")
            return None
    
    async def finish_log(self, log_id: int, status: str = "completed", error_message: Optional[str] = None) -> bool:
        """
        Завершение лога парсинга
        
        Args:
            log_id: ID лога
            status: Статус завершения
            error_message: Сообщение об ошибке
            
        Returns:
            bool: True если успешно
        """
        try:
            result = await self.update_log(
                log_id,
                end_time=datetime.utcnow(),
                status=status,
                error_message=error_message
            )
            return result is not None
        except Exception as e:
            logger.error(f"Ошибка завершения лога {log_id}: {e}")
            return False


class StatisticsRepository:
    """
    Репозиторий для получения статистики
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_database_stats(self) -> DatabaseStats:
        """
        Получение статистики базы данных
        
        Returns:
            DatabaseStats: Статистика БД
        """
        try:
            # Общее количество проектов
            total_result = await self.session.execute(
                select(func.count(ProjectModel.id))
            )
            total_projects = total_result.scalar()
            
            # Новые проекты
            new_result = await self.session.execute(
                select(func.count(ProjectModel.id))
                .where(ProjectModel.status == ProjectStatus.NEW)
            )
            new_projects = new_result.scalar()
            
            # Отправленные уведомления
            sent_result = await self.session.execute(
                select(func.count(ProjectModel.id))
                .where(ProjectModel.notification_sent == True)
            )
            sent_notifications = sent_result.scalar()
            
            # Статистика по категориям
            categories_result = await self.session.execute(
                select(ProjectModel.category, func.count(ProjectModel.id))
                .group_by(ProjectModel.category)
                .order_by(desc(func.count(ProjectModel.id)))
            )
            categories = dict(categories_result.fetchall())
            
            # Диапазон дат
            date_result = await self.session.execute(
                select(
                    func.min(ProjectModel.date_created),
                    func.max(ProjectModel.date_created)
                )
            )
            date_range = date_result.fetchone()
            
            return DatabaseStats(
                total_projects=total_projects,
                new_projects=new_projects,
                sent_notifications=sent_notifications,
                categories=categories,
                date_range=(date_range[0] or datetime.utcnow(), date_range[1] or datetime.utcnow())
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            # Возвращаем пустую статистику
            return DatabaseStats(
                total_projects=0,
                new_projects=0,
                sent_notifications=0,
                categories={},
                date_range=(datetime.utcnow(), datetime.utcnow())
            )


# Фабричные функции для получения репозиториев

async def get_project_repository() -> ProjectRepository:
    """
    Получение репозитория проектов
    
    Returns:
        ProjectRepository: Репозиторий проектов
    """
    async with get_db_session() as session:
        return ProjectRepository(session)


async def get_parse_log_repository() -> ParseLogRepository:
    """
    Получение репозитория логов парсинга
    
    Returns:
        ParseLogRepository: Репозиторий логов
    """
    async with get_db_session() as session:
        return ParseLogRepository(session)


async def get_statistics_repository() -> StatisticsRepository:
    """
    Получение репозитория статистики
    
    Returns:
        StatisticsRepository: Репозиторий статистики
    """
    async with get_db_session() as session:
        return StatisticsRepository(session) 
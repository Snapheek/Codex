"""
Система логирования для парсера Kwork.ru
Настройка логирования с ротацией файлов и различными уровнями
"""

import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

from loguru import logger as loguru_logger
from config.settings import Settings, get_settings


@dataclass
class LoggingConfig:
    """Конфигурация логирования"""
    level: str = "INFO"
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    
    # Файлы логов
    main_log: str = "logs/kwork_parser.log"
    parser_log: str = "logs/parser.log"
    telegram_log: str = "logs/telegram.log"
    database_log: str = "logs/database.log"
    error_log: str = "logs/errors.log"
    
    # Ротация
    rotation_size: str = "10 MB"
    rotation_time: str = "1 day"
    retention_count: int = 7
    retention_time: str = "1 week"
    
    # Формат
    console_format: str = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>"
    file_format: str = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    
    # Дополнительные настройки
    colorize: bool = True
    diagnose: bool = True
    enqueue: bool = True
    serialize: bool = False


class KworkLogger:
    """
    Основной класс для логирования парсера
    """
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        self.config = config or LoggingConfig()
        self._is_configured = False
        self._loggers = {}
        
        # Создаем директорию для логов
        self._ensure_log_directory()
        
        # Настраиваем loguru
        self._configure_loguru()
        
        # Настраиваем стандартное логирование
        self._configure_stdlib_logging()
        
        self._is_configured = True
    
    def _ensure_log_directory(self) -> None:
        """Создание директории для логов"""
        log_files = [
            self.config.main_log,
            self.config.parser_log,
            self.config.telegram_log,
            self.config.database_log,
            self.config.error_log
        ]
        
        for log_file in log_files:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _configure_loguru(self) -> None:
        """Настройка loguru логирования"""
        # Очищаем существующие обработчики
        loguru_logger.remove()
        
        # Консольный вывод
        loguru_logger.add(
            sys.stderr,
            format=self.config.console_format,
            level=self.config.console_level,
            colorize=self.config.colorize,
            enqueue=self.config.enqueue,
            diagnose=self.config.diagnose
        )
        
        # Основной лог файл
        loguru_logger.add(
            self.config.main_log,
            format=self.config.file_format,
            level=self.config.file_level,
            rotation=self.config.rotation_size,
            retention=self.config.retention_count,
            enqueue=self.config.enqueue,
            serialize=self.config.serialize,
            encoding="utf-8"
        )
        
        # Лог ошибок (только ERROR и выше)
        loguru_logger.add(
            self.config.error_log,
            format=self.config.file_format,
            level="ERROR",
            rotation=self.config.rotation_size,
            retention=self.config.retention_count,
            enqueue=self.config.enqueue,
            serialize=self.config.serialize,
            encoding="utf-8",
            filter=lambda record: record["level"].no >= loguru_logger.level("ERROR").no
        )
        
        # Специализированные логи
        self._add_filtered_logger("parser", self.config.parser_log, ["core", "parser"])
        self._add_filtered_logger("telegram", self.config.telegram_log, ["telegram", "bot"])
        self._add_filtered_logger("database", self.config.database_log, ["database", "sqlalchemy"])
    
    def _add_filtered_logger(self, name: str, file_path: str, modules: list) -> None:
        """Добавление фильтрованного логгера для конкретных модулей"""
        def module_filter(record):
            return any(module in record["name"] for module in modules)
        
        loguru_logger.add(
            file_path,
            format=self.config.file_format,
            level=self.config.file_level,
            rotation=self.config.rotation_size,
            retention=self.config.retention_count,
            filter=module_filter,
            enqueue=self.config.enqueue,
            serialize=self.config.serialize,
            encoding="utf-8"
        )
    
    def _configure_stdlib_logging(self) -> None:
        """Настройка стандартного logging для интеграции с библиотеками"""
        # Создаем форматтер
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Настраиваем root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.level.upper()))
        
        # Очищаем существующие обработчики
        root_logger.handlers.clear()
        
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.config.console_level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Файловый обработчик с ротацией
        file_handler = logging.handlers.RotatingFileHandler(
            self.config.main_log,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=self.config.retention_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, self.config.file_level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Настройка уровней для конкретных библиотек
        self._configure_library_loggers()
    
    def _configure_library_loggers(self) -> None:
        """Настройка логирования для конкретных библиотек"""
        library_levels = {
            'aiohttp': 'WARNING',
            'aiohttp.access': 'WARNING',
            'urllib3': 'WARNING',
            'requests': 'WARNING',
            'httpx': 'WARNING',
            'sqlalchemy.engine': 'WARNING',
            'sqlalchemy.pool': 'WARNING',
            'telegram': 'INFO',
            'asyncio': 'WARNING',
        }
        
        for library, level in library_levels.items():
            library_logger = logging.getLogger(library)
            library_logger.setLevel(getattr(logging, level.upper()))
    
    def get_logger(self, name: str) -> loguru_logger:
        """
        Получение логгера для конкретного модуля
        
        Args:
            name: Имя модуля
            
        Returns:
            loguru_logger: Настроенный логгер
        """
        return loguru_logger.bind(name=name)
    
    def set_level(self, level: str) -> None:
        """
        Изменение уровня логирования
        
        Args:
            level: Новый уровень логирования
        """
        self.config.level = level.upper()
        
        # Обновляем loguru
        loguru_logger.remove()
        self._configure_loguru()
        
        # Обновляем stdlib logging
        logging.getLogger().setLevel(getattr(logging, level.upper()))
    
    def add_file_logger(
        self,
        name: str,
        file_path: str,
        level: str = "DEBUG",
        filter_func: Optional[callable] = None
    ) -> None:
        """
        Добавление дополнительного файлового логгера
        
        Args:
            name: Имя логгера
            file_path: Путь к файлу
            level: Уровень логирования
            filter_func: Функция фильтрации
        """
        # Создаем директорию если нужно
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Добавляем в loguru
        handler_config = {
            "format": self.config.file_format,
            "level": level,
            "rotation": self.config.rotation_size,
            "retention": self.config.retention_count,
            "enqueue": self.config.enqueue,
            "serialize": self.config.serialize,
            "encoding": "utf-8"
        }
        
        if filter_func:
            handler_config["filter"] = filter_func
        
        loguru_logger.add(file_path, **handler_config)
    
    def log_request(
        self,
        url: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Логирование HTTP запроса
        
        Args:
            url: URL запроса
            method: HTTP метод
            status_code: Статус код ответа
            response_time: Время ответа в секундах
            error: Сообщение об ошибке
        """
        log_data = {
            "url": url,
            "method": method,
            "status_code": status_code,
            "response_time": response_time,
            "error": error
        }
        
        if error:
            loguru_logger.error(f"HTTP {method} {url} failed: {error}", extra=log_data)
        elif status_code and status_code >= 400:
            loguru_logger.warning(f"HTTP {method} {url} returned {status_code}", extra=log_data)
        else:
            loguru_logger.info(f"HTTP {method} {url} -> {status_code} ({response_time:.2f}s)", extra=log_data)
    
    def log_parsing_stats(
        self,
        url: str,
        projects_found: int,
        projects_new: int,
        parsing_time: float,
        errors: int = 0
    ) -> None:
        """
        Логирование статистики парсинга
        
        Args:
            url: URL страницы
            projects_found: Найдено проектов
            projects_new: Новых проектов
            parsing_time: Время парсинга
            errors: Количество ошибок
        """
        stats_data = {
            "url": url,
            "projects_found": projects_found,
            "projects_new": projects_new,
            "parsing_time": parsing_time,
            "errors": errors
        }
        
        loguru_logger.info(
            f"Парсинг {url}: найдено {projects_found}, новых {projects_new}, "
            f"время {parsing_time:.2f}с, ошибок {errors}",
            extra=stats_data
        )
    
    def log_performance(self, operation: str, duration: float, **kwargs) -> None:
        """
        Логирование производительности операций
        
        Args:
            operation: Название операции
            duration: Продолжительность в секундах
            **kwargs: Дополнительные данные
        """
        perf_data = {
            "operation": operation,
            "duration": duration,
            **kwargs
        }
        
        if duration > 5.0:  # Медленные операции
            loguru_logger.warning(f"Медленная операция {operation}: {duration:.2f}с", extra=perf_data)
        else:
            loguru_logger.debug(f"Операция {operation}: {duration:.2f}с", extra=perf_data)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики логирования
        
        Returns:
            Dict: Статистика логирования
        """
        stats = {
            "config": {
                "level": self.config.level,
                "console_level": self.config.console_level,
                "file_level": self.config.file_level,
            },
            "files": {
                "main_log": self.config.main_log,
                "parser_log": self.config.parser_log,
                "telegram_log": self.config.telegram_log,
                "database_log": self.config.database_log,
                "error_log": self.config.error_log,
            },
            "file_sizes": {}
        }
        
        # Проверяем размеры файлов логов
        for log_name, log_path in stats["files"].items():
            try:
                file_path = Path(log_path)
                if file_path.exists():
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    stats["file_sizes"][log_name] = f"{size_mb:.2f} MB"
                else:
                    stats["file_sizes"][log_name] = "не существует"
            except Exception:
                stats["file_sizes"][log_name] = "ошибка"
        
        return stats


# Глобальный экземпляр логгера
_global_logger: Optional[KworkLogger] = None


def setup_logging(config: Optional[LoggingConfig] = None, settings: Optional[Settings] = None) -> KworkLogger:
    """
    Настройка глобального логирования
    
    Args:
        config: Конфигурация логирования
        settings: Настройки приложения
        
    Returns:
        KworkLogger: Настроенный логгер
    """
    global _global_logger
    
    # Если настройки не переданы, загружаем из конфигурации
    if config is None and settings is None:
        try:
            settings = get_settings()
        except Exception:
            pass  # Используем конфигурацию по умолчанию
    
    # Создаем конфигурацию из настроек приложения
    if config is None and settings:
        config = LoggingConfig(
            level=settings.logging.level,
            main_log=settings.logging.files.main,
            parser_log=settings.logging.files.parser,
            telegram_log=settings.logging.files.telegram,
            database_log=settings.logging.files.database,
            file_format=settings.logging.format,
            retention_time=settings.logging.retention
        )
    
    _global_logger = KworkLogger(config)
    return _global_logger


def get_logger(name: str = __name__) -> loguru_logger:
    """
    Получение логгера для модуля
    
    Args:
        name: Имя модуля
        
    Returns:
        loguru_logger: Логгер
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = setup_logging()
    
    return _global_logger.get_logger(name)


def log_function_call(func):
    """
    Декоратор для логирования вызовов функций
    
    Args:
        func: Декорируемая функция
        
    Returns:
        Decorator: Декорированная функция
    """
    def wrapper(*args, **kwargs):
        func_logger = get_logger(func.__module__)
        func_logger.debug(f"Вызов функции {func.__name__} с args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            func_logger.debug(f"Функция {func.__name__} завершена успешно")
            return result
        except Exception as e:
            func_logger.error(f"Ошибка в функции {func.__name__}: {e}")
            raise
    
    return wrapper


def log_async_function_call(func):
    """
    Декоратор для логирования асинхронных функций
    
    Args:
        func: Асинхронная функция
        
    Returns:
        Decorator: Декорированная асинхронная функция
    """
    async def wrapper(*args, **kwargs):
        func_logger = get_logger(func.__module__)
        func_logger.debug(f"Вызов async функции {func.__name__}")
        
        try:
            result = await func(*args, **kwargs)
            func_logger.debug(f"Async функция {func.__name__} завершена успешно")
            return result
        except Exception as e:
            func_logger.error(f"Ошибка в async функции {func.__name__}: {e}")
            raise
    
    return wrapper


# Предустановленные конфигурации
DEBUG_CONFIG = LoggingConfig(
    level="DEBUG",
    console_level="DEBUG",
    file_level="DEBUG",
    colorize=True,
    diagnose=True
)

PRODUCTION_CONFIG = LoggingConfig(
    level="INFO",
    console_level="WARNING",
    file_level="INFO",
    colorize=False,
    diagnose=False,
    serialize=True
)

SILENT_CONFIG = LoggingConfig(
    level="WARNING",
    console_level="ERROR",
    file_level="WARNING",
    colorize=False,
    diagnose=False
)


# Интеграция с loguru для удобства
def trace(message: str, **kwargs) -> None:
    """Trace уровень логирования"""
    get_logger().trace(message, **kwargs)


def debug(message: str, **kwargs) -> None:
    """Debug уровень логирования"""
    get_logger().debug(message, **kwargs)


def info(message: str, **kwargs) -> None:
    """Info уровень логирования"""
    get_logger().info(message, **kwargs)


def success(message: str, **kwargs) -> None:
    """Success уровень логирования"""
    get_logger().success(message, **kwargs)


def warning(message: str, **kwargs) -> None:
    """Warning уровень логирования"""
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs) -> None:
    """Error уровень логирования"""
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs) -> None:
    """Critical уровень логирования"""
    get_logger().critical(message, **kwargs) 
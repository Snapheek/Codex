"""
Retry логика с exponential backoff для парсера Kwork.ru
Обеспечивает устойчивость к сетевым сбоям и временным блокировкам
"""

import asyncio
import functools
import random
import time
from typing import Any, Callable, List, Optional, Type, Union
from dataclasses import dataclass

import aiohttp
from loguru import logger


@dataclass
class RetryConfig:
    """Конфигурация retry логики"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    backoff_multiplier: float = 1.0


class RetryableError(Exception):
    """Базовый класс для ошибок, которые можно повторить"""
    pass


class NonRetryableError(Exception):
    """Базовый класс для ошибок, которые нельзя повторить"""
    pass


# Стандартные ошибки для retry
RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientError,
    aiohttp.ServerTimeoutError,
    aiohttp.ClientTimeout,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    RetryableError
)

# HTTP статусы для retry
RETRYABLE_STATUS_CODES = {
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
    521,  # Web Server Is Down
    522,  # Connection Timed Out
    523,  # Origin Is Unreachable
    524,  # A Timeout Occurred
}


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Вычисляет задержку для retry с exponential backoff
    
    Args:
        attempt: Номер попытки (начиная с 1)
        config: Конфигурация retry
        
    Returns:
        float: Задержка в секундах
    """
    # Exponential backoff
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    delay *= config.backoff_multiplier
    
    # Ограничиваем максимальной задержкой
    delay = min(delay, config.max_delay)
    
    # Добавляем jitter для избежания thundering herd
    if config.jitter:
        jitter_range = delay * 0.1  # 10% jitter
        delay += random.uniform(-jitter_range, jitter_range)
    
    return max(0, delay)


def is_retryable_http_status(status_code: int) -> bool:
    """
    Проверяет, является ли HTTP статус код ретраебельным
    
    Args:
        status_code: HTTP статус код
        
    Returns:
        bool: True если можно повторить запрос
    """
    return status_code in RETRYABLE_STATUS_CODES


def is_retryable_exception(exception: Exception) -> bool:
    """
    Проверяет, является ли исключение ретраебельным
    
    Args:
        exception: Исключение для проверки
        
    Returns:
        bool: True если можно повторить операцию
    """
    # Проверяем тип исключения
    if isinstance(exception, NonRetryableError):
        return False
    
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True
    
    # Проверяем HTTP ошибки
    if isinstance(exception, aiohttp.ClientResponseError):
        return is_retryable_http_status(exception.status)
    
    return False


async def retry_async(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Optional[tuple] = None,
    on_retry: Optional[Callable] = None,
    **kwargs
) -> Any:
    """
    Асинхронная функция retry с exponential backoff
    
    Args:
        func: Функция для выполнения
        *args: Аргументы для функции
        config: Конфигурация retry
        retryable_exceptions: Кастомные исключения для retry
        on_retry: Callback при retry
        **kwargs: Именованные аргументы для функции
        
    Returns:
        Any: Результат выполнения функции
        
    Raises:
        Exception: Последнее исключение если все попытки неуспешны
    """
    if config is None:
        config = RetryConfig()
    
    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS
    
    last_exception = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            # Выполняем функцию
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            logger.debug(f"Операция успешна с попытки {attempt}")
            return result
            
        except Exception as e:
            last_exception = e
            
            # Проверяем, можно ли повторить
            if not is_retryable_exception(e):
                logger.warning(f"Неретраебельная ошибка: {e}")
                raise e
            
            # Если это последняя попытка, поднимаем исключение
            if attempt == config.max_attempts:
                logger.error(f"Все {config.max_attempts} попыток неуспешны. Последняя ошибка: {e}")
                raise e
            
            # Вычисляем задержку
            delay = calculate_delay(attempt, config)
            
            logger.warning(
                f"Попытка {attempt}/{config.max_attempts} неуспешна: {e}. "
                f"Повтор через {delay:.2f} секунд"
            )
            
            # Вызываем callback если есть
            if on_retry:
                try:
                    if asyncio.iscoroutinefunction(on_retry):
                        await on_retry(attempt, e, delay)
                    else:
                        on_retry(attempt, e, delay)
                except Exception as callback_error:
                    logger.error(f"Ошибка в callback on_retry: {callback_error}")
            
            # Ждем перед следующей попыткой
            await asyncio.sleep(delay)
    
    # Это не должно произойти, но на всякий случай
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Неожиданная ошибка в retry логике")


def retry_decorator(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[tuple] = None
):
    """
    Декоратор для добавления retry логики к функциям
    
    Args:
        max_attempts: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        max_delay: Максимальная задержка в секундах
        exponential_base: База для exponential backoff
        jitter: Добавлять ли случайность к задержке
        retryable_exceptions: Кастомные исключения для retry
        
    Returns:
        Decorator: Декорированная функция
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter
    )
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func, *args,
                config=config,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper
    
    return decorator


# Предустановленные конфигурации
FAST_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=1.5
)

STANDARD_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0
)

AGGRESSIVE_RETRY = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=120.0,
    exponential_base=2.5
)


class RetrySession:
    """
    HTTP сессия с автоматическим retry
    """
    
    def __init__(
        self, 
        session: aiohttp.ClientSession,
        config: Optional[RetryConfig] = None
    ):
        self.session = session
        self.config = config or STANDARD_RETRY
    
    async def request(
        self, 
        method: str, 
        url: str, 
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        HTTP запрос с retry логикой
        
        Args:
            method: HTTP метод
            url: URL для запроса
            **kwargs: Дополнительные аргументы для запроса
            
        Returns:
            aiohttp.ClientResponse: Ответ сервера
        """
        async def _make_request():
            async with self.session.request(method, url, **kwargs) as response:
                # Проверяем статус код
                if is_retryable_http_status(response.status):
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"HTTP {response.status}: {response.reason}"
                    )
                
                # Читаем содержимое для предотвращения закрытия соединения
                await response.read()
                return response
        
        return await retry_async(_make_request, config=self.config)
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """GET запрос с retry"""
        return await self.request('GET', url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """POST запрос с retry"""
        return await self.request('POST', url, **kwargs)


# Утилитарные функции для быстрого использования

async def retry_get(
    session: aiohttp.ClientSession,
    url: str,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> aiohttp.ClientResponse:
    """
    GET запрос с retry логикой
    
    Args:
        session: HTTP сессия
        url: URL для запроса
        config: Конфигурация retry
        **kwargs: Дополнительные аргументы
        
    Returns:
        aiohttp.ClientResponse: Ответ сервера
    """
    retry_session = RetrySession(session, config)
    return await retry_session.get(url, **kwargs)


async def retry_post(
    session: aiohttp.ClientSession,
    url: str,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> aiohttp.ClientResponse:
    """
    POST запрос с retry логикой
    
    Args:
        session: HTTP сессия
        url: URL для запроса
        config: Конфигурация retry
        **kwargs: Дополнительные аргументы
        
    Returns:
        aiohttp.ClientResponse: Ответ сервера
    """
    retry_session = RetrySession(session, config)
    return await retry_session.post(url, **kwargs) 
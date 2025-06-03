"""
Rate limiting система для парсера Kwork.ru
Предотвращает блокировки через контроль частоты запросов
"""

import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from collections import deque

from loguru import logger


@dataclass
class RateLimitConfig:
    """Конфигурация rate limiter"""
    requests_per_second: float = 1.0
    requests_per_minute: float = 30.0
    requests_per_hour: float = 1000.0
    burst_size: int = 5
    adaptive: bool = True
    backoff_factor: float = 2.0
    recovery_time: float = 300.0  # 5 минут для восстановления
    min_delay: float = 0.5
    max_delay: float = 60.0


class RateLimiter:
    """
    Асинхронный rate limiter с поддержкой адаптивного ограничения
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        
        # Временные окна для подсчета запросов
        self.second_window = deque()
        self.minute_window = deque() 
        self.hour_window = deque()
        
        # Блокировка для синхронизации
        self._lock = asyncio.Lock()
        
        # Адаптивные настройки
        self.current_delay = self.config.min_delay
        self.consecutive_errors = 0
        self.last_error_time = 0
        self.is_blocked = False
        self.block_until = 0
        
        logger.info(f"Rate limiter инициализирован: {self.config}")
    
    async def acquire(self) -> None:
        """
        Получение разрешения на выполнение запроса
        Блокирует выполнение если превышены лимиты
        """
        async with self._lock:
            await self._wait_if_blocked()
            await self._enforce_rate_limits()
            await self._add_request()
            await self._apply_delay()
    
    async def _wait_if_blocked(self) -> None:
        """Ожидание если установлена блокировка"""
        if self.is_blocked and time.time() < self.block_until:
            wait_time = self.block_until - time.time()
            logger.warning(f"Rate limiter заблокирован. Ожидание {wait_time:.1f} секунд")
            await asyncio.sleep(wait_time)
            self.is_blocked = False
    
    async def _enforce_rate_limits(self) -> None:
        """Проверка и применение лимитов скорости"""
        now = time.time()
        
        # Очищаем старые записи
        self._cleanup_windows(now)
        
        # Проверяем лимиты
        delays = []
        
        # Лимит в секунду
        if len(self.second_window) >= self.config.requests_per_second:
            oldest_in_second = self.second_window[0]
            delay_needed = 1.0 - (now - oldest_in_second)
            if delay_needed > 0:
                delays.append(delay_needed)
        
        # Лимит в минуту
        if len(self.minute_window) >= self.config.requests_per_minute:
            oldest_in_minute = self.minute_window[0]
            delay_needed = 60.0 - (now - oldest_in_minute)
            if delay_needed > 0:
                delays.append(delay_needed)
        
        # Лимит в час
        if len(self.hour_window) >= self.config.requests_per_hour:
            oldest_in_hour = self.hour_window[0]
            delay_needed = 3600.0 - (now - oldest_in_hour)
            if delay_needed > 0:
                delays.append(delay_needed)
        
        # Применяем максимальную задержку
        if delays:
            max_delay = max(delays)
            logger.info(f"Rate limit достигнут. Ожидание {max_delay:.1f} секунд")
            await asyncio.sleep(max_delay)
    
    def _cleanup_windows(self, now: float) -> None:
        """Очистка старых записей из временных окон"""
        # Очищаем записи старше 1 секунды
        while self.second_window and now - self.second_window[0] > 1.0:
            self.second_window.popleft()
        
        # Очищаем записи старше 1 минуты
        while self.minute_window and now - self.minute_window[0] > 60.0:
            self.minute_window.popleft()
        
        # Очищаем записи старше 1 часа
        while self.hour_window and now - self.hour_window[0] > 3600.0:
            self.hour_window.popleft()
    
    async def _add_request(self) -> None:
        """Добавление записи о выполненном запросе"""
        now = time.time()
        self.second_window.append(now)
        self.minute_window.append(now)
        self.hour_window.append(now)
    
    async def _apply_delay(self) -> None:
        """Применение базовой задержки между запросами"""
        if self.current_delay > 0:
            await asyncio.sleep(self.current_delay)
    
    async def report_error(self, status_code: Optional[int] = None) -> None:
        """
        Сообщение об ошибке для адаптивного ограничения
        
        Args:
            status_code: HTTP статус код ошибки
        """
        if not self.config.adaptive:
            return
        
        async with self._lock:
            self.consecutive_errors += 1
            self.last_error_time = time.time()
            
            # Проверяем критические статусы
            if status_code in [429, 503, 521, 522, 523, 524]:
                logger.warning(f"Получен статус {status_code}. Увеличиваем задержки")
                await self._increase_delay()
                
                if status_code == 429:  # Too Many Requests
                    await self._apply_temporary_block()
    
    async def report_success(self) -> None:
        """Сообщение об успешном запросе"""
        if not self.config.adaptive:
            return
        
        async with self._lock:
            if self.consecutive_errors > 0:
                self.consecutive_errors = max(0, self.consecutive_errors - 1)
                
                # Восстанавливаем скорость при успешных запросах
                if self.consecutive_errors == 0:
                    await self._decrease_delay()
    
    async def _increase_delay(self) -> None:
        """Увеличение задержки при ошибках"""
        old_delay = self.current_delay
        self.current_delay = min(
            self.current_delay * self.config.backoff_factor,
            self.config.max_delay
        )
        
        logger.info(f"Увеличена задержка с {old_delay:.2f} до {self.current_delay:.2f} секунд")
    
    async def _decrease_delay(self) -> None:
        """Уменьшение задержки при успешных запросах"""
        if self.current_delay > self.config.min_delay:
            old_delay = self.current_delay
            self.current_delay = max(
                self.current_delay / self.config.backoff_factor,
                self.config.min_delay
            )
            
            logger.info(f"Уменьшена задержка с {old_delay:.2f} до {self.current_delay:.2f} секунд")
    
    async def _apply_temporary_block(self) -> None:
        """Применение временной блокировки при критических ошибках"""
        block_duration = min(
            self.consecutive_errors * 30,  # 30 секунд за каждую ошибку
            self.config.recovery_time
        )
        
        self.is_blocked = True
        self.block_until = time.time() + block_duration
        
        logger.warning(f"Применена временная блокировка на {block_duration} секунд")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики rate limiter
        
        Returns:
            Dict: Статистика использования
        """
        now = time.time()
        self._cleanup_windows(now)
        
        return {
            "requests_in_last_second": len(self.second_window),
            "requests_in_last_minute": len(self.minute_window),
            "requests_in_last_hour": len(self.hour_window),
            "current_delay": self.current_delay,
            "consecutive_errors": self.consecutive_errors,
            "is_blocked": self.is_blocked,
            "block_time_remaining": max(0, self.block_until - now) if self.is_blocked else 0,
            "limits": {
                "per_second": self.config.requests_per_second,
                "per_minute": self.config.requests_per_minute,
                "per_hour": self.config.requests_per_hour
            }
        }
    
    async def reset(self) -> None:
        """Сброс состояния rate limiter"""
        async with self._lock:
            self.second_window.clear()
            self.minute_window.clear()
            self.hour_window.clear()
            self.current_delay = self.config.min_delay
            self.consecutive_errors = 0
            self.is_blocked = False
            self.block_until = 0
            
        logger.info("Rate limiter сброшен")


class GlobalRateLimiter:
    """
    Глобальный rate limiter с поддержкой доменов
    """
    
    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}
        self._default_config = RateLimitConfig()
    
    def get_limiter(self, domain: str, config: Optional[RateLimitConfig] = None) -> RateLimiter:
        """
        Получение rate limiter для домена
        
        Args:
            domain: Доменное имя
            config: Конфигурация (если не указана, используется по умолчанию)
            
        Returns:
            RateLimiter: Rate limiter для домена
        """
        if domain not in self._limiters:
            limiter_config = config or self._default_config
            self._limiters[domain] = RateLimiter(limiter_config)
            logger.info(f"Создан rate limiter для домена: {domain}")
        
        return self._limiters[domain]
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики всех rate limiter"""
        stats = {}
        for domain, limiter in self._limiters.items():
            stats[domain] = limiter.get_stats()
        return stats
    
    async def reset_all(self) -> None:
        """Сброс всех rate limiter"""
        for limiter in self._limiters.values():
            await limiter.reset()
        logger.info("Все rate limiter сброшены")


# Глобальный экземпляр
global_rate_limiter = GlobalRateLimiter()


def get_rate_limiter(domain: str = "default", config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """
    Получение rate limiter для домена
    
    Args:
        domain: Доменное имя
        config: Конфигурация rate limiter
        
    Returns:
        RateLimiter: Rate limiter для домена
    """
    return global_rate_limiter.get_limiter(domain, config)


# Предустановленные конфигурации
CONSERVATIVE_CONFIG = RateLimitConfig(
    requests_per_second=0.5,
    requests_per_minute=20,
    requests_per_hour=500,
    min_delay=2.0,
    max_delay=120.0
)

STANDARD_CONFIG = RateLimitConfig(
    requests_per_second=1.0,
    requests_per_minute=30,
    requests_per_hour=1000,
    min_delay=1.0,
    max_delay=60.0
)

AGGRESSIVE_CONFIG = RateLimitConfig(
    requests_per_second=2.0,
    requests_per_minute=60,
    requests_per_hour=2000,
    min_delay=0.5,
    max_delay=30.0
)


class RateLimitedSession:
    """
    HTTP сессия с автоматическим rate limiting
    """
    
    def __init__(self, domain: str, config: Optional[RateLimitConfig] = None):
        self.domain = domain
        self.rate_limiter = get_rate_limiter(domain, config)
    
    async def request(self, method: str, url: str, **kwargs):
        """
        HTTP запрос с rate limiting
        
        Args:
            method: HTTP метод
            url: URL для запроса
            **kwargs: Дополнительные аргументы
        """
        await self.rate_limiter.acquire()
        
        try:
            # Здесь должен быть настоящий HTTP запрос
            # Пример для интеграции с aiohttp:
            # async with aiohttp.ClientSession() as session:
            #     async with session.request(method, url, **kwargs) as response:
            #         if response.status >= 400:
            #             await self.rate_limiter.report_error(response.status)
            #         else:
            #             await self.rate_limiter.report_success()
            #         return response
            
            logger.debug(f"Rate limited {method} запрос к {url}")
            await self.rate_limiter.report_success()
            
        except Exception as e:
            await self.rate_limiter.report_error()
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики rate limiter"""
        return self.rate_limiter.get_stats() 
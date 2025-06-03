"""
Вспомогательные утилиты парсера Kwork.ru

Предоставляет:
- Retry логику с exponential backoff
- Rate limiting для предотвращения блокировок
- Ротацию User-Agent заголовков
- Настроенное логирование с ротацией файлов
"""

# Retry логика
from .retry import (
    RetryConfig,
    RetryableError,
    NonRetryableError,
    retry_async,
    retry_decorator,
    RetrySession,
    retry_get,
    retry_post,
    FAST_RETRY,
    STANDARD_RETRY,
    AGGRESSIVE_RETRY
)

# Rate limiting
from .rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    GlobalRateLimiter,
    RateLimitedSession,
    get_rate_limiter,
    global_rate_limiter,
    CONSERVATIVE_CONFIG,
    STANDARD_CONFIG as RATE_STANDARD_CONFIG,
    AGGRESSIVE_CONFIG as RATE_AGGRESSIVE_CONFIG
)

# User Agent ротация
from .user_agents import (
    UserAgentConfig,
    UserAgentRotator,
    BrowserProfile,
    get_user_agent_rotator,
    get_random_user_agent,
    get_browser_headers,
    generate_dynamic_user_agent,
    STEALTH_CONFIG,
    STANDARD_CONFIG as UA_STANDARD_CONFIG,
    DIVERSE_CONFIG
)

# Логирование
from .logger import (
    LoggingConfig,
    KworkLogger,
    setup_logging,
    get_logger,
    log_function_call,
    log_async_function_call,
    DEBUG_CONFIG,
    PRODUCTION_CONFIG,
    SILENT_CONFIG,
    trace,
    debug,
    info,
    success,
    warning,
    error,
    critical
)

__all__ = [
    # Retry
    'RetryConfig',
    'RetryableError',
    'NonRetryableError',
    'retry_async',
    'retry_decorator',
    'RetrySession',
    'retry_get',
    'retry_post',
    'FAST_RETRY',
    'STANDARD_RETRY',
    'AGGRESSIVE_RETRY',
    
    # Rate Limiting
    'RateLimitConfig',
    'RateLimiter',
    'GlobalRateLimiter',
    'RateLimitedSession',
    'get_rate_limiter',
    'global_rate_limiter',
    'CONSERVATIVE_CONFIG',
    'RATE_STANDARD_CONFIG',
    'RATE_AGGRESSIVE_CONFIG',
    
    # User Agents
    'UserAgentConfig',
    'UserAgentRotator',
    'BrowserProfile',
    'get_user_agent_rotator',
    'get_random_user_agent',
    'get_browser_headers',
    'generate_dynamic_user_agent',
    'STEALTH_CONFIG',
    'UA_STANDARD_CONFIG',
    'DIVERSE_CONFIG',
    
    # Logging
    'LoggingConfig',
    'KworkLogger',
    'setup_logging',
    'get_logger',
    'log_function_call',
    'log_async_function_call',
    'DEBUG_CONFIG',
    'PRODUCTION_CONFIG',
    'SILENT_CONFIG',
    'trace',
    'debug',
    'info',
    'success',
    'warning',
    'error',
    'critical'
] 
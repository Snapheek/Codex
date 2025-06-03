"""
Модуль для загрузки и валидации конфигурации парсера Kwork.ru
Использует Pydantic для валидации и PyYAML для загрузки
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class FilterSettings(BaseModel):
    """Настройки фильтров проектов"""
    category: Optional[int] = 41
    min_price: int = Field(default=0, ge=0)
    max_price: Optional[int] = Field(default=None, ge=0)
    exclude_keywords: List[str] = Field(default_factory=list)
    include_keywords: List[str] = Field(default_factory=list)


class ParserSettings(BaseModel):
    """Настройки парсера"""
    base_url: str = "https://kwork.ru/projects"
    max_pages: int = Field(default=50, ge=1, le=500)
    concurrent_requests: int = Field(default=5, ge=1, le=20)
    request_delay: int = Field(default=2, ge=0)
    page_delay: int = Field(default=5, ge=0)
    request_timeout: int = Field(default=30, ge=5)
    session_timeout: int = Field(default=300, ge=60)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: int = Field(default=5, ge=1)
    exponential_backoff: bool = True
    filters: FilterSettings = Field(default_factory=FilterSettings)

    @validator('base_url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL должен начинаться с http:// или https://')
        return v


class SQLiteSettings(BaseModel):
    """Настройки SQLite"""
    path: str = "data/kwork_projects.db"


class PostgreSQLSettings(BaseModel):
    """Настройки PostgreSQL"""
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    database: str
    username: str
    password: str


class DatabaseSettings(BaseModel):
    """Настройки базы данных"""
    type: str = Field(default="sqlite", pattern="^(sqlite|postgresql)$")
    sqlite: SQLiteSettings = Field(default_factory=SQLiteSettings)
    postgresql: Optional[PostgreSQLSettings] = None
    echo: bool = False
    pool_size: int = Field(default=5, ge=1, le=50)
    max_overflow: int = Field(default=10, ge=0, le=100)


class TelegramSettings(BaseModel):
    """Настройки Telegram бота"""
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    send_notifications: bool = True
    group_notifications: bool = True
    max_group_size: int = Field(default=5, ge=1, le=20)
    message_format: str = Field(default="rich", pattern="^(simple|rich)$")
    use_emojis: bool = True
    parse_mode: str = Field(default="Markdown", pattern="^(Markdown|HTML)$")
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: int = Field(default=2, ge=1)


class WorkingHoursSettings(BaseModel):
    """Настройки рабочих часов"""
    enabled: bool = False
    start: str = Field(default="09:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    end: str = Field(default="21:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    timezone: str = "Europe/Moscow"


class HealthCheckSettings(BaseModel):
    """Настройки health check"""
    enabled: bool = True
    port: int = Field(default=8080, ge=1000, le=65535)
    endpoint: str = "/health"


class AutoRestartSettings(BaseModel):
    """Настройки автоматического перезапуска"""
    enabled: bool = True
    max_failures: int = Field(default=5, ge=1)
    restart_delay: int = Field(default=60, ge=10)


class MonitoringSettings(BaseModel):
    """Настройки мониторинга"""
    check_interval: int = Field(default=300, ge=30)
    working_hours: WorkingHoursSettings = Field(default_factory=WorkingHoursSettings)
    health_check: HealthCheckSettings = Field(default_factory=HealthCheckSettings)
    auto_restart: AutoRestartSettings = Field(default_factory=AutoRestartSettings)


class CSVExportSettings(BaseModel):
    """Настройки экспорта CSV"""
    delimiter: str = ","
    encoding: str = "utf-8-sig"


class ExcelExportSettings(BaseModel):
    """Настройки экспорта Excel"""
    sheet_name: str = "Kwork Projects"
    include_formulas: bool = False


class JSONExportSettings(BaseModel):
    """Настройки экспорта JSON"""
    indent: int = Field(default=2, ge=0)
    ensure_ascii: bool = False


class ExportSettings(BaseModel):
    """Настройки экспорта"""
    output_dir: str = "exports"
    default_format: str = Field(default="csv", pattern="^(csv|json|excel)$")
    csv: CSVExportSettings = Field(default_factory=CSVExportSettings)
    excel: ExcelExportSettings = Field(default_factory=ExcelExportSettings)
    json_config: JSONExportSettings = Field(default_factory=JSONExportSettings, alias="json")


class UserAgentSettings(BaseModel):
    """Настройки User-Agent"""
    enabled: bool = True
    rotate_interval: int = Field(default=10, ge=1)


class ProxySettings(BaseModel):
    """Настройки прокси"""
    enabled: bool = False
    proxy_list: List[str] = Field(default_factory=list)
    rotate_interval: int = Field(default=100, ge=1)


class BrowserSimulationSettings(BaseModel):
    """Настройки имитации браузера"""
    enabled: bool = True
    random_scroll: bool = False
    random_clicks: bool = False


class BypassSettings(BaseModel):
    """Настройки обхода защиты"""
    use_sessions: bool = True
    accept_cookies: bool = True
    follow_redirects: bool = True


class AntibotSettings(BaseModel):
    """Настройки антибот защиты"""
    user_agents: UserAgentSettings = Field(default_factory=UserAgentSettings)
    proxies: ProxySettings = Field(default_factory=ProxySettings)
    browser_simulation: BrowserSimulationSettings = Field(default_factory=BrowserSimulationSettings)
    bypass: BypassSettings = Field(default_factory=BypassSettings)


class LoggingFilesSettings(BaseModel):
    """Настройки файлов логов"""
    main: str = "logs/kwork_parser.log"
    parser: str = "logs/parser.log"
    telegram: str = "logs/telegram.log"
    database: str = "logs/database.log"


class LoggingSettings(BaseModel):
    """Настройки логирования"""
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    files: LoggingFilesSettings = Field(default_factory=LoggingFilesSettings)
    rotation: str = "1 day"
    retention: str = "7 days"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"


class Settings(BaseModel):
    """Основные настройки приложения"""
    parser: ParserSettings = Field(default_factory=ParserSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)
    antibot: AntibotSettings = Field(default_factory=AntibotSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def model_post_init(self, __context):
        """Пост-инициализация модели"""
        # Создаем необходимые директории
        self._create_directories()

    def _create_directories(self):
        """Создание необходимых директорий"""
        directories = [
            "logs",
            "data", 
            self.export.output_dir,
            Path(self.database.sqlite.path).parent if self.database.type == "sqlite" else None
        ]
        
        for directory in directories:
            if directory:
                Path(directory).mkdir(parents=True, exist_ok=True)


def substitute_env_vars(data: Any) -> Any:
    """Рекурсивная замена переменных окружения в конфигурации"""
    if isinstance(data, dict):
        return {key: substitute_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Замена переменных вида ${VAR_NAME}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_env_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))
        
        return re.sub(pattern, replace_env_var, data)
    else:
        return data


def load_config(config_path: str = "config/config.yaml") -> Settings:
    """
    Загрузка конфигурации из YAML файла с валидацией
    
    Args:
        config_path: Путь к конфигурационному файлу
        
    Returns:
        Settings: Валидированные настройки
        
    Raises:
        FileNotFoundError: Если файл конфигурации не найден
        yaml.YAMLError: Если ошибка парсинга YAML
        ValidationError: Если ошибка валидации настроек
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Ошибка парсинга YAML: {e}")
    
    # Замена переменных окружения
    config_data = substitute_env_vars(config_data)
    
    # Создание и валидация настроек
    return Settings(**config_data)


# Глобальный экземпляр настроек (инициализируется при первом импорте)
settings: Optional[Settings] = None


def get_settings(config_path: str = "config/config.yaml") -> Settings:
    """
    Получение экземпляра настроек (Singleton pattern)
    
    Args:
        config_path: Путь к конфигурационному файлу
        
    Returns:
        Settings: Экземпляр настроек
    """
    global settings
    
    if settings is None:
        settings = load_config(config_path)
    
    return settings


if __name__ == "__main__":
    # Тестирование загрузки конфигурации
    try:
        config = load_config()
        print("✅ Конфигурация успешно загружена и валидирована")
        print(f"📊 Макс. страниц: {config.parser.max_pages}")
        print(f"🗄️ Тип БД: {config.database.type}")
        print(f"📱 Telegram уведомления: {'включены' if config.telegram.send_notifications else 'отключены'}")
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}") 
"""
Система ротации User-Agent заголовков для парсера Kwork.ru
Обеспечивает обход детекции ботов через имитацию реальных браузеров
"""

import random
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from loguru import logger


@dataclass
class UserAgentConfig:
    """Конфигурация ротации User-Agent"""
    rotation_interval: int = 10  # Количество запросов между ротацией
    random_rotation: bool = True  # Случайная ротация
    prefer_chrome: bool = True    # Предпочитать Chrome
    prefer_desktop: bool = True   # Предпочитать десктопные браузеры
    include_mobile: bool = False  # Включать мобильные браузеры


# Современные User-Agent строки
DESKTOP_CHROME_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

DESKTOP_FIREFOX_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

DESKTOP_SAFARI_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]

DESKTOP_EDGE_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

MOBILE_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]

# Популярные операционные системы для Chrome
WINDOWS_VERSIONS = [
    "Windows NT 10.0; Win64; x64",
    "Windows NT 11.0; Win64; x64", 
    "Windows NT 10.0; WOW64",
]

MACOS_VERSIONS = [
    "Macintosh; Intel Mac OS X 10_15_7",
    "Macintosh; Intel Mac OS X 10_15_6",
    "Macintosh; Apple M1 Mac OS X 10_15_7",
    "Macintosh; Apple M2 Mac OS X 10_15_7",
]

LINUX_VERSIONS = [
    "X11; Linux x86_64",
    "X11; Ubuntu; Linux x86_64",
    "X11; Linux i686",
]


class UserAgentRotator:
    """
    Класс для ротации User-Agent заголовков
    """
    
    def __init__(self, config: Optional[UserAgentConfig] = None):
        self.config = config or UserAgentConfig()
        self.current_agent = None
        self.request_count = 0
        self.agents_pool = self._build_agents_pool()
        self.used_agents = []
        
        logger.info(f"User-Agent ротатор инициализирован с {len(self.agents_pool)} агентами")
    
    def _build_agents_pool(self) -> List[str]:
        """Построение пула User-Agent строк"""
        pool = []
        
        # Добавляем Chrome (приоритет если включен)
        if self.config.prefer_chrome or not self.config.prefer_desktop:
            pool.extend(DESKTOP_CHROME_AGENTS * 2)  # Двойной вес для Chrome
        
        # Добавляем другие десктопные браузеры
        if self.config.prefer_desktop:
            pool.extend(DESKTOP_FIREFOX_AGENTS)
            pool.extend(DESKTOP_SAFARI_AGENTS)
            pool.extend(DESKTOP_EDGE_AGENTS)
        
        # Добавляем мобильные если разрешено
        if self.config.include_mobile:
            pool.extend(MOBILE_AGENTS)
        
        # Если пул пуст, используем Chrome по умолчанию
        if not pool:
            pool = DESKTOP_CHROME_AGENTS
        
        return pool
    
    def get_user_agent(self) -> str:
        """
        Получение текущего User-Agent
        
        Returns:
            str: User-Agent строка
        """
        # Проверяем необходимость ротации
        if (self.current_agent is None or 
            self.request_count >= self.config.rotation_interval):
            self._rotate_agent()
        
        self.request_count += 1
        return self.current_agent
    
    def _rotate_agent(self) -> None:
        """Ротация User-Agent"""
        if self.config.random_rotation:
            # Случайный выбор
            available_agents = [agent for agent in self.agents_pool 
                              if agent not in self.used_agents[-5:]]  # Избегаем последние 5
            
            if not available_agents:
                available_agents = self.agents_pool
            
            self.current_agent = random.choice(available_agents)
        else:
            # Последовательная ротация
            current_index = 0
            if self.current_agent in self.agents_pool:
                current_index = self.agents_pool.index(self.current_agent)
            
            next_index = (current_index + 1) % len(self.agents_pool)
            self.current_agent = self.agents_pool[next_index]
        
        # Сбрасываем счетчик запросов
        self.request_count = 0
        
        # Запоминаем использованный агент
        self.used_agents.append(self.current_agent)
        if len(self.used_agents) > 20:
            self.used_agents = self.used_agents[-20:]  # Храним только последние 20
        
        logger.debug(f"User-Agent изменен на: {self.current_agent[:50]}...")
    
    def force_rotate(self) -> str:
        """
        Принудительная ротация User-Agent
        
        Returns:
            str: Новый User-Agent
        """
        self.request_count = self.config.rotation_interval
        return self.get_user_agent()
    
    def get_random_agent(self) -> str:
        """
        Получение случайного User-Agent без изменения текущего
        
        Returns:
            str: Случайный User-Agent
        """
        return random.choice(self.agents_pool)
    
    def get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Получение HTTP заголовков с User-Agent
        
        Args:
            additional_headers: Дополнительные заголовки
            
        Returns:
            Dict: HTTP заголовки
        """
        headers = {
            'User-Agent': self.get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        # Добавляем специфичные заголовки для Chrome
        if 'Chrome' in headers['User-Agent']:
            headers.update({
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
            })
        
        # Добавляем дополнительные заголовки
        if additional_headers:
            headers.update(additional_headers)
        
        return headers
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики ротатора
        
        Returns:
            Dict: Статистика использования
        """
        return {
            'current_agent': self.current_agent[:50] + '...' if self.current_agent else None,
            'request_count': self.request_count,
            'rotation_interval': self.config.rotation_interval,
            'total_agents': len(self.agents_pool),
            'used_agents_count': len(self.used_agents),
            'config': {
                'random_rotation': self.config.random_rotation,
                'prefer_chrome': self.config.prefer_chrome,
                'prefer_desktop': self.config.prefer_desktop,
                'include_mobile': self.config.include_mobile,
            }
        }


class BrowserProfile:
    """
    Профиль браузера с согласованными заголовками
    """
    
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._browser_type = self._detect_browser_type()
        self._os_type = self._detect_os_type()
    
    def _detect_browser_type(self) -> str:
        """Определение типа браузера"""
        ua = self.user_agent.lower()
        if 'chrome' in ua and 'edg' not in ua:
            return 'chrome'
        elif 'firefox' in ua:
            return 'firefox'
        elif 'safari' in ua and 'chrome' not in ua:
            return 'safari'
        elif 'edg' in ua:
            return 'edge'
        else:
            return 'unknown'
    
    def _detect_os_type(self) -> str:
        """Определение операционной системы"""
        ua = self.user_agent.lower()
        if 'windows' in ua:
            return 'windows'
        elif 'mac os x' in ua or 'macos' in ua:
            return 'macos'
        elif 'linux' in ua:
            return 'linux'
        elif 'iphone' in ua or 'ipad' in ua:
            return 'ios'
        elif 'android' in ua:
            return 'android'
        else:
            return 'unknown'
    
    def get_headers(self) -> Dict[str, str]:
        """Получение согласованных заголовков для браузера"""
        base_headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Специфичные заголовки для Chrome/Edge
        if self._browser_type in ['chrome', 'edge']:
            base_headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
                'sec-ch-ua-mobile': '?0',
            })
            
            # Определяем платформу для sec-ch-ua-platform
            if self._os_type == 'windows':
                base_headers['sec-ch-ua-platform'] = '"Windows"'
            elif self._os_type == 'macos':
                base_headers['sec-ch-ua-platform'] = '"macOS"'
            elif self._os_type == 'linux':
                base_headers['sec-ch-ua-platform'] = '"Linux"'
        
        # Специфичные заголовки для Firefox
        elif self._browser_type == 'firefox':
            base_headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            })
        
        return base_headers


# Глобальный ротатор
_global_rotator: Optional[UserAgentRotator] = None


def get_user_agent_rotator(config: Optional[UserAgentConfig] = None) -> UserAgentRotator:
    """
    Получение глобального ротатора User-Agent
    
    Args:
        config: Конфигурация ротатора
        
    Returns:
        UserAgentRotator: Глобальный ротатор
    """
    global _global_rotator
    
    if _global_rotator is None:
        _global_rotator = UserAgentRotator(config)
    
    return _global_rotator


def get_random_user_agent() -> str:
    """
    Получение случайного User-Agent
    
    Returns:
        str: Случайный User-Agent
    """
    rotator = get_user_agent_rotator()
    return rotator.get_random_agent()


def get_browser_headers(user_agent: Optional[str] = None) -> Dict[str, str]:
    """
    Получение заголовков браузера
    
    Args:
        user_agent: User-Agent (если не указан, используется текущий)
        
    Returns:
        Dict: HTTP заголовки
    """
    if user_agent is None:
        rotator = get_user_agent_rotator()
        user_agent = rotator.get_user_agent()
    
    profile = BrowserProfile(user_agent)
    return profile.get_headers()


def generate_dynamic_user_agent(
    browser: str = 'chrome',
    os_type: str = 'windows',
    version: Optional[str] = None
) -> str:
    """
    Генерация динамического User-Agent
    
    Args:
        browser: Тип браузера (chrome, firefox, safari, edge)
        os_type: Операционная система (windows, macos, linux)
        version: Версия браузера (если не указана, используется случайная)
        
    Returns:
        str: Сгенерированный User-Agent
    """
    chrome_versions = ['120.0.0.0', '119.0.0.0', '118.0.0.0', '121.0.0.0']
    firefox_versions = ['121.0', '120.0', '119.0']
    
    if browser == 'chrome':
        version = version or random.choice(chrome_versions)
        if os_type == 'windows':
            os_string = random.choice(WINDOWS_VERSIONS)
        elif os_type == 'macos':
            os_string = random.choice(MACOS_VERSIONS)
        else:
            os_string = random.choice(LINUX_VERSIONS)
        
        return f"Mozilla/5.0 ({os_string}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"
    
    elif browser == 'firefox':
        version = version or random.choice(firefox_versions)
        if os_type == 'windows':
            return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{version}) Gecko/20100101 Firefox/{version}"
        elif os_type == 'macos':
            return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{version}) Gecko/20100101 Firefox/{version}"
        else:
            return f"Mozilla/5.0 (X11; Linux x86_64; rv:{version}) Gecko/20100101 Firefox/{version}"
    
    # По умолчанию возвращаем Chrome
    return random.choice(DESKTOP_CHROME_AGENTS)


# Предустановленные конфигурации
STEALTH_CONFIG = UserAgentConfig(
    rotation_interval=5,
    random_rotation=True,
    prefer_chrome=True,
    prefer_desktop=True,
    include_mobile=False
)

STANDARD_CONFIG = UserAgentConfig(
    rotation_interval=10,
    random_rotation=True,
    prefer_chrome=True,
    prefer_desktop=True,
    include_mobile=False
)

DIVERSE_CONFIG = UserAgentConfig(
    rotation_interval=15,
    random_rotation=True,
    prefer_chrome=False,
    prefer_desktop=True,
    include_mobile=True
) 
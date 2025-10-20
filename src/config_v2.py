"""
Обновленная конфигурация для ML Data Pipeline

Поддерживает:
- Модульную настройку компонентов
- Локальные и облачные LLM модели
- Гибкую настройку pipeline
- Режимы работы (development/production)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Загружаем .env
try:
    from dotenv import load_dotenv, find_dotenv
    _dotenv_path = find_dotenv(usecwd=True)
    load_dotenv(_dotenv_path or ".env", override=False)
except Exception:
    pass


class TelegramConfig(BaseSettings):
    """Конфигурация Telegram бота"""
    
    bot_token: str = Field(..., description="Токен Telegram бота")
    public_url: Optional[str] = Field(None, description="Public URL для webhook")
    port: int = Field(8080, description="Порт для webhook")
    
    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=".env",
        extra="ignore"
    )


class LLMConfig(BaseSettings):
    """Конфигурация LLM"""
    
    # Основная модель
    api_key: str = Field("", description="API ключ")
    api_base: Optional[str] = Field(None, description="Базовый URL (для локальных моделей)")
    model: str = Field("gpt-4o-mini", description="Название модели")
    
    # Ролевые модели (опционально)
    labeler_api_key: Optional[str] = Field(None, description="API ключ для Labeler")
    labeler_api_base: Optional[str] = Field(None, description="API base для Labeler")
    labeler_model: Optional[str] = Field(None, description="Модель для Labeler")
    
    augmenter_api_key: Optional[str] = Field(None, description="API ключ для Augmenter")
    augmenter_api_base: Optional[str] = Field(None, description="API base для Augmenter")
    augmenter_model: Optional[str] = Field(None, description="Модель для Augmenter")
    
    # Параметры
    temperature: float = Field(1.0, description="Temperature для генерации")
    max_tokens: Optional[int] = Field(None, description="Максимум токенов")
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore"
    )


class ETLConfig(BaseSettings):
    """Конфигурация ETL процесса"""
    
    max_rows: Optional[int] = Field(None, description="Максимум строк для обработки")
    deduplicate: bool = Field(True, description="Удалять дубликаты")
    min_text_length: int = Field(3, description="Минимальная длина текста")
    max_text_length: int = Field(1000, description="Максимальная длина текста")
    
    model_config = SettingsConfigDict(
        env_prefix="ETL_",
        env_file=".env",
        extra="ignore"
    )


class LabelerConfig(BaseSettings):
    """Конфигурация Labeler агента"""
    
    batch_size: int = Field(20, description="Размер батча")
    rate_limit: float = Field(0.4, description="Задержка между запросами (сек)")
    low_conf_threshold: float = Field(0.5, description="Порог низкой уверенности")
    
    use_cache: bool = Field(True, description="Использовать кэш")
    use_dynamic_fewshot: bool = Field(True, description="Использовать динамические примеры")
    
    model_config = SettingsConfigDict(
        env_prefix="LABELER_",
        env_file=".env",
        extra="ignore"
    )


class AugmenterConfig(BaseSettings):
    """Конфигурация Augmenter агента"""
    
    variants_per_sample: int = Field(3, description="Вариантов на образец")
    include_hard_negatives: bool = Field(False, description="Включать пограничные случаи")
    
    concurrency: int = Field(8, description="Конкурентность")
    rate_limit: float = Field(0.1, description="Задержка между запросами (сек)")
    max_samples_per_domain: int = Field(30, description="Максимум образцов на домен")
    
    use_cache: bool = Field(True, description="Использовать кэш")
    
    model_config = SettingsConfigDict(
        env_prefix="AUGMENTER_",
        env_file=".env",
        extra="ignore"
    )


class ReviewConfig(BaseSettings):
    """Конфигурация ReviewDataset (HITL)"""
    
    low_confidence_threshold: float = Field(0.5, description="Порог низкой уверенности")
    high_priority_threshold: float = Field(0.3, description="Порог высокого приоритета")
    max_queue_size: int = Field(10000, description="Максимальный размер очереди")
    auto_approve_threshold: float = Field(0.95, description="Порог автоодобрения")
    
    model_config = SettingsConfigDict(
        env_prefix="REVIEW_",
        env_file=".env",
        extra="ignore"
    )


class DataWriterConfig(BaseSettings):
    """Конфигурация DataWriter"""
    
    eval_fraction: float = Field(0.1, description="Доля eval датасета")
    min_eval_samples: int = Field(50, description="Минимум образцов в eval")
    min_samples_per_domain: int = Field(5, description="Минимум образцов на домен")
    
    balance_domains: bool = Field(True, description="Балансировать домены")
    max_samples_per_domain: Optional[int] = Field(None, description="Максимум образцов на домен")
    
    shard_size: Optional[int] = Field(None, description="Размер шарда")
    
    include_metadata: bool = Field(True, description="Включать метаданные")
    validate_quality: bool = Field(True, description="Валидировать качество")
    
    model_config = SettingsConfigDict(
        env_prefix="DATA_WRITER_",
        env_file=".env",
        extra="ignore"
    )


class DataStorageConfig(BaseSettings):
    """Конфигурация DataStorage"""
    
    enable_compression: bool = Field(False, description="Сжимать датасеты")
    max_versions: int = Field(100, description="Максимум версий")
    auto_archive_old: bool = Field(True, description="Автоархивирование старых версий")
    
    model_config = SettingsConfigDict(
        env_prefix="DATA_STORAGE_",
        env_file=".env",
        extra="ignore"
    )


class CacheConfig(BaseSettings):
    """Конфигурация кэша"""
    
    ttl_hours: int = Field(24, description="TTL кэша в часах")
    enabled: bool = Field(True, description="Включить кэш")
    
    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        env_file=".env",
        extra="ignore"
    )


class AppConfig(BaseSettings):
    """Общая конфигурация приложения"""
    
    # Режим работы
    mode: Literal["development", "production"] = Field("development", description="Режим работы")
    
    # Директории
    data_dir: Path = Field(Path("data"), description="Директория для данных")
    prompts_dir: Path = Field(Path("prompts"), description="Директория с промптами")
    
    # Логирование
    log_level: str = Field("INFO", description="Уровень логирования")
    log_to_file: bool = Field(False, description="Логировать в файл")
    log_file: Optional[Path] = Field(None, description="Путь к лог файлу")
    
    # Прогресс
    progress_chunk: int = Field(100, description="Чанк для прогресса")
    send_partials: bool = Field(True, description="Отправлять промежуточные результаты")
    
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore"
    )


class Settings:
    """
    Главный класс настроек приложения.
    
    Объединяет все конфигурации компонентов.
    """
    
    def __init__(self):
        self.app = AppConfig()
        self.telegram = TelegramConfig()
        self.llm = LLMConfig()
        self.etl = ETLConfig()
        self.labeler = LabelerConfig()
        self.augmenter = AugmenterConfig()
        self.review = ReviewConfig()
        self.data_writer = DataWriterConfig()
        self.data_storage = DataStorageConfig()
        self.cache = CacheConfig()
        
        # Создаем директории
        self._setup_directories()
    
    def _setup_directories(self):
        """Создает необходимые директории"""
        self.app.data_dir.mkdir(parents=True, exist_ok=True)
        (self.app.data_dir / "artifacts").mkdir(exist_ok=True)
        (self.app.data_dir / "hitl").mkdir(exist_ok=True)
        (self.app.data_dir / "llm_cache").mkdir(exist_ok=True)
        (self.app.data_dir / "storage" / "versions").mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load(cls) -> "Settings":
        """Загружает настройки из переменных окружения"""
        return cls()
    
    def get_labeler_llm_config(self) -> dict:
        """Возвращает конфиг LLM для Labeler"""
        return {
            "api_key": self.llm.labeler_api_key or self.llm.api_key,
            "api_base": self.llm.labeler_api_base or self.llm.api_base,
            "model": self.llm.labeler_model or self.llm.model,
        }
    
    def get_augmenter_llm_config(self) -> dict:
        """Возвращает конфиг LLM для Augmenter"""
        return {
            "api_key": self.llm.augmenter_api_key or self.llm.api_key,
            "api_base": self.llm.augmenter_api_base or self.llm.api_base,
            "model": self.llm.augmenter_model or self.llm.model,
        }
    
    def is_production(self) -> bool:
        """Проверяет, запущено ли приложение в production режиме"""
        return self.app.mode == "production"
    
    def is_development(self) -> bool:
        """Проверяет, запущено ли приложение в development режиме"""
        return self.app.mode == "development"


# Функция совместимости со старым API
def load_settings() -> Settings:
    """Загружает настройки"""
    return Settings.load()


"""
Labeler Agent - агент для автоматической разметки текстов доменами

Использует PydanticAI для структурированного взаимодействия с LLM.
Поддерживает:
- Batch обработку с rate limiting
- Кэширование результатов
- Динамические few-shot примеры
- Валидацию доменов
- Адаптивное обучение на основе feedback
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd
from pydantic import BaseModel, Field, validator
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from ..taxonomy import CANON_LABELS, validate_domain, is_stop_word
from ..cache import get_cache

logger = logging.getLogger(__name__)


class ClassificationResult(BaseModel):
    """Результат классификации текста"""
    
    text: str = Field(..., description="Исходный текст")
    domain_id: str = Field(..., description="Идентификатор домена")
    domain_true: str = Field(..., description="Истинный домен (изначально = domain_id)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность классификации")
    top_candidates: List[List[Any]] = Field(
        default_factory=list,
        description="Топ кандидатов: [[domain, confidence], ...]"
    )
    reasoning: Optional[str] = Field(None, description="Объяснение выбора домена")
    
    @validator("domain_id", "domain_true")
    def validate_domains(cls, v):
        return validate_domain(v)
    
    @validator("top_candidates")
    def validate_candidates(cls, v):
        # Валидируем каждый домен в кандидатах
        validated = []
        for item in v:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                validated_domain = validate_domain(str(item[0]))
                validated.append([validated_domain, float(item[1])])
        return validated


class LabelerConfig(BaseModel):
    """Конфигурация Labeler агента"""
    
    model: str = Field("gpt-4o-mini", description="Модель LLM")
    api_key: str = Field(..., description="API ключ")
    api_base: Optional[str] = Field(None, description="Базовый URL API (для локальных моделей)")
    
    batch_size: int = Field(20, description="Размер батча для обработки", ge=1)
    rate_limit: float = Field(0.4, description="Задержка между запросами (сек)", ge=0.0)
    max_retries: int = Field(3, description="Максимальное количество повторов при ошибке", ge=1)
    
    low_conf_threshold: float = Field(0.5, description="Порог низкой уверенности", ge=0.0, le=1.0)
    
    use_cache: bool = Field(True, description="Использовать кэш для результатов")
    use_dynamic_fewshot: bool = Field(True, description="Использовать динамические few-shot примеры")
    
    system_prompt_path: Path = Field(
        Path("prompts/labeler_system.txt"),
        description="Путь к системному промпту"
    )
    fewshot_prompt_path: Path = Field(
        Path("prompts/labeler_fewshot.txt"),
        description="Путь к few-shot примерам"
    )


class LabelerAgent:
    """
    LLM-агент для автоматической разметки текстов доменами.
    
    Использует PydanticAI для типобезопасного взаимодействия с LLM.
    """
    
    def __init__(self, config: LabelerConfig):
        self.config = config
        
        # Загружаем промпты
        self.system_prompt = self._load_prompt(config.system_prompt_path)
        self.fewshot_prompt = self._load_prompt(config.fewshot_prompt_path)
        
        # Инициализируем PydanticAI агента
        self._init_agent()
        
        # Статистика
        self.stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "llm_calls": 0,
            "errors": 0,
            "low_confidence_count": 0,
        }
    
    def _load_prompt(self, path: Path) -> str:
        """Загружает промпт из файла"""
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
            else:
                logger.warning(f"Prompt file not found: {path}")
                return ""
        except Exception as e:
            logger.error(f"Failed to load prompt from {path}: {e}")
            return ""
    
    def _init_agent(self):
        """Инициализирует PydanticAI агента"""
        
        # Создаем модель
        if self.config.api_base:
            # Локальная модель с custom base_url
            model = OpenAIModel(
                self.config.model,
                api_key=self.config.api_key,
                base_url=self.config.api_base
            )
        else:
            # OpenAI или совместимый API
            model = OpenAIModel(
                self.config.model,
                api_key=self.config.api_key
            )
        
        # Создаем агента с типизированным результатом
        self.agent = Agent(
            model=model,
            result_type=ClassificationResult,
            system_prompt=self._build_system_prompt(),
        )
    
    def _build_system_prompt(self) -> str:
        """Строит полный системный промпт с few-shot примерами"""
        
        prompt_parts = [self.system_prompt]
        
        # Добавляем канонические домены
        domains_list = "\n".join(f"- {domain}" for domain in CANON_LABELS)
        prompt_parts.append(f"\nДОСТУПНЫЕ ДОМЕНЫ:\n{domains_list}\n")
        
        # Добавляем few-shot примеры
        if self.fewshot_prompt:
            prompt_parts.append(f"\nПРИМЕРЫ КЛАССИФИКАЦИИ:\n{self.fewshot_prompt}\n")
        
        # Добавляем инструкции по формату ответа
        prompt_parts.append(
            "\nФОРМАТ ОТВЕТА:\n"
            "Верни JSON объект с полями:\n"
            "- domain_id: идентификатор домена из списка выше\n"
            "- confidence: уверенность от 0.0 до 1.0\n"
            "- top_candidates: топ-3 кандидата [[domain, confidence], ...]\n"
            "- reasoning: краткое объяснение выбора (опционально)\n"
        )
        
        return "\n".join(prompt_parts)
    
    async def classify_one(
        self,
        text: str,
        *,
        allowed_labels: Optional[List[str]] = None,
        user_context: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Классифицирует один текст.
        
        Args:
            text: текст для классификации
            allowed_labels: опциональный список разрешенных доменов
            user_context: опциональный контекст пользователя
            
        Returns:
            ClassificationResult с результатом классификации
        """
        
        # Проверяем стоп-слова
        if is_stop_word(text):
            return ClassificationResult(
                text=text,
                domain_id="oos",
                domain_true="oos",
                confidence=0.95,
                top_candidates=[["oos", 0.95]],
                reasoning="Stop word detected"
            )
        
        # Проверяем кэш
        if self.config.use_cache:
            cache = get_cache()
            if cache:
                cache_key = self._build_cache_key(text, allowed_labels, user_context)
                cached = cache.get_classification(text, cache_key, "")
                if cached:
                    self.stats["cache_hits"] += 1
                    self.stats["total_processed"] += 1
                    return ClassificationResult(**cached)
        
        # Строим промпт
        user_prompt = self._build_user_prompt(text, allowed_labels, user_context)
        
        # Вызываем агента
        try:
            result = await self.agent.run(user_prompt)
            
            # Извлекаем результат
            classification = result.data
            classification.text = text
            
            # Обновляем статистику
            self.stats["llm_calls"] += 1
            self.stats["total_processed"] += 1
            
            if classification.confidence < self.config.low_conf_threshold:
                self.stats["low_confidence_count"] += 1
            
            # Сохраняем в кэш
            if self.config.use_cache:
                cache = get_cache()
                if cache:
                    cache_key = self._build_cache_key(text, allowed_labels, user_context)
                    cache.set_classification(text, cache_key, "", classification.dict())
            
            return classification
            
        except Exception as e:
            logger.error(f"Classification failed for text: {text[:100]}... Error: {e}")
            self.stats["errors"] += 1
            
            # Возвращаем fallback результат
            return ClassificationResult(
                text=text,
                domain_id="oos",
                domain_true="oos",
                confidence=0.0,
                top_candidates=[["oos", 0.0]],
                reasoning=f"Error: {str(e)}"
            )
    
    def _build_cache_key(
        self,
        text: str,
        allowed_labels: Optional[List[str]],
        user_context: Optional[str]
    ) -> str:
        """Строит ключ для кэша"""
        
        parts = [text]
        
        if allowed_labels:
            parts.append(",".join(sorted(allowed_labels)))
        
        if user_context:
            parts.append(user_context[:100])  # Ограничиваем длину
        
        return "|".join(parts)
    
    def _build_user_prompt(
        self,
        text: str,
        allowed_labels: Optional[List[str]],
        user_context: Optional[str]
    ) -> str:
        """Строит промпт для пользователя"""
        
        parts = []
        
        # Контекст пользователя
        if user_context:
            parts.append(user_context)
        
        # Ограничение доменов
        if allowed_labels:
            domains_list = ", ".join(allowed_labels)
            parts.append(f"Ограничение: используй только эти домены: {domains_list}")
        
        # Сам текст
        parts.append(f"Классифицируй следующий текст:\n\"{text}\"")
        
        return "\n\n".join(parts)
    
    async def classify_batch(
        self,
        texts: List[str],
        *,
        progress_callback: Optional[callable] = None,
    ) -> List[ClassificationResult]:
        """
        Классифицирует батч текстов с rate limiting.
        
        Args:
            texts: список текстов для классификации
            progress_callback: опциональный callback для отслеживания прогресса
            
        Returns:
            Список ClassificationResult
        """
        
        results = []
        
        for i, text in enumerate(texts):
            try:
                result = await self.classify_one(text)
                results.append(result)
                
                # Callback для прогресса
                if progress_callback:
                    await progress_callback(i + 1, len(texts), result)
                
                # Rate limiting
                if i < len(texts) - 1:  # Не делаем паузу после последнего
                    await asyncio.sleep(self.config.rate_limit)
                    
            except Exception as e:
                logger.error(f"Failed to classify text at index {i}: {e}")
                self.stats["errors"] += 1
                
                # Добавляем fallback результат
                results.append(ClassificationResult(
                    text=text,
                    domain_id="oos",
                    domain_true="oos",
                    confidence=0.0,
                    top_candidates=[["oos", 0.0]],
                    reasoning=f"Error: {str(e)}"
                ))
        
        return results
    
    async def classify_dataframe(
        self,
        df: pd.DataFrame,
        text_column: str = "text",
        *,
        progress_callback: Optional[callable] = None,
    ) -> List[ClassificationResult]:
        """
        Классифицирует DataFrame.
        
        Args:
            df: DataFrame с текстами
            text_column: название колонки с текстами
            progress_callback: опциональный callback для прогресса
            
        Returns:
            Список ClassificationResult
        """
        
        if text_column not in df.columns:
            raise ValueError(f"Column '{text_column}' not found in DataFrame")
        
        texts = df[text_column].astype(str).tolist()
        return await self.classify_batch(texts, progress_callback=progress_callback)
    
    def get_low_confidence_items(
        self,
        results: List[ClassificationResult],
        threshold: Optional[float] = None
    ) -> List[ClassificationResult]:
        """
        Возвращает элементы с низкой уверенностью для HITL.
        
        Args:
            results: список результатов классификации
            threshold: порог уверенности (если не указан, используется из config)
            
        Returns:
            Список результатов с низкой уверенностью
        """
        
        threshold = threshold or self.config.low_conf_threshold
        return [r for r in results if r.confidence < threshold]
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику работы агента"""
        
        stats = self.stats.copy()
        
        # Добавляем вычисляемые метрики
        if stats["total_processed"] > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / stats["total_processed"]
            stats["error_rate"] = stats["errors"] / stats["total_processed"]
            stats["low_confidence_rate"] = stats["low_confidence_count"] / stats["total_processed"]
        
        return stats
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "llm_calls": 0,
            "errors": 0,
            "low_confidence_count": 0,
        }


# Функция совместимости со старым API
async def label_dataframe_batched(
    df: pd.DataFrame,
    client: Any,  # LLMClient (старый)
    system_prompt: str,
    fewshot: str,
    batch_size: int = 20,
    rate_limit: float = 0.4,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Совместимость со старым API.
    Использует новый LabelerAgent под капотом.
    """
    
    # Создаем конфиг из старых параметров
    config = LabelerConfig(
        model=getattr(client, "model", "gpt-4o-mini"),
        api_key=getattr(client, "client", None).api_key if hasattr(client, "client") else "",
        api_base=getattr(client, "client", None).base_url if hasattr(client, "client") else None,
        batch_size=batch_size,
        rate_limit=rate_limit,
    )
    
    # Создаем агента
    agent = LabelerAgent(config)
    
    # Классифицируем
    results = await agent.classify_dataframe(df)
    
    # Конвертируем в старый формат
    return [result.dict() for result in results]


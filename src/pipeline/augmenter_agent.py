"""
Augmenter Agent - агент для синтетического обогащения данных

Использует PydanticAI для генерации перефразировок и вариантов текстов.
Поддерживает:
- Параллельную обработку с ограничением конкурентности
- Балансировку по доменам
- Контроль качества генерации
- Кэширование результатов
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from ..cache import get_cache

logger = logging.getLogger(__name__)


class AugmentedSample(BaseModel):
    """Синтетический пример"""
    
    text: str = Field(..., description="Сгенерированный текст")
    domain_id: str = Field(..., description="Домен текста")
    source: str = Field("synthetic", description="Источник (synthetic)")
    quality_score: Optional[float] = Field(None, description="Оценка качества 0-1")


class AugmentationResult(BaseModel):
    """Результат аугментации одного текста"""
    
    original_text: str = Field(..., description="Исходный текст")
    domain: str = Field(..., description="Домен")
    variants: List[str] = Field(default_factory=list, description="Сгенерированные варианты")
    success: bool = Field(True, description="Успешность генерации")
    error: Optional[str] = Field(None, description="Ошибка если была")


class AugmenterConfig(BaseModel):
    """Конфигурация Augmenter агента"""
    
    model: str = Field("gpt-4o-mini", description="Модель LLM")
    api_key: str = Field(..., description="API ключ")
    api_base: Optional[str] = Field(None, description="Базовый URL API")
    
    variants_per_sample: int = Field(3, description="Количество вариантов на образец", ge=1, le=10)
    include_hard_negatives: bool = Field(False, description="Включать пограничные случаи")
    
    concurrency: int = Field(8, description="Максимальная конкурентность", ge=1, le=50)
    rate_limit: float = Field(0.1, description="Задержка между запросами (сек)", ge=0.0)
    
    max_samples_per_domain: int = Field(30, description="Максимум образцов на домен", ge=1)
    
    use_cache: bool = Field(True, description="Использовать кэш")
    
    system_prompt_path: Path = Field(
        Path("prompts/augmenter_system.txt"),
        description="Путь к системному промпту"
    )


class AugmenterAgent:
    """
    LLM-агент для синтетического обогащения датасета.
    
    Генерирует перефразировки и вариации существующих текстов
    для увеличения разнообразия обучающих данных.
    """
    
    def __init__(self, config: AugmenterConfig):
        self.config = config
        
        # Загружаем системный промпт
        self.system_prompt = self._load_prompt(config.system_prompt_path)
        
        # Инициализируем агента
        self._init_agent()
        
        # Статистика
        self.stats = {
            "total_processed": 0,
            "total_generated": 0,
            "cache_hits": 0,
            "llm_calls": 0,
            "errors": 0,
        }
    
    def _load_prompt(self, path: Path) -> str:
        """Загружает промпт из файла"""
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
            else:
                logger.warning(f"Prompt file not found: {path}, using default")
                return self._get_default_prompt()
        except Exception as e:
            logger.error(f"Failed to load prompt from {path}: {e}")
            return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """Возвращает промпт по умолчанию"""
        return """Ты - эксперт по генерации синтетических данных для обучения NLP моделей.

Твоя задача - генерировать разнообразные перефразировки текстов, сохраняя их смысл и домен.

Правила:
1. Сохраняй семантику и намерение исходного текста
2. Используй разные стилистики (формальный, разговорный, краткий, развернутый)
3. Меняй структуру предложений, но не смысл
4. Используй синонимы и вариации формулировок
5. НЕ добавляй информацию, которой нет в оригинале
6. НЕ меняй домен или тему текста

Примеры:
Оригинал: "передать показания счетчика"
Варианты:
- "подать данные со счётчика"
- "отправить показания прибора учета"
- "передать цифры с водомера"

Генерируй высококачественные варианты текста!"""
    
    def _init_agent(self):
        """Инициализирует PydanticAI агента"""
        
        # Создаем модель
        if self.config.api_base:
            model = OpenAIModel(
                self.config.model,
                api_key=self.config.api_key,
                base_url=self.config.api_base
            )
        else:
            model = OpenAIModel(
                self.config.model,
                api_key=self.config.api_key
            )
        
        # Создаем агента
        self.agent = Agent(
            model=model,
            result_type=AugmentationResult,
            system_prompt=self.system_prompt,
        )
    
    async def augment_one(
        self,
        text: str,
        domain: str,
    ) -> AugmentationResult:
        """
        Генерирует варианты для одного текста.
        
        Args:
            text: исходный текст
            domain: домен текста
            
        Returns:
            AugmentationResult с вариантами
        """
        
        # Проверяем кэш
        if self.config.use_cache:
            cache = get_cache()
            if cache:
                cached = cache.get_augmentation(text, domain, self.system_prompt)
                if cached:
                    self.stats["cache_hits"] += 1
                    self.stats["total_processed"] += 1
                    self.stats["total_generated"] += len(cached)
                    return AugmentationResult(
                        original_text=text,
                        domain=domain,
                        variants=[item["text"] for item in cached],
                        success=True
                    )
        
        # Строим промпт
        user_prompt = self._build_user_prompt(text, domain)
        
        try:
            # Вызываем агента
            result = await self.agent.run(user_prompt)
            
            augmentation = result.data
            
            # Обновляем статистику
            self.stats["llm_calls"] += 1
            self.stats["total_processed"] += 1
            self.stats["total_generated"] += len(augmentation.variants)
            
            # Сохраняем в кэш
            if self.config.use_cache:
                cache = get_cache()
                if cache:
                    cache_data = [
                        {"text": variant, "domain_id": domain, "source": "aug_llm"}
                        for variant in augmentation.variants
                    ]
                    cache.set_augmentation(text, domain, self.system_prompt, cache_data)
            
            return augmentation
            
        except Exception as e:
            logger.error(f"Augmentation failed for text: {text[:100]}... Error: {e}")
            self.stats["errors"] += 1
            
            return AugmentationResult(
                original_text=text,
                domain=domain,
                variants=[],
                success=False,
                error=str(e)
            )
    
    def _build_user_prompt(self, text: str, domain: str) -> str:
        """Строит промпт для генерации вариантов"""
        
        hard_negative_instruction = ""
        if self.config.include_hard_negatives:
            hard_negative_instruction = (
                "\nТакже добавь 1 пограничный вариант - похожий, "
                "но который можно спутать с другим доменом."
            )
        
        prompt = (
            f"Домен: {domain}\n"
            f"Исходный текст: \"{text}\"\n\n"
            f"Сгенерируй {self.config.variants_per_sample} различных перефразировки этого текста."
            f"{hard_negative_instruction}\n\n"
            f"Верни список строк (перефразировки)."
        )
        
        return prompt
    
    async def augment_batch(
        self,
        items: List[Dict[str, Any]],
        *,
        balance_domains: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> List[AugmentedSample]:
        """
        Аугментирует батч текстов с балансировкой по доменам.
        
        Args:
            items: список словарей с полями text, domain_id/domain_true
            balance_domains: балансировать количество образцов по доменам
            progress_callback: опциональный callback для прогресса
            
        Returns:
            Список AugmentedSample
        """
        
        # Группируем по доменам
        by_domain: Dict[str, List[Dict]] = defaultdict(list)
        
        for item in items:
            domain = item.get("domain_true") or item.get("domain_id") or "unknown"
            text = item.get("text") or item.get("query") or ""
            
            if text and domain != "unknown":
                by_domain[domain].append({"text": text, "domain": domain})
        
        # Отбираем образцы для аугментации
        tasks = []
        
        for domain, texts in by_domain.items():
            # Ограничиваем количество на домен
            sample_size = min(len(texts), self.config.max_samples_per_domain)
            samples = texts[:sample_size]
            
            for sample in samples:
                tasks.append((sample["text"], sample["domain"]))
        
        logger.info(f"Starting augmentation for {len(tasks)} samples across {len(by_domain)} domains")
        
        # Обрабатываем с ограничением конкурентности
        semaphore = asyncio.Semaphore(self.config.concurrency)
        results: List[AugmentedSample] = []
        
        async def _worker(idx: int, text: str, domain: str):
            async with semaphore:
                result = await self.augment_one(text, domain)
                
                # Создаем AugmentedSample из вариантов
                samples = []
                for variant in result.variants:
                    samples.append(AugmentedSample(
                        text=variant,
                        domain_id=domain,
                        source="synthetic",
                        quality_score=1.0 if result.success else 0.5
                    ))
                
                results.extend(samples)
                
                # Progress callback
                if progress_callback:
                    await progress_callback(idx + 1, len(tasks), samples)
                
                # Rate limiting
                await asyncio.sleep(self.config.rate_limit)
        
        # Запускаем все задачи
        await asyncio.gather(*[
            _worker(idx, text, domain)
            for idx, (text, domain) in enumerate(tasks)
        ])
        
        logger.info(f"Generated {len(results)} synthetic samples")
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику работы агента"""
        
        stats = self.stats.copy()
        
        # Добавляем вычисляемые метрики
        if stats["total_processed"] > 0:
            stats["avg_variants_per_sample"] = stats["total_generated"] / stats["total_processed"]
            stats["cache_hit_rate"] = stats["cache_hits"] / stats["total_processed"]
            stats["error_rate"] = stats["errors"] / stats["total_processed"]
        
        return stats
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.stats = {
            "total_processed": 0,
            "total_generated": 0,
            "cache_hits": 0,
            "llm_calls": 0,
            "errors": 0,
        }


# Функции совместимости со старым API
async def augment_dataset(
    llm: Any,
    system_prompt: str,
    items: List[Dict[str, Any]],
    *,
    rate_limit: float = 0.1,
    include_low_conf: bool = False,
    low_conf_threshold: float = 0.5,
    only_positive: bool = False,
    concurrency: int = 8,
) -> List[Dict[str, Any]]:
    """
    Совместимость со старым API.
    Использует новый AugmenterAgent под капотом.
    """
    
    # Фильтруем по уверенности если нужно
    if not include_low_conf:
        items = [r for r in items if float(r.get("confidence", 0.0)) >= low_conf_threshold]
    
    # Создаем конфиг
    config = AugmenterConfig(
        model=getattr(llm, "model", "gpt-4o-mini"),
        api_key=getattr(llm, "client", None).api_key if hasattr(llm, "client") else "",
        api_base=getattr(llm, "client", None).base_url if hasattr(llm, "client") else None,
        concurrency=concurrency,
        rate_limit=rate_limit,
        include_hard_negatives=not only_positive,
    )
    
    # Создаем агента
    agent = AugmenterAgent(config)
    
    # Аугментируем
    results = await agent.augment_batch(items)
    
    # Конвертируем в старый формат
    return [{"text": r.text, "domain_id": r.domain_id, "source": r.source} for r in results]


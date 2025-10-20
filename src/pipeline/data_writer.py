"""
DataWriter Component - запись train/eval датасетов

Управляет записью финальных датасетов с поддержкой:
- Стратифицированного сплита train/eval
- Балансировки по доменам
- Валидации качества данных
- Шардинга больших датасетов
- Метаданных и статистики
"""

from __future__ import annotations

import json
import math
import random
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DataWriterConfig(BaseModel):
    """Конфигурация DataWriter"""
    
    output_dir: Path = Field(..., description="Директория для датасетов")
    
    eval_fraction: float = Field(0.1, description="Доля eval датасета", ge=0.0, le=0.5)
    min_eval_samples: int = Field(50, description="Минимум образцов в eval", ge=1)
    min_samples_per_domain: int = Field(5, description="Минимум образцов на домен", ge=1)
    
    balance_domains: bool = Field(True, description="Балансировать домены")
    max_samples_per_domain: Optional[int] = Field(None, description="Максимум образцов на домен")
    
    shard_size: Optional[int] = Field(None, description="Размер шарда (для больших датасетов)")
    
    include_metadata: bool = Field(True, description="Включать метаданные")
    validate_quality: bool = Field(True, description="Валидировать качество данных")


class DatasetStats(BaseModel):
    """Статистика датасета"""
    
    total_samples: int = Field(..., description="Всего образцов")
    train_samples: int = Field(..., description="Образцов в train")
    eval_samples: int = Field(..., description="Образцов в eval")
    
    domain_distribution: Dict[str, int] = Field(..., description="Распределение по доменам")
    source_distribution: Dict[str, int] = Field(..., description="Распределение по источникам")
    
    avg_text_length: float = Field(..., description="Средняя длина текста")
    avg_confidence: float = Field(..., description="Средняя уверенность")
    
    quality_issues: List[str] = Field(default_factory=list, description="Проблемы качества")
    
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания")


class DataWriter:
    """
    Компонент для записи финальных train/eval датасетов.
    
    Функции:
    - Стратифицированный сплит по доменам
    - Балансировка классов
    - Валидация качества
    - Шардинг для больших датасетов
    - Генерация метаданных и статистики
    """
    
    def __init__(self, config: DataWriterConfig):
        self.config = config
        
        # Создаем директории
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Статистика
        self.last_stats: Optional[DatasetStats] = None
    
    def write_datasets(
        self,
        items: List[Dict[str, Any]],
        *,
        dataset_name: str = "dataset",
    ) -> Tuple[Path, Path, DatasetStats]:
        """
        Записывает train и eval датасеты.
        
        Args:
            items: список словарей с обучающими примерами
            dataset_name: базовое имя датасета
            
        Returns:
            Tuple[train_path, eval_path, stats]
        """
        
        logger.info(f"Writing datasets with {len(items)} items")
        
        # Валидация качества если включена
        if self.config.validate_quality:
            items = self._validate_quality(items)
        
        # Балансировка доменов если включена
        if self.config.balance_domains:
            items = self._balance_domains(items)
        
        # Сплит на train/eval
        train_items, eval_items = self._split_train_eval(items)
        
        logger.info(f"Split: train={len(train_items)}, eval={len(eval_items)}")
        
        # Записываем датасеты
        train_path = self._write_jsonl(
            train_items,
            self.config.output_dir / f"{dataset_name}_train.jsonl"
        )
        
        eval_path = self._write_jsonl(
            eval_items,
            self.config.output_dir / f"{dataset_name}_eval.jsonl"
        )
        
        # Генерируем статистику
        stats = self._compute_stats(train_items, eval_items)
        self.last_stats = stats
        
        # Записываем метаданные
        if self.config.include_metadata:
            self._write_metadata(stats, dataset_name)
        
        logger.info(f"Datasets written: train={train_path}, eval={eval_path}")
        
        return train_path, eval_path, stats
    
    def _validate_quality(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Валидирует качество данных"""
        
        valid_items = []
        issues = []
        
        for item in items:
            # Проверяем наличие обязательных полей
            text = item.get("text", "")
            domain = item.get("domain_id") or item.get("domain_true") or item.get("label")
            
            if not text or not isinstance(text, str):
                issues.append(f"Missing or invalid text: {item}")
                continue
            
            if not domain:
                issues.append(f"Missing domain: {item}")
                continue
            
            # Проверяем длину текста
            if len(text.strip()) < 3:
                issues.append(f"Text too short: {text}")
                continue
            
            if len(text) > 5000:
                issues.append(f"Text too long: {text[:100]}...")
                continue
            
            # Проверяем на дубликаты (простая проверка)
            # В production нужна более сложная логика
            
            valid_items.append(item)
        
        if issues:
            logger.warning(f"Found {len(issues)} quality issues")
            for issue in issues[:10]:  # Показываем первые 10
                logger.warning(f"  - {issue}")
        
        logger.info(f"Validated: {len(valid_items)}/{len(items)} items passed")
        
        return valid_items
    
    def _balance_domains(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Балансирует домены"""
        
        # Группируем по доменам
        by_domain: Dict[str, List[Dict]] = defaultdict(list)
        
        for item in items:
            domain = item.get("domain_true") or item.get("domain_id") or item.get("label") or "unknown"
            by_domain[domain].append(item)
        
        # Определяем целевой размер
        domain_sizes = [len(samples) for samples in by_domain.values()]
        
        if self.config.max_samples_per_domain:
            target_size = min(
                self.config.max_samples_per_domain,
                int(sum(domain_sizes) / len(by_domain))
            )
        else:
            # Медианный размер
            target_size = sorted(domain_sizes)[len(domain_sizes) // 2]
        
        # Балансируем
        balanced_items = []
        
        for domain, samples in by_domain.items():
            if len(samples) < self.config.min_samples_per_domain:
                logger.warning(f"Domain '{domain}' has only {len(samples)} samples (min: {self.config.min_samples_per_domain})")
                balanced_items.extend(samples)
                continue
            
            if len(samples) > target_size:
                # Downsampling: берем случайную выборку
                sampled = random.sample(samples, target_size)
                balanced_items.extend(sampled)
                logger.info(f"Domain '{domain}': downsampled from {len(samples)} to {target_size}")
            else:
                # Upsampling: дублируем образцы
                multiplier = math.ceil(target_size / len(samples))
                upsampled = (samples * multiplier)[:target_size]
                balanced_items.extend(upsampled)
                logger.info(f"Domain '{domain}': upsampled from {len(samples)} to {target_size}")
        
        random.shuffle(balanced_items)
        
        logger.info(f"Balanced: {len(items)} → {len(balanced_items)} items")
        
        return balanced_items
    
    def _split_train_eval(
        self,
        items: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Стратифицированный сплит на train/eval"""
        
        if not items:
            return [], []
        
        # Группируем по доменам
        by_domain: Dict[str, List[Dict]] = defaultdict(list)
        
        for item in items:
            domain = item.get("domain_true") or item.get("domain_id") or item.get("label") or "unknown"
            by_domain[domain].append(item)
        
        train_set = []
        eval_set = []
        
        # Вычисляем целевой размер eval
        target_eval_total = max(
            self.config.min_eval_samples,
            math.floor(len(items) * self.config.eval_fraction)
        )
        
        # Стратифицированный сплит по каждому домену
        for domain, samples in by_domain.items():
            if len(samples) == 1:
                # Единственный образец идет в train
                train_set.extend(samples)
                continue
            
            # Перемешиваем
            random.shuffle(samples)
            
            # Вычисляем количество для eval
            eval_count = max(1, math.floor(len(samples) * self.config.eval_fraction))
            
            # Сплит
            eval_set.extend(samples[:eval_count])
            train_set.extend(samples[eval_count:])
        
        # Если eval меньше целевого, добираем из train
        if len(eval_set) < target_eval_total:
            deficit = target_eval_total - len(eval_set)
            
            # Группируем train по доменам
            train_by_domain: Dict[str, List[Dict]] = defaultdict(list)
            for item in train_set:
                domain = item.get("domain_true") or item.get("domain_id") or item.get("label") or "unknown"
                train_by_domain[domain].append(item)
            
            # Берем из самых больших групп
            for domain, samples in sorted(train_by_domain.items(), key=lambda x: len(x[1]), reverse=True):
                if deficit <= 0:
                    break
                
                if len(samples) > 1:
                    move_count = min(deficit, len(samples) - 1)
                    eval_set.extend(samples[:move_count])
                    train_by_domain[domain] = samples[move_count:]
                    deficit -= move_count
            
            # Пересобираем train
            train_set = [item for samples in train_by_domain.values() for item in samples]
        
        # Перемешиваем
        random.shuffle(train_set)
        random.shuffle(eval_set)
        
        return train_set, eval_set
    
    def _write_jsonl(self, items: List[Dict[str, Any]], path: Path) -> Path:
        """Записывает JSONL файл"""
        
        if not items:
            logger.warning(f"No items to write to {path}")
            # Создаем пустой файл
            path.touch()
            return path
        
        # Проверяем нужно ли шардирование
        if self.config.shard_size and len(items) > self.config.shard_size:
            return self._write_sharded(items, path)
        
        # Записываем обычный файл
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                # Нормализуем формат
                normalized = self._normalize_item(item)
                f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
        
        return path
    
    def _write_sharded(self, items: List[Dict[str, Any]], base_path: Path) -> Path:
        """Записывает датасет в виде шардов"""
        
        shard_dir = base_path.parent / "chunks"
        shard_dir.mkdir(parents=True, exist_ok=True)
        
        base_name = base_path.stem
        
        # Разбиваем на шарды
        num_shards = math.ceil(len(items) / self.config.shard_size)
        
        for shard_idx in range(num_shards):
            start_idx = shard_idx * self.config.shard_size
            end_idx = min((shard_idx + 1) * self.config.shard_size, len(items))
            
            shard_items = items[start_idx:end_idx]
            shard_path = shard_dir / f"{base_name}_part_{shard_idx+1:04d}.jsonl"
            
            with open(shard_path, "w", encoding="utf-8") as f:
                for item in shard_items:
                    normalized = self._normalize_item(item)
                    f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            
            logger.info(f"Written shard {shard_idx+1}/{num_shards}: {shard_path}")
        
        # Записываем также consolidated файл
        with open(base_path, "w", encoding="utf-8") as f:
            for item in items:
                normalized = self._normalize_item(item)
                f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
        
        return base_path
    
    def _normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализует элемент к стандартному формату"""
        
        # Стандартные поля
        normalized = {
            "text": item.get("text", ""),
            "label": item.get("domain_true") or item.get("domain_id") or item.get("label", "unknown"),
        }
        
        # Опциональные поля
        if "confidence" in item:
            normalized["confidence"] = item["confidence"]
        
        if "source" in item:
            normalized["source"] = item["source"]
        
        # Дополнительная метаинформация
        if self.config.include_metadata and "metadata" in item:
            normalized["metadata"] = item["metadata"]
        
        return normalized
    
    def _compute_stats(
        self,
        train_items: List[Dict[str, Any]],
        eval_items: List[Dict[str, Any]]
    ) -> DatasetStats:
        """Вычисляет статистику датасета"""
        
        all_items = train_items + eval_items
        
        # Распределение по доменам
        domain_dist = Counter()
        for item in all_items:
            domain = item.get("domain_true") or item.get("domain_id") or item.get("label") or "unknown"
            domain_dist[domain] += 1
        
        # Распределение по источникам
        source_dist = Counter()
        for item in all_items:
            source = item.get("source", "unknown")
            source_dist[source] += 1
        
        # Средняя длина текста
        text_lengths = [len(item.get("text", "")) for item in all_items]
        avg_text_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0.0
        
        # Средняя уверенность
        confidences = [item.get("confidence", 0.0) for item in all_items if "confidence" in item]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return DatasetStats(
            total_samples=len(all_items),
            train_samples=len(train_items),
            eval_samples=len(eval_items),
            domain_distribution=dict(domain_dist),
            source_distribution=dict(source_dist),
            avg_text_length=avg_text_length,
            avg_confidence=avg_confidence,
        )
    
    def _write_metadata(self, stats: DatasetStats, dataset_name: str):
        """Записывает метаданные датасета"""
        
        metadata_path = self.config.output_dir / f"{dataset_name}_metadata.json"
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(stats.dict(), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Metadata written to {metadata_path}")
    
    def get_last_stats(self) -> Optional[DatasetStats]:
        """Возвращает статистику последней записи"""
        return self.last_stats


# Функции совместимости со старым API
def split_train_eval(
    items: List[Dict[str, Any]],
    eval_frac: float = 0.1,
    min_eval: int = 50
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Совместимость со старым API.
    """
    config = DataWriterConfig(
        output_dir=Path("./temp"),
        eval_fraction=eval_frac,
        min_eval_samples=min_eval,
        balance_domains=False,
    )
    
    writer = DataWriter(config)
    return writer._split_train_eval(items)


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> bool:
    """
    Совместимость со старым API.
    """
    if not rows:
        if path.exists():
            path.unlink()
        return False
    
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    return True


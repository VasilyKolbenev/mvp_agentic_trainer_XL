"""
ML Data Pipeline Components

Компоненты согласно обновленной архитектуре:
- ETL: обработка входящих данных
- LabelerAgent: разметка + валидация существующих меток
- AugmenterAgent: синтетическое обогащение
- QualityControl: контроль качества (косинусное расстояние + Левенштейн)
- LabelerAgent (повторно): разметка синтетических данных
- ReviewDataset: HITL для сомнительных случаев
- DataWriter: запись train/eval датасетов
- DataStorage: версионирование и хранение артефактов

Правильный flow:
1. ETL - обработка данных
2. Labeler - валидация существующих меток
3. Augmenter - генерация синтетики
4. QualityControl - проверка качества синтетики (cosine + Levenshtein)
5. Labeler - разметка валидной синтетики
6. Review - HITL для низкой уверенности
7. DataWriter - запись финальных датасетов
8. DataStorage - версионирование
"""

from .etl import ETLProcessor, ETLConfig
from .labeler_agent import LabelerAgent, LabelerConfig
from .augmenter_agent import AugmenterAgent, AugmenterConfig
from .quality_control import QualityControl, QualityControlConfig
from .review_dataset import ReviewDataset, ReviewDatasetConfig
from .data_writer import DataWriter, DataWriterConfig
from .data_storage import DataStorage, DataStorageConfig

__all__ = [
    "ETLProcessor",
    "ETLConfig",
    "LabelerAgent",
    "LabelerConfig",
    "AugmenterAgent",
    "AugmenterConfig",
    "QualityControl",
    "QualityControlConfig",
    "ReviewDataset",
    "ReviewDatasetConfig",
    "DataWriter",
    "DataWriterConfig",
    "DataStorage",
    "DataStorageConfig",
]

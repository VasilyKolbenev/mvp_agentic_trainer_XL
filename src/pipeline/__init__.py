"""
ML Data Pipeline Components

Компоненты согласно архитектуре:
- ECKLogs: источник данных (Telegram бот)
- ETL: обработка и нормализация данных
- LabelerAgent: LLM-агент для автоматической разметки
- AugmenterAgent: LLM-агент для синтетического обогащения
- ReviewDataset: компонент для ручной проверки/правок (HITL)
- DataWriter: запись train/eval датасетов
- DataStorage: версионирование и хранение артефактов
"""

from .etl import ETLProcessor
from .labeler_agent import LabelerAgent
from .augmenter_agent import AugmenterAgent
from .review_dataset import ReviewDataset
from .data_writer import DataWriter
from .data_storage import DataStorage

__all__ = [
    "ETLProcessor",
    "LabelerAgent",
    "AugmenterAgent",
    "ReviewDataset",
    "DataWriter",
    "DataStorage",
]


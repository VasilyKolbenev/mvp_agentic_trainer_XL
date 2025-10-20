"""
ReviewDataset Component - Human-in-the-Loop (HITL) процесс

Управляет очередью на ручную проверку и исправления.
Поддерживает:
- Приоритизацию по уверенности и важности
- Отслеживание статуса проверки
- Интеграцию с системой обучения на feedback
- Метрики качества ручной разметки
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    """Статус проверки элемента"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CORRECTED = "corrected"
    SKIPPED = "skipped"
    REJECTED = "rejected"


class ReviewPriority(str, Enum):
    """Приоритет проверки"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewItem(BaseModel):
    """Элемент для ручной проверки"""
    
    id: str = Field(..., description="Уникальный идентификатор")
    text: str = Field(..., description="Текст для проверки")
    
    predicted_domain: str = Field(..., description="Предсказанный домен")
    confidence: float = Field(..., description="Уверенность модели")
    top_candidates: List[List[Any]] = Field(default_factory=list, description="Топ кандидатов")
    
    corrected_domain: Optional[str] = Field(None, description="Исправленный домен")
    reviewer_id: Optional[str] = Field(None, description="ID проверяющего")
    review_timestamp: Optional[datetime] = Field(None, description="Время проверки")
    
    status: ReviewStatus = Field(ReviewStatus.PENDING, description="Статус проверки")
    priority: ReviewPriority = Field(ReviewPriority.MEDIUM, description="Приоритет")
    
    notes: Optional[str] = Field(None, description="Комментарии проверяющего")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные данные")
    
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания")
    updated_at: datetime = Field(default_factory=datetime.now, description="Время обновления")


class ReviewDatasetConfig(BaseModel):
    """Конфигурация ReviewDataset"""
    
    data_dir: Path = Field(..., description="Директория для данных")
    
    low_confidence_threshold: float = Field(0.5, description="Порог низкой уверенности", ge=0.0, le=1.0)
    high_priority_threshold: float = Field(0.3, description="Порог высокого приоритета", ge=0.0, le=1.0)
    
    max_queue_size: int = Field(10000, description="Максимальный размер очереди", ge=1)
    
    auto_approve_threshold: float = Field(0.95, description="Порог автоодобрения", ge=0.0, le=1.0)


class ReviewDataset:
    """
    Компонент для управления Human-in-the-Loop процессом.
    
    Функции:
    - Добавление элементов в очередь с приоритизацией
    - Выдача элементов на проверку
    - Сохранение исправлений
    - Статистика качества разметки
    """
    
    def __init__(self, config: ReviewDatasetConfig):
        self.config = config
        
        # Пути к файлам
        self.queue_file = config.data_dir / "hitl" / "queue.jsonl"
        self.history_file = config.data_dir / "hitl" / "history.jsonl"
        
        # Создаем директории
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем очередь
        self.queue: List[ReviewItem] = []
        self._load_queue()
        
        # Статистика
        self.stats = {
            "total_added": 0,
            "total_reviewed": 0,
            "total_corrected": 0,
            "total_approved": 0,
            "total_skipped": 0,
            "avg_review_time": 0.0,
        }
    
    def _load_queue(self):
        """Загружает очередь из файла"""
        
        if not self.queue_file.exists():
            return
        
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            item = ReviewItem(**data)
                            
                            # Загружаем только pending и in_review
                            if item.status in [ReviewStatus.PENDING, ReviewStatus.IN_REVIEW]:
                                self.queue.append(item)
                                
                        except Exception as e:
                            logger.warning(f"Failed to parse review item: {e}")
                            continue
            
            # Сортируем по приоритету и уверенности
            self._sort_queue()
            
            logger.info(f"Loaded {len(self.queue)} items from review queue")
            
        except Exception as e:
            logger.error(f"Failed to load review queue: {e}")
    
    def _save_queue(self):
        """Сохраняет очередь в файл"""
        
        try:
            # Перезаписываем файл с актуальной очередью
            with open(self.queue_file, "w", encoding="utf-8") as f:
                for item in self.queue:
                    f.write(json.dumps(item.dict(), default=str, ensure_ascii=False) + "\n")
                    
        except Exception as e:
            logger.error(f"Failed to save review queue: {e}")
    
    def _append_history(self, item: ReviewItem):
        """Добавляет элемент в историю"""
        
        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(item.dict(), default=str, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to append to history: {e}")
    
    def _sort_queue(self):
        """Сортирует очередь по приоритету и уверенности"""
        
        priority_order = {
            ReviewPriority.CRITICAL: 0,
            ReviewPriority.HIGH: 1,
            ReviewPriority.MEDIUM: 2,
            ReviewPriority.LOW: 3,
        }
        
        self.queue.sort(
            key=lambda x: (
                priority_order.get(x.priority, 99),
                x.confidence,  # Меньше уверенность = выше в очереди
                x.created_at
            )
        )
    
    def _calculate_priority(self, confidence: float) -> ReviewPriority:
        """Вычисляет приоритет на основе уверенности"""
        
        if confidence < self.config.high_priority_threshold:
            return ReviewPriority.CRITICAL
        elif confidence < self.config.low_confidence_threshold:
            return ReviewPriority.HIGH
        elif confidence < 0.7:
            return ReviewPriority.MEDIUM
        else:
            return ReviewPriority.LOW
    
    def add_items(self, items: List[Dict[str, Any]]) -> int:
        """
        Добавляет элементы в очередь на проверку.
        
        Args:
            items: список словарей с полями text, domain_id, confidence, etc.
            
        Returns:
            Количество добавленных элементов
        """
        
        added_count = 0
        
        for item_data in items:
            try:
                # Проверяем лимит очереди
                if len(self.queue) >= self.config.max_queue_size:
                    logger.warning("Review queue is full, skipping items")
                    break
                
                text = item_data.get("text", "")
                confidence = float(item_data.get("confidence", 0.0))
                
                # Автоодобрение высокоуверенных
                if confidence >= self.config.auto_approve_threshold:
                    continue
                
                # Пропускаем элементы с низкой уверенностью но уже в очереди
                if any(existing.text == text for existing in self.queue):
                    continue
                
                # Вычисляем приоритет
                priority = self._calculate_priority(confidence)
                
                # Создаем ReviewItem
                review_item = ReviewItem(
                    id=self._generate_id(text),
                    text=text,
                    predicted_domain=item_data.get("domain_id", "unknown"),
                    confidence=confidence,
                    top_candidates=item_data.get("top_candidates", []),
                    priority=priority,
                    metadata=item_data.get("metadata", {}),
                )
                
                self.queue.append(review_item)
                added_count += 1
                self.stats["total_added"] += 1
                
            except Exception as e:
                logger.error(f"Failed to add item to review queue: {e}")
                continue
        
        # Сортируем и сохраняем
        self._sort_queue()
        self._save_queue()
        
        logger.info(f"Added {added_count} items to review queue")
        
        return added_count
    
    def _generate_id(self, text: str) -> str:
        """Генерирует уникальный ID для элемента"""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def get_next(self, count: int = 1, reviewer_id: Optional[str] = None) -> List[ReviewItem]:
        """
        Возвращает следующие элементы для проверки.
        
        Args:
            count: количество элементов
            reviewer_id: ID проверяющего (опционально)
            
        Returns:
            Список ReviewItem
        """
        
        # Берем первые count элементов со статусом PENDING
        items = []
        
        for item in self.queue:
            if item.status == ReviewStatus.PENDING and len(items) < count:
                # Меняем статус на IN_REVIEW
                item.status = ReviewStatus.IN_REVIEW
                item.reviewer_id = reviewer_id
                item.updated_at = datetime.now()
                items.append(item)
        
        if items:
            self._save_queue()
        
        return items
    
    def submit_review(
        self,
        item_id: str,
        corrected_domain: str,
        reviewer_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Отправляет результат проверки.
        
        Args:
            item_id: ID элемента
            corrected_domain: исправленный домен
            reviewer_id: ID проверяющего
            notes: комментарии
            
        Returns:
            True если успешно
        """
        
        # Находим элемент в очереди
        item = None
        for i, q_item in enumerate(self.queue):
            if q_item.id == item_id:
                item = q_item
                break
        
        if not item:
            logger.warning(f"Review item {item_id} not found in queue")
            return False
        
        # Обновляем элемент
        item.corrected_domain = corrected_domain
        item.reviewer_id = reviewer_id or item.reviewer_id
        item.review_timestamp = datetime.now()
        item.notes = notes
        item.updated_at = datetime.now()
        
        # Определяем статус
        if corrected_domain == item.predicted_domain:
            item.status = ReviewStatus.APPROVED
            self.stats["total_approved"] += 1
        else:
            item.status = ReviewStatus.CORRECTED
            self.stats["total_corrected"] += 1
        
        self.stats["total_reviewed"] += 1
        
        # Удаляем из очереди и добавляем в историю
        self.queue.remove(item)
        self._append_history(item)
        self._save_queue()
        
        logger.info(f"Review submitted for item {item_id}: {item.predicted_domain} → {corrected_domain}")
        
        return True
    
    def skip_item(self, item_id: str, reviewer_id: Optional[str] = None) -> bool:
        """
        Пропускает элемент (возвращает в очередь с низким приоритетом).
        
        Args:
            item_id: ID элемента
            reviewer_id: ID проверяющего
            
        Returns:
            True если успешно
        """
        
        for item in self.queue:
            if item.id == item_id:
                item.status = ReviewStatus.PENDING
                item.priority = ReviewPriority.LOW  # Понижаем приоритет
                item.reviewer_id = reviewer_id
                item.updated_at = datetime.now()
                
                self.stats["total_skipped"] += 1
                
                self._sort_queue()
                self._save_queue()
                
                return True
        
        return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Возвращает статистику очереди"""
        
        # Группируем по статусам
        by_status = {}
        for status in ReviewStatus:
            by_status[status.value] = sum(1 for item in self.queue if item.status == status)
        
        # Группируем по приоритетам
        by_priority = {}
        for priority in ReviewPriority:
            by_priority[priority.value] = sum(1 for item in self.queue if item.priority == priority)
        
        # Средняя уверенность
        avg_confidence = (
            sum(item.confidence for item in self.queue) / len(self.queue)
            if self.queue else 0.0
        )
        
        return {
            "queue_size": len(self.queue),
            "by_status": by_status,
            "by_priority": by_priority,
            "avg_confidence": avg_confidence,
            **self.stats,
        }
    
    def export_reviewed(self, output_path: Optional[Path] = None) -> Path:
        """
        Экспортирует проверенные элементы.
        
        Args:
            output_path: путь для экспорта (опционально)
            
        Returns:
            Путь к файлу
        """
        
        if not output_path:
            output_path = self.config.data_dir / "hitl" / "reviewed_export.jsonl"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Читаем историю и фильтруем approved/corrected
        reviewed_items = []
        
        if self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            item = ReviewItem(**data)
                            
                            if item.status in [ReviewStatus.APPROVED, ReviewStatus.CORRECTED]:
                                # Формат для обучения
                                training_item = {
                                    "text": item.text,
                                    "domain_id": item.corrected_domain or item.predicted_domain,
                                    "domain_true": item.corrected_domain or item.predicted_domain,
                                    "confidence": 1.0,  # Высокая уверенность для ручной разметки
                                    "source": "human_review",
                                    "was_corrected": item.status == ReviewStatus.CORRECTED,
                                }
                                reviewed_items.append(training_item)
                                
                        except Exception as e:
                            logger.warning(f"Failed to parse history item: {e}")
                            continue
        
        # Записываем
        with open(output_path, "w", encoding="utf-8") as f:
            for item in reviewed_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        logger.info(f"Exported {len(reviewed_items)} reviewed items to {output_path}")
        
        return output_path


# Функции совместимости со старым API
def low_conf_items(rows: List[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    """
    Совместимость со старым API.
    Возвращает элементы с низкой уверенностью.
    """
    return [r for r in rows if float(r.get("confidence", 0.0)) < float(threshold)]


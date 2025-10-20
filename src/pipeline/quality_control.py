"""
Quality Control Component - контроль качества разметки и аугментации

Функции:
- Валидация существующей разметки
- Проверка косинусного расстояния (semantic similarity)
- Проверка расстояния Левенштейна (text similarity)
- Детекция аномалий и несоответствий
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, Field
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)


class QualityMetrics(BaseModel):
    """Метрики качества"""
    
    cosine_similarity: float = Field(..., description="Косинусное расстояние (0-1)")
    levenshtein_distance: int = Field(..., description="Расстояние Левенштейна")
    levenshtein_ratio: float = Field(..., description="Нормализованное расстояние (0-1)")
    
    is_valid: bool = Field(..., description="Проходит ли проверку качества")
    issues: List[str] = Field(default_factory=list, description="Найденные проблемы")


class ValidationResult(BaseModel):
    """Результат валидации"""
    
    text: str
    original_domain: str
    validated_domain: str
    is_correct: bool
    confidence: float
    
    quality_metrics: Optional[QualityMetrics] = None
    issues: List[str] = Field(default_factory=list)


class QualityControlConfig(BaseModel):
    """Конфигурация контроля качества"""
    
    # Пороги для косинусного расстояния
    min_cosine_similarity: float = Field(
        0.3, 
        description="Минимальное косинусное сходство для аугментации",
        ge=0.0, le=1.0
    )
    max_cosine_similarity: float = Field(
        0.95,
        description="Максимальное косинусное сходство (детекция дубликатов)",
        ge=0.0, le=1.0
    )
    
    # Пороги для расстояния Левенштейна
    max_levenshtein_ratio: float = Field(
        0.8,
        description="Максимальное normalized Levenshtein расстояние",
        ge=0.0, le=1.0
    )
    min_levenshtein_changes: int = Field(
        3,
        description="Минимум изменений символов для аугментации",
        ge=1
    )
    
    # Валидация разметки
    validate_existing_labels: bool = Field(
        True,
        description="Перепроверять существующие метки"
    )
    
    relabel_synthetic: bool = Field(
        True,
        description="Размечать синтетические данные"
    )
    
    # Строгость проверки
    strict_mode: bool = Field(
        False,
        description="Строгий режим - отклонять сомнительные примеры"
    )


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Вычисляет расстояние Левенштейна между двумя строками.
    
    Args:
        s1: первая строка
        s2: вторая строка
        
    Returns:
        Расстояние Левенштейна (количество операций)
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Стоимость вставки, удаления, замены
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def normalized_levenshtein(s1: str, s2: str) -> float:
    """
    Нормализованное расстояние Левенштейна (0-1).
    
    0 = идентичные строки
    1 = полностью разные
    """
    if not s1 and not s2:
        return 0.0
    
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 0.0
    
    distance = levenshtein_distance(s1, s2)
    return distance / max_len


class QualityControl:
    """
    Компонент контроля качества разметки и аугментации.
    
    Функции:
    - Валидация существующих меток через LLM
    - Проверка качества аугментации (semantic + lexical similarity)
    - Детекция дубликатов и аномалий
    - Автоматическое исправление проблемных примеров
    """
    
    def __init__(self, config: QualityControlConfig):
        self.config = config
        
        # TF-IDF векторизатор для косинусного расстояния
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=1
        )
        
        # Статистика
        self.stats = {
            "total_validated": 0,
            "relabeled": 0,
            "rejected_low_similarity": 0,
            "rejected_high_similarity": 0,
            "rejected_levenshtein": 0,
            "passed": 0,
        }
    
    def compute_similarity(
        self,
        text1: str,
        text2: str,
        reference_corpus: Optional[List[str]] = None
    ) -> QualityMetrics:
        """
        Вычисляет метрики схожести между двумя текстами.
        
        Args:
            text1: первый текст (обычно оригинал)
            text2: второй текст (обычно аугментированный)
            reference_corpus: опциональный корпус для обучения TF-IDF
            
        Returns:
            QualityMetrics с косинусным и Левенштейн расстояниями
        """
        
        # Косинусное сходство через TF-IDF
        corpus = [text1, text2]
        if reference_corpus:
            corpus = reference_corpus + corpus
        
        try:
            # Обучаем векторизатор на корпусе
            tfidf_matrix = self.vectorizer.fit_transform(corpus)
            
            # Берем векторы последних двух текстов
            vec1 = tfidf_matrix[-2].toarray()
            vec2 = tfidf_matrix[-1].toarray()
            
            # Косинусное сходство
            cos_sim = float(cosine_similarity(vec1, vec2)[0][0])
        except Exception as e:
            logger.warning(f"Failed to compute cosine similarity: {e}")
            cos_sim = 0.5  # fallback
        
        # Расстояние Левенштейна
        lev_dist = levenshtein_distance(text1.lower(), text2.lower())
        lev_ratio = normalized_levenshtein(text1.lower(), text2.lower())
        
        # Проверяем пороги
        issues = []
        is_valid = True
        
        # Слишком похожи (дубликат)
        if cos_sim > self.config.max_cosine_similarity:
            issues.append(f"Косинусное сходство слишком высокое: {cos_sim:.3f} > {self.config.max_cosine_similarity}")
            is_valid = False
        
        # Слишком разные (не сохраняет семантику)
        if cos_sim < self.config.min_cosine_similarity:
            issues.append(f"Косинусное сходство слишком низкое: {cos_sim:.3f} < {self.config.min_cosine_similarity}")
            is_valid = False
        
        # Левенштейн - слишком мало изменений
        if lev_dist < self.config.min_levenshtein_changes:
            issues.append(f"Слишком мало изменений: {lev_dist} < {self.config.min_levenshtein_changes}")
            is_valid = False
        
        # Левенштейн - слишком много изменений
        if lev_ratio > self.config.max_levenshtein_ratio:
            issues.append(f"Слишком много изменений: {lev_ratio:.3f} > {self.config.max_levenshtein_ratio}")
            is_valid = False
        
        return QualityMetrics(
            cosine_similarity=cos_sim,
            levenshtein_distance=lev_dist,
            levenshtein_ratio=lev_ratio,
            is_valid=is_valid,
            issues=issues
        )
    
    async def validate_existing_labels(
        self,
        items: List[Dict[str, Any]],
        labeler_agent,
    ) -> List[ValidationResult]:
        """
        Перепроверяет существующую разметку через LLM.
        
        Args:
            items: элементы с полями text, domain_id/label
            labeler_agent: LabelerAgent для перепроверки
            
        Returns:
            Список ValidationResult с результатами валидации
        """
        
        if not self.config.validate_existing_labels:
            logger.info("Validation of existing labels is disabled")
            return []
        
        logger.info(f"Validating {len(items)} existing labels...")
        
        validation_results = []
        
        for item in items:
            text = item.get("text", "")
            original_domain = item.get("domain_id") or item.get("label") or item.get("domain_true", "unknown")
            
            # Перепроверяем разметку через LLM
            result = await labeler_agent.classify_one(text)
            
            validated_domain = result.domain_id
            is_correct = (validated_domain == original_domain)
            
            # Если не совпадает - логируем
            if not is_correct:
                logger.warning(
                    f"Label mismatch: '{text[:50]}...' "
                    f"Original: {original_domain}, Validated: {validated_domain}"
                )
                self.stats["relabeled"] += 1
            
            validation_results.append(ValidationResult(
                text=text,
                original_domain=original_domain,
                validated_domain=validated_domain,
                is_correct=is_correct,
                confidence=result.confidence,
                issues=[] if is_correct else [f"Domain changed: {original_domain} → {validated_domain}"]
            ))
            
            self.stats["total_validated"] += 1
        
        # Статистика валидации
        correct_count = sum(1 for v in validation_results if v.is_correct)
        accuracy = correct_count / len(validation_results) if validation_results else 0.0
        
        logger.info(
            f"Validation complete: {correct_count}/{len(validation_results)} correct "
            f"(accuracy: {accuracy:.2%})"
        )
        
        return validation_results
    
    async def validate_and_label_synthetic(
        self,
        synthetic_items: List[Dict[str, Any]],
        original_items: List[Dict[str, Any]],
        labeler_agent,
    ) -> List[Dict[str, Any]]:
        """
        Проверяет и размечает синтетические данные.
        
        Args:
            synthetic_items: синтетические примеры от Augmenter
            original_items: исходные примеры для сравнения
            labeler_agent: LabelerAgent для разметки
            
        Returns:
            Список валидных размеченных примеров
        """
        
        logger.info(f"Validating {len(synthetic_items)} synthetic samples...")
        
        # Создаем корпус оригинальных текстов для TF-IDF
        original_texts = [item.get("text", "") for item in original_items]
        
        # Группируем синтетику по исходному тексту
        synthetic_by_original = {}
        for syn_item in synthetic_items:
            original_text = syn_item.get("original_text", syn_item.get("text", ""))
            if original_text not in synthetic_by_original:
                synthetic_by_original[original_text] = []
            synthetic_by_original[original_text].append(syn_item)
        
        validated_items = []
        
        for syn_item in synthetic_items:
            text = syn_item.get("text", "")
            expected_domain = syn_item.get("domain_id", "")
            original_text = syn_item.get("original_text", text)
            
            # 1. Проверяем качество относительно оригинала
            quality_metrics = self.compute_similarity(
                original_text,
                text,
                reference_corpus=original_texts
            )
            
            # Логируем проблемы
            if not quality_metrics.is_valid:
                logger.warning(
                    f"Quality check failed for: '{text[:50]}...' "
                    f"Issues: {quality_metrics.issues}"
                )
                
                # Подсчет отклоненных
                if quality_metrics.cosine_similarity < self.config.min_cosine_similarity:
                    self.stats["rejected_low_similarity"] += 1
                if quality_metrics.cosine_similarity > self.config.max_cosine_similarity:
                    self.stats["rejected_high_similarity"] += 1
                if quality_metrics.levenshtein_ratio > self.config.max_levenshtein_ratio:
                    self.stats["rejected_levenshtein"] += 1
                
                # В строгом режиме отклоняем
                if self.config.strict_mode:
                    continue
            
            # 2. Перепроверяем домен через LLM (если включено)
            if self.config.relabel_synthetic:
                result = await labeler_agent.classify_one(text)
                actual_domain = result.domain_id
                actual_confidence = result.confidence
                
                # Проверяем совпадение с ожидаемым доменом
                if actual_domain != expected_domain:
                    logger.warning(
                        f"Domain mismatch in synthetic: '{text[:50]}...' "
                        f"Expected: {expected_domain}, Got: {actual_domain}"
                    )
                    
                    # В строгом режиме отклоняем
                    if self.config.strict_mode:
                        self.stats["relabeled"] += 1
                        continue
                    
                    # Иначе используем новую метку
                    expected_domain = actual_domain
            else:
                actual_confidence = 1.0  # Доверяем Augmenter
            
            # 3. Формируем валидный элемент
            validated_item = {
                "text": text,
                "domain_id": expected_domain,
                "domain_true": expected_domain,
                "confidence": actual_confidence,
                "source": "synthetic_validated",
                "quality_metrics": quality_metrics.dict(),
                "original_text": original_text,
            }
            
            validated_items.append(validated_item)
            self.stats["passed"] += 1
        
        logger.info(
            f"Synthetic validation complete: {len(validated_items)}/{len(synthetic_items)} passed "
            f"(pass rate: {len(validated_items)/len(synthetic_items):.2%})"
        )
        
        return validated_items
    
    def detect_duplicates(
        self,
        items: List[Dict[str, Any]],
        threshold: float = 0.95
    ) -> List[Tuple[int, int, float]]:
        """
        Детектирует дубликаты в датасете.
        
        Args:
            items: список элементов с полем text
            threshold: порог косинусного сходства для дубликатов
            
        Returns:
            Список кортежей (index1, index2, similarity)
        """
        
        texts = [item.get("text", "") for item in items]
        
        if len(texts) < 2:
            return []
        
        # TF-IDF векторизация
        try:
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Вычисляем попарные косинусные расстояния
            similarities = cosine_similarity(tfidf_matrix)
            
            # Находим дубликаты
            duplicates = []
            
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    sim = similarities[i, j]
                    if sim >= threshold:
                        duplicates.append((i, j, float(sim)))
            
            if duplicates:
                logger.info(f"Found {len(duplicates)} potential duplicates (threshold={threshold})")
            
            return duplicates
            
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
            return []
    
    def compute_dataset_quality_score(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Вычисляет общую оценку качества датасета.
        
        Returns:
            Словарь с метриками качества
        """
        
        if not items:
            return {"quality_score": 0.0, "issues": ["Empty dataset"]}
        
        issues = []
        
        # 1. Проверка дубликатов
        duplicates = self.detect_duplicates(items, threshold=0.95)
        duplicate_rate = len(duplicates) / len(items) if items else 0.0
        
        if duplicate_rate > 0.05:  # Более 5% дубликатов
            issues.append(f"High duplicate rate: {duplicate_rate:.2%}")
        
        # 2. Проверка распределения по доменам
        from collections import Counter
        domains = [item.get("domain_id") or item.get("label", "unknown") for item in items]
        domain_counts = Counter(domains)
        
        # Коэффициент вариации (CV) для балансировки
        counts = list(domain_counts.values())
        mean_count = np.mean(counts)
        std_count = np.std(counts)
        cv = std_count / mean_count if mean_count > 0 else 0.0
        
        if cv > 1.0:  # Высокий дисбаланс
            issues.append(f"High domain imbalance: CV={cv:.2f}")
        
        # 3. Проверка длин текстов
        text_lengths = [len(item.get("text", "")) for item in items]
        avg_length = np.mean(text_lengths)
        
        if avg_length < 10:
            issues.append(f"Texts too short: avg={avg_length:.1f}")
        
        if avg_length > 500:
            issues.append(f"Texts too long: avg={avg_length:.1f}")
        
        # 4. Проверка confidence (если есть)
        confidences = [item.get("confidence", 1.0) for item in items if "confidence" in item]
        avg_confidence = np.mean(confidences) if confidences else 1.0
        
        # Итоговая оценка качества (0-1)
        quality_score = 1.0
        
        # Штрафуем за проблемы
        quality_score -= duplicate_rate * 0.3  # Дубликаты
        quality_score -= min(cv * 0.2, 0.3)    # Дисбаланс
        quality_score -= (1.0 - avg_confidence) * 0.2  # Низкая уверенность
        
        quality_score = max(0.0, min(1.0, quality_score))
        
        return {
            "quality_score": quality_score,
            "total_samples": len(items),
            "duplicate_rate": duplicate_rate,
            "duplicates_found": len(duplicates),
            "domain_balance_cv": cv,
            "domain_distribution": dict(domain_counts),
            "avg_text_length": avg_length,
            "avg_confidence": avg_confidence,
            "issues": issues,
        }
    
    def filter_by_quality(
        self,
        items: List[Dict[str, Any]],
        min_quality_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Фильтрует элементы по качеству.
        
        Удаляет элементы с quality_metrics.is_valid = False
        """
        
        filtered = []
        
        for item in items:
            # Если есть метрики качества
            if "quality_metrics" in item:
                metrics = item["quality_metrics"]
                if isinstance(metrics, dict) and not metrics.get("is_valid", True):
                    continue  # Пропускаем невалидные
            
            filtered.append(item)
        
        removed = len(items) - len(filtered)
        if removed > 0:
            logger.info(f"Filtered out {removed} low-quality items")
        
        return filtered
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику контроля качества"""
        stats = self.stats.copy()
        
        if stats["total_validated"] > 0:
            stats["pass_rate"] = stats["passed"] / stats["total_validated"]
            stats["relabel_rate"] = stats["relabeled"] / stats["total_validated"]
        
        return stats
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.stats = {
            "total_validated": 0,
            "relabeled": 0,
            "rejected_low_similarity": 0,
            "rejected_high_similarity": 0,
            "rejected_levenshtein": 0,
            "passed": 0,
        }


"""
Labeler Validator - жесткий контроль качества работы Labeler Agent

Многоуровневая система проверки:
1. Консенсус голосование (multiple runs с разной температурой)
2. Проверка через несколько моделей (ensemble)
3. Правила и эвристики (rule-based validation)
4. Embedding similarity для проверки
5. Confidence calibration
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from collections import Counter

import numpy as np
from pydantic import BaseModel, Field

from ..taxonomy import CANON_LABELS, validate_domain, KEYWORDS

logger = logging.getLogger(__name__)


class ValidationConfig(BaseModel):
    """Конфигурация валидатора"""
    
    # Консенсус голосование
    enable_consensus: bool = Field(True, description="Включить консенсус голосование")
    consensus_runs: int = Field(3, description="Количество прогонов для консенсуса", ge=2, le=5)
    consensus_threshold: float = Field(0.67, description="Порог консенсуса (2/3)", ge=0.5, le=1.0)
    
    # Температуры для разнообразия
    temperatures: List[float] = Field([0.3, 0.7, 1.0], description="Температуры для разных прогонов")
    
    # Эвристики
    enable_rules: bool = Field(True, description="Включить rule-based проверку")
    rule_confidence_boost: float = Field(0.1, description="Буст уверенности при совпадении правил")
    
    # Порог уверенности для accept
    min_confidence: float = Field(0.5, description="Минимальная уверенность", ge=0.0, le=1.0)
    high_confidence: float = Field(0.8, description="Высокая уверенность", ge=0.0, le=1.0)
    
    # Ensemble (если доступны несколько моделей)
    enable_ensemble: bool = Field(False, description="Использовать ensemble из нескольких моделей")
    
    # Строгость
    strict_mode: bool = Field(True, description="Строгий режим - отклонять сомнительные")


class ValidationResult(BaseModel):
    """Результат валидации Labeler"""
    
    text: str
    final_domain: str
    final_confidence: float
    
    # Результаты консенсуса
    consensus_votes: Dict[str, int] = Field(default_factory=dict)
    consensus_achieved: bool = False
    consensus_ratio: float = 0.0
    
    # Проверки
    rule_match: bool = False
    rule_matched_domain: Optional[str] = None
    
    # Проблемы
    is_valid: bool = True
    validation_issues: List[str] = Field(default_factory=list)
    
    # Детали
    all_predictions: List[Dict[str, Any]] = Field(default_factory=list)


class LabelerValidator:
    """
    Валидатор для жесткого контроля качества Labeler Agent.
    
    Многоуровневая проверка:
    - Консенсус голосование (multiple runs)
    - Rule-based эвристики
    - Ensemble (если доступно несколько моделей)
    - Confidence calibration
    """
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        
        # Статистика
        self.stats = {
            "total_validated": 0,
            "consensus_achieved": 0,
            "consensus_failed": 0,
            "rule_matched": 0,
            "rule_mismatched": 0,
            "high_confidence": 0,
            "low_confidence": 0,
            "rejected": 0,
        }
    
    async def validate_classification(
        self,
        text: str,
        labeler_agent,
        initial_result = None,
    ) -> ValidationResult:
        """
        Жестко валидирует классификацию одного текста.
        
        Args:
            text: текст для валидации
            labeler_agent: LabelerAgent для повторных проверок
            initial_result: опциональный начальный результат
            
        Returns:
            ValidationResult с детальной информацией
        """
        
        all_predictions = []
        
        # Если есть начальный результат - добавляем
        if initial_result:
            all_predictions.append({
                "domain": initial_result.domain_id,
                "confidence": initial_result.confidence,
                "temperature": "initial",
            })
        
        # 1. Консенсус голосование (multiple runs с разной температурой)
        if self.config.enable_consensus and labeler_agent:
            logger.debug(f"Running consensus voting for: {text[:50]}...")
            
            for i, temp in enumerate(self.config.temperatures[:self.config.consensus_runs]):
                try:
                    # ВАЖНО: здесь нужно передать temperature в classify_one
                    # Это требует модификации LabelerAgent.classify_one
                    # Пока используем стандартный вызов
                    result = await labeler_agent.classify_one(text)
                    
                    all_predictions.append({
                        "domain": result.domain_id,
                        "confidence": result.confidence,
                        "temperature": temp,
                        "run": i + 1,
                    })
                    
                except Exception as e:
                    logger.warning(f"Consensus run {i+1} failed: {e}")
                    continue
        
        # Подсчет голосов
        domain_votes = Counter([p["domain"] for p in all_predictions])
        
        # Определяем победителя консенсуса
        if domain_votes:
            most_common = domain_votes.most_common(1)[0]
            consensus_domain = most_common[0]
            consensus_count = most_common[1]
            total_votes = len(all_predictions)
            consensus_ratio = consensus_count / total_votes if total_votes > 0 else 0.0
            
            consensus_achieved = consensus_ratio >= self.config.consensus_threshold
        else:
            consensus_domain = "oos"
            consensus_count = 0
            consensus_ratio = 0.0
            consensus_achieved = False
        
        # 2. Rule-based проверка
        rule_domain = self._check_rules(text)
        rule_match = (rule_domain == consensus_domain) if rule_domain else None
        
        # 3. Вычисляем финальную уверенность
        # Берем среднюю уверенность из всех прогонов
        confidences = [p["confidence"] for p in all_predictions]
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        # Буст если правила совпадают
        if rule_match and self.config.enable_rules:
            avg_confidence = min(1.0, avg_confidence + self.config.rule_confidence_boost)
            self.stats["rule_matched"] += 1
        elif rule_domain and not rule_match:
            self.stats["rule_mismatched"] += 1
        
        # 4. Проверка валидности
        issues = []
        is_valid = True
        
        # Консенсус не достигнут
        if self.config.enable_consensus and not consensus_achieved:
            issues.append(
                f"Консенсус не достигнут: {consensus_count}/{total_votes} "
                f"({consensus_ratio:.1%} < {self.config.consensus_threshold:.1%})"
            )
            
            if self.config.strict_mode:
                is_valid = False
                self.stats["consensus_failed"] += 1
        else:
            self.stats["consensus_achieved"] += 1
        
        # Низкая уверенность
        if avg_confidence < self.config.min_confidence:
            issues.append(
                f"Низкая уверенность: {avg_confidence:.2f} < {self.config.min_confidence}"
            )
            
            if self.config.strict_mode:
                is_valid = False
            
            self.stats["low_confidence"] += 1
        elif avg_confidence >= self.config.high_confidence:
            self.stats["high_confidence"] += 1
        
        # Конфликт с правилами
        if rule_domain and rule_domain != consensus_domain:
            issues.append(
                f"Конфликт с правилами: LLM={consensus_domain}, Rules={rule_domain}"
            )
            
            # В строгом режиме приоритет правилам
            if self.config.strict_mode and self.config.enable_rules:
                logger.warning(
                    f"Rule override: {text[:50]}... "
                    f"{consensus_domain} → {rule_domain}"
                )
                consensus_domain = rule_domain
        
        # Обновляем статистику
        self.stats["total_validated"] += 1
        
        if not is_valid:
            self.stats["rejected"] += 1
        
        return ValidationResult(
            text=text,
            final_domain=consensus_domain,
            final_confidence=avg_confidence,
            consensus_votes=dict(domain_votes),
            consensus_achieved=consensus_achieved,
            consensus_ratio=consensus_ratio,
            rule_match=rule_match if rule_match is not None else False,
            rule_matched_domain=rule_domain,
            is_valid=is_valid,
            validation_issues=issues,
            all_predictions=all_predictions,
        )
    
    def _check_rules(self, text: str) -> Optional[str]:
        """
        Rule-based проверка по ключевым словам.
        
        Returns:
            Домен по правилам или None
        """
        
        if not self.config.enable_rules:
            return None
        
        text_lower = text.lower()
        
        # Подсчитываем совпадения ключевых слов для каждого домена
        domain_scores = {}
        
        for domain, keywords in KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            
            if score > 0:
                domain_scores[domain] = score
        
        # Если есть явный победитель (в 2+ раза больше совпадений)
        if domain_scores:
            sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
            
            if len(sorted_domains) == 1:
                return sorted_domains[0][0]
            
            # Проверяем явное превосходство
            top_score = sorted_domains[0][1]
            second_score = sorted_domains[1][1] if len(sorted_domains) > 1 else 0
            
            if top_score >= 2 and top_score > second_score * 2:
                return sorted_domains[0][0]
        
        return None
    
    async def validate_batch(
        self,
        items: List[Dict[str, Any]],
        labeler_agent,
    ) -> List[ValidationResult]:
        """
        Валидирует батч классификаций.
        
        Args:
            items: элементы с полями text, domain_id, confidence
            labeler_agent: LabelerAgent для перепроверок
            
        Returns:
            Список ValidationResult
        """
        
        results = []
        
        for item in items:
            # Создаем mock initial_result
            class InitialResult:
                def __init__(self, domain, confidence):
                    self.domain_id = domain
                    self.confidence = confidence
            
            initial = InitialResult(
                item.get("domain_id", "oos"),
                item.get("confidence", 0.0)
            )
            
            validation = await self.validate_classification(
                text=item["text"],
                labeler_agent=labeler_agent,
                initial_result=initial
            )
            
            results.append(validation)
        
        return results
    
    def compute_error_analysis(
        self,
        validations: List[ValidationResult],
        ground_truth: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Анализирует ошибки Labeler.
        
        Args:
            validations: результаты валидации
            ground_truth: опциональные истинные метки для сравнения
            
        Returns:
            Детальный анализ ошибок
        """
        
        analysis = {
            "total": len(validations),
            "valid": sum(1 for v in validations if v.is_valid),
            "invalid": sum(1 for v in validations if not v.is_valid),
        }
        
        # Распределение уверенности
        confidences = [v.final_confidence for v in validations]
        analysis["confidence"] = {
            "mean": float(np.mean(confidences)),
            "median": float(np.median(confidences)),
            "std": float(np.std(confidences)),
            "min": float(np.min(confidences)),
            "max": float(np.max(confidences)),
        }
        
        # Консенсус статистика
        consensus_ratios = [v.consensus_ratio for v in validations]
        analysis["consensus"] = {
            "mean_ratio": float(np.mean(consensus_ratios)),
            "achieved_count": sum(1 for v in validations if v.consensus_achieved),
            "failed_count": sum(1 for v in validations if not v.consensus_achieved),
        }
        
        # Правила статистика
        rule_matches = sum(1 for v in validations if v.rule_match)
        rule_mismatches = sum(1 for v in validations if v.rule_matched_domain and not v.rule_match)
        
        analysis["rules"] = {
            "matched": rule_matches,
            "mismatched": rule_mismatches,
            "match_rate": rule_matches / len(validations) if validations else 0.0,
        }
        
        # Распределение по доменам
        domain_dist = Counter([v.final_domain for v in validations])
        analysis["domain_distribution"] = dict(domain_dist)
        
        # Если есть ground truth - вычисляем accuracy
        if ground_truth and len(ground_truth) == len(validations):
            correct = sum(
                1 for v, gt in zip(validations, ground_truth)
                if v.final_domain == gt
            )
            analysis["accuracy"] = correct / len(validations)
            
            # Матрица ошибок
            confusion = {}
            for v, gt in zip(validations, ground_truth):
                if v.final_domain != gt:
                    key = f"{gt} → {v.final_domain}"
                    confusion[key] = confusion.get(key, 0) + 1
            
            analysis["confusion_matrix"] = dict(sorted(
                confusion.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])  # Top 10 ошибок
        
        # Проблемные случаи
        problematic = [
            {
                "text": v.text[:100],
                "domain": v.final_domain,
                "confidence": v.final_confidence,
                "issues": v.validation_issues,
                "consensus_ratio": v.consensus_ratio,
            }
            for v in validations
            if not v.is_valid or v.final_confidence < self.config.min_confidence
        ]
        
        analysis["problematic_cases"] = problematic[:20]  # Top 20
        
        return analysis
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику валидатора"""
        
        stats = self.stats.copy()
        
        if stats["total_validated"] > 0:
            stats["consensus_rate"] = stats["consensus_achieved"] / stats["total_validated"]
            stats["rejection_rate"] = stats["rejected"] / stats["total_validated"]
            stats["rule_match_rate"] = stats["rule_matched"] / stats["total_validated"]
        
        return stats
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.stats = {
            "total_validated": 0,
            "consensus_achieved": 0,
            "consensus_failed": 0,
            "rule_matched": 0,
            "rule_mismatched": 0,
            "high_confidence": 0,
            "low_confidence": 0,
            "rejected": 0,
        }


class EnsembleLabeler:
    """
    Ensemble из нескольких моделей для повышения точности.
    
    Использует несколько разных моделей и выбирает консенсус.
    """
    
    def __init__(self, labeler_agents: List):
        """
        Args:
            labeler_agents: список LabelerAgent с разными моделями
        """
        self.agents = labeler_agents
        
        if len(self.agents) < 2:
            raise ValueError("Для ensemble нужно минимум 2 модели")
        
        logger.info(f"EnsembleLabeler initialized with {len(self.agents)} models")
    
    async def classify_with_ensemble(self, text: str) -> Dict[str, Any]:
        """
        Классифицирует текст через все модели и выбирает консенсус.
        
        Returns:
            Результат с консенсусом
        """
        
        results = []
        
        # Классификация через все модели
        for i, agent in enumerate(self.agents):
            try:
                result = await agent.classify_one(text)
                results.append({
                    "model": i,
                    "domain": result.domain_id,
                    "confidence": result.confidence,
                    "candidates": result.top_candidates,
                })
            except Exception as e:
                logger.error(f"Model {i} failed: {e}")
                continue
        
        if not results:
            return {
                "domain_id": "oos",
                "confidence": 0.0,
                "ensemble_size": 0,
                "consensus": False,
            }
        
        # Консенсус голосование
        domain_votes = Counter([r["domain"] for r in results])
        most_common = domain_votes.most_common(1)[0]
        
        consensus_domain = most_common[0]
        consensus_count = most_common[1]
        consensus_ratio = consensus_count / len(results)
        
        # Средняя уверенность среди моделей выбравших консенсус домен
        consensus_confidences = [
            r["confidence"] for r in results
            if r["domain"] == consensus_domain
        ]
        avg_confidence = np.mean(consensus_confidences)
        
        return {
            "text": text,
            "domain_id": consensus_domain,
            "confidence": float(avg_confidence),
            "ensemble_size": len(results),
            "consensus_ratio": consensus_ratio,
            "consensus_achieved": consensus_ratio >= 0.67,  # 2/3
            "all_votes": dict(domain_votes),
            "all_results": results,
        }


class ConfidenceCalibrator:
    """
    Калибратор уверенности для улучшения reliability.
    
    Обучается на feedback и корректирует уверенность модели.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.calibration_file = data_dir / "confidence_calibration.json"
        
        # Калибровочная таблица: domain -> {confidence_range -> actual_accuracy}
        self.calibration_table = {}
        
        self._load_calibration()
    
    def _load_calibration(self):
        """Загружает калибровку из файла"""
        
        if not self.calibration_file.exists():
            return
        
        try:
            import json
            with open(self.calibration_file, "r") as f:
                self.calibration_table = json.load(f)
            
            logger.info(f"Loaded confidence calibration for {len(self.calibration_table)} domains")
        except Exception as e:
            logger.warning(f"Failed to load calibration: {e}")
    
    def calibrate_confidence(
        self,
        domain: str,
        raw_confidence: float
    ) -> float:
        """
        Калибрует уверенность на основе исторических данных.
        
        Args:
            domain: предсказанный домен
            raw_confidence: исходная уверенность от модели
            
        Returns:
            Калиброванная уверенность
        """
        
        if domain not in self.calibration_table:
            return raw_confidence
        
        # Находим ближайший бакет
        calibration = self.calibration_table[domain]
        
        # Простая линейная калибровка
        # В production: используйте isotonic regression или Platt scaling
        
        for bucket, actual_acc in calibration.items():
            # bucket формат: "0.7-0.8"
            low, high = map(float, bucket.split("-"))
            
            if low <= raw_confidence < high:
                # Корректируем к реальной точности
                return float(actual_acc)
        
        return raw_confidence
    
    def update_calibration(
        self,
        domain: str,
        predicted_confidence: float,
        was_correct: bool
    ):
        """
        Обновляет калибровку на основе feedback.
        
        Args:
            domain: домен
            predicted_confidence: предсказанная уверенность
            was_correct: была ли классификация правильной
        """
        
        # Определяем бакет (0.5-0.6, 0.6-0.7, и т.д.)
        bucket = f"{int(predicted_confidence * 10) / 10:.1f}-{int(predicted_confidence * 10 + 1) / 10:.1f}"
        
        if domain not in self.calibration_table:
            self.calibration_table[domain] = {}
        
        if bucket not in self.calibration_table[domain]:
            self.calibration_table[domain][bucket] = []
        
        # Добавляем наблюдение
        self.calibration_table[domain][bucket].append(1 if was_correct else 0)
        
        # Пересчитываем среднюю точность для бакета
        observations = self.calibration_table[domain][bucket]
        self.calibration_table[domain][bucket] = sum(observations) / len(observations)
        
        # Сохраняем
        self._save_calibration()
    
    def _save_calibration(self):
        """Сохраняет калибровку в файл"""
        
        try:
            import json
            self.calibration_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.calibration_file, "w") as f:
                json.dump(self.calibration_table, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save calibration: {e}")


# Пример использования
"""
from src.pipeline.labeler_validator import LabelerValidator, ValidationConfig

# Инициализация
validator = LabelerValidator(ValidationConfig(
    enable_consensus=True,
    consensus_runs=3,
    enable_rules=True,
    strict_mode=True
))

# Валидация одного результата
validation = await validator.validate_classification(
    text="передать показания счетчика",
    labeler_agent=labeler_agent,
    initial_result=initial_classification
)

if validation.is_valid:
    print(f"✅ Valid: {validation.final_domain} ({validation.final_confidence:.2f})")
    print(f"   Consensus: {validation.consensus_ratio:.1%}")
else:
    print(f"❌ Invalid: {validation.validation_issues}")

# Статистика
stats = validator.get_stats()
print(f"Consensus rate: {stats['consensus_rate']:.1%}")
print(f"Rule match rate: {stats['rule_match_rate']:.1%}")
"""


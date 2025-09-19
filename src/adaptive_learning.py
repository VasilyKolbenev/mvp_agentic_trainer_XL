from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


class FeedbackLearner:
    """
    Система активного обучения на основе пользовательских исправлений.
    Динамически обновляет few-shot примеры и улучшает качество классификации.
    """
    
    def __init__(self, data_dir: Path, max_examples_per_domain: int = 3):
        self.data_dir = data_dir
        self.feedback_file = data_dir / "feedback.jsonl"
        self.dynamic_examples_file = data_dir / "dynamic_fewshot.json"
        self.max_examples_per_domain = max_examples_per_domain
        
        # Создаем файлы если их нет
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
    def log_feedback(self, 
                    text: str, 
                    predicted_domain: str, 
                    corrected_domain: str, 
                    confidence: float,
                    user_id: Optional[str] = None) -> None:
        """Записывает feedback от пользователя"""
        
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "text": text,
            "predicted_domain": predicted_domain,
            "corrected_domain": corrected_domain,
            "confidence": confidence,
            "user_id": user_id,
            "was_correction": predicted_domain != corrected_domain
        }
        
        # Добавляем в файл
        with open(self.feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
            
        logger.info(f"Logged feedback: {text[:50]}... -> {corrected_domain}")
        
        # Обновляем динамические примеры если это исправление
        if feedback_entry["was_correction"]:
            self._update_dynamic_examples()
    
    def _update_dynamic_examples(self) -> None:
        """Обновляет динамические few-shot примеры на основе накопленного feedback"""
        
        if not self.feedback_file.exists():
            return
            
        # Загружаем весь feedback
        feedback_data = []
        with open(self.feedback_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    feedback_data.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        if not feedback_data:
            return
            
        # Фильтруем только исправления за последние 30 дней
        recent_cutoff = datetime.now() - timedelta(days=30)
        recent_corrections = []
        
        for entry in feedback_data:
            if not entry.get("was_correction", False):
                continue
                
            try:
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if entry_time > recent_cutoff:
                    recent_corrections.append(entry)
            except (ValueError, KeyError):
                continue
        
        # Группируем по доменам и выбираем лучшие примеры
        domain_examples = defaultdict(list)
        
        for correction in recent_corrections:
            domain = correction["corrected_domain"]
            text = correction["text"]
            
            # Добавляем пример если он качественный
            if self._is_good_example(text, domain, recent_corrections):
                domain_examples[domain].append({
                    "text": text,
                    "domain": domain,
                    "confidence": 0.95,  # Высокая уверенность для исправлений
                    "source": "user_feedback"
                })
        
        # Ограничиваем количество примеров на домен
        for domain in domain_examples:
            domain_examples[domain] = domain_examples[domain][:self.max_examples_per_domain]
        
        # Сохраняем динамические примеры
        dynamic_examples = {
            "updated_at": datetime.now().isoformat(),
            "examples_by_domain": dict(domain_examples),
            "total_corrections": len(recent_corrections)
        }
        
        with open(self.dynamic_examples_file, "w", encoding="utf-8") as f:
            json.dump(dynamic_examples, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Updated dynamic examples: {len(domain_examples)} domains, "
                   f"{sum(len(examples) for examples in domain_examples.values())} examples")
    
    def _is_good_example(self, text: str, domain: str, all_corrections: List[Dict]) -> bool:
        """Определяет, является ли пример качественным для few-shot"""
        
        # Фильтры качества
        if len(text.strip()) < 5:  # Слишком короткий
            return False
            
        if len(text) > 200:  # Слишком длинный
            return False
            
        # Проверяем, что этот текст не исправлялся в разные стороны
        text_corrections = [c for c in all_corrections if c["text"] == text]
        if len(text_corrections) > 1:
            # Если есть противоречивые исправления - пропускаем
            domains = set(c["corrected_domain"] for c in text_corrections)
            if len(domains) > 1:
                return False
        
        return True
    
    def get_dynamic_fewshot(self) -> str:
        """Возвращает динамически сгенерированные few-shot примеры"""
        
        if not self.dynamic_examples_file.exists():
            return ""
            
        try:
            with open(self.dynamic_examples_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return ""
        
        examples_by_domain = data.get("examples_by_domain", {})
        if not examples_by_domain:
            return ""
        
        # Формируем few-shot примеры
        fewshot_parts = []
        example_num = 1
        
        for domain, examples in examples_by_domain.items():
            for example in examples:
                fewshot_parts.append(f"ПРИМЕР {example_num}")
                fewshot_parts.append("ТЕКСТ:")
                fewshot_parts.append(f'"{example["text"]}"')
                fewshot_parts.append("ОТВЕТ:")
                fewshot_parts.append(f'{{"domain_id":"{domain}", "confidence":{example["confidence"]:.2f}}}')
                fewshot_parts.append("")
                example_num += 1
        
        return "\n".join(fewshot_parts)
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по feedback"""
        
        if not self.feedback_file.exists():
            return {"total_feedback": 0, "corrections": 0, "domains": {}}
            
        feedback_data = []
        with open(self.feedback_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    feedback_data.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        corrections = [f for f in feedback_data if f.get("was_correction", False)]
        
        # Статистика по доменам
        predicted_domains = Counter(f["predicted_domain"] for f in corrections)
        corrected_domains = Counter(f["corrected_domain"] for f in corrections)
        
        # Матрица ошибок (топ проблемных переходов)
        error_matrix = Counter()
        for correction in corrections:
            error_matrix[(correction["predicted_domain"], correction["corrected_domain"])] += 1
        
        return {
            "total_feedback": len(feedback_data),
            "corrections": len(corrections),
            "correction_rate": len(corrections) / len(feedback_data) if feedback_data else 0,
            "predicted_domains": dict(predicted_domains),
            "corrected_domains": dict(corrected_domains),
            "top_errors": dict(error_matrix.most_common(10)),
            "recent_corrections": len([c for c in corrections 
                                     if datetime.fromisoformat(c["timestamp"]) > datetime.now() - timedelta(days=7)])
        }


class PromptOptimizer:
    """Оптимизирует промпты на основе накопленной статистики"""
    
    def __init__(self, feedback_learner: FeedbackLearner):
        self.feedback_learner = feedback_learner
    
    def get_optimized_system_prompt(self, base_prompt: str) -> str:
        """Возвращает оптимизированный системный промпт"""
        
        stats = self.feedback_learner.get_feedback_stats()
        if stats["corrections"] < 10:  # Недостаточно данных
            return base_prompt
            
        # Добавляем предупреждения о частых ошибках
        error_warnings = []
        for (predicted, corrected), count in stats["top_errors"].items():
            if count >= 3:
                error_warnings.append(
                    f"⚠️ Частая ошибка: НЕ путай '{predicted}' с '{corrected}'"
                )
        
        if error_warnings:
            warnings_text = "\n".join(error_warnings)
            optimized_prompt = f"{base_prompt}\n\nЧАСТЫЕ ОШИБКИ (избегай):\n{warnings_text}\n"
            return optimized_prompt
            
        return base_prompt
    
    def should_retrain(self) -> bool:
        """Определяет, нужно ли переобучение на основе статистики"""
        
        stats = self.feedback_learner.get_feedback_stats()
        
        # Критерии для переобучения
        if stats["recent_corrections"] > 20:  # Много недавних исправлений
            return True
            
        if stats["correction_rate"] > 0.3:  # Высокий процент исправлений
            return True
            
        return False

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class LLMCache:
    """
    Кэш для LLM ответов с TTL и персистентностью.
    Экономит токены на повторяющихся запросах.
    """
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir / "llm_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        
        # Файлы кэша
        self.classification_cache_file = self.cache_dir / "classification_cache.jsonl"
        self.augmentation_cache_file = self.cache_dir / "augmentation_cache.jsonl"
        
        # In-memory кэши для быстрого доступа
        self._classification_cache = {}
        self._augmentation_cache = {}
        
        # Загружаем кэш при инициализации
        self._load_caches()
    
    def _generate_key(self, text: str, system_prompt: str, fewshot: str = "") -> str:
        """Генерирует ключ кэша на основе входных данных"""
        combined = f"{text}|{system_prompt}|{fewshot}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    def _is_expired(self, timestamp: str) -> bool:
        """Проверяет, истек ли TTL записи"""
        try:
            cached_time = datetime.fromisoformat(timestamp)
            return datetime.now() - cached_time > timedelta(hours=self.ttl_hours)
        except (ValueError, TypeError):
            return True
    
    def _load_caches(self) -> None:
        """Загружает кэши из файлов"""
        # Загружаем кэш классификации
        if self.classification_cache_file.exists():
            try:
                with open(self.classification_cache_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if not self._is_expired(entry.get("timestamp", "")):
                                self._classification_cache[entry["key"]] = entry
                        except json.JSONDecodeError:
                            continue
                logger.info(f"Loaded {len(self._classification_cache)} classification cache entries")
            except Exception as e:
                logger.warning(f"Failed to load classification cache: {e}")
        
        # Загружаем кэш аугментации
        if self.augmentation_cache_file.exists():
            try:
                with open(self.augmentation_cache_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if not self._is_expired(entry.get("timestamp", "")):
                                self._augmentation_cache[entry["key"]] = entry
                        except json.JSONDecodeError:
                            continue
                logger.info(f"Loaded {len(self._augmentation_cache)} augmentation cache entries")
            except Exception as e:
                logger.warning(f"Failed to load augmentation cache: {e}")
    
    def _save_cache_entry(self, file_path: Path, entry: Dict[str, Any]) -> None:
        """Сохраняет запись в файл кэша"""
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to save cache entry: {e}")
    
    def get_classification(self, text: str, system_prompt: str, fewshot: str) -> Optional[Dict[str, Any]]:
        """Получает результат классификации из кэша"""
        key = self._generate_key(text, system_prompt, fewshot)
        
        if key in self._classification_cache:
            entry = self._classification_cache[key]
            if not self._is_expired(entry.get("timestamp", "")):
                logger.debug(f"Cache hit for classification: {text[:50]}...")
                return entry["result"]
            else:
                # Удаляем просроченную запись
                del self._classification_cache[key]
        
        return None
    
    def set_classification(self, text: str, system_prompt: str, fewshot: str, result: Dict[str, Any]) -> None:
        """Сохраняет результат классификации в кэш"""
        key = self._generate_key(text, system_prompt, fewshot)
        
        entry = {
            "key": key,
            "text": text,
            "system_prompt_hash": hashlib.md5(system_prompt.encode()).hexdigest()[:8],
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        self._classification_cache[key] = entry
        self._save_cache_entry(self.classification_cache_file, entry)
        logger.debug(f"Cached classification result for: {text[:50]}...")
    
    def get_augmentation(self, text: str, domain: str, system_prompt: str) -> Optional[list]:
        """Получает результат аугментации из кэша"""
        key = self._generate_key(f"{text}|{domain}", system_prompt)
        
        if key in self._augmentation_cache:
            entry = self._augmentation_cache[key]
            if not self._is_expired(entry.get("timestamp", "")):
                logger.debug(f"Cache hit for augmentation: {text[:50]}...")
                return entry["result"]
            else:
                del self._augmentation_cache[key]
        
        return None
    
    def set_augmentation(self, text: str, domain: str, system_prompt: str, result: list) -> None:
        """Сохраняет результат аугментации в кэш"""
        key = self._generate_key(f"{text}|{domain}", system_prompt)
        
        entry = {
            "key": key,
            "text": text,
            "domain": domain,
            "system_prompt_hash": hashlib.md5(system_prompt.encode()).hexdigest()[:8],
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        self._augmentation_cache[key] = entry
        self._save_cache_entry(self.augmentation_cache_file, entry)
        logger.debug(f"Cached augmentation result for: {text[:50]}...")
    
    def cleanup_expired(self) -> int:
        """Очищает просроченные записи из кэша"""
        cleaned_count = 0
        
        # Очищаем кэш классификации
        expired_keys = []
        for key, entry in self._classification_cache.items():
            if self._is_expired(entry.get("timestamp", "")):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._classification_cache[key]
            cleaned_count += 1
        
        # Очищаем кэш аугментации
        expired_keys = []
        for key, entry in self._augmentation_cache.items():
            if self._is_expired(entry.get("timestamp", "")):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._augmentation_cache[key]
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired cache entries")
        
        return cleaned_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кэша"""
        return {
            "classification_entries": len(self._classification_cache),
            "augmentation_entries": len(self._augmentation_cache),
            "total_entries": len(self._classification_cache) + len(self._augmentation_cache),
            "ttl_hours": self.ttl_hours
        }


# Глобальный экземпляр кэша (будет инициализирован в bot.py)
llm_cache: Optional[LLMCache] = None


def get_cache() -> Optional[LLMCache]:
    """Возвращает глобальный экземпляр кэша"""
    return llm_cache


def init_cache(cache_dir: Path, ttl_hours: int = 24) -> LLMCache:
    """Инициализирует глобальный кэш"""
    global llm_cache
    llm_cache = LLMCache(cache_dir, ttl_hours)
    return llm_cache

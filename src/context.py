from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class UserContext:
    """
    Контекст пользователя для улучшения классификации на основе истории.
    """
    
    def __init__(self, user_id: str, max_history: int = 10):
        self.user_id = user_id
        self.max_history = max_history
        self.message_history: deque = deque(maxlen=max_history)
        self.domain_preferences: Dict[str, float] = {}
        self.last_activity = datetime.now()
        
    def add_message(self, text: str, predicted_domain: str, 
                   corrected_domain: Optional[str] = None, confidence: float = 0.0) -> None:
        """Добавляет сообщение в историю пользователя"""
        
        message_entry = {
            "timestamp": datetime.now().isoformat(),
            "text": text,
            "predicted_domain": predicted_domain,
            "corrected_domain": corrected_domain or predicted_domain,
            "confidence": confidence,
            "was_corrected": corrected_domain is not None and corrected_domain != predicted_domain
        }
        
        self.message_history.append(message_entry)
        self.last_activity = datetime.now()
        
        # Обновляем предпочтения доменов
        final_domain = corrected_domain or predicted_domain
        if final_domain in self.domain_preferences:
            self.domain_preferences[final_domain] += 1.0
        else:
            self.domain_preferences[final_domain] = 1.0
            
        # Нормализуем предпочтения
        total = sum(self.domain_preferences.values())
        if total > 0:
            for domain in self.domain_preferences:
                self.domain_preferences[domain] /= total
    
    def get_context_for_classification(self) -> str:
        """Возвращает контекст для улучшения классификации"""
        
        if not self.message_history:
            return ""
        
        # Последние 3 сообщения для контекста
        recent_messages = list(self.message_history)[-3:]
        
        context_parts = ["КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ:"]
        
        # История сообщений
        for i, msg in enumerate(recent_messages[:-1]):  # Исключаем текущее сообщение
            context_parts.append(
                f"Сообщение {i+1}: \"{msg['text'][:100]}\" → {msg['corrected_domain']}"
            )
        
        # Предпочтения доменов
        if self.domain_preferences:
            top_domains = sorted(self.domain_preferences.items(), 
                               key=lambda x: x[1], reverse=True)[:3]
            context_parts.append("Частые домены пользователя: " + 
                               ", ".join(f"{domain} ({prob:.1%})" for domain, prob in top_domains))
        
        return "\n".join(context_parts) + "\n"
    
    def get_preferred_domains(self, top_k: int = 5) -> List[str]:
        """Возвращает предпочтительные домены для пользователя"""
        
        if not self.domain_preferences:
            return []
            
        sorted_domains = sorted(self.domain_preferences.items(), 
                              key=lambda x: x[1], reverse=True)
        return [domain for domain, _ in sorted_domains[:top_k]]
    
    def is_active(self, hours: int = 24) -> bool:
        """Проверяет, активен ли пользователь в последние N часов"""
        return datetime.now() - self.last_activity < timedelta(hours=hours)
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализует контекст в словарь"""
        return {
            "user_id": self.user_id,
            "message_history": list(self.message_history),
            "domain_preferences": self.domain_preferences,
            "last_activity": self.last_activity.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserContext':
        """Десериализует контекст из словаря"""
        context = cls(data["user_id"])
        
        # Восстанавливаем историю
        for msg in data.get("message_history", []):
            context.message_history.append(msg)
        
        context.domain_preferences = data.get("domain_preferences", {})
        
        try:
            context.last_activity = datetime.fromisoformat(data["last_activity"])
        except (ValueError, KeyError):
            context.last_activity = datetime.now()
        
        return context


class ContextManager:
    """
    Менеджер контекстов пользователей с персистентностью.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.contexts_file = data_dir / "user_contexts.jsonl"
        self.contexts: Dict[str, UserContext] = {}
        
        # Создаем директорию если нет
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Загружаем существующие контексты
        self._load_contexts()
    
    def _load_contexts(self) -> None:
        """Загружает контексты из файла"""
        
        if not self.contexts_file.exists():
            return
        
        try:
            with open(self.contexts_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        context = UserContext.from_dict(data)
                        
                        # Загружаем только активные контексты (последние 7 дней)
                        if context.is_active(hours=24 * 7):
                            self.contexts[context.user_id] = context
                            
                    except json.JSONDecodeError:
                        continue
                        
            logger.info(f"Loaded {len(self.contexts)} user contexts")
            
        except Exception as e:
            logger.warning(f"Failed to load user contexts: {e}")
    
    def _save_context(self, context: UserContext) -> None:
        """Сохраняет контекст в файл"""
        
        try:
            with open(self.contexts_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(context.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to save context for user {context.user_id}: {e}")
    
    def get_context(self, user_id: str) -> UserContext:
        """Получает или создает контекст пользователя"""
        
        if user_id not in self.contexts:
            self.contexts[user_id] = UserContext(user_id)
        
        return self.contexts[user_id]
    
    def update_context(self, user_id: str, text: str, predicted_domain: str,
                      corrected_domain: Optional[str] = None, confidence: float = 0.0) -> None:
        """Обновляет контекст пользователя"""
        
        context = self.get_context(user_id)
        context.add_message(text, predicted_domain, corrected_domain, confidence)
        
        # Сохраняем обновленный контекст
        self._save_context(context)
    
    def get_classification_context(self, user_id: str) -> str:
        """Получает контекст для улучшения классификации"""
        
        if user_id not in self.contexts:
            return ""
        
        return self.contexts[user_id].get_context_for_classification()
    
    def get_preferred_domains(self, user_id: str, top_k: int = 5) -> List[str]:
        """Получает предпочтительные домены пользователя"""
        
        if user_id not in self.contexts:
            return []
        
        return self.contexts[user_id].get_preferred_domains(top_k)
    
    def cleanup_inactive_contexts(self, hours: int = 24 * 7) -> int:
        """Очищает неактивные контексты"""
        
        inactive_users = []
        for user_id, context in self.contexts.items():
            if not context.is_active(hours):
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            del self.contexts[user_id]
        
        logger.info(f"Cleaned up {len(inactive_users)} inactive user contexts")
        return len(inactive_users)
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику контекстов"""
        
        if not self.contexts:
            return {"total_users": 0, "active_users": 0, "total_messages": 0}
        
        active_users = sum(1 for ctx in self.contexts.values() if ctx.is_active(hours=24))
        total_messages = sum(len(ctx.message_history) for ctx in self.contexts.values())
        
        # Топ доменов по всем пользователям
        all_preferences = {}
        for ctx in self.contexts.values():
            for domain, count in ctx.domain_preferences.items():
                all_preferences[domain] = all_preferences.get(domain, 0) + count
        
        top_domains = sorted(all_preferences.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_users": len(self.contexts),
            "active_users": active_users,
            "total_messages": total_messages,
            "top_domains": dict(top_domains)
        }

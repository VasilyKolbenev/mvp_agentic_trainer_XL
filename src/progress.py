from __future__ import annotations

import asyncio
import logging
from typing import Optional, Callable, Any
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Отслеживает прогресс длительных операций и обновляет сообщения в Telegram.
    """
    
    def __init__(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE, 
                 total_items: int, operation_name: str = "Обработка"):
        self.update = update
        self.ctx = ctx
        self.total_items = total_items
        self.operation_name = operation_name
        self.processed_items = 0
        self.start_time = datetime.now()
        self.last_update_time = datetime.now()
        self.message_id: Optional[int] = None
        self.update_interval = 5  # секунд между обновлениями
        
    async def start(self) -> None:
        """Отправляет начальное сообщение о прогрессе"""
        text = f"🔄 {self.operation_name}: 0/{self.total_items} (0%)"
        message = await self.update.message.reply_text(text)
        self.message_id = message.message_id
        
    async def update_progress(self, processed: int, status_text: str = "") -> None:
        """Обновляет прогресс"""
        self.processed_items = processed
        current_time = datetime.now()
        
        # Обновляем сообщение не чаще чем раз в N секунд
        if (current_time - self.last_update_time).total_seconds() < self.update_interval:
            return
            
        self.last_update_time = current_time
        
        # Вычисляем прогресс
        progress_percent = (processed / self.total_items * 100) if self.total_items > 0 else 0
        elapsed = current_time - self.start_time
        
        # ETA расчет
        if processed > 0:
            avg_time_per_item = elapsed.total_seconds() / processed
            remaining_items = self.total_items - processed
            eta_seconds = remaining_items * avg_time_per_item
            eta_text = self._format_time(eta_seconds)
        else:
            eta_text = "неизвестно"
        
        # Прогресс-бар
        bar_length = 20
        filled_length = int(bar_length * progress_percent / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        text_lines = [
            f"🔄 {self.operation_name}",
            f"📊 {processed}/{self.total_items} ({progress_percent:.1f}%)",
            f"⏱️ Прошло: {self._format_time(elapsed.total_seconds())}",
            f"🕐 Осталось: ~{eta_text}",
            f"[{bar}]"
        ]
        
        if status_text:
            text_lines.append(f"💬 {status_text}")
        
        text = "\n".join(text_lines)
        
        try:
            await self.ctx.bot.edit_message_text(
                chat_id=self.update.effective_chat.id,
                message_id=self.message_id,
                text=text
            )
        except Exception as e:
            logger.warning(f"Failed to update progress message: {e}")
    
    async def complete(self, final_message: str = "") -> None:
        """Завершает отслеживание прогресса"""
        elapsed = datetime.now() - self.start_time
        
        if not final_message:
            final_message = f"✅ {self.operation_name} завершена!"
        
        text_lines = [
            final_message,
            f"📊 Обработано: {self.total_items} элементов",
            f"⏱️ Время: {self._format_time(elapsed.total_seconds())}"
        ]
        
        text = "\n".join(text_lines)
        
        try:
            await self.ctx.bot.edit_message_text(
                chat_id=self.update.effective_chat.id,
                message_id=self.message_id,
                text=text
            )
        except Exception as e:
            logger.warning(f"Failed to update final progress message: {e}")
    
    async def error(self, error_message: str) -> None:
        """Сообщает об ошибке"""
        text = f"❌ {self.operation_name} прервана!\n💬 {error_message}"
        
        try:
            await self.ctx.bot.edit_message_text(
                chat_id=self.update.effective_chat.id,
                message_id=self.message_id,
                text=text
            )
        except Exception as e:
            logger.warning(f"Failed to update error message: {e}")
    
    def _format_time(self, seconds: float) -> str:
        """Форматирует время в читаемый вид"""
        if seconds < 60:
            return f"{seconds:.0f}с"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}м"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}ч"


class BatchProcessor:
    """
    Обработчик больших массивов данных с прогрессом и контролем скорости.
    """
    
    def __init__(self, batch_size: int = 20, rate_limit: float = 0.4):
        self.batch_size = batch_size
        self.rate_limit = rate_limit
        
    async def process_with_progress(self,
                                  items: list,
                                  process_func: Callable[[Any], Any],
                                  progress_tracker: ProgressTracker,
                                  **kwargs) -> list:
        """
        Обрабатывает элементы батчами с отслеживанием прогресса.
        
        Args:
            items: Список элементов для обработки
            process_func: Функция обработки одного элемента
            progress_tracker: Трекер прогресса
            **kwargs: Дополнительные аргументы для process_func
        """
        results = []
        processed_count = 0
        
        await progress_tracker.start()
        
        try:
            # Обрабатываем батчами
            for i in range(0, len(items), self.batch_size):
                batch = items[i:i + self.batch_size]
                
                # Обрабатываем батч
                if asyncio.iscoroutinefunction(process_func):
                    # Асинхронная обработка
                    batch_results = await asyncio.gather(
                        *[process_func(item, **kwargs) for item in batch],
                        return_exceptions=True
                    )
                else:
                    # Синхронная обработка
                    batch_results = []
                    for item in batch:
                        try:
                            result = process_func(item, **kwargs)
                            batch_results.append(result)
                        except Exception as e:
                            batch_results.append(e)
                
                # Фильтруем ошибки и добавляем результаты
                for result in batch_results:
                    if not isinstance(result, Exception):
                        results.append(result)
                    else:
                        logger.warning(f"Batch processing error: {result}")
                
                processed_count += len(batch)
                
                # Обновляем прогресс
                await progress_tracker.update_progress(
                    processed_count,
                    f"Обработано батчей: {(i // self.batch_size) + 1}"
                )
                
                # Rate limiting
                if self.rate_limit > 0:
                    await asyncio.sleep(self.rate_limit)
            
            await progress_tracker.complete(
                f"✅ Успешно обработано {len(results)} из {len(items)} элементов"
            )
            
        except Exception as e:
            await progress_tracker.error(f"Ошибка обработки: {str(e)}")
            raise
        
        return results


# Декоратор для автоматического прогресса
def with_progress(operation_name: str):
    """Декоратор для автоматического добавления прогресса к функции"""
    def decorator(func):
        async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE, 
                         items: list, *args, **kwargs):
            progress = ProgressTracker(update, ctx, len(items), operation_name)
            return await func(update, ctx, items, progress, *args, **kwargs)
        return wrapper
    return decorator

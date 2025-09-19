#!/usr/bin/env python3
"""
Скрипт для проверки здоровья ESK Agent LLM Pro
Запускать перед передачей системы коллегам
"""

import os
import sys
from pathlib import Path

def check_environment():
    """Проверяет окружение и конфигурацию"""
    print("🔍 Проверка окружения...")
    
    issues = []
    
    # Проверяем .env файл
    if not Path(".env").exists():
        issues.append("❌ Файл .env не найден (скопируйте config.example)")
    
    # Проверяем обязательные переменные
    required_vars = ["TELEGRAM_BOT_TOKEN", "LLM_API_KEY"]
    for var in required_vars:
        if not os.getenv(var):
            issues.append(f"❌ Переменная {var} не установлена")
    
    # Проверяем директории
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        print("✅ Создана директория data/")
    
    if not issues:
        print("✅ Окружение настроено корректно")
    else:
        for issue in issues:
            print(issue)
        return False
    
    return True

def check_imports():
    """Проверяет импорты модулей"""
    print("\n🔍 Проверка модулей...")
    
    try:
        from src.adaptive_learning import FeedbackLearner, PromptOptimizer
        from src.cache import LLMCache, init_cache
        from src.context import ContextManager
        from src.progress import ProgressTracker, BatchProcessor
        from src.bot import settings, store
        print("✅ Все модули импортируются успешно")
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def check_llm_connection():
    """Проверяет подключение к LLM"""
    print("\n🔍 Проверка LLM подключения...")
    
    try:
        from src.llm import LLMClient
        from src.config import Settings
        
        settings = Settings.load()
        client = LLMClient(
            api_key=settings.llm_api_key,
            api_base=settings.llm_api_base,
            model=settings.llm_model
        )
        
        # Тестовый запрос
        response = client.chat([
            {"role": "user", "content": "Привет! Это тест подключения."}
        ], response_json=False, temperature=0.1)
        
        if response:
            print("✅ LLM подключение работает")
            return True
        else:
            print("❌ LLM не отвечает")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка LLM подключения: {e}")
        return False

def check_telegram_bot():
    """Проверяет Telegram бота"""
    print("\n🔍 Проверка Telegram бота...")
    
    try:
        from telegram import Bot
        from src.config import Settings
        
        settings = Settings.load()
        bot = Bot(token=settings.bot_token)
        
        # Получаем информацию о боте
        bot_info = bot.get_me()
        print(f"✅ Telegram бот: @{bot_info.username}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка Telegram бота: {e}")
        return False

def check_file_structure():
    """Проверяет файловую структуру"""
    print("\n🔍 Проверка файловой структуры...")
    
    required_files = [
        "src/bot.py",
        "src/adaptive_learning.py", 
        "src/cache.py",
        "src/context.py",
        "src/progress.py",
        "prompts/labeler_system.txt",
        "prompts/labeler_fewshot.txt",
        "requirements.txt"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if not missing_files:
        print("✅ Все необходимые файлы на месте")
        return True
    else:
        print("❌ Отсутствуют файлы:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False

def show_system_info():
    """Показывает информацию о системе"""
    print("\n📊 Информация о системе:")
    
    try:
        from src.config import Settings
        settings = Settings.load()
        
        print(f"• Модель LLM: {settings.llm_model}")
        print(f"• Размер батча: {settings.batch_size}")
        print(f"• Порог низкой уверенности: {settings.low_conf}")
        print(f"• Директория данных: {settings.data_dir}")
        print(f"• Уровень логирования: {settings.log_level}")
        
        # Статистика файлов
        data_dir = Path(settings.data_dir)
        if data_dir.exists():
            files = list(data_dir.rglob("*"))
            print(f"• Файлов в data/: {len([f for f in files if f.is_file()])}")
        
    except Exception as e:
        print(f"❌ Ошибка получения информации: {e}")

def main():
    """Основная функция проверки"""
    print("🔧 ESK Agent LLM Pro - Проверка системы")
    print("=" * 50)
    
    checks = [
        check_file_structure,
        check_environment, 
        check_imports,
        check_llm_connection,
        check_telegram_bot
    ]
    
    passed = 0
    for check in checks:
        if check():
            passed += 1
    
    show_system_info()
    
    print("\n" + "=" * 50)
    print(f"📋 Результат: {passed}/{len(checks)} проверок пройдено")
    
    if passed == len(checks):
        print("🎉 Система готова к использованию!")
        print("\n🚀 Для запуска: python -m src.bot")
        return True
    else:
        print("⚠️  Исправьте ошибки перед использованием")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

# ⚡ Быстрый старт ESK ML Pipeline v2.0

## 5 минут до запуска

### Шаг 1: Установка (1 мин)

```bash
# Клонируем (если еще не сделали)
git clone https://github.com/your-username/esk-agent-llm-pro.git
cd esk-agent-llm-pro

# Или просто pull если уже есть
git pull origin main

# Создаем venv
python -m venv .venv

# Активируем
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### Шаг 2: Конфигурация (2 мин)

```bash
# Копируем пример
cp config.example.v2 .env

# Редактируем .env (минимум 2 переменные!)
# Windows:
notepad .env
# Linux/Mac:
nano .env
```

**Минимально необходимые переменные:**

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here  # Получить у @BotFather
LLM_API_KEY=sk-your-key-here            # OpenAI ключ или dummy для локальных
```

### Шаг 3: Проверка (30 сек)

```bash
python health_check.py
```

Должен показать:
```
✅ Telegram config OK
✅ LLM config OK
✅ Data directories created
✅ All checks passed!
```

### Шаг 4: Запуск (30 сек)

```bash
python -m src.bot
```

Должен показать:
```
INFO - Bot started in POLLING mode
INFO - Loaded 0 user contexts
INFO - Ready to process messages
```

### Шаг 5: Тестирование (1 мин)

1. **Откройте Telegram**, найдите своего бота
2. **Отправьте:** `/start`
3. **Отправьте текст:** "передать показания счетчика"
4. **Получите:** классификацию + кнопки для коррекции

**Готово! 🎉**

---

## Альтернатива: Локальная LLM модель

Хотите бесплатно? Используйте Ollama:

### Установка Ollama (3 мин)

```bash
# Windows
# Скачайте с https://ollama.ai/download

# Linux/Mac
curl -fsSL https://ollama.ai/install.sh | sh

# Запуск
ollama serve

# В другом терминале - загрузка модели
ollama pull llama3.1:8b
```

### Конфигурация для Ollama

В `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
LLM_API_BASE=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=dummy
```

Запускаем бота:
```bash
python -m src.bot
```

**Работает бесплатно! 🆓**

---

## Первый pipeline (3 мин)

Создайте `quick_test.py`:

```python
import asyncio
from pathlib import Path
from src.pipeline.etl import ETLProcessor, ETLConfig
from src.pipeline.labeler_agent import LabelerAgent, LabelerConfig
from src.config_v2 import Settings

async def test_pipeline():
    # Настройки
    settings = Settings.load()
    
    # ETL - если есть файл
    if Path("data/logs.xlsx").exists():
        print("📥 Processing file...")
        etl = ETLProcessor(ETLConfig(max_rows=100))
        df = etl.process_file(Path("data/logs.xlsx"))
        print(f"✅ Processed {len(df)} rows")
    else:
        print("⚠️ No logs.xlsx found, skipping ETL")
        return
    
    # Labeler
    print("🏷️  Classifying...")
    labeler_config = LabelerConfig(
        **settings.get_labeler_llm_config(),
        batch_size=10  # Маленький batch для теста
    )
    labeler = LabelerAgent(labeler_config)
    
    results = await labeler.classify_dataframe(df.head(10))  # Только 10 строк
    
    print(f"✅ Classified {len(results)} texts")
    
    # Статистика
    stats = labeler.get_stats()
    print(f"📊 Stats: {stats}")
    
    # Результаты
    for r in results[:3]:
        print(f"  • {r.text[:50]}... → {r.domain_id} ({r.confidence:.2f})")
    
    print("\n🎉 Pipeline test completed!")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
```

Запуск:
```bash
python quick_test.py
```

---

## Troubleshooting

### Ошибка: `ModuleNotFoundError: No module named 'pydantic_ai'`

```bash
pip install --upgrade -r requirements.txt
```

### Ошибка: `ValidationError: TELEGRAM_BOT_TOKEN field required`

Проверьте `.env`:
```bash
cat .env  # Linux/Mac
type .env  # Windows
```

Убедитесь что есть:
```env
TELEGRAM_BOT_TOKEN=...
LLM_API_KEY=...
```

### Ошибка: `openai.OpenAIError: Connection error`

Если используете локальную модель, проверьте что сервер запущен:
```bash
# Ollama
ollama serve

# Проверка
curl http://localhost:11434/v1/models
```

### Бот не отвечает в Telegram

1. Проверьте токен: правильный ли?
2. Проверьте логи бота: есть ли ошибки?
3. Попробуйте `/start` и подождите 5 сек

---

## Следующие шаги

✅ **Бот работает** → см. [README_V2.md](README_V2.md) для полной документации

✅ **Хочу понять архитектуру** → см. [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)

✅ **Мигрирую со старой версии** → см. [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

✅ **Хочу примеры кода** → см. `src/pipeline/` + README_V2.md

---

## Команды бота

После запуска бота доступны команды:

- `/start` - начало работы
- `/menu` - главное меню с кнопками
- `/stats` - статистика качества модели
- `/help` - помощь

**Отправьте файл** `.xlsx` или `.csv` для автоматической обработки

**Отправьте текст** для классификации

---

## Полезные ссылки

- 📖 Полная документация: [README_V2.md](README_V2.md)
- 🏗️ Архитектура: [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)
- 🔄 Миграция: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- 📋 Обзор изменений: [V2_SUMMARY.md](V2_SUMMARY.md)

---

**Готово! Система работает. Удачи! 🚀**


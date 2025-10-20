# 📋 Руководство по миграции на v2.0

Это руководство поможет вам мигрировать с предыдущей версии на новую архитектуру ML Data Pipeline v2.0.

## 🎯 Что изменилось

### Основные изменения

1. **Модульная архитектура** - код разделен на независимые компоненты в `src/pipeline/`
2. **PydanticAI** - AI-агенты теперь используют PydanticAI для типобезопасности
3. **Pydantic Settings** - новая система конфигурации через `src/config_v2.py`
4. **Версионирование датасетов** - полноценная система версий с git-like командами
5. **HITL улучшения** - расширенный ReviewDataset с приоритизацией

### Обратная совместимость

✅ **Все старые функции остаются работающими** через обёртки совместимости.

---

## 🚀 Поэтапная миграция

### Фаза 1: Обновление зависимостей (5 мин)

1. **Обновите requirements.txt:**

```bash
pip install -r requirements.txt
```

Новые зависимости:
- `pydantic-ai>=0.0.14` - для AI-агентов
- `pydantic-settings>=2.5` - для конфигурации
- `ollama>=0.1.0` - опционально, для локальных моделей

2. **Проверьте установку:**

```bash
python -c "import pydantic_ai; print('PydanticAI installed:', pydantic_ai.__version__)"
```

---

### Фаза 2: Обновление конфигурации (10 мин)

#### Старая конфигурация (`src/config.py`):

```python
from src.config import Settings
settings = Settings.load()

print(settings.llm_api_key)
print(settings.llm_model)
print(settings.batch_size)
```

#### Новая конфигурация (`src/config_v2.py`):

```python
from src.config_v2 import Settings
settings = Settings.load()

# Доступ к конфигам компонентов
print(settings.telegram.bot_token)
print(settings.llm.model)
print(settings.labeler.batch_size)
print(settings.augmenter.variants_per_sample)
```

#### Миграция .env файла:

Старый `.env`:
```env
TELEGRAM_BOT_TOKEN=...
LLM_API_KEY=...
LLM_MODEL=gpt-4o-mini
BATCH_SIZE=20
LOW_CONF=0.5
```

Новый `.env` (расширенный):
```env
# Telegram
TELEGRAM_BOT_TOKEN=...

# LLM
LLM_API_KEY=...
LLM_MODEL=gpt-4o-mini

# Labeler
LABELER_BATCH_SIZE=20
LABELER_LOW_CONF_THRESHOLD=0.5

# Augmenter
AUGMENTER_VARIANTS_PER_SAMPLE=3
AUGMENTER_CONCURRENCY=8

# Review (HITL)
REVIEW_LOW_CONFIDENCE_THRESHOLD=0.5

# Data Writer
DATA_WRITER_EVAL_FRACTION=0.1
DATA_WRITER_BALANCE_DOMAINS=true

# Data Storage
DATA_STORAGE_MAX_VERSIONS=100

# Cache
CACHE_TTL_HOURS=24

# App
APP_MODE=development
APP_LOG_LEVEL=INFO
```

**💡 Tip:** Используйте `config.example.v2` как шаблон.

---

### Фаза 3: Миграция компонентов (опционально)

Вы можете мигрировать постепенно или сразу использовать новые компоненты.

#### 3.1 ETL Component

**Старый код:**
```python
from src.etl import normalize_file_to_df

df = normalize_file_to_df(Path("data/logs.xlsx"), max_rows=10000)
```

**Новый код:**
```python
from src.pipeline.etl import ETLProcessor, ETLConfig

config = ETLConfig(max_rows=10000, deduplicate=True)
processor = ETLProcessor(config)
df = processor.process_file(Path("data/logs.xlsx"))

# Получить статистику
stats = processor.get_stats()
print(f"Processed: {stats['processed_rows']}, Filtered: {stats['filtered_rows']}")
```

**Совместимость:** Старая функция `normalize_file_to_df` всё ещё работает!

---

#### 3.2 Labeler Agent

**Старый код:**
```python
from src.labeler import label_dataframe_batched, classify_one
from src.llm import LLMClient

client = LLMClient(api_key="...", api_base=None, model="gpt-4o-mini")

# Один текст
result = classify_one(client, system_prompt, fewshot, "передать показания")

# Batch
results = await label_dataframe_batched(
    df, client, system_prompt, fewshot, 
    batch_size=20, rate_limit=0.4
)
```

**Новый код:**
```python
from src.pipeline.labeler_agent import LabelerAgent, LabelerConfig

config = LabelerConfig(
    model="gpt-4o-mini",
    api_key="...",
    batch_size=20,
    rate_limit=0.4,
    use_cache=True
)

agent = LabelerAgent(config)

# Один текст - типобезопасный результат!
result: ClassificationResult = await agent.classify_one("передать показания")
print(f"Domain: {result.domain_id}, Confidence: {result.confidence}")

# Batch
results: List[ClassificationResult] = await agent.classify_dataframe(df)

# Низкая уверенность
low_conf = agent.get_low_confidence_items(results, threshold=0.5)

# Статистика
stats = agent.get_stats()
print(f"Cache hits: {stats['cache_hits']}, LLM calls: {stats['llm_calls']}")
```

**Преимущества нового подхода:**
- ✅ Типобезопасность через Pydantic
- ✅ Автоматическая валидация
- ✅ Встроенная статистика
- ✅ Лучшее кэширование

**Совместимость:** Старые функции работают через новый агент под капотом!

---

#### 3.3 Augmenter Agent

**Старый код:**
```python
from src.augmenter import augment_dataset

synthetic = await augment_dataset(
    llm_client, system_prompt, items,
    rate_limit=0.1, 
    include_low_conf=False,
    only_positive=True,
    concurrency=8
)
```

**Новый код:**
```python
from src.pipeline.augmenter_agent import AugmenterAgent, AugmenterConfig

config = AugmenterConfig(
    model="gpt-4o-mini",
    api_key="...",
    variants_per_sample=3,
    include_hard_negatives=False,
    concurrency=8,
    rate_limit=0.1
)

agent = AugmenterAgent(config)

# Аугментация с балансировкой
synthetic = await agent.augment_batch(items, balance_domains=True)

# Статистика
stats = agent.get_stats()
print(f"Generated {stats['total_generated']} samples, Cache hits: {stats['cache_hits']}")
```

---

#### 3.4 Review Dataset (HITL)

**Старый код:**
```python
from src.store import Store

store = Store(Path("data"))

# Добавление в очередь
store.append_hitl_queue(low_conf_items)

# Чтение очереди
items = store.read_hitl_queue(limit=10)
```

**Новый код:**
```python
from src.pipeline.review_dataset import ReviewDataset, ReviewDatasetConfig

config = ReviewDatasetConfig(
    data_dir=Path("data"),
    low_confidence_threshold=0.5,
    high_priority_threshold=0.3
)

review = ReviewDataset(config)

# Добавление с приоритизацией
review.add_items(low_conf_items)

# Получение следующего
items = review.get_next(count=1, reviewer_id="user123")

# Отправка результата
review.submit_review(
    item_id=items[0].id,
    corrected_domain="house",
    reviewer_id="user123",
    notes="Очевидно ЖКХ"
)

# Статистика очереди
stats = review.get_queue_stats()
print(f"Queue: {stats['queue_size']}, By priority: {stats['by_priority']}")

# Экспорт проверенных
reviewed_path = review.export_reviewed()
```

**Преимущества:**
- ✅ Приоритизация по уверенности
- ✅ Статусы элементов (PENDING, IN_REVIEW, APPROVED, CORRECTED)
- ✅ Метаданные и комментарии
- ✅ Экспорт для обучения

---

#### 3.5 DataWriter - NEW! 🆕

**Старый код:**
```python
from src.augmenter import split_train_eval, write_jsonl

# Сплит
train, eval_ = split_train_eval(items, eval_frac=0.1, min_eval=50)

# Запись
write_jsonl(Path("data/artifacts/dataset_train.jsonl"), train)
write_jsonl(Path("data/artifacts/dataset_eval.jsonl"), eval_)
```

**Новый код:**
```python
from src.pipeline.data_writer import DataWriter, DataWriterConfig

config = DataWriterConfig(
    output_dir=Path("data/artifacts"),
    eval_fraction=0.1,
    min_eval_samples=50,
    balance_domains=True,
    validate_quality=True,
    include_metadata=True
)

writer = DataWriter(config)

# Запись с валидацией и статистикой
train_path, eval_path, stats = writer.write_datasets(
    items,
    dataset_name="production"
)

print(f"Train: {stats.train_samples}, Eval: {stats.eval_samples}")
print(f"Domains: {stats.domain_distribution}")
print(f"Avg confidence: {stats.avg_confidence:.2f}")
print(f"Quality issues: {stats.quality_issues}")
```

**Преимущества:**
- ✅ Стратифицированный сплит
- ✅ Балансировка доменов
- ✅ Валидация качества
- ✅ Детальная статистика
- ✅ Шардинг для больших датасетов

---

#### 3.6 DataStorage - NEW! 🆕

Полностью новый компонент для версионирования датасетов.

```python
from src.pipeline.data_storage import DataStorage, DataStorageConfig, VersionStatus

config = DataStorageConfig(
    storage_dir=Path("data/storage"),
    max_versions=100,
    auto_archive_old=True
)

storage = DataStorage(config)

# Создание версии
version = storage.commit_version(
    train_path=train_path,
    eval_path=eval_path,
    version_tag="v1.2.0",  # или None для auto-increment
    description="Added feedback, balanced domains",
    status=VersionStatus.STABLE,
    created_by="bot_pipeline"
)

# Теги
storage.tag_version("v1.2.0", "production")
storage.tag_version("v1.2.0", "latest")

# Переключение версии
storage.checkout("v1.2.0")

# Список версий
versions = storage.list_versions(status=VersionStatus.STABLE)

# Сравнение
diff = storage.compare_versions("v1.1.0", "v1.2.0")

# Статистика
stats = storage.get_stats()
print(f"Total versions: {stats['total_versions']}")
print(f"Current: {stats['current_version']}")
```

**Преимущества:**
- ✅ Git-like версионирование
- ✅ Семантические теги (v1.2.3)
- ✅ Сравнение версий
- ✅ Автоархивирование
- ✅ Метаданные и статистика

---

### Фаза 4: Обновление бота (опционально)

Telegram бот (`src/bot.py`) уже обновлен для работы с новыми компонентами через функции совместимости.

**Что работает автоматически:**
- ✅ Все команды бота
- ✅ Загрузка файлов
- ✅ Классификация текстов
- ✅ HITL интерфейс
- ✅ Feedback система

**Что можно улучшить:**

1. **Использовать новую конфигурацию:**

```python
# Старое
from src.config import Settings
settings = Settings.load()

# Новое
from src.config_v2 import Settings
settings = Settings.load()
```

2. **Включить версионирование датасетов:**

```python
# После создания dataset_train.jsonl и dataset_eval.jsonl
from src.pipeline.data_storage import DataStorage, DataStorageConfig

storage = DataStorage(DataStorageConfig(storage_dir=Path("data/storage")))
version = storage.commit_version(
    train_path=train_p,
    eval_path=eval_p,
    description="Bot upload processed",
    status=VersionStatus.DRAFT
)

await update.message.reply_text(f"✅ Version created: {version.version_tag}")
```

---

## 🔧 Типичные сценарии миграции

### Сценарий 1: Минимальная миграция (работает как раньше)

```bash
# 1. Обновляем зависимости
pip install -r requirements.txt

# 2. Проверяем
python health_check.py

# 3. Запускаем бота (всё работает!)
python -m src.bot
```

✅ **Готово!** Система работает с новыми компонентами через совместимые API.

---

### Сценарий 2: Постепенная миграция (рекомендуется)

**Неделя 1: Конфигурация**
```python
# Обновляем bot.py
from src.config_v2 import Settings
settings = Settings.load()
```

**Неделя 2: ETL и Labeler**
```python
# Используем новый ETL
from src.pipeline.etl import ETLProcessor
etl = ETLProcessor()

# Используем новый Labeler
from src.pipeline.labeler_agent import LabelerAgent
labeler = LabelerAgent(config)
```

**Неделя 3: HITL и DataWriter**
```python
# Обновляем HITL
from src.pipeline.review_dataset import ReviewDataset
review = ReviewDataset(config)

# Используем DataWriter
from src.pipeline.data_writer import DataWriter
writer = DataWriter(config)
```

**Неделя 4: Версионирование**
```python
# Добавляем DataStorage
from src.pipeline.data_storage import DataStorage
storage = DataStorage(config)
```

---

### Сценарий 3: Полная миграция сразу

Используйте полный pipeline из примера в `README_V2.md`:

```python
from pathlib import Path
from src.pipeline import *
from src.config_v2 import Settings

async def full_pipeline():
    settings = Settings.load()
    
    # ETL
    etl = ETLProcessor()
    df = etl.process_file(Path("data/logs.xlsx"))
    
    # Labeler
    labeler = LabelerAgent.from_settings(settings)
    results = await labeler.classify_dataframe(df)
    
    # Review
    review = ReviewDataset.from_settings(settings)
    low_conf = labeler.get_low_confidence_items(results)
    review.add_items([r.dict() for r in low_conf])
    
    # Augmenter
    augmenter = AugmenterAgent.from_settings(settings)
    synthetic = await augmenter.augment_batch([r.dict() for r in results])
    
    # DataWriter
    writer = DataWriter.from_settings(settings)
    train_path, eval_path, stats = writer.write_datasets(
        [r.dict() for r in results] + [s.dict() for s in synthetic]
    )
    
    # DataStorage
    storage = DataStorage.from_settings(settings)
    version = storage.commit_version(train_path, eval_path)
    
    print(f"✅ Pipeline completed! Version: {version.version_tag}")

import asyncio
asyncio.run(full_pipeline())
```

---

## 🐛 Решение проблем

### Проблема: Import errors

```python
ModuleNotFoundError: No module named 'pydantic_ai'
```

**Решение:**
```bash
pip install --upgrade -r requirements.txt
```

---

### Проблема: Конфигурация не работает

```python
ValidationError: TELEGRAM_BOT_TOKEN field required
```

**Решение:**
```bash
# Убедитесь что .env файл существует
cp config.example.v2 .env

# Заполните обязательные поля
nano .env  # или любой редактор
```

---

### Проблема: Старые функции не работают

```python
AttributeError: 'Settings' object has no attribute 'llm_model'
```

**Решение:**
```python
# Вместо старого
settings.llm_model

# Используйте новый
settings.llm.model
```

---

### Проблема: Локальные модели не работают

```python
openai.OpenAIError: Connection error
```

**Решение:**
```bash
# Убедитесь что сервер запущен
ollama serve

# Проверьте доступность
curl http://localhost:11434/v1/models

# Проверьте конфигурацию
LLM_API_BASE=http://localhost:11434/v1  # правильный формат
LLM_MODEL=llama3.1:8b  # модель существует
```

---

## ✅ Чек-лист миграции

- [ ] Обновлены зависимости (`pip install -r requirements.txt`)
- [ ] Создан новый `.env` файл из `config.example.v2`
- [ ] Заполнены обязательные переменные (TELEGRAM_BOT_TOKEN, LLM_API_KEY)
- [ ] Проверена работа через `health_check.py`
- [ ] Запущен бот (`python -m src.bot`)
- [ ] Протестирована загрузка файла
- [ ] Протестирована классификация текста
- [ ] Проверена работа HITL
- [ ] Опционально: обновлен код для использования новых компонентов
- [ ] Опционально: настроено версионирование датасетов

---

## 📚 Дополнительные ресурсы

- [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) - полная архитектура системы
- [README_V2.md](README_V2.md) - документация и примеры
- [config.example.v2](config.example.v2) - пример конфигурации

---

## 💬 Поддержка

Если у вас возникли проблемы с миграцией:

1. Проверьте [Issues](https://github.com/your-username/esk-agent-llm-pro/issues)
2. Создайте новый Issue с описанием проблемы
3. Свяжитесь с разработчиками

---

**Удачной миграции! 🚀**


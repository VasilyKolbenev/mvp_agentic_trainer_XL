# 🏗️ Архитектура ML Data Pipeline v2.0

## Обзор

Проект реорганизован согласно современной архитектуре ML Data Pipeline с использованием компонентного подхода и PydanticAI для реализации AI-агентов.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ML Data Pipeline System                          │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────┐    ┌─────────┐    ┌──────────────┐    ┌──────────────┐
│  ECK_Logs  │───▶│   ETL   │───▶│Labeler_Agent │───▶│ReviewDataset │
│(Telegram)  │    │(Обработ)│    │(LLM-агент)   │    │   (HITL)     │
└────────────┘    └─────────┘    └──────────────┘    └──────────────┘
                                         │                     │
                                         ▼                     ▼
                              ┌────────────────────┐    ┌──────────┐
                              │ Augmenter_Agent    │    │          │
                              │ (Синтетика)        │    │          │
                              └────────────────────┘    │          │
                                         │              │          │
                                         ▼              ▼          ▼
                                    ┌──────────────────────────────┐
                                    │      DataWriter              │
                                    │ (train/eval сплит)           │
                                    └──────────────────────────────┘
                                               │
                                               ▼
                                    ┌──────────────────────────────┐
                                    │      DataStorage             │
                                    │  (Версионирование)           │
                                    └──────────────────────────────┘
```

## Компоненты системы

### 1. ECK_Logs (Источник данных)

**Расположение:** `src/bot.py`

**Описание:** Telegram бот как источник входящих логов и запросов пользователей.

**Функции:**
- Прием текстовых сообщений от пользователей
- Загрузка файлов (XLSX/CSV)
- Интерактивное взаимодействие через inline-кнопки
- HITL интерфейс для ручной проверки

**Технологии:**
- `python-telegram-bot` v21.6
- Async/await для неблокирующих операций

---

### 2. ETL (Extract, Transform, Load)

**Расположение:** `src/pipeline/etl.py`

**Описание:** Универсальный обработчик входящих данных из различных источников.

**Функции:**
- Чтение множественных форматов: XLSX, CSV, JSON, JSONL, Parquet
- Автодетекция кодировки и разделителей
- Нормализация и очистка текстов
- Дедупликация
- Валидация структуры данных

**Конфигурация:**
```python
class ETLConfig:
    max_rows: Optional[int] = None
    deduplicate: bool = True
    min_text_length: int = 3
    max_text_length: int = 1000
    remove_empty: bool = True
    normalize_whitespace: bool = True
```

**Пример использования:**
```python
from src.pipeline.etl import ETLProcessor, ETLConfig

config = ETLConfig(max_rows=10000, deduplicate=True)
processor = ETLProcessor(config)

df = processor.process_file(Path("data/logs.xlsx"))
# Результат: DataFrame с колонками [text, ts, user_id, source, metadata]
```

---

### 3. Labeler_Agent (LLM-агент разметки)

**Расположение:** `src/pipeline/labeler_agent.py`

**Описание:** AI-агент на базе PydanticAI для автоматической разметки текстов доменами.

**Функции:**
- Batch классификация с rate limiting
- Типобезопасные результаты через Pydantic
- Кэширование результатов
- Динамические few-shot примеры
- Адаптивное обучение на feedback
- Поддержка локальных LLM моделей

**Технологии:**
- **PydanticAI** - фреймворк для AI-агентов
- **Pydantic** v2.8+ для валидации
- OpenAI-совместимый API

**Архитектура агента:**
```python
class LabelerAgent:
    def __init__(self, config: LabelerConfig):
        # Инициализация PydanticAI агента
        self.agent = Agent(
            model=OpenAIModel(...),
            result_type=ClassificationResult,
            system_prompt=self._build_system_prompt()
        )
    
    async def classify_one(self, text: str) -> ClassificationResult:
        # Типобезопасная классификация
        result = await self.agent.run(text)
        return result.data  # Гарантированно ClassificationResult
```

**Поддержка локальных моделей:**
```python
# Ollama
config = LabelerConfig(
    api_base="http://localhost:11434/v1",
    model="llama3.1:8b",
    api_key="dummy"
)

# vLLM
config = LabelerConfig(
    api_base="http://localhost:8000/v1",
    model="microsoft/DialoGPT-large"
)

# LM Studio
config = LabelerConfig(
    api_base="http://localhost:1234/v1",
    model="local-model"
)
```

**Конфигурация:**
```python
class LabelerConfig:
    model: str = "gpt-4o-mini"
    api_key: str
    api_base: Optional[str] = None
    
    batch_size: int = 20
    rate_limit: float = 0.4
    max_retries: int = 3
    
    low_conf_threshold: float = 0.5
    use_cache: bool = True
    use_dynamic_fewshot: bool = True
```

---

### 4. Augmenter_Agent (Синтетическая аугментация)

**Расположение:** `src/pipeline/augmenter_agent.py`

**Описание:** AI-агент для генерации синтетических вариантов текстов.

**Функции:**
- Генерация перефразировок
- Балансировка по доменам
- Контроль качества генерации
- Параллельная обработка с ограничением конкурентности
- Кэширование результатов

**Конфигурация:**
```python
class AugmenterConfig:
    model: str = "gpt-4o-mini"
    api_key: str
    api_base: Optional[str] = None
    
    variants_per_sample: int = 3
    include_hard_negatives: bool = False
    
    concurrency: int = 8
    rate_limit: float = 0.1
    max_samples_per_domain: int = 30
```

**Пример использования:**
```python
from src.pipeline.augmenter_agent import AugmenterAgent, AugmenterConfig

config = AugmenterConfig(
    model="gpt-4o-mini",
    api_key="sk-...",
    variants_per_sample=3,
    concurrency=8
)

agent = AugmenterAgent(config)

# Аугментация батча
items = [{"text": "передать показания", "domain_id": "house"}, ...]
synthetic_samples = await agent.augment_batch(items)

# Результат: [AugmentedSample(...), ...]
```

---

### 5. ReviewDataset (Human-in-the-Loop)

**Расположение:** `src/pipeline/review_dataset.py`

**Описание:** Компонент для управления ручной проверкой и исправлениями.

**Функции:**
- Приоритизация по уверенности
- Очередь на проверку с статусами
- Интеграция с системой обучения
- Метрики качества разметки
- Экспорт проверенных данных

**Структура ReviewItem:**
```python
class ReviewItem:
    id: str
    text: str
    predicted_domain: str
    confidence: float
    top_candidates: List[List[Any]]
    
    corrected_domain: Optional[str]
    reviewer_id: Optional[str]
    review_timestamp: Optional[datetime]
    
    status: ReviewStatus  # PENDING, IN_REVIEW, APPROVED, CORRECTED
    priority: ReviewPriority  # LOW, MEDIUM, HIGH, CRITICAL
```

**Рабочий процесс:**
```python
from src.pipeline.review_dataset import ReviewDataset, ReviewDatasetConfig

config = ReviewDatasetConfig(
    data_dir=Path("data"),
    low_confidence_threshold=0.5,
    high_priority_threshold=0.3
)

review = ReviewDataset(config)

# Добавление в очередь
review.add_items(low_confidence_items)

# Получение следующего элемента
items = review.get_next(count=1, reviewer_id="user123")

# Отправка результата
review.submit_review(
    item_id=items[0].id,
    corrected_domain="house",
    reviewer_id="user123"
)

# Экспорт проверенных данных
reviewed_path = review.export_reviewed()
```

---

### 6. DataWriter (Запись датасетов)

**Расположение:** `src/pipeline/data_writer.py`

**Описание:** Компонент для записи финальных train/eval датасетов.

**Функции:**
- Стратифицированный сплит по доменам
- Балансировка классов
- Валидация качества данных
- Шардинг для больших датасетов
- Генерация метаданных и статистики

**Конфигурация:**
```python
class DataWriterConfig:
    output_dir: Path
    
    eval_fraction: float = 0.1
    min_eval_samples: int = 50
    min_samples_per_domain: int = 5
    
    balance_domains: bool = True
    max_samples_per_domain: Optional[int] = None
    
    shard_size: Optional[int] = None
    include_metadata: bool = True
    validate_quality: bool = True
```

**Пример использования:**
```python
from src.pipeline.data_writer import DataWriter, DataWriterConfig

config = DataWriterConfig(
    output_dir=Path("data/artifacts"),
    eval_fraction=0.1,
    balance_domains=True
)

writer = DataWriter(config)

# Запись датасетов
train_path, eval_path, stats = writer.write_datasets(
    items=all_labeled_items,
    dataset_name="dataset"
)

# Статистика
print(f"Train: {stats.train_samples}, Eval: {stats.eval_samples}")
print(f"Domains: {stats.domain_distribution}")
```

---

### 7. DataStorage (Версионирование)

**Расположение:** `src/pipeline/data_storage.py`

**Описание:** Компонент для версионирования и хранения артефактов.

**Функции:**
- Семантическое версионирование (v1.2.3)
- Git-like операции (commit, tag, checkout)
- Сравнение версий и diff
- Автоархивирование старых версий
- Экспорт/импорт версий

**Структура хранилища:**
```
storage_dir/
├── versions/
│   ├── v1.0.0/
│   │   ├── train.jsonl
│   │   ├── eval.jsonl
│   │   └── metadata.json
│   ├── v1.1.0/
│   │   └── ...
│   └── v2.0.0/
│       └── ...
├── current -> versions/v2.0.0  (symlink)
└── versions.json  (реестр)
```

**Пример использования:**
```python
from src.pipeline.data_storage import DataStorage, DataStorageConfig

config = DataStorageConfig(
    storage_dir=Path("data/storage"),
    max_versions=100,
    auto_archive_old=True
)

storage = DataStorage(config)

# Создание новой версии
version = storage.commit_version(
    train_path=Path("data/artifacts/dataset_train.jsonl"),
    eval_path=Path("data/artifacts/dataset_eval.jsonl"),
    version_tag="v1.2.0",  # или auto-increment
    description="Added user feedback, balanced domains",
    status=VersionStatus.STABLE,
    created_by="bot_pipeline"
)

# Переключение на версию
storage.checkout("v1.2.0")

# Добавление тега
storage.tag_version("v1.2.0", "production")

# Список версий
versions = storage.list_versions(status=VersionStatus.STABLE)

# Сравнение версий
diff = storage.compare_versions("v1.1.0", "v1.2.0")

# Статистика
stats = storage.get_stats()
print(f"Total versions: {stats['total_versions']}")
print(f"Storage size: {stats['total_size_mb']:.2f} MB")
```

---

## Интеграция компонентов

### Полный pipeline (пример)

```python
from pathlib import Path
from src.pipeline import (
    ETLProcessor, ETLConfig,
    LabelerAgent, LabelerConfig,
    AugmenterAgent, AugmenterConfig,
    ReviewDataset, ReviewDatasetConfig,
    DataWriter, DataWriterConfig,
    DataStorage, DataStorageConfig,
)

# 1. ETL - обработка входных данных
etl_config = ETLConfig(max_rows=10000, deduplicate=True)
etl = ETLProcessor(etl_config)
df = etl.process_file(Path("data/logs.xlsx"))

# 2. Labeler - автоматическая разметка
labeler_config = LabelerConfig(
    model="gpt-4o-mini",
    api_key="sk-...",
    batch_size=20,
    rate_limit=0.4
)
labeler = LabelerAgent(labeler_config)
results = await labeler.classify_dataframe(df)

# 3. Review - HITL для низкой уверенности
low_conf_items = labeler.get_low_confidence_items(results)

review_config = ReviewDatasetConfig(data_dir=Path("data"))
review = ReviewDataset(review_config)
review.add_items([r.dict() for r in low_conf_items])

# ... Пользователь проверяет через Telegram UI ...

reviewed_items = review.export_reviewed()

# 4. Augmenter - синтетическая аугментация
augmenter_config = AugmenterConfig(
    model="gpt-4o-mini",
    api_key="sk-...",
    variants_per_sample=3
)
augmenter = AugmenterAgent(augmenter_config)

high_conf_items = [r for r in results if r.confidence >= 0.7]
synthetic_items = await augmenter.augment_batch(
    [r.dict() for r in high_conf_items]
)

# 5. DataWriter - запись train/eval
writer_config = DataWriterConfig(
    output_dir=Path("data/artifacts"),
    eval_fraction=0.1,
    balance_domains=True
)
writer = DataWriter(writer_config)

all_items = (
    [r.dict() for r in results] +
    [s.dict() for s in synthetic_items]
)

train_path, eval_path, stats = writer.write_datasets(
    all_items,
    dataset_name="dataset"
)

# 6. DataStorage - версионирование
storage_config = DataStorageConfig(
    storage_dir=Path("data/storage"),
    max_versions=100
)
storage = DataStorage(storage_config)

version = storage.commit_version(
    train_path=train_path,
    eval_path=eval_path,
    description="Balanced domains with synthetic augmentation",
    status=VersionStatus.STABLE
)

print(f"Created version: {version.version_tag}")
```

---

## Конфигурация

### Новая система конфигурации

**Расположение:** `src/config_v2.py`

Использует **Pydantic Settings** для типобезопасной конфигурации:

```python
from src.config_v2 import Settings

settings = Settings.load()

# Telegram config
print(settings.telegram.bot_token)

# LLM config
print(settings.llm.model)
print(settings.llm.api_base)

# Компонентные конфиги
print(settings.labeler.batch_size)
print(settings.augmenter.variants_per_sample)
```

### Переменные окружения

Создайте `.env` файл:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_PUBLIC_URL=https://your-app.railway.app
TELEGRAM_PORT=8080

# LLM (главная модель)
LLM_API_KEY=sk-...
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# LLM Labeler (опционально - использует отдельную модель)
LLM_LABELER_API_KEY=sk-...
LLM_LABELER_API_BASE=http://localhost:11434/v1
LLM_LABELER_MODEL=llama3.1:8b

# LLM Augmenter (опционально)
LLM_AUGMENTER_API_KEY=sk-...
LLM_AUGMENTER_MODEL=gpt-4o-mini

# ETL
ETL_MAX_ROWS=10000
ETL_DEDUPLICATE=true

# Labeler
LABELER_BATCH_SIZE=20
LABELER_RATE_LIMIT=0.4
LABELER_LOW_CONF_THRESHOLD=0.5
LABELER_USE_CACHE=true

# Augmenter
AUGMENTER_VARIANTS_PER_SAMPLE=3
AUGMENTER_CONCURRENCY=8
AUGMENTER_RATE_LIMIT=0.1

# Review (HITL)
REVIEW_LOW_CONFIDENCE_THRESHOLD=0.5
REVIEW_MAX_QUEUE_SIZE=10000

# DataWriter
DATA_WRITER_EVAL_FRACTION=0.1
DATA_WRITER_BALANCE_DOMAINS=true

# DataStorage
DATA_STORAGE_MAX_VERSIONS=100
DATA_STORAGE_AUTO_ARCHIVE_OLD=true

# Cache
CACHE_TTL_HOURS=24
CACHE_ENABLED=true

# App
APP_MODE=production
APP_DATA_DIR=data
APP_LOG_LEVEL=INFO
```

---

## Локальные LLM модели

### Поддерживаемые решения

#### 1. **Ollama**

```bash
# Установка
curl -fsSL https://ollama.ai/install.sh | sh

# Запуск сервера
ollama serve

# Загрузка модели
ollama pull llama3.1:8b

# Конфигурация
LLM_API_BASE=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=dummy
```

#### 2. **vLLM**

```bash
# Установка
pip install vllm

# Запуск сервера
python -m vllm.entrypoints.openai.api_server \
  --model microsoft/DialoGPT-large \
  --port 8000

# Конфигурация
LLM_API_BASE=http://localhost:8000/v1
LLM_MODEL=microsoft/DialoGPT-large
```

#### 3. **LM Studio**

```bash
# 1. Запустить LM Studio GUI
# 2. Загрузить модель
# 3. Запустить локальный сервер

# Конфигурация
LLM_API_BASE=http://localhost:1234/v1
LLM_MODEL=local-model
LLM_API_KEY=dummy
```

#### 4. **Text Generation WebUI (Oobabooga)**

```bash
# Установка
git clone https://github.com/oobabooga/text-generation-webui
cd text-generation-webui
pip install -r requirements.txt

# Запуск с OpenAI API
python server.py --api --listen

# Конфигурация
LLM_API_BASE=http://localhost:5000/v1
LLM_MODEL=local-model
```

### Адаптеры моделей (будущие улучшения)

Планируется добавить адаптеры для оптимизации промптов под конкретные модели:

- **Llama 3.1**: Chat template, stop tokens
- **Mistral**: Instruction template
- **Qwen**: Special tokens
- **GPT**: Native JSON mode

---

## Преимущества новой архитектуры

### 1. **Модульность**
- Каждый компонент независим и тестируем
- Легко заменить или обновить компонент
- Четкое разделение ответственности

### 2. **Типобезопасность**
- Pydantic для всех конфигураций
- PydanticAI для типобезопасных AI-агентов
- Автодополнение в IDE

### 3. **Масштабируемость**
- Асинхронная обработка
- Параллельные операции с ограничением
- Шардинг для больших датасетов

### 4. **Мониторинг**
- Детальная статистика каждого компонента
- Метрики производительности
- Логирование всех операций

### 5. **Гибкость**
- Поддержка локальных и облачных LLM
- Различные модели для разных задач
- Настраиваемые пайплайны

### 6. **Production-ready**
- Версионирование датасетов
- Кэширование для экономии
- Обработка ошибок и fallback
- HITL для контроля качества

---

## Миграция со старой версии

### Совместимость

Все новые компоненты предоставляют функции совместимости со старым API:

```python
# Старый API
from src.labeler import label_dataframe_batched

# Новый API (автоматически используется под капотом)
from src.pipeline.labeler_agent import label_dataframe_batched

# Работает идентично!
results = await label_dataframe_batched(df, llm_client, system_prompt, fewshot)
```

### Поэтапная миграция

1. **Фаза 1**: Установить новые зависимости
   ```bash
   pip install -r requirements.txt
   ```

2. **Фаза 2**: Обновить конфигурацию
   ```python
   from src.config_v2 import Settings
   settings = Settings.load()
   ```

3. **Фаза 3**: Постепенно переходить на новые компоненты
   - Начать с ETL
   - Затем Labeler/Augmenter
   - В конце DataWriter/Storage

4. **Фаза 4**: Использовать полный pipeline
   - Версионирование датасетов
   - HITL процесс
   - Мониторинг метрик

---

## Следующие шаги

### Запланированные улучшения

- [ ] **Multi-model routing** - автоматический выбор модели
- [ ] **Distributed processing** - распределенная обработка
- [ ] **MLOps integration** - интеграция с MLflow/Weights & Biases
- [ ] **A/B testing** - сравнение версий моделей
- [ ] **Real-time monitoring** - Prometheus/Grafana
- [ ] **API server** - REST API для pipeline

---

## Заключение

Новая архитектура ML Data Pipeline v2.0 предоставляет:

✅ **Современный подход** к построению ML систем
✅ **Production-ready** код с типобезопасностью
✅ **Гибкость** в выборе моделей и конфигурации
✅ **Масштабируемость** для роста данных
✅ **Мониторинг** качества и производительности

Система готова к использованию как в development, так и в production окружении.


# 🚀 ESK ML Data Pipeline v2.0

**Production-ready ML pipeline для подготовки и версионирования датасетов с использованием LLM-агентов**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Pydantic](https://img.shields.io/badge/pydantic-v2.8+-green.svg)](https://docs.pydantic.dev/)
[![PydanticAI](https://img.shields.io/badge/pydanticai-latest-purple.svg)](https://ai.pydantic.dev/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## ✨ Что нового в v2.0

### 🏗️ **Модульная архитектура**
- Компонентный дизайн с четким разделением ответственности
- 7 независимых модулей: ETL, Labeler, Augmenter, Review, DataWriter, DataStorage
- Легкое тестирование и замена компонентов

### 🤖 **PydanticAI интеграция**
- Типобезопасные AI-агенты для разметки и аугментации
- Автоматическая валидация результатов через Pydantic
- Структурированное взаимодействие с LLM

### 🌐 **Локальные LLM модели**
- Полная поддержка Ollama, vLLM, LM Studio
- Экономия на API calls
- Контроль над данными

### 📦 **Версионирование датасетов**
- Git-like операции (commit, tag, checkout)
- Семантическое версионирование (v1.2.3)
- Сравнение версий и diff

### 🔄 **Human-in-the-Loop (HITL)**
- Приоритизация по уверенности
- Интеграция с feedback системой
- Экспорт проверенных данных

### 📊 **Production-ready**
- Кэширование результатов
- Мониторинг и метрики
- Обработка ошибок и fallback
- Асинхронная обработка

---

## 📋 Содержание

- [Быстрый старт](#-быстрый-старт)
- [Архитектура](#-архитектура)
- [Установка](#-установка)
- [Конфигурация](#-конфигурация)
- [Использование](#-использование)
- [Локальные LLM](#-локальные-llm)
- [API Reference](#-api-reference)
- [Примеры](#-примеры)
- [Деплой](#-деплой)
- [Contributing](#-contributing)

---

## 🚀 Быстрый старт

### 1. Установка

```bash
# Клонируем репозиторий
git clone https://github.com/your-username/esk-agent-llm-pro.git
cd esk-agent-llm-pro

# Создаем виртуальное окружение
python -m venv .venv

# Активируем (Windows)
.venv\Scripts\activate
# Или (Linux/Mac)
source .venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 2. Конфигурация

```bash
# Копируем пример конфигурации
cp config.example .env

# Редактируем .env
# Минимум нужно указать:
TELEGRAM_BOT_TOKEN=your_bot_token_here
LLM_API_KEY=your_openai_key_or_local_dummy
LLM_MODEL=gpt-4o-mini
```

### 3. Запуск

```bash
# Проверяем систему
python health_check.py

# Запускаем бота
python -m src.bot
```

### 4. Первый pipeline

```python
from pathlib import Path
from src.pipeline import ETLProcessor, LabelerAgent, DataWriter
from src.config_v2 import Settings

# Загружаем настройки
settings = Settings.load()

# ETL - обработка файла
etl = ETLProcessor()
df = etl.process_file(Path("data/logs.xlsx"))

# Labeler - автоматическая разметка
labeler = LabelerAgent.from_settings(settings)
results = await labeler.classify_dataframe(df)

# DataWriter - сохранение датасетов
writer = DataWriter.from_settings(settings)
train_path, eval_path, stats = writer.write_datasets(
    [r.dict() for r in results],
    dataset_name="my_dataset"
)

print(f"✅ Created train ({stats.train_samples}) and eval ({stats.eval_samples})")
```

---

## 🏗️ Архитектура

```
┌────────────┐    ┌─────────┐    ┌──────────────┐    ┌──────────────┐
│  ECK_Logs  │───▶│   ETL   │───▶│Labeler_Agent │───▶│ReviewDataset │
│(Telegram)  │    │(Process)│    │(LLM-агент)   │    │   (HITL)     │
└────────────┘    └─────────┘    └──────────────┘    └──────────────┘
                                         │                     │
                                         ▼                     ▼
                              ┌────────────────────┐    ┌──────────┐
                              │ Augmenter_Agent    │───▶│          │
                              │ (Синтетика)        │    │          │
                              └────────────────────┘    │          │
                                                        │          │
                                                        ▼          ▼
                                                 ┌──────────────────┐
                                                 │   DataWriter     │
                                                 │ (train/eval)     │
                                                 └──────────────────┘
                                                          │
                                                          ▼
                                                 ┌──────────────────┐
                                                 │   DataStorage    │
                                                 │ (версионирование)│
                                                 └──────────────────┘
```

Подробнее: [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)

---

## 💾 Установка

### Требования

- Python 3.10+
- pip / poetry

### Зависимости

```txt
# Core
python-telegram-bot==21.6
pydantic>=2.8
pydantic-ai>=0.0.14
pydantic-settings>=2.5

# LLM
openai>=1.40.0
tiktoken>=0.7.0
ollama>=0.1.0  # Optional

# Data
pandas>=2.2
openpyxl>=3.1
pyarrow>=15.0

# Utils
httpx>=0.27
python-dotenv>=1.0
tqdm>=4.66.0
rich>=13.7.0
loguru>=0.7.0
```

### Установка с Poetry

```bash
poetry install
poetry shell
```

### Установка с pip

```bash
pip install -r requirements.txt
```

---

## ⚙️ Конфигурация

### Структура .env

```env
# ========== Telegram ==========
TELEGRAM_BOT_TOKEN=1234567890:ABC...
TELEGRAM_PUBLIC_URL=https://your-app.railway.app
TELEGRAM_PORT=8080

# ========== LLM (основная модель) ==========
LLM_API_KEY=sk-...
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=1.0

# ========== LLM Labeler (опционально - своя модель) ==========
# Если не указано, использует основную модель
LLM_LABELER_API_KEY=sk-...
LLM_LABELER_API_BASE=http://localhost:11434/v1  # Ollama
LLM_LABELER_MODEL=llama3.1:8b

# ========== LLM Augmenter (опционально) ==========
LLM_AUGMENTER_API_KEY=sk-...
LLM_AUGMENTER_MODEL=gpt-4o-mini

# ========== ETL ==========
ETL_MAX_ROWS=10000
ETL_DEDUPLICATE=true
ETL_MIN_TEXT_LENGTH=3
ETL_MAX_TEXT_LENGTH=1000

# ========== Labeler ==========
LABELER_BATCH_SIZE=20
LABELER_RATE_LIMIT=0.4
LABELER_LOW_CONF_THRESHOLD=0.5
LABELER_USE_CACHE=true
LABELER_USE_DYNAMIC_FEWSHOT=true

# ========== Augmenter ==========
AUGMENTER_VARIANTS_PER_SAMPLE=3
AUGMENTER_INCLUDE_HARD_NEGATIVES=false
AUGMENTER_CONCURRENCY=8
AUGMENTER_RATE_LIMIT=0.1
AUGMENTER_MAX_SAMPLES_PER_DOMAIN=30

# ========== Review (HITL) ==========
REVIEW_LOW_CONFIDENCE_THRESHOLD=0.5
REVIEW_HIGH_PRIORITY_THRESHOLD=0.3
REVIEW_MAX_QUEUE_SIZE=10000
REVIEW_AUTO_APPROVE_THRESHOLD=0.95

# ========== DataWriter ==========
DATA_WRITER_EVAL_FRACTION=0.1
DATA_WRITER_MIN_EVAL_SAMPLES=50
DATA_WRITER_BALANCE_DOMAINS=true
DATA_WRITER_VALIDATE_QUALITY=true

# ========== DataStorage ==========
DATA_STORAGE_MAX_VERSIONS=100
DATA_STORAGE_AUTO_ARCHIVE_OLD=true
DATA_STORAGE_ENABLE_COMPRESSION=false

# ========== Cache ==========
CACHE_TTL_HOURS=24
CACHE_ENABLED=true

# ========== App ==========
APP_MODE=production  # или development
APP_DATA_DIR=data
APP_LOG_LEVEL=INFO
APP_LOG_TO_FILE=false
```

### Программная конфигурация

```python
from src.config_v2 import Settings

settings = Settings.load()

# Доступ к конфигу
print(settings.telegram.bot_token)
print(settings.llm.model)
print(settings.labeler.batch_size)

# Проверка режима
if settings.is_production():
    print("Running in production mode")
```

---

## 🎯 Использование

### Telegram Bot

```bash
# Запуск бота
python -m src.bot

# Команды в боте:
/start - Начало работы
/menu - Главное меню
/stats - Статистика качества
/help - Помощь

# Отправить файл .xlsx/.csv для обработки
# Отправить текст для классификации
```

### Python API

#### 1. ETL - Обработка данных

```python
from src.pipeline.etl import ETLProcessor, ETLConfig

config = ETLConfig(
    max_rows=10000,
    deduplicate=True,
    min_text_length=3
)

etl = ETLProcessor(config)
df = etl.process_file("data/logs.xlsx")

print(f"Processed {len(df)} rows")
print(df.head())
```

#### 2. Labeler - Классификация

```python
from src.pipeline.labeler_agent import LabelerAgent, LabelerConfig

config = LabelerConfig(
    model="gpt-4o-mini",
    api_key="sk-...",
    batch_size=20,
    rate_limit=0.4
)

labeler = LabelerAgent(config)

# Классификация одного текста
result = await labeler.classify_one("передать показания счетчика")
print(f"Domain: {result.domain_id}, Confidence: {result.confidence}")

# Классификация DataFrame
results = await labeler.classify_dataframe(df, text_column="text")

# Низкая уверенность для HITL
low_conf = labeler.get_low_confidence_items(results, threshold=0.5)
print(f"Need review: {len(low_conf)}")
```

#### 3. Augmenter - Синтетическая аугментация

```python
from src.pipeline.augmenter_agent import AugmenterAgent, AugmenterConfig

config = AugmenterConfig(
    model="gpt-4o-mini",
    api_key="sk-...",
    variants_per_sample=3,
    concurrency=8
)

augmenter = AugmenterAgent(config)

# Аугментация батча
items = [{"text": "передать показания", "domain_id": "house"}, ...]
synthetic = await augmenter.augment_batch(items, balance_domains=True)

print(f"Generated {len(synthetic)} synthetic samples")
```

#### 4. ReviewDataset - HITL

```python
from src.pipeline.review_dataset import ReviewDataset, ReviewDatasetConfig

config = ReviewDatasetConfig(
    data_dir=Path("data"),
    low_confidence_threshold=0.5
)

review = ReviewDataset(config)

# Добавление в очередь
review.add_items(low_confidence_items)

# Получение на проверку
items = review.get_next(count=10, reviewer_id="user123")

# Отправка результата
review.submit_review(
    item_id=items[0].id,
    corrected_domain="house",
    reviewer_id="user123",
    notes="Очевидно ЖКХ"
)

# Статистика
stats = review.get_queue_stats()
print(f"Queue size: {stats['queue_size']}")
```

#### 5. DataWriter - Сохранение датасетов

```python
from src.pipeline.data_writer import DataWriter, DataWriterConfig

config = DataWriterConfig(
    output_dir=Path("data/artifacts"),
    eval_fraction=0.1,
    balance_domains=True,
    validate_quality=True
)

writer = DataWriter(config)

# Запись датасетов
train_path, eval_path, stats = writer.write_datasets(
    items=all_items,
    dataset_name="production_v1"
)

print(f"Train: {stats.train_samples}, Eval: {stats.eval_samples}")
print(f"Domains: {stats.domain_distribution}")
print(f"Avg confidence: {stats.avg_confidence:.2f}")
```

#### 6. DataStorage - Версионирование

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
    created_by="pipeline_bot"
)

print(f"Created version: {version.version_tag}")

# Теги
storage.tag_version("v1.2.0", "production")
storage.tag_version("v1.2.0", "latest")

# Переключение версии
storage.checkout("v1.2.0")

# Список версий
versions = storage.list_versions(status=VersionStatus.STABLE)
for v in versions:
    print(f"{v.version_tag}: {v.description} ({v.created_at})")

# Сравнение
diff = storage.compare_versions("v1.1.0", "v1.2.0")
print(f"Train hash match: {diff['train_hash_match']}")
print(f"Metadata changes: {diff['metadata_diff']}")

# Статистика
stats = storage.get_stats()
print(f"Total versions: {stats['total_versions']}")
print(f"Storage size: {stats['total_size_mb']:.2f} MB")
```

---

## 🌐 Локальные LLM

### Ollama

```bash
# Установка
curl -fsSL https://ollama.ai/install.sh | sh

# Запуск
ollama serve

# Загрузка модели
ollama pull llama3.1:8b

# .env конфиг
LLM_API_BASE=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=dummy
```

**Рекомендуемые модели для классификации:**
- `llama3.1:8b` - хороший баланс качества/скорости
- `mistral:7b` - быстрая, хорошо следует инструкциям
- `qwen2:7b` - отличная для русского языка

### vLLM

```bash
# Установка
pip install vllm

# Запуск
python -m vllm.entrypoints.openai.api_server \
  --model microsoft/DialoGPT-large \
  --port 8000

# .env конфиг
LLM_API_BASE=http://localhost:8000/v1
LLM_MODEL=microsoft/DialoGPT-large
```

### LM Studio

1. Скачайте и установите [LM Studio](https://lmstudio.ai/)
2. Загрузите модель через GUI
3. Запустите локальный сервер
4. Настройте `.env`:

```env
LLM_API_BASE=http://localhost:1234/v1
LLM_MODEL=local-model
LLM_API_KEY=dummy
```

### Смешанный режим

Используйте локальные модели для Labeler и облачные для Augmenter:

```env
# Labeler - локально (быстро, бесплатно)
LLM_LABELER_API_BASE=http://localhost:11434/v1
LLM_LABELER_MODEL=llama3.1:8b
LLM_LABELER_API_KEY=dummy

# Augmenter - OpenAI (качество генерации)
LLM_AUGMENTER_API_KEY=sk-...
LLM_AUGMENTER_MODEL=gpt-4o-mini
```

---

## 📚 API Reference

### ETLProcessor

```python
class ETLProcessor:
    def __init__(self, config: ETLConfig)
    
    def process_file(self, file_path: Path, source_name: Optional[str] = None) -> pd.DataFrame
    """
    Обрабатывает файл и возвращает DataFrame.
    
    Поддерживаемые форматы: XLSX, CSV, JSON, JSONL, Parquet
    
    Returns:
        DataFrame с колонками: text, ts, user_id, source, metadata
    """
    
    def get_stats(self) -> Dict[str, Any]
    """Возвращает статистику обработки"""
```

### LabelerAgent

```python
class LabelerAgent:
    def __init__(self, config: LabelerConfig)
    
    async def classify_one(
        self,
        text: str,
        *,
        allowed_labels: Optional[List[str]] = None,
        user_context: Optional[str] = None
    ) -> ClassificationResult
    """Классифицирует один текст"""
    
    async def classify_batch(
        self,
        texts: List[str],
        *,
        progress_callback: Optional[callable] = None
    ) -> List[ClassificationResult]
    """Классифицирует батч текстов с rate limiting"""
    
    async def classify_dataframe(
        self,
        df: pd.DataFrame,
        text_column: str = "text",
        *,
        progress_callback: Optional[callable] = None
    ) -> List[ClassificationResult]
    """Классифицирует DataFrame"""
    
    def get_low_confidence_items(
        self,
        results: List[ClassificationResult],
        threshold: Optional[float] = None
    ) -> List[ClassificationResult]
    """Возвращает элементы с низкой уверенностью"""
    
    def get_stats(self) -> Dict[str, Any]
    """Возвращает статистику работы агента"""
```

### AugmenterAgent

```python
class AugmenterAgent:
    def __init__(self, config: AugmenterConfig)
    
    async def augment_one(self, text: str, domain: str) -> AugmentationResult
    """Генерирует варианты для одного текста"""
    
    async def augment_batch(
        self,
        items: List[Dict[str, Any]],
        *,
        balance_domains: bool = True,
        progress_callback: Optional[callable] = None
    ) -> List[AugmentedSample]
    """Аугментирует батч текстов"""
    
    def get_stats(self) -> Dict[str, Any]
    """Возвращает статистику"""
```

### ReviewDataset

```python
class ReviewDataset:
    def __init__(self, config: ReviewDatasetConfig)
    
    def add_items(self, items: List[Dict[str, Any]]) -> int
    """Добавляет элементы в очередь"""
    
    def get_next(self, count: int = 1, reviewer_id: Optional[str] = None) -> List[ReviewItem]
    """Возвращает следующие элементы для проверки"""
    
    def submit_review(
        self,
        item_id: str,
        corrected_domain: str,
        reviewer_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool
    """Отправляет результат проверки"""
    
    def get_queue_stats(self) -> Dict[str, Any]
    """Возвращает статистику очереди"""
    
    def export_reviewed(self, output_path: Optional[Path] = None) -> Path
    """Экспортирует проверенные элементы"""
```

### DataWriter

```python
class DataWriter:
    def __init__(self, config: DataWriterConfig)
    
    def write_datasets(
        self,
        items: List[Dict[str, Any]],
        *,
        dataset_name: str = "dataset"
    ) -> Tuple[Path, Path, DatasetStats]
    """
    Записывает train и eval датасеты.
    
    Returns:
        Tuple[train_path, eval_path, stats]
    """
    
    def get_last_stats(self) -> Optional[DatasetStats]
    """Возвращает статистику последней записи"""
```

### DataStorage

```python
class DataStorage:
    def __init__(self, config: DataStorageConfig)
    
    def commit_version(
        self,
        train_path: Path,
        eval_path: Path,
        *,
        version_tag: Optional[str] = None,
        description: Optional[str] = None,
        status: VersionStatus = VersionStatus.DRAFT,
        metadata: Optional[Dict[str, Any]] = None,
        increment_type: str = "minor",
        created_by: Optional[str] = None
    ) -> Version
    """Создает новую версию датасета"""
    
    def checkout(self, version_tag: str) -> bool
    """Переключается на указанную версию"""
    
    def tag_version(self, version_tag: str, tag: str) -> bool
    """Добавляет тег к версии"""
    
    def list_versions(
        self,
        status: Optional[VersionStatus] = None,
        tag: Optional[str] = None
    ) -> List[Version]
    """Возвращает список версий"""
    
    def compare_versions(self, version_tag1: str, version_tag2: str) -> Dict[str, Any]
    """Сравнивает две версии"""
    
    def get_stats(self) -> Dict[str, Any]
    """Возвращает статистику хранилища"""
```

---

## 💡 Примеры

### Полный pipeline

```python
import asyncio
from pathlib import Path
from src.pipeline import *
from src.config_v2 import Settings

async def full_pipeline():
    # Загружаем настройки
    settings = Settings.load()
    
    # 1. ETL - обработка
    print("📥 ETL Processing...")
    etl = ETLProcessor(ETLConfig(max_rows=10000))
    df = etl.process_file(Path("data/logs.xlsx"))
    print(f"✅ Processed: {len(df)} rows")
    
    # 2. Labeler - разметка
    print("🏷️  Labeling...")
    labeler_config = LabelerConfig(
        **settings.get_labeler_llm_config(),
        batch_size=20,
        rate_limit=0.4
    )
    labeler = LabelerAgent(labeler_config)
    results = await labeler.classify_dataframe(df)
    print(f"✅ Labeled: {len(results)} texts")
    
    # 3. Review - HITL
    print("👤 HITL Review...")
    low_conf = labeler.get_low_confidence_items(results, threshold=0.5)
    if low_conf:
        review = ReviewDataset(ReviewDatasetConfig(data_dir=Path("data")))
        review.add_items([r.dict() for r in low_conf])
        print(f"⏳ Added {len(low_conf)} items to review queue")
    
    # 4. Augmenter - синтетика
    print("🧬 Augmentation...")
    high_conf = [r for r in results if r.confidence >= 0.7]
    augmenter_config = AugmenterConfig(
        **settings.get_augmenter_llm_config(),
        variants_per_sample=3
    )
    augmenter = AugmenterAgent(augmenter_config)
    synthetic = await augmenter.augment_batch(
        [r.dict() for r in high_conf[:100]]  # Лимитируем для примера
    )
    print(f"✅ Generated: {len(synthetic)} synthetic samples")
    
    # 5. DataWriter - сохранение
    print("💾 Writing datasets...")
    all_items = [r.dict() for r in results] + [s.dict() for s in synthetic]
    writer = DataWriter(DataWriterConfig(
        output_dir=Path("data/artifacts"),
        eval_fraction=0.1,
        balance_domains=True
    ))
    train_path, eval_path, stats = writer.write_datasets(
        all_items,
        dataset_name="production"
    )
    print(f"✅ Train: {stats.train_samples}, Eval: {stats.eval_samples}")
    
    # 6. DataStorage - версионирование
    print("📦 Versioning...")
    storage = DataStorage(DataStorageConfig(
        storage_dir=Path("data/storage")
    ))
    version = storage.commit_version(
        train_path=train_path,
        eval_path=eval_path,
        description="Automated pipeline run with synthetic augmentation",
        status=VersionStatus.STABLE
    )
    storage.tag_version(version.version_tag, "latest")
    print(f"✅ Version: {version.version_tag}")
    
    print("\n🎉 Pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(full_pipeline())
```

---

## 🚀 Деплой

### Railway

1. **Push в GitHub**
   ```bash
   git add .
   git commit -m "Ready for deploy"
   git push origin main
   ```

2. **Railway Deploy**
   - Connect GitHub repo
   - Add variables (см. `.env`)
   - Start Command: `python -m src.bot`

3. **Настройка**
   ```env
   TELEGRAM_PUBLIC_URL=https://your-app.railway.app
   APP_MODE=production
   ```

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.bot"]
```

```bash
docker build -t esk-pipeline .
docker run -d --env-file .env esk-pipeline
```

---

## 🤝 Contributing

Приветствуются pull requests!

### Процесс

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменений (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

### Стиль кода

- Black для форматирования
- Pydantic для всех конфигов
- Type hints везде
- Docstrings для публичных методов

---

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE)

---

## 🙏 Благодарности

- [PydanticAI](https://ai.pydantic.dev/) - типобезопасные AI-агенты
- [Pydantic](https://docs.pydantic.dev/) - валидация данных
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram API
- [Ollama](https://ollama.ai/) - локальные LLM модели

---

## 📞 Поддержка

- 📧 Email: your-email@example.com
- 💬 Telegram: @your_username
- 🐛 Issues: [GitHub Issues](https://github.com/your-username/esk-agent-llm-pro/issues)

---

**Built with ❤️ for Production ML**


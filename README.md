# 🚀 ESK ML Data Pipeline v2.0

**Production-ready backend сервис для обработки логов и создания датасетов с использованием LLM-агентов**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PydanticAI](https://img.shields.io/badge/pydanticai-latest-purple.svg)](https://ai.pydantic.dev/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

> ⚡ **Быстрый старт:** `docker-compose up -d` → API готов на http://localhost:8000

---

## ✨ Возможности v2.0

### 🏗️ Модульная архитектура
- **7 независимых компонентов**: ETL, Labeler, Augmenter, Review, DataWriter, DataStorage
- **Типобезопасность** через Pydantic и PydanticAI
- **Production-ready** код с обработкой ошибок и метриками

### 🤖 AI-агенты на PydanticAI
- **LabelerAgent** - автоматическая разметка с типобезопасностью
- **AugmenterAgent** - синтетическая аугментация данных
- **Поддержка локальных моделей** (Ollama, vLLM, LM Studio)

### 🐳 Docker-ready
- **Готовый Dockerfile** и docker-compose
- **Multi-stage build** для оптимизации размера
- **Health checks** и мониторинг
- **Volume persistence** для данных

### 📦 Версионирование датасетов
- **Git-like операции**: commit, tag, checkout
- Сравнение версий и rollback
- Автоматическое архивирование

### 🌐 FastAPI Backend
- **REST API** без UI
- **Swagger** документация из коробки
- **Async** обработка
- **Rate limiting** и кэширование

---

## 🐳 Docker Deployment (рекомендуется)

### Быстрый старт

```bash
# 1. Конфигурация
cp env.docker.example .env
# Отредактируйте .env: укажите LLM_API_KEY

# 2. Запуск
docker-compose up -d

# 3. Проверка
curl http://localhost:8000/health
```

**API доступен:** http://localhost:8000  
**Документация:** http://localhost:8000/docs

### Использование API

```bash
# Загрузка файла
curl -X POST "http://localhost:8000/upload" -F "file=@logs.xlsx"

# Обработка логов
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/uploads/logs.xlsx",
    "balance_domains": true,
    "augment": true,
    "create_version": true
  }'

# Классификация текстов
curl -X POST "http://localhost:8000/classify" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["передать показания счетчика"]}'

# Список версий
curl http://localhost:8000/versions

# Скачать датасет
curl -O http://localhost:8000/download/train/v1.0.0
```

**Полная документация:** [README_DOCKER.md](README_DOCKER.md)

---

## 💻 Локальная установка

### Требования
- Python 3.10+
- pip / poetry

### Установка

```bash
git clone https://github.com/your-username/esk-agent-llm-pro.git
cd esk-agent-llm-pro

python -m venv .venv
source .venv/bin/activate  # или .venv\Scripts\activate на Windows

pip install -r requirements.txt
```

### Конфигурация

```bash
cp config.example.v2 .env
```

Отредактируйте `.env`:
```env
LLM_API_KEY=your_openai_key
LLM_MODEL=gpt-4o-mini
```

### Запуск API сервера

```bash
python -m uvicorn src.api:app --reload
```

API доступен на http://localhost:8000

---

## 📚 API Endpoints

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/` | GET | Главная страница API |
| `/docs` | GET | Swagger документация |
| `/health` | GET | Health check |
| `/upload` | POST | Загрузка файла |
| `/process` | POST | Полная обработка (ETL → Label → Augment → Write → Storage) |
| `/classify` | POST | Классификация списка текстов |
| `/versions` | GET | Список версий датасетов |
| `/versions/{tag}` | GET | Информация о версии |
| `/versions/{tag}/checkout` | POST | Переключение на версию |
| `/download/train/{tag}` | GET | Скачать train датасет |
| `/download/eval/{tag}` | GET | Скачать eval датасет |
| `/stats` | GET | Статистика компонентов |

---

## 🎯 Примеры использования

### Python Client

```python
import requests

# Загрузка и обработка файла
with open("logs.xlsx", "rb") as f:
    response = requests.post("http://localhost:8000/upload", files={"file": f})

file_path = response.json()["path"]

# Полная обработка
response = requests.post(
    "http://localhost:8000/process",
    json={
        "file_path": file_path,
        "balance_domains": True,
        "augment": True,
        "create_version": True
    }
)

result = response.json()
print(f"✅ Train: {result['stats']['train_samples']}, Eval: {result['stats']['eval_samples']}")
print(f"📦 Version: {result['version_tag']}")
```

### Bash Script

```bash
#!/bin/bash

# Upload
FILE_PATH=$(curl -s -X POST "http://localhost:8000/upload" \
  -F "file=@logs.xlsx" | jq -r '.path')

# Process
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d "{
    \"file_path\": \"$FILE_PATH\",
    \"balance_domains\": true,
    \"augment\": true,
    \"create_version\": true
  }" | jq '.'
```

---

## 🌐 Локальные LLM модели

### Ollama (рекомендуется)

**В Docker:**
```yaml
# Раскомментируйте в docker-compose.yml:
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"

# В .env:
LLM_API_BASE=http://ollama:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=dummy
```

**Локально:**
```bash
# Установка
curl -fsSL https://ollama.ai/install.sh | sh

# Запуск
ollama serve
ollama pull llama3.1:8b

# Конфигурация
LLM_API_BASE=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b
```

**Работает бесплатно! 🆓**

Также поддерживаются: vLLM, LM Studio, Text Generation WebUI

---

## 🏗️ Архитектура

```
┌──────────┐    ┌─────────┐    ┌──────────────┐    ┌──────────────┐
│   API    │───▶│   ETL   │───▶│Labeler_Agent │───▶│ReviewDataset │
│(FastAPI) │    │         │    │(PydanticAI)  │    │   (HITL)     │
└──────────┘    └─────────┘    └──────────────┘    └──────────────┘
                                       │                     │
                                       ▼                     ▼
                            ┌────────────────────┐    ┌──────────┐
                            │ Augmenter_Agent    │───▶│          │
                            │ (PydanticAI)       │    │          │
                            └────────────────────┘    │          │
                                                      ▼          ▼
                                               ┌──────────────────┐
                                               │   DataWriter     │
                                               │ (train/eval)     │
                                               └──────────────────┘
                                                        │
                                                        ▼
                                               ┌──────────────────┐
                                               │   DataStorage    │
                                               │(версионирование) │
                                               └──────────────────┘
```

### Компоненты

- **ETLProcessor** - Универсальная обработка данных (XLSX, CSV, JSON, JSONL, Parquet)
- **LabelerAgent** - AI-агент для классификации (PydanticAI)
- **AugmenterAgent** - Генерация синтетических данных (PydanticAI)
- **ReviewDataset** - Human-in-the-Loop с приоритизацией
- **DataWriter** - Интеллектуальная запись train/eval с балансировкой
- **DataStorage** - Git-like версионирование датасетов

---

## 📖 Документация

- **[QUICK_START_DOCKER.md](QUICK_START_DOCKER.md)** - Быстрый старт Docker
- **[README_DOCKER.md](README_DOCKER.md)** - Полная Docker документация
- **[ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)** - Подробная архитектура
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Миграция со старой версии
- **[API Docs](http://localhost:8000/docs)** - Swagger документация (после запуска)

---

## 🛠️ Управление

```bash
# Docker
docker-compose up -d          # Запуск
docker-compose down           # Остановка
docker-compose logs -f        # Логи
docker-compose restart        # Перезапуск

# Локально
python -m uvicorn src.api:app --reload  # Dev режим
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000  # Production
```

---

## 🔧 Конфигурация

Все настройки через переменные окружения (`.env` файл):

```env
# LLM
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Labeler
LABELER_BATCH_SIZE=20
LABELER_RATE_LIMIT=0.4
LABELER_LOW_CONF_THRESHOLD=0.5

# Augmenter
AUGMENTER_VARIANTS_PER_SAMPLE=3
AUGMENTER_CONCURRENCY=8

# Data Writer
DATA_WRITER_EVAL_FRACTION=0.1
DATA_WRITER_BALANCE_DOMAINS=true

# Storage
DATA_STORAGE_MAX_VERSIONS=100
```

Полный пример: `env.docker.example`

---

## 📊 Мониторинг

```bash
# Health check
curl http://localhost:8000/health

# Статистика
curl http://localhost:8000/stats

# Логи (Docker)
docker-compose logs -f ml-pipeline
```

---

## 🤝 Contributing

Приветствуются pull requests!

---

## 📄 Лицензия

MIT License

---

## 🙏 Благодарности

- [FastAPI](https://fastapi.tiangolo.com/) - современный web framework
- [PydanticAI](https://ai.pydantic.dev/) - типобезопасные AI-агенты
- [Pydantic](https://docs.pydantic.dev/) - валидация данных
- [Ollama](https://ollama.ai/) - локальные LLM модели

---

## 📞 Поддержка

- 📧 Email: your-email@example.com
- 💬 Telegram: @your_username
- 🐛 Issues: [GitHub Issues](https://github.com/your-username/esk-agent-llm-pro/issues)

---

**Built with ❤️ for Production ML**

**🐳 Backend сервис готов к работе!**

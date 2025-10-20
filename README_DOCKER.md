# 🐳 Docker Deployment Guide

Backend сервис ML Data Pipeline без UI, готовый к production.

## 🚀 Быстрый старт

### 1. Подготовка

```bash
# Скопируйте пример конфигурации
cp env.docker.example .env

# Отредактируйте .env - укажите LLM_API_KEY
nano .env
```

### 2. Запуск

```bash
# Сборка и запуск
docker-compose up -d

# Проверка логов
docker-compose logs -f ml-pipeline

# Проверка здоровья
curl http://localhost:8000/health
```

### 3. Использование API

```bash
# Swagger документация
open http://localhost:8000/docs

# Загрузка файла
curl -X POST "http://localhost:8000/upload" \
  -F "file=@logs.xlsx"

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
  -d '{
    "texts": ["передать показания счетчика", "оплатить питание"]
  }'

# Список версий
curl http://localhost:8000/versions

# Скачать датасет
curl -O http://localhost:8000/download/train/v1.0.0
```

## 📋 API Endpoints

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/` | GET | Главная страница API |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger документация |
| `/upload` | POST | Загрузка файла |
| `/process` | POST | Полная обработка логов |
| `/classify` | POST | Классификация текстов |
| `/versions` | GET | Список версий |
| `/versions/{tag}` | GET | Инфо о версии |
| `/download/train/{tag}` | GET | Скачать train |
| `/download/eval/{tag}` | GET | Скачать eval |
| `/stats` | GET | Статистика компонентов |

## 🔧 Конфигурация

### OpenAI (по умолчанию)

```env
LLM_API_KEY=sk-...
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### Ollama (локально)

```yaml
# В docker-compose.yml раскомментируйте:
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

## 📊 Monitoring

```bash
# Логи
docker-compose logs -f

# Статистика
curl http://localhost:8000/stats

# Health check
curl http://localhost:8000/health
```

## 🛠️ Управление

```bash
# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Обновление образа
docker-compose build --no-cache
docker-compose up -d

# Просмотр логов
docker-compose logs -f ml-pipeline
```

## 📁 Volumes

```
./data - данные сервиса
├── artifacts/ - train/eval датасеты
├── storage/ - версионированные датасеты
├── uploads/ - загруженные файлы
└── llm_cache/ - кэш LLM
```

## 🚨 Troubleshooting

### Ошибка подключения к LLM

```bash
# Проверьте конфигурацию
docker-compose exec ml-pipeline env | grep LLM

# Проверьте логи
docker-compose logs ml-pipeline | grep -i error
```

### Порт занят

```yaml
# Измените порт в docker-compose.yml:
ports:
  - "8080:8000"  # вместо 8000:8000
```

## 🎯 Production Tips

1. **Используйте .env для секретов** (не коммитьте .env)
2. **Настройте reverse proxy** (nginx/traefik)
3. **Добавьте мониторинг** (Prometheus/Grafana)
4. **Регулярно backup data/** директории
5. **Настройте log rotation**

## 📚 Примеры

### Python Client

```python
import requests

# Upload file
with open("logs.xlsx", "rb") as f:
    response = requests.post(
        "http://localhost:8000/upload",
        files={"file": f}
    )
file_path = response.json()["path"]

# Process
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
print(f"Version: {result['version_tag']}")
```

### Bash Script

```bash
#!/bin/bash

# Upload
RESPONSE=$(curl -s -X POST "http://localhost:8000/upload" \
  -F "file=@logs.xlsx")

FILE_PATH=$(echo $RESPONSE | jq -r '.path')

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

**🐳 Backend сервис готов к работе!**


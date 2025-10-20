# ⚡ Быстрый старт Docker Backend

**Чистый backend сервис без Telegram бота - готов за 3 минуты!**

## 🚀 Запуск

```bash
# 1. Конфигурация
cp env.docker.example .env
# Отредактируйте .env - укажите LLM_API_KEY

# 2. Запуск
docker-compose up -d

# 3. Проверка
curl http://localhost:8000/health
```

**Готово! API работает на http://localhost:8000** 🎉

## 📖 Документация

Откройте http://localhost:8000/docs - интерактивная Swagger документация

## 🎯 Использование

### Обработка файла

```bash
# 1. Загрузить файл
curl -X POST "http://localhost:8000/upload" \
  -F "file=@logs.xlsx"

# 2. Обработать
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/uploads/logs.xlsx",
    "balance_domains": true,
    "augment": true,
    "create_version": true
  }'
```

### Классификация текстов

```bash
curl -X POST "http://localhost:8000/classify" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": ["передать показания счетчика"]
  }'
```

### Версии датасетов

```bash
# Список
curl http://localhost:8000/versions

# Скачать
curl -O http://localhost:8000/download/train/v1.0.0
```

## 🛠️ Управление

```bash
# Логи
docker-compose logs -f

# Остановка
docker-compose down

# Перезапуск
docker-compose restart
```

## 🌐 С Ollama (бесплатно)

```bash
# 1. Раскомментируйте ollama в docker-compose.yml

# 2. В .env:
LLM_API_BASE=http://ollama:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=dummy

# 3. Запустите
docker-compose up -d

# 4. Загрузите модель (первый раз)
docker-compose exec ollama ollama pull llama3.1:8b
```

---

**Полная документация:** [README_DOCKER.md](README_DOCKER.md)


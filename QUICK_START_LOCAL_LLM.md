# ⚡ Быстрый старт с локальными LLM (Mistral + Qwen)

**Закрытый контур без внешних API - готов за 10 минут!**

---

## 🚀 Запуск (3 команды)

```bash
# 1. Конфигурация
cp docker-compose.local-llm.yml docker-compose.yml

# 2. Запуск (скачает модели при первом запуске)
docker-compose up -d

# 3. Проверка (подождите ~5 минут пока модели загрузятся)
curl http://localhost:8080/health
```

**API работает:** http://localhost:8080  
**Swagger:** http://localhost:8080/docs

---

## 🔧 Что работает

### Mistral для классификации:
```
http://localhost:8000 ← Labeler использует
```

### Qwen для генерации:
```
http://localhost:8001 ← Augmenter использует
```

### ML Pipeline:
```
http://localhost:8080 ← Ваш API
```

---

## 📊 Проверка работы

### 1. Health Check

```bash
curl http://localhost:8080/health
```

Должно быть:
```json
{
  "status": "healthy",
  "components": {
    "labeler": "ok",
    "augmenter": "ok",
    "quality_control": "ok"
  }
}
```

### 2. Тест классификации

```bash
curl -X POST "http://localhost:8080/classify" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["передать показания счетчика"]}'
```

### 3. Swagger UI

Откройте http://localhost:8080/docs в браузере

---

## ⚙️ Требования

- **Docker** с GPU support
- **NVIDIA GPU** с минимум 24GB VRAM (для 2 моделей по 7B)
- **Диск:** ~30GB свободного места (модели + кэш)

---

## 🎯 Альтернатива: Ollama (проще)

Если нет GPU или хотите проще:

```bash
# 1. В docker-compose.yml используйте Ollama:
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"

# 2. Загрузите модели
docker-compose exec ollama ollama pull mistral:7b
docker-compose exec ollama ollama pull qwen2:7b

# 3. В .env:
LLM_LABELER_API_BASE=http://ollama:11434/v1
LLM_LABELER_MODEL=mistral:7b

LLM_AUGMENTER_API_BASE=http://ollama:11434/v1
LLM_AUGMENTER_MODEL=qwen2:7b
```

---

## 📝 Логи

```bash
# Все сервисы
docker-compose logs -f

# Только pipeline
docker-compose logs -f ml-pipeline

# Только LLM
docker-compose logs -f llm-labeler llm-augmenter
```

---

## 🎉 Готово!

**Локальные модели работают в закрытом контуре!** 🔒

**Полная документация:** [LOCAL_LLM_SETUP.md](LOCAL_LLM_SETUP.md)


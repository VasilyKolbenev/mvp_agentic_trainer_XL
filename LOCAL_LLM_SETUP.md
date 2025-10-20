# 🌐 Настройка локальных LLM в закрытом контуре

Руководство по развертыванию Mistral, Qwen и других моделей для работы с pipeline.

---

## 🎯 Архитектура закрытого контура

```
┌─────────────────────────────────────────────────┐
│         Закрытый контур (внутренняя сеть)        │
│                                                  │
│  ┌──────────────┐         ┌─────────────────┐  │
│  │ ML Pipeline  │────────▶│ LLM Instance    │  │
│  │   (API)      │  HTTP   │ (Mistral/Qwen)  │  │
│  └──────────────┘         └─────────────────┘  │
│        ↓                                         │
│  ┌──────────────┐                               │
│  │ Data Storage │                               │
│  └──────────────┘                               │
└─────────────────────────────────────────────────┘
```

**Нет внешних API calls!** Всё работает внутри вашей инфраструктуры.

---

## 🚀 Варианты развертывания

### Вариант 1: vLLM (рекомендуется для production)

**Преимущества:**
- ✅ Высокая производительность
- ✅ Batch processing из коробки
- ✅ OpenAI-совместимый API
- ✅ Легко масштабируется

#### Развертывание:

```bash
# Установка
pip install vllm

# Запуск Mistral
python -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.2 \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype float16 \
  --max-model-len 8192

# Запуск Qwen
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2-7B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype float16 \
  --max-model-len 8192
```

#### Docker для vLLM:

```yaml
# docker-compose.yml
services:
  vllm-mistral:
    image: vllm/vllm-openai:latest
    command: >
      --model mistralai/Mistral-7B-Instruct-v0.2
      --host 0.0.0.0
      --port 8000
    ports:
      - "8000:8000"
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  vllm-qwen:
    image: vllm/vllm-openai:latest
    command: >
      --model Qwen/Qwen2-7B-Instruct
      --host 0.0.0.0
      --port 8001
    ports:
      - "8001:8001"
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  ml-pipeline:
    build: .
    ports:
      - "8080:8000"
    environment:
      # Labeler использует Mistral
      - LLM_LABELER_API_BASE=http://vllm-mistral:8000/v1
      - LLM_LABELER_MODEL=mistralai/Mistral-7B-Instruct-v0.2
      - LLM_LABELER_API_KEY=dummy
      
      # Augmenter использует Qwen
      - LLM_AUGMENTER_API_BASE=http://vllm-qwen:8001/v1
      - LLM_AUGMENTER_MODEL=Qwen/Qwen2-7B-Instruct
      - LLM_AUGMENTER_API_KEY=dummy
    depends_on:
      - vllm-mistral
      - vllm-qwen
```

---

### Вариант 2: Ollama (проще для dev/test)

**Преимущества:**
- ✅ Простая установка
- ✅ Удобное управление моделями
- ✅ GUI опционально

#### Развертывание:

```bash
# Установка
curl -fsSL https://ollama.ai/install.sh | sh

# Запуск сервера
ollama serve

# Загрузка моделей
ollama pull mistral:7b
ollama pull qwen2:7b

# Проверка
ollama list
```

#### Docker для Ollama:

```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
  
  ml-pipeline:
    build: .
    ports:
      - "8080:8000"
    environment:
      # Используем Ollama для всего
      - LLM_API_BASE=http://ollama:11434/v1
      - LLM_MODEL=mistral:7b
      - LLM_API_KEY=dummy
      
      # Или разные модели:
      - LLM_LABELER_API_BASE=http://ollama:11434/v1
      - LLM_LABELER_MODEL=mistral:7b
      - LLM_LABELER_API_KEY=dummy
      
      - LLM_AUGMENTER_API_BASE=http://ollama:11434/v1
      - LLM_AUGMENTER_MODEL=qwen2:7b
      - LLM_AUGMENTER_API_KEY=dummy
    depends_on:
      - ollama

volumes:
  ollama_data:
```

После запуска:
```bash
# Загрузка моделей в контейнер
docker-compose exec ollama ollama pull mistral:7b
docker-compose exec ollama ollama pull qwen2:7b
```

---

### Вариант 3: Text Generation WebUI (GUI + API)

**Преимущества:**
- ✅ Веб-интерфейс для управления
- ✅ Много параметров настройки
- ✅ Поддержка разных форматов моделей

#### Развертывание:

```bash
# Клонирование
git clone https://github.com/oobabooga/text-generation-webui
cd text-generation-webui

# Установка
pip install -r requirements.txt

# Загрузка модели (через веб-интерфейс или CLI)
python download-model.py mistralai/Mistral-7B-Instruct-v0.2

# Запуск с API
python server.py \
  --api \
  --listen \
  --model mistralai_Mistral-7B-Instruct-v0.2
```

Конфигурация:
```env
LLM_API_BASE=http://localhost:5000/v1
LLM_MODEL=mistralai_Mistral-7B-Instruct-v0.2
LLM_API_KEY=dummy
```

---

## 🔧 Конфигурация для pipeline

### .env для закрытого контура:

```env
# ========== Для vLLM ==========

# Labeler - Mistral (классификация)
LLM_LABELER_API_BASE=http://your-vllm-server:8000/v1
LLM_LABELER_MODEL=mistralai/Mistral-7B-Instruct-v0.2
LLM_LABELER_API_KEY=dummy

# Augmenter - Qwen (генерация)
LLM_AUGMENTER_API_BASE=http://your-vllm-server:8001/v1
LLM_AUGMENTER_MODEL=Qwen/Qwen2-7B-Instruct
LLM_AUGMENTER_API_KEY=dummy

# ========== Для Ollama ==========

# Обе задачи через одну модель
LLM_API_BASE=http://your-ollama-server:11434/v1
LLM_MODEL=mistral:7b
LLM_API_KEY=dummy

# Или разные модели:
LLM_LABELER_API_BASE=http://your-ollama-server:11434/v1
LLM_LABELER_MODEL=mistral:7b

LLM_AUGMENTER_API_BASE=http://your-ollama-server:11434/v1
LLM_AUGMENTER_MODEL=qwen2:7b

# ========== Параметры для локальных моделей ==========

# Увеличиваем rate limit (локально быстрее)
LABELER_RATE_LIMIT=0.2
AUGMENTER_RATE_LIMIT=0.05

# Увеличиваем batch size
LABELER_BATCH_SIZE=50

# Увеличиваем concurrency
AUGMENTER_CONCURRENCY=16
```

---

## 🎯 Рекомендуемые модели для задач

### Для Labeler (классификация):

| Модель | Размер | Скорость | Качество | Рекомендация |
|--------|--------|----------|----------|--------------|
| **Mistral-7B-Instruct-v0.2** | 7B | ⚡⚡⚡ | ⭐⭐⭐⭐ | ✅ Лучший выбор |
| **Qwen2-7B-Instruct** | 7B | ⚡⚡⚡ | ⭐⭐⭐⭐ | ✅ Отлично для русского |
| **Llama-3.1-8B-Instruct** | 8B | ⚡⚡ | ⭐⭐⭐⭐⭐ | ✅ Высокое качество |
| **Phi-3-mini** | 3.8B | ⚡⚡⚡⚡ | ⭐⭐⭐ | 💡 Если мало ресурсов |

### Для Augmenter (генерация):

| Модель | Размер | Креативность | Качество | Рекомендация |
|--------|--------|--------------|----------|--------------|
| **Qwen2-7B-Instruct** | 7B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Лучший для генерации |
| **Mistral-7B-Instruct-v0.2** | 7B | ⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ Хороший баланс |
| **Llama-3.1-8B-Instruct** | 8B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Высокое качество |

---

## 🔒 Безопасность в закрытом контуре

### 1. Изолированная сеть Docker

```yaml
# docker-compose.yml
networks:
  internal:
    driver: bridge
    internal: true  # Нет выхода в интернет!

services:
  vllm-mistral:
    networks:
      - internal
  
  ml-pipeline:
    networks:
      - internal
    # Только этот сервис имеет доступ наружу (если нужно)
    ports:
      - "8080:8000"
```

### 2. Без внешних зависимостей

```env
# НЕТ OpenAI API
# НЕТ внешних сервисов
# ВСЁ работает внутри контура

LLM_LABELER_API_BASE=http://vllm-mistral:8000/v1
LLM_AUGMENTER_API_BASE=http://vllm-qwen:8001/v1
```

### 3. Firewall правила

```bash
# Разрешаем только внутренние подключения
iptables -A INPUT -s 172.16.0.0/12 -j ACCEPT  # Docker сеть
iptables -A INPUT -j DROP  # Остальное блокируем
```

---

## ⚙️ Полная конфигурация для закрытого контура

### docker-compose.yml (production):

```yaml
version: '3.8'

networks:
  ml-network:
    driver: bridge
    internal: false  # true если полная изоляция

services:
  # Mistral для классификации
  llm-labeler:
    image: vllm/vllm-openai:latest
    container_name: llm-labeler
    command: >
      --model mistralai/Mistral-7B-Instruct-v0.2
      --host 0.0.0.0
      --port 8000
      --dtype float16
      --max-model-len 8192
      --gpu-memory-utilization 0.9
    ports:
      - "8000:8000"  # Только для внутренней сети
    volumes:
      - huggingface_cache:/root/.cache/huggingface
    networks:
      - ml-network
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  # Qwen для аугментации
  llm-augmenter:
    image: vllm/vllm-openai:latest
    container_name: llm-augmenter
    command: >
      --model Qwen/Qwen2-7B-Instruct
      --host 0.0.0.0
      --port 8001
      --dtype float16
      --max-model-len 8192
      --gpu-memory-utilization 0.9
    ports:
      - "8001:8001"  # Только для внутренней сети
    volumes:
      - huggingface_cache:/root/.cache/huggingface
    networks:
      - ml-network
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  # ML Pipeline
  ml-pipeline:
    build: .
    container_name: ml-pipeline
    ports:
      - "8080:8000"  # Единственный внешний порт
    environment:
      # Labeler → Mistral
      - LLM_LABELER_API_BASE=http://llm-labeler:8000/v1
      - LLM_LABELER_MODEL=mistralai/Mistral-7B-Instruct-v0.2
      - LLM_LABELER_API_KEY=dummy
      
      # Augmenter → Qwen
      - LLM_AUGMENTER_API_BASE=http://llm-augmenter:8001/v1
      - LLM_AUGMENTER_MODEL=Qwen/Qwen2-7B-Instruct
      - LLM_AUGMENTER_API_KEY=dummy
      
      # Оптимизация для локальных моделей
      - LABELER_BATCH_SIZE=50
      - LABELER_RATE_LIMIT=0.1
      - AUGMENTER_CONCURRENCY=16
      - AUGMENTER_RATE_LIMIT=0.05
      
      # Quality Control
      - QC_MIN_COSINE_SIMILARITY=0.3
      - QC_MAX_COSINE_SIMILARITY=0.95
      - QC_STRICT_MODE=true
      
      # Cache
      - CACHE_TTL_HOURS=168  # 7 дней для локальных моделей
      - CACHE_ENABLED=true
      
      # App
      - APP_MODE=production
      - APP_LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
    networks:
      - ml-network
    depends_on:
      llm-labeler:
        condition: service_healthy
      llm-augmenter:
        condition: service_healthy
    restart: unless-stopped

volumes:
  huggingface_cache:
    driver: local
```

---

## 🚀 Запуск закрытого контура

### 1. Подготовка

```bash
# Создайте директорию проекта
cd /path/to/esk-agent-llm-pro

# Скопируйте конфигурацию
cp env.docker.example .env
```

### 2. Конфигурация `.env`:

```env
# НЕТ OpenAI API!
# Только локальные модели

# Labeler - Mistral
LLM_LABELER_API_BASE=http://llm-labeler:8000/v1
LLM_LABELER_MODEL=mistralai/Mistral-7B-Instruct-v0.2
LLM_LABELER_API_KEY=dummy

# Augmenter - Qwen
LLM_AUGMENTER_API_BASE=http://llm-augmenter:8001/v1
LLM_AUGMENTER_MODEL=Qwen/Qwen2-7B-Instruct
LLM_AUGMENTER_API_KEY=dummy

# Оптимизация для локальных
LABELER_BATCH_SIZE=50
LABELER_RATE_LIMIT=0.1
AUGMENTER_CONCURRENCY=16
CACHE_TTL_HOURS=168
```

### 3. Запуск

```bash
# Первый запуск - скачает модели (может занять время)
docker-compose up -d

# Логи
docker-compose logs -f

# Проверка
curl http://localhost:8080/health
```

### 4. Проверка моделей

```bash
# Mistral
curl http://localhost:8000/v1/models

# Qwen
curl http://localhost:8001/v1/models

# Pipeline
curl http://localhost:8080/health
```

---

## 📊 Производительность

### Ожидаемая скорость (7B модели на GPU):

| Операция | vLLM | Ollama | Примечание |
|----------|------|--------|------------|
| Классификация 1 текста | ~0.5s | ~1s | Mistral |
| Batch 50 текстов | ~10s | ~25s | Параллельно |
| Генерация 3 вариантов | ~2s | ~4s | Qwen |
| Обработка 1000 логов | ~5 мин | ~12 мин | Полный pipeline |

### Оптимизация:

```env
# Для максимальной скорости (vLLM)
LABELER_BATCH_SIZE=100
LABELER_RATE_LIMIT=0.05
AUGMENTER_CONCURRENCY=32
AUGMENTER_RATE_LIMIT=0.02

# Для экономии памяти (Ollama)
LABELER_BATCH_SIZE=20
LABELER_RATE_LIMIT=0.3
AUGMENTER_CONCURRENCY=4
```

---

## 🎯 Рекомендации для production

### 1. Разделение моделей

```
Labeler  → Mistral-7B  (быстрая, точная для classification)
Augmenter → Qwen2-7B   (креативная для generation)
```

**Почему разные:**
- Классификация требует **точности**
- Генерация требует **креативности**

### 2. GPU требования

| Setup | Модели | GPU | VRAM |
|-------|--------|-----|------|
| Минимальный | 1 × 7B | 1 × RTX 3090 | 24GB |
| Рекомендуемый | 2 × 7B | 2 × RTX 3090 | 48GB |
| Оптимальный | 2 × 13B | 2 × A100 | 80GB |

### 3. Кэширование

```env
# Агрессивное кэширование для локальных моделей
CACHE_TTL_HOURS=168  # 7 дней
CACHE_ENABLED=true

# Экономия:
# - 1000 логов → ~500 LLM calls (50% cache hit)
# - Повторная обработка → ~900 cache hits (90%)
```

---

## 🔍 Мониторинг

### Метрики для отслеживания:

```bash
# Статистика pipeline
curl http://localhost:8080/stats

{
  "labeler": {
    "total_processed": 5000,
    "cache_hits": 2500,
    "llm_calls": 2500,
    "cache_hit_rate": 0.50,
    "avg_latency": 0.52  # секунды
  },
  "quality_control": {
    "passed": 4200,
    "pass_rate": 0.84,
    "rejected_low_similarity": 300,
    "rejected_high_similarity": 150
  }
}
```

### Логи vLLM:

```bash
# Производительность Mistral
docker-compose logs llm-labeler | grep "throughput"

# Производительность Qwen
docker-compose logs llm-augmenter | grep "throughput"
```

---

## 🧪 Тестирование в закрытом контуре

### 1. Проверка изоляции

```bash
# Внутри контейнера ml-pipeline НЕ должно быть доступа к интернету
docker-compose exec ml-pipeline ping -c 1 google.com
# Ожидаем: Network is unreachable (если internal: true)

# Но должен быть доступ к локальным LLM
docker-compose exec ml-pipeline curl http://llm-labeler:8000/health
# Ожидаем: {"status": "ok"}
```

### 2. Тест производительности

```bash
# Запуск с тестовыми данными (100 логов)
time curl -X POST "http://localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/uploads/logs_100.csv",
    "augment": true,
    "create_version": true
  }'

# Ожидаемое время:
# vLLM: ~30-60 секунд
# Ollama: ~2-3 минуты
```

---

## 📝 Checklist для production

- [ ] vLLM серверы запущены и доступны
- [ ] Модели загружены (Mistral + Qwen)
- [ ] Pipeline подключается к локальным LLM
- [ ] Health checks проходят
- [ ] Тест классификации работает
- [ ] Тест аугментации работает
- [ ] Quality Control фильтрует корректно
- [ ] Нет внешних API calls (проверено логами)
- [ ] Кэширование работает
- [ ] Версионирование создает версии
- [ ] Производительность приемлемая

---

## 🎉 Готовый docker-compose для закрытого контура

Создал полную конфигурацию выше - просто скопируйте в `docker-compose.yml`.

### Запуск:

```bash
# 1. Подготовка
cp env.docker.example .env
# Отредактируйте .env (используйте локальные настройки)

# 2. Первый запуск (скачает модели)
docker-compose up -d

# 3. Ждем пока модели загрузятся (~10-20 мин)
docker-compose logs -f llm-labeler
# Дождитесь: "Application startup complete"

# 4. Проверка
curl http://localhost:8080/health

# 5. Тест
python test_pipeline.py
```

---

## 🚀 Преимущества локального контура

✅ **Безопасность** - данные не покидают инфраструктуру  
✅ **Скорость** - нет сетевой задержки  
✅ **Стоимость** - бесплатно после развертывания  
✅ **Контроль** - полный контроль над моделями  
✅ **Приватность** - никаких внешних API  
✅ **Масштабируемость** - добавляйте GPU по мере роста  

---

**Ваш закрытый контур готов! 🔒✨**


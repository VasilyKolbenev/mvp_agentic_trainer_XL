# Multi-stage build для оптимизации размера образа

# Stage 1: Builder
FROM python:3.10-slim as builder

WORKDIR /app

# Установка системных зависимостей для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.10-slim

WORKDIR /app

# Копируем установленные пакеты из builder
COPY --from=builder /root/.local /root/.local

# Обновляем PATH
ENV PATH=/root/.local/bin:$PATH

# Копируем исходный код
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY config.example.v2 ./config.example

# Создаем директории для данных
RUN mkdir -p data/artifacts data/storage/versions data/uploads data/hitl data/llm_cache

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV APP_MODE=production
ENV APP_DATA_DIR=/app/data

# Expose порт
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Запуск сервиса
CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]


# 🗄️ Интеграция с ClickHouse (ECK_Logs)

**Подключение к ClickHouse для автоматической выгрузки логов ESK**

---

## 🏗️ Полная архитектура с ClickHouse

```
┌─────────────────────────────────────────────────────────┐
│              Закрытый контур (ваша сеть)                 │
│                                                          │
│  ┌──────────────┐                                        │
│  │  ECK_Logs    │ Логи контакт-центра                   │
│  │ (ClickHouse) │                                        │
│  └──────┬───────┘                                        │
│         │ SQL Export                                     │
│         ▼                                                │
│  ┌──────────────┐                                        │
│  │  API Service │ FastAPI + ClickHouse Connector        │
│  │  (FastAPI)   │                                        │
│  └──────┬───────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌──────────────────────────────────────────┐          │
│  │     ML Data Pipeline                      │          │
│  │  ETL → Labeler → Augmenter → QC → ...    │          │
│  └──────┬───────────────────────────────────┘          │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐         ┌──────────────┐             │
│  │ LLM Mistral  │         │  LLM Qwen    │             │
│  │ (Labeler)    │         │ (Augmenter)  │             │
│  └──────────────┘         └──────────────┘             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Всё работает внутри вашей инфраструктуры!** 🔒

---

## 🔧 Настройка

### 1. Конфигурация ClickHouse

В `.env` добавьте:

```env
# ===== ClickHouse (ECK_Logs) =====
CLICKHOUSE_HOST=clickhouse.your-domain.local
CLICKHOUSE_PORT=8123
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=your-secure-password
CLICKHOUSE_DATABASE=esk

# Таблица и колонки
CLICKHOUSE_TABLE=logs
CLICKHOUSE_TEXT_COLUMN=query_text
CLICKHOUSE_DOMAIN_COLUMN=domain
CLICKHOUSE_TIMESTAMP_COLUMN=created_at
CLICKHOUSE_USER_ID_COLUMN=user_id
```

---

### 2. Использование в коде

```python
from src.clickhouse_connector import ClickHouseConnector, ClickHouseConfig
from src.pipeline import ETLProcessor, LabelerAgent

# Инициализация
ch_config = ClickHouseConfig(
    host=os.getenv("CLICKHOUSE_HOST"),
    port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
    username=os.getenv("CLICKHOUSE_USERNAME"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
    database=os.getenv("CLICKHOUSE_DATABASE"),
    table_name=os.getenv("CLICKHOUSE_TABLE"),
)

connector = ClickHouseConnector(ch_config)

# Выгрузка логов за последние 7 дней
df = connector.fetch_logs(days=7, limit=10000)

# Передача в pipeline
etl = ETLProcessor()
# df уже в формате для ETL
processed_df = etl.process_file(...)  # или работаем напрямую с df

# Далее классификация
labeler = LabelerAgent(config)
results = await labeler.classify_dataframe(df)
```

---

### 3. Добавление endpoint в API

Добавьте в `src/api.py`:

```python
from .clickhouse_connector import ClickHouseConnector, ClickHouseConfig

# Глобальный коннектор
clickhouse_connector = None

def init_clickhouse():
    """Инициализация ClickHouse connector"""
    global clickhouse_connector
    
    if os.getenv("CLICKHOUSE_HOST"):
        config = ClickHouseConfig(
            host=os.getenv("CLICKHOUSE_HOST"),
            port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
            username=os.getenv("CLICKHOUSE_USERNAME", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DATABASE", "default"),
            table_name=os.getenv("CLICKHOUSE_TABLE", "esk_logs"),
        )
        
        clickhouse_connector = ClickHouseConnector(config)
        if clickhouse_connector.connect():
            logger.info("ClickHouse connector initialized")
        else:
            logger.warning("ClickHouse connection failed")

@app.on_event("startup")
async def startup_event():
    init_components()
    init_clickhouse()  # ← Добавить

# Новый endpoint
@app.post("/fetch-from-clickhouse")
async def fetch_from_clickhouse(
    days: int = 7,
    limit: Optional[int] = None,
    process: bool = True
):
    """
    Выгружает логи из ClickHouse и опционально обрабатывает.
    
    Args:
        days: количество дней для выгрузки
        limit: максимум строк
        process: сразу обработать через pipeline
    """
    
    if not clickhouse_connector:
        raise HTTPException(
            status_code=503,
            detail="ClickHouse not configured"
        )
    
    # Выгрузка
    df = clickhouse_connector.fetch_logs(days=days, limit=limit)
    
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail="No data found in ClickHouse"
        )
    
    # Сохраняем во временный файл
    temp_path = Path("data/uploads/clickhouse_export.csv")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(temp_path, index=False)
    
    response = {
        "status": "success",
        "rows_fetched": len(df),
        "file_path": str(temp_path),
    }
    
    # Опционально - сразу обработать
    if process:
        # Запускаем полный pipeline
        # ... (код из /process endpoint)
        pass
    
    return response
```

---

## 🔄 Автоматическая выгрузка (Scheduled)

### Docker Compose с cron job:

```yaml
services:
  ml-pipeline:
    # ... основной сервис
  
  clickhouse-fetcher:
    build: .
    command: python -m src.scheduled_fetcher
    environment:
      - CLICKHOUSE_HOST=clickhouse.local
      - CLICKHOUSE_DATABASE=esk
      - FETCH_INTERVAL_HOURS=6  # Каждые 6 часов
    depends_on:
      - ml-pipeline
```

### Скрипт `src/scheduled_fetcher.py`:

```python
import asyncio
import os
from datetime import datetime
from pathlib import Path

from .clickhouse_connector import ClickHouseConnector, ClickHouseConfig

async def scheduled_fetch():
    """Периодическая выгрузка из ClickHouse"""
    
    config = ClickHouseConfig(
        host=os.getenv("CLICKHOUSE_HOST"),
        port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
        username=os.getenv("CLICKHOUSE_USERNAME", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DATABASE", "esk"),
    )
    
    connector = ClickHouseConnector(config)
    interval_hours = int(os.getenv("FETCH_INTERVAL_HOURS", 6))
    
    while True:
        print(f"[{datetime.now()}] Fetching logs from ClickHouse...")
        
        # Выгрузка
        df = connector.fetch_logs(days=1, limit=10000)
        
        if not df.empty:
            # Экспорт
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = Path(f"data/uploads/clickhouse_{timestamp}.csv")
            
            connector.export_to_file(output_file, days=1, format="csv")
            
            print(f"✅ Exported {len(df)} rows to {output_file}")
            
            # TODO: Вызвать API для обработки
            # requests.post("http://ml-pipeline:8000/process", ...)
        
        # Ждем до следующей выгрузки
        await asyncio.sleep(interval_hours * 3600)

if __name__ == "__main__":
    asyncio.run(scheduled_fetch())
```

---

## 📊 Пример SQL запроса

### Таблица в ClickHouse (пример):

```sql
CREATE TABLE esk.logs (
    id UInt64,
    query_text String,
    domain Nullable(String),
    created_at DateTime,
    user_id Nullable(String),
    session_id Nullable(String),
    confidence Nullable(Float32)
) ENGINE = MergeTree()
ORDER BY created_at;
```

### Выгрузка логов:

```sql
-- Логи за последние 7 дней с существующими метками
SELECT 
    query_text as text,
    domain,
    created_at as ts,
    user_id
FROM esk.logs
WHERE created_at >= today() - 7
  AND length(query_text) > 3
ORDER BY created_at DESC
LIMIT 10000;
```

---

## 🎯 Режимы работы

### Режим 1: Ручная выгрузка

```bash
# 1. Экспортируйте из ClickHouse в CSV
clickhouse-client --query "SELECT ... FROM esk.logs" --format CSV > logs.csv

# 2. Загрузите через API
curl -X POST http://localhost:8080/upload -F "file=@logs.csv"

# 3. Обработайте
curl -X POST http://localhost:8080/process -d '{...}'
```

---

### Режим 2: Автоматический через коннектор

```bash
# API endpoint для прямой выгрузки из ClickHouse
curl -X POST "http://localhost:8080/fetch-from-clickhouse?days=7&process=true"
```

---

### Режим 3: Scheduled (автоматический)

```yaml
# docker-compose.yml с cron job
services:
  clickhouse-fetcher:
    # Автоматически выгружает каждые 6 часов
```

---

## 🔒 Безопасность

### В закрытом контуре:

```
┌──────────────────────────────────────┐
│     Внутренняя сеть (VPN/LAN)        │
│                                      │
│  ClickHouse ──▶ API ──▶ Pipeline    │
│      ▲                    │          │
│      │                    ▼          │
│  ESK Logs            LLM Models      │
│                   (Mistral/Qwen)     │
└──────────────────────────────────────┘

NO external connections! 🔐
```

### .env конфигурация:

```env
# ClickHouse (внутренний хост)
CLICKHOUSE_HOST=clickhouse.internal.local
CLICKHOUSE_PORT=8123
CLICKHOUSE_USERNAME=pipeline_user
CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}  # Из секретов

# LLM (внутренние инстансы)
LLM_LABELER_API_BASE=http://llm-mistral.internal:8000/v1
LLM_AUGMENTER_API_BASE=http://llm-qwen.internal:8001/v1
```

---

## ✅ Готово!

**ClickHouse интегрирован в архитектуру:**

- ✅ Коннектор создан (`src/clickhouse_connector.py`)
- ✅ Зависимость добавлена (`clickhouse-connect`)
- ✅ Документация обновлена
- ✅ Примеры использования
- ✅ Архитектура исправлена (ECK_Logs из ClickHouse)

**Теперь правильно: ClickHouse → API → ETL → Pipeline! 🎯**


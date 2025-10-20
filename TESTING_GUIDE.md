# 🧪 Руководство по тестированию

Несколько способов протестировать ML Data Pipeline v2.0

---

## 1️⃣ Быстрый тест компонентов (Python)

### Запуск:

```bash
python test_pipeline.py
```

### Что тестируется:

- ✅ Импорты всех зависимостей
- ✅ Конфигурация из .env
- ✅ ETL обработка
- ✅ Labeler классификация
- ✅ Quality Control (cosine + Levenshtein)
- ✅ DataWriter создание датасетов
- ✅ DataStorage версионирование

### Ожидаемый результат:

```
🧪 ML DATA PIPELINE - ТЕСТИРОВАНИЕ
====================================

✅ Все импорты успешны
✅ Конфигурация загружена
✅ ETL: обработано 3 строк
✅ Labeler: классифицировано 2 текстов
✅ Quality Control работает
✅ DataWriter: train=4, eval=1
✅ DataStorage: version v1.0.0 created

🎉 ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!
```

**Время:** ~30-60 секунд (зависит от LLM)

---

## 2️⃣ Тест API endpoints (Bash)

### Требование:
API должен быть запущен:

```bash
# Docker
docker-compose up -d

# Или локально
python -m uvicorn src.api:app
```

### Запуск тестов:

```bash
chmod +x test_api.sh
./test_api.sh
```

### Что тестируется:

- ✅ `/` - главная страница
- ✅ `/health` - health check
- ✅ `/classify` - классификация
- ✅ `/versions` - список версий
- ✅ `/stats` - статистика
- ✅ `/upload` - загрузка файла (если есть test_logs.csv)
- ✅ `/process` - полный pipeline

### Ожидаемый результат:

```
🧪 Тестирование ML Data Pipeline API

1️⃣  Проверка подключения...
✅ API доступен

Тест: Главная страница
✅ OK (HTTP 200)
{
  "service": "ESK ML Data Pipeline API",
  "version": "2.0.0",
  "status": "running"
}

Тест: Health Check
✅ OK (HTTP 200)
{
  "status": "healthy",
  "components": {
    "etl": "ok",
    "labeler": "ok",
    ...
  }
}

🎉 Тестирование завершено
```

---

## 3️⃣ Тест через Swagger UI

### Запуск:

1. Запустите API:
   ```bash
   docker-compose up -d
   ```

2. Откройте браузер:
   ```
   http://localhost:8000/docs
   ```

3. Протестируйте endpoints через интерактивный UI:
   - `POST /classify` - попробуйте классифицировать текст
   - `GET /stats` - посмотрите статистику
   - `GET /versions` - список версий

**Преимущество:** Визуальный интерфейс, можно тестировать вручную

---

## 4️⃣ Тест полного pipeline (Python скрипт)

### Создайте `test_full_flow.py`:

```python
import asyncio
import requests
from pathlib import Path

async def test_full_pipeline():
    """Тест полного pipeline через API"""
    
    base_url = "http://localhost:8000"
    
    print("🧪 Полный pipeline тест\n")
    
    # 1. Health check
    print("1️⃣  Health check...")
    r = requests.get(f"{base_url}/health")
    assert r.status_code == 200
    print(f"   ✅ {r.json()['status']}\n")
    
    # 2. Создаем тестовый файл
    print("2️⃣  Создание тестовых данных...")
    test_file = Path("test_logs.csv")
    test_file.write_text(
        "text,domain\n"
        "передать показания счетчика,house\n"
        "оплатить питание в школе,payments\n"
        "расписание метро,okc\n"
        "передать показания воды,house\n"
        "оплатить кружок,payments\n",
        encoding="utf-8"
    )
    print("   ✅ Файл создан\n")
    
    # 3. Upload
    print("3️⃣  Загрузка файла...")
    with open(test_file, "rb") as f:
        r = requests.post(f"{base_url}/upload", files={"file": f})
    
    assert r.status_code == 200
    file_path = r.json()["path"]
    print(f"   ✅ Загружено: {file_path}\n")
    
    # 4. Process (полный pipeline)
    print("4️⃣  Обработка через полный pipeline...")
    print("   (ETL → Labeler → Augmenter → QC → Labeler → DataWriter → Storage)")
    
    r = requests.post(
        f"{base_url}/process",
        json={
            "file_path": file_path,
            "max_rows": 100,
            "balance_domains": True,
            "augment": True,
            "create_version": True
        }
    )
    
    if r.status_code == 200:
        result = r.json()
        print(f"   ✅ Обработка завершена!")
        print(f"   📊 Train: {result['stats']['train_samples']}")
        print(f"   📊 Eval: {result['stats']['eval_samples']}")
        print(f"   📊 Synthetic: {result['stats']['synthetic']}")
        print(f"   📦 Version: {result['version_tag']}\n")
    else:
        print(f"   ❌ Ошибка: {r.status_code}")
        print(f"   {r.text}\n")
        return False
    
    # 5. Статистика
    print("5️⃣  Статистика компонентов...")
    r = requests.get(f"{base_url}/stats")
    assert r.status_code == 200
    
    stats = r.json()
    print(f"   📊 Labeler:")
    print(f"      Total: {stats['labeler'].get('total_processed', 0)}")
    print(f"      Cache hits: {stats['labeler'].get('cache_hits', 0)}")
    
    print(f"   📊 Quality Control:")
    print(f"      Passed: {stats['quality_control'].get('passed', 0)}")
    print(f"      Pass rate: {stats['quality_control'].get('pass_rate', 0):.2%}")
    
    print(f"   📊 Storage:")
    print(f"      Versions: {stats['storage'].get('total_versions', 0)}\n")
    
    # 6. Список версий
    print("6️⃣  Список версий...")
    r = requests.get(f"{base_url}/versions")
    versions = r.json()
    
    for v in versions[:3]:
        print(f"   📦 {v['version_tag']}: {v.get('description', 'N/A')}")
    
    print(f"\n   ✅ Всего версий: {len(versions)}\n")
    
    # Очистка
    test_file.unlink(missing_ok=True)
    
    print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    return True

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
```

### Запуск:

```bash
# 1. Запустите API
docker-compose up -d

# 2. Подождите 5 секунд

# 3. Запустите тест
python test_full_flow.py
```

---

## 5️⃣ Ручное тестирование через curl

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:
```json
{
  "status": "healthy",
  "components": {
    "etl": "ok",
    "labeler": "ok",
    "augmenter": "ok",
    "quality_control": "ok",
    "data_writer": "ok",
    "data_storage": "ok"
  }
}
```

---

### 2. Классификация текста

```bash
curl -X POST "http://localhost:8000/classify" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "передать показания счетчика",
      "оплатить питание в школе",
      "расписание метро"
    ]
  }'
```

Ожидаемый ответ:
```json
{
  "results": [
    {
      "text": "передать показания счетчика",
      "domain_id": "house",
      "confidence": 0.92,
      "top_candidates": [["house", 0.92], ["okc", 0.05], ...]
    },
    ...
  ],
  "stats": {
    "total_processed": 3,
    "cache_hits": 0,
    "llm_calls": 3
  }
}
```

---

### 3. Загрузка и обработка файла

```bash
# Создаем тестовый файл
cat > test.csv << EOF
text,domain
передать показания счетчика,house
оплатить питание,payments
расписание метро,okc
EOF

# Загружаем
curl -X POST "http://localhost:8000/upload" \
  -F "file=@test.csv"

# Ответ содержит path к файлу
# Используем его для обработки:

curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/uploads/test.csv",
    "balance_domains": true,
    "augment": true,
    "create_version": true
  }'
```

---

### 4. Статистика

```bash
curl http://localhost:8000/stats | jq '.'
```

Показывает метрики всех компонентов:
- Labeler: cache hit rate, error rate
- Augmenter: generated samples
- Quality Control: pass rate, rejections
- Storage: versions count, size

---

## 6️⃣ Тест Quality Control (Python)

### Скрипт `test_quality.py`:

```python
from src.pipeline.quality_control import QualityControl, QualityControlConfig

# Инициализация
qc = QualityControl(QualityControlConfig())

# Тестовые примеры
test_pairs = [
    ("передать показания", "передать показа"),  # Мало изменений
    ("передать показания", "подать данные"),    # ОК
    ("передать показания", "купить хлеб"),      # Другой смысл
    ("передать показания", "передать показания"), # Дубликат
]

for orig, synth in test_pairs:
    metrics = qc.compute_similarity(orig, synth)
    
    print(f"\nОригинал: {orig}")
    print(f"Синтетика: {synth}")
    print(f"Cosine: {metrics.cosine_similarity:.3f}")
    print(f"Levenshtein: {metrics.levenshtein_distance} (ratio: {metrics.levenshtein_ratio:.3f})")
    print(f"Valid: {'✅' if metrics.is_valid else '❌'}")
    if metrics.issues:
        print(f"Issues: {metrics.issues}")
```

### Запуск:

```bash
python test_quality.py
```

---

## 7️⃣ Docker тест

### Полный тест в Docker:

```bash
# 1. Сборка
docker-compose build

# 2. Запуск
docker-compose up -d

# 3. Логи
docker-compose logs -f ml-pipeline

# Должно быть:
# ✅ LabelerAgent initialized
# ✅ AugmenterAgent initialized
# ✅ QualityControl initialized
# ✅ DataWriter initialized
# ✅ DataStorage initialized

# 4. Health check
curl http://localhost:8000/health

# 5. Тест API
./test_api.sh

# 6. Остановка
docker-compose down
```

---

## 8️⃣ Тест с Ollama (локальная модель)

### Настройка:

```bash
# 1. В docker-compose.yml раскомментируйте ollama сервис

# 2. В .env:
LLM_API_BASE=http://ollama:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=dummy

# 3. Запуск
docker-compose up -d

# 4. Загрузка модели (первый раз)
docker-compose exec ollama ollama pull llama3.1:8b

# 5. Проверка
docker-compose exec ollama ollama list

# 6. Тест классификации
curl -X POST "http://localhost:8000/classify" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["передать показания"]}'
```

**Работает бесплатно!** 🆓

---

## 9️⃣ Интеграционный тест (полный workflow)

### Создайте `test_integration.py`:

```python
import asyncio
from pathlib import Path
from src.pipeline import *
from src.config_v2 import Settings

async def integration_test():
    """Полный интеграционный тест"""
    
    settings = Settings.load()
    
    print("🧪 Интеграционный тест pipeline\n")
    
    # Создаем тестовый датасет
    test_file = Path("integration_test.csv")
    test_file.write_text(
        "text,domain\n"
        "передать показания счетчика,house\n"
        "передать показания воды,house\n"
        "передать показания электричества,house\n"
        "оплатить питание в школе,payments\n"
        "оплатить кружок,payments\n"
        "расписание метро,okc\n"
        "график автобусов,okc\n",
        encoding="utf-8"
    )
    
    # ШАГИ PIPELINE:
    
    # 1. ETL
    print("1️⃣  ETL...")
    etl = ETLProcessor(ETLConfig())
    df = etl.process_file(test_file)
    assert len(df) == 7
    print(f"   ✅ {len(df)} строк\n")
    
    # 2. Labeler - валидация
    print("2️⃣  Labeler - валидация существующих меток...")
    labeler = LabelerAgent(LabelerConfig(**settings.get_labeler_llm_config()))
    results = await labeler.classify_dataframe(df)
    
    # Валидация
    qc = QualityControl(QualityControlConfig())
    original_items = [
        {"text": row["text"], "domain_id": row["domain"]}
        for _, row in df.iterrows()
    ]
    validation = await qc.validate_existing_labels(original_items, labeler)
    
    correct = sum(1 for v in validation if v.is_correct)
    print(f"   ✅ Валидация: {correct}/{len(validation)} корректных\n")
    
    # 3. Augmenter
    print("3️⃣  Augmenter - генерация...")
    augmenter = AugmenterAgent(AugmenterConfig(
        **settings.get_augmenter_llm_config(),
        variants_per_sample=2
    ))
    
    high_conf = [r.dict() for r in results if r.confidence >= 0.7][:3]
    synthetic = await augmenter.augment_batch(high_conf)
    print(f"   ✅ {len(synthetic)} синтетических примеров\n")
    
    # 4. Quality Control
    print("4️⃣  Quality Control...")
    validated_synthetic = await qc.validate_and_label_synthetic(
        [s.dict() for s in synthetic],
        high_conf,
        labeler
    )
    
    pass_rate = len(validated_synthetic) / len(synthetic) if synthetic else 0
    print(f"   ✅ {len(validated_synthetic)}/{len(synthetic)} прошло (pass rate: {pass_rate:.1%})\n")
    
    # 5. DataWriter
    print("5️⃣  DataWriter...")
    all_items = [r.dict() for r in results] + validated_synthetic
    
    writer = DataWriter(DataWriterConfig(
        output_dir=Path("test_int_output")
    ))
    train_p, eval_p, stats = writer.write_datasets(all_items)
    print(f"   ✅ Train: {stats.train_samples}, Eval: {stats.eval_samples}\n")
    
    # 6. DataStorage
    print("6️⃣  DataStorage...")
    storage = DataStorage(DataStorageConfig(
        storage_dir=Path("test_int_storage")
    ))
    
    from src.pipeline.data_storage import VersionStatus
    version = storage.commit_version(
        train_p, eval_p,
        description="Integration test",
        status=VersionStatus.DRAFT
    )
    print(f"   ✅ Version: {version.version_tag}\n")
    
    # Очистка
    import shutil
    test_file.unlink()
    shutil.rmtree("test_int_output", ignore_errors=True)
    shutil.rmtree("test_int_storage", ignore_errors=True)
    
    print("🎉 ИНТЕГРАЦИОННЫЙ ТЕСТ УСПЕШЕН!")
    return True

asyncio.run(integration_test())
```

---

## 🔟 Checklist перед production

- [ ] `python test_pipeline.py` - все компоненты работают
- [ ] `./test_api.sh` - все endpoints отвечают
- [ ] Swagger UI доступен и работает
- [ ] Quality Control фильтрует корректно
- [ ] Версионирование создает версии
- [ ] Логи не содержат ошибок
- [ ] Health check возвращает "healthy"
- [ ] Docker образ собирается без ошибок
- [ ] Тест с реальными данными прошел успешно

---

## 📊 Ожидаемые метрики

### После обработки 100 логов:

```json
{
  "labeler": {
    "total_processed": 100,
    "cache_hits": 0,
    "llm_calls": 100,
    "low_confidence_count": 15
  },
  "quality_control": {
    "total_validated": 210,
    "passed": 175,
    "pass_rate": 0.83,
    "rejected_low_similarity": 15,
    "rejected_high_similarity": 10,
    "rejected_levenshtein": 10
  },
  "storage": {
    "total_versions": 1,
    "total_size_mb": 0.5
  }
}
```

---

## ⚠️ Troubleshooting

### API не запускается

```bash
# Проверьте .env
cat .env

# Проверьте логи
docker-compose logs ml-pipeline

# Проверьте порт
netstat -an | grep 8000
```

### LLM ошибки

```bash
# Проверьте ключ
echo $LLM_API_KEY

# Проверьте подключение
curl -I https://api.openai.com/v1/models
```

### Quality Control отклоняет всё

```bash
# Снизьте строгость в config
QC_STRICT_MODE=false
QC_MIN_COSINE_SIMILARITY=0.2
```

---

## 🎯 Рекомендации

1. **Начните с** `python test_pipeline.py` - быстро, ~1 минута
2. **Затем** Swagger UI - визуально, интерактивно
3. **Потом** `./test_api.sh` - полное покрытие endpoints
4. **Финально** тест с реальными данными

---

**Успешного тестирования! 🧪✨**


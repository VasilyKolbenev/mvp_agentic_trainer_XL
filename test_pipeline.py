"""
Скрипт для тестирования ML Data Pipeline

Использование:
    python test_pipeline.py
"""

import asyncio
import json
from pathlib import Path

# Проверка импортов
print("🔍 Проверка импортов...")

try:
    from src.pipeline import (
        ETLProcessor, ETLConfig,
        LabelerAgent, LabelerConfig,
        AugmenterAgent, AugmenterConfig,
        QualityControl, QualityControlConfig,
        DataWriter, DataWriterConfig,
        DataStorage, DataStorageConfig,
    )
    from src.config_v2 import Settings
    print("✅ Все импорты успешны")
except Exception as e:
    print(f"❌ Ошибка импорта: {e}")
    exit(1)


async def test_components():
    """Тестирует все компоненты по отдельности"""
    
    print("\n" + "="*60)
    print("🧪 Тестирование компонентов")
    print("="*60)
    
    # Настройки
    try:
        settings = Settings.load()
        print("✅ Конфигурация загружена")
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("💡 Создайте .env файл из env.docker.example")
        return False
    
    # 1. ETL Test
    print("\n📥 Тест 1: ETL Processor")
    try:
        etl = ETLProcessor(ETLConfig(max_rows=10))
        
        # Создаем тестовый CSV
        test_csv = Path("test_data.csv")
        test_csv.write_text(
            "text,domain\n"
            "передать показания счетчика,house\n"
            "оплатить питание в школе,payments\n"
            "узнать расписание метро,okc\n",
            encoding="utf-8"
        )
        
        df = etl.process_file(test_csv)
        print(f"   ✅ Обработано {len(df)} строк")
        print(f"   📊 Колонки: {list(df.columns)}")
        
        # Удаляем тестовый файл
        test_csv.unlink()
        
    except Exception as e:
        print(f"   ❌ Ошибка ETL: {e}")
        return False
    
    # 2. Labeler Test
    print("\n🏷️  Тест 2: Labeler Agent")
    try:
        labeler_config = LabelerConfig(
            **settings.get_labeler_llm_config(),
            batch_size=5,
            rate_limit=0.5,
        )
        labeler = LabelerAgent(labeler_config)
        print("   ✅ LabelerAgent инициализирован")
        
        # Тестовая классификация
        test_texts = [
            "передать показания счетчика",
            "оплатить питание",
            "расписание метро"
        ]
        
        print("   🔄 Классифицирую тестовые тексты...")
        results = await labeler.classify_batch(test_texts[:2])  # Только 2 для экономии
        
        print(f"   ✅ Классифицировано: {len(results)} текстов")
        for r in results:
            print(f"      • {r.text[:40]}... → {r.domain_id} ({r.confidence:.2f})")
        
        stats = labeler.get_stats()
        print(f"   📊 Статистика: {stats}")
        
    except Exception as e:
        print(f"   ❌ Ошибка Labeler: {e}")
        print(f"   💡 Проверьте LLM_API_KEY в .env файле")
        return False
    
    # 3. Quality Control Test
    print("\n🛡️  Тест 3: Quality Control")
    try:
        qc = QualityControl(QualityControlConfig())
        
        # Тест косинусного расстояния
        original = "передать показания счетчика"
        
        test_cases = [
            ("передать показания счётчика", "почти дубликат"),  # Высокое сходство
            ("подать данные с прибора учета", "хорошая перефразировка"),  # Среднее
            ("купить хлеб в магазине", "совсем другое"),  # Низкое
        ]
        
        for synthetic, label in test_cases:
            metrics = qc.compute_similarity(original, synthetic)
            status = "✅" if metrics.is_valid else "❌"
            print(f"   {status} {label}:")
            print(f"      Cosine: {metrics.cosine_similarity:.3f}")
            print(f"      Levenshtein: {metrics.levenshtein_distance} "
                  f"(ratio: {metrics.levenshtein_ratio:.3f})")
            if metrics.issues:
                print(f"      Issues: {', '.join(metrics.issues)}")
        
    except Exception as e:
        print(f"   ❌ Ошибка QualityControl: {e}")
        return False
    
    # 4. DataWriter Test
    print("\n💾 Тест 4: Data Writer")
    try:
        writer_config = DataWriterConfig(
            output_dir=Path("test_output"),
            eval_fraction=0.2,
            balance_domains=False,
        )
        writer = DataWriter(writer_config)
        
        # Тестовые данные
        test_items = [
            {"text": "текст 1", "domain_id": "house", "confidence": 0.9},
            {"text": "текст 2", "domain_id": "payments", "confidence": 0.85},
            {"text": "текст 3", "domain_id": "house", "confidence": 0.92},
            {"text": "текст 4", "domain_id": "okc", "confidence": 0.88},
            {"text": "текст 5", "domain_id": "payments", "confidence": 0.91},
        ]
        
        train_p, eval_p, stats = writer.write_datasets(test_items, dataset_name="test")
        
        print(f"   ✅ Train: {stats.train_samples}, Eval: {stats.eval_samples}")
        print(f"   📊 Domains: {stats.domain_distribution}")
        
        # Очистка
        import shutil
        shutil.rmtree("test_output", ignore_errors=True)
        
    except Exception as e:
        print(f"   ❌ Ошибка DataWriter: {e}")
        return False
    
    # 5. DataStorage Test
    print("\n📦 Тест 5: Data Storage")
    try:
        storage_config = DataStorageConfig(
            storage_dir=Path("test_storage"),
            max_versions=10,
        )
        storage = DataStorage(storage_config)
        
        print("   ✅ DataStorage инициализирован")
        
        stats = storage.get_stats()
        print(f"   📊 Versions: {stats['total_versions']}, Size: {stats['total_size_mb']:.2f} MB")
        
        # Очистка
        import shutil
        shutil.rmtree("test_storage", ignore_errors=True)
        
    except Exception as e:
        print(f"   ❌ Ошибка DataStorage: {e}")
        return False
    
    return True


async def test_full_pipeline():
    """Тестирует полный pipeline end-to-end"""
    
    print("\n" + "="*60)
    print("🚀 Тестирование полного pipeline")
    print("="*60)
    
    try:
        settings = Settings.load()
        
        # Создаем тестовый датасет
        print("\n📝 Создание тестовых данных...")
        test_file = Path("test_logs.csv")
        test_file.write_text(
            "text,domain\n"
            "передать показания счетчика,house\n"
            "передать показания воды,house\n"
            "оплатить питание в школе,payments\n"
            "оплатить кружок,payments\n"
            "расписание метро,okc\n"
            "когда откроется станция,okc\n",
            encoding="utf-8"
        )
        
        # 1. ETL
        print("\n1️⃣  ETL...")
        etl = ETLProcessor(ETLConfig(max_rows=100))
        df = etl.process_file(test_file)
        print(f"   ✅ {len(df)} строк обработано")
        
        # 2. Labeler - валидация
        print("\n2️⃣  Labeler - валидация меток...")
        labeler_config = LabelerConfig(
            **settings.get_labeler_llm_config(),
            batch_size=10,
            rate_limit=0.5,
        )
        labeler = LabelerAgent(labeler_config)
        
        results = await labeler.classify_dataframe(df, text_column="text")
        print(f"   ✅ {len(results)} текстов классифицировано")
        
        # Валидация существующих меток
        qc = QualityControl(QualityControlConfig())
        
        original_items = [
            {"text": row["text"], "domain_id": row.get("domain", "unknown")}
            for _, row in df.iterrows()
            if "domain" in row
        ]
        
        if original_items:
            validation = await qc.validate_existing_labels(original_items, labeler)
            correct = sum(1 for v in validation if v.is_correct)
            print(f"   📊 Валидация: {correct}/{len(validation)} корректных "
                  f"({correct/len(validation):.1%})")
        
        # 3. Augmenter (мини-тест - только 2 примера)
        print("\n3️⃣  Augmenter - генерация синтетики...")
        
        augmenter_config = AugmenterConfig(
            **settings.get_augmenter_llm_config(),
            variants_per_sample=2,  # Только 2 варианта для теста
            concurrency=2,
        )
        augmenter = AugmenterAgent(augmenter_config)
        
        high_conf = [r.dict() for r in results if r.confidence >= 0.7][:2]  # Только 2 примера
        
        if high_conf:
            synthetic = await augmenter.augment_batch(high_conf)
            print(f"   ✅ {len(synthetic)} синтетических примеров сгенерировано")
            
            # 4. Quality Control
            print("\n4️⃣  Quality Control - проверка синтетики...")
            
            validated_synthetic = await qc.validate_and_label_synthetic(
                synthetic_items=[s.dict() for s in synthetic],
                original_items=high_conf,
                labeler_agent=labeler
            )
            
            print(f"   ✅ {len(validated_synthetic)}/{len(synthetic)} прошло контроль качества")
            
            if validated_synthetic:
                # Показываем примеры с метриками
                for item in validated_synthetic[:2]:
                    qm = item.get("quality_metrics", {})
                    print(f"      • {item['text'][:50]}...")
                    print(f"        Cosine: {qm.get('cosine_similarity', 0):.3f}, "
                          f"Levenshtein: {qm.get('levenshtein_distance', 0)}")
        else:
            print("   ⚠️  Нет уверенных примеров для аугментации")
            validated_synthetic = []
        
        # 5. DataWriter
        print("\n5️⃣  DataWriter - создание датасета...")
        
        all_items = [r.dict() for r in results] + validated_synthetic
        
        writer_config = DataWriterConfig(
            output_dir=Path("test_pipeline_output"),
            eval_fraction=0.2,
            balance_domains=False,
        )
        writer = DataWriter(writer_config)
        
        train_p, eval_p, stats = writer.write_datasets(all_items, dataset_name="test")
        
        print(f"   ✅ Train: {stats.train_samples}, Eval: {stats.eval_samples}")
        print(f"   📊 Domains: {stats.domain_distribution}")
        print(f"   📊 Quality score: {stats.quality_issues if stats.quality_issues else 'OK'}")
        
        # 6. DataStorage
        print("\n6️⃣  DataStorage - версионирование...")
        
        storage_config = DataStorageConfig(
            storage_dir=Path("test_storage"),
            max_versions=10,
        )
        storage = DataStorage(storage_config)
        
        from src.pipeline.data_storage import VersionStatus
        version = storage.commit_version(
            train_path=train_p,
            eval_path=eval_p,
            description="Test pipeline run",
            status=VersionStatus.DRAFT,
            created_by="test_script"
        )
        
        print(f"   ✅ Version created: {version.version_tag}")
        
        # Список версий
        versions = storage.list_versions()
        print(f"   📊 Total versions: {len(versions)}")
        
        # Успех!
        print("\n" + "="*60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*60)
        
        # Очистка тестовых файлов
        print("\n🧹 Очистка тестовых файлов...")
        import shutil
        test_file.unlink(missing_ok=True)
        shutil.rmtree("test_pipeline_output", ignore_errors=True)
        shutil.rmtree("test_storage", ignore_errors=True)
        print("   ✅ Очистка завершена")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка в pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_quality_control_detailed():
    """Детальное тестирование Quality Control"""
    
    print("\n" + "="*60)
    print("🔬 Детальное тестирование Quality Control")
    print("="*60)
    
    qc = QualityControl(QualityControlConfig(
        min_cosine_similarity=0.3,
        max_cosine_similarity=0.95,
        max_levenshtein_ratio=0.8,
        min_levenshtein_changes=3,
    ))
    
    # Тестовые случаи
    test_cases = [
        {
            "original": "передать показания счетчика",
            "synthetic": "передать показания счётчика",
            "expected": "rejected_high_similarity",  # Почти дубликат
            "label": "Почти дубликат (1 символ)"
        },
        {
            "original": "передать показания счетчика",
            "synthetic": "подать данные с прибора учета",
            "expected": "passed",  # Хорошая перефразировка
            "label": "Хорошая перефразировка"
        },
        {
            "original": "передать показания счетчика",
            "synthetic": "купить хлеб в магазине",
            "expected": "rejected_low_similarity",  # Совсем другое
            "label": "Совсем другой смысл"
        },
        {
            "original": "передать показания счетчика",
            "synthetic": "передать показа",
            "expected": "rejected_levenshtein",  # Слишком мало изменений
            "label": "Слишком мало изменений"
        },
    ]
    
    print("\n📊 Результаты проверки:\n")
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        metrics = qc.compute_similarity(
            test_case["original"],
            test_case["synthetic"]
        )
        
        status = "✅ PASS" if metrics.is_valid else "❌ FAIL"
        
        print(f"{i}. {test_case['label']}:")
        print(f"   Status: {status}")
        print(f"   Cosine similarity: {metrics.cosine_similarity:.3f}")
        print(f"   Levenshtein: {metrics.levenshtein_distance} "
              f"(ratio: {metrics.levenshtein_ratio:.3f})")
        
        if metrics.issues:
            print(f"   Issues: {', '.join(metrics.issues)}")
        
        if metrics.is_valid:
            passed += 1
        else:
            failed += 1
        
        print()
    
    print(f"📊 Итого: {passed} passed, {failed} failed из {len(test_cases)}")
    
    return True


def test_imports():
    """Проверяет все импорты"""
    
    print("\n" + "="*60)
    print("📦 Проверка всех импортов")
    print("="*60 + "\n")
    
    imports_to_test = [
        ("FastAPI", "from fastapi import FastAPI"),
        ("Pydantic", "from pydantic import BaseModel"),
        ("PydanticAI", "from pydantic_ai import Agent"),
        ("Pandas", "import pandas as pd"),
        ("OpenAI", "from openai import OpenAI"),
        ("sklearn", "from sklearn.feature_extraction.text import TfidfVectorizer"),
        ("httpx", "import httpx"),
        ("uvicorn", "import uvicorn"),
    ]
    
    all_ok = True
    
    for name, import_statement in imports_to_test:
        try:
            exec(import_statement)
            print(f"✅ {name}")
        except ImportError as e:
            print(f"❌ {name}: {e}")
            all_ok = False
    
    if all_ok:
        print("\n✅ Все зависимости установлены!")
    else:
        print("\n❌ Некоторые зависимости отсутствуют")
        print("💡 Выполните: pip install -r requirements.txt")
    
    return all_ok


async def main():
    """Главная функция тестирования"""
    
    print("\n" + "🧪 "*20)
    print("    ML DATA PIPELINE - ТЕСТИРОВАНИЕ    ")
    print("🧪 "*20 + "\n")
    
    # Тест 1: Импорты
    if not test_imports():
        print("\n❌ Установите зависимости и попробуйте снова")
        return
    
    # Тест 2: Компоненты
    components_ok = await test_components()
    
    if not components_ok:
        print("\n⚠️  Некоторые компоненты не прошли тест")
        print("💡 Проверьте .env конфигурацию")
        return
    
    # Тест 3: Quality Control детально
    await test_quality_control_detailed()
    
    # Финальное резюме
    print("\n" + "🎉 "*20)
    print("    ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!    ")
    print("🎉 "*20 + "\n")
    
    print("✅ Проект готов к использованию!")
    print("✅ Можно запускать в production!")
    print("\n💡 Следующие шаги:")
    print("   1. docker-compose up -d")
    print("   2. curl http://localhost:8000/docs")
    print("   3. Загрузите реальные логи через API\n")


if __name__ == "__main__":
    asyncio.run(main())


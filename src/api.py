"""
FastAPI Backend Service для ML Data Pipeline

Обработка логов без UI, чистый backend сервис.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .pipeline import (
    ETLProcessor, ETLConfig,
    LabelerAgent, LabelerConfig,
    AugmenterAgent, AugmenterConfig,
    QualityControl, QualityControlConfig,
    ReviewDataset, ReviewDatasetConfig,
    DataWriter, DataWriterConfig,
    DataStorage, DataStorageConfig,
)
from .pipeline.labeler_validator import LabelerValidator, ValidationConfig
from .config_v2 import Settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Загружаем настройки
settings = Settings.load()

# Инициализация FastAPI
app = FastAPI(
    title="ESK ML Data Pipeline API",
    description="Backend сервис для обработки логов и создания датасетов",
    version="2.0.0"
)

# Глобальные компоненты
etl_processor = ETLProcessor(ETLConfig())
labeler_agent = None
labeler_validator = None
augmenter_agent = None
quality_control = None
data_writer = None
data_storage = None


def init_components():
    """Инициализация компонентов при старте"""
    global labeler_agent, labeler_validator, augmenter_agent, quality_control, data_writer, data_storage
    
    # Labeler
    labeler_config = LabelerConfig(
        **settings.get_labeler_llm_config(),
        batch_size=settings.labeler.batch_size,
        rate_limit=settings.labeler.rate_limit,
        low_conf_threshold=settings.labeler.low_conf_threshold,
    )
    labeler_agent = LabelerAgent(labeler_config)
    logger.info("LabelerAgent initialized")
    
    # Labeler Validator (жесткий контроль качества)
    labeler_validator = LabelerValidator(ValidationConfig(
        enable_consensus=True,
        consensus_runs=3,
        enable_rules=True,
        strict_mode=True,
        min_confidence=0.5,
        high_confidence=0.8,
    ))
    logger.info("LabelerValidator initialized")
    
    # Augmenter
    augmenter_config = AugmenterConfig(
        **settings.get_augmenter_llm_config(),
        variants_per_sample=settings.augmenter.variants_per_sample,
        concurrency=settings.augmenter.concurrency,
    )
    augmenter_agent = AugmenterAgent(augmenter_config)
    logger.info("AugmenterAgent initialized")
    
    # QualityControl
    quality_control = QualityControl(QualityControlConfig(
        min_cosine_similarity=0.3,
        max_cosine_similarity=0.95,
        max_levenshtein_ratio=0.8,
        validate_existing_labels=True,
        relabel_synthetic=True,
        strict_mode=False,
    ))
    logger.info("QualityControl initialized")
    
    # DataWriter
    data_writer = DataWriter(DataWriterConfig(
        output_dir=settings.app.data_dir / "artifacts",
        eval_fraction=settings.data_writer.eval_fraction,
        balance_domains=settings.data_writer.balance_domains,
    ))
    logger.info("DataWriter initialized")
    
    # DataStorage
    data_storage = DataStorage(DataStorageConfig(
        storage_dir=settings.app.data_dir / "storage",
        max_versions=settings.data_storage.max_versions,
    ))
    logger.info("DataStorage initialized")


@app.on_event("startup")
async def startup_event():
    """Инициализация при старте сервиса"""
    logger.info("Starting ESK ML Data Pipeline API...")
    init_components()
    logger.info("All components initialized successfully")


# ==================== Pydantic Models ====================

class ProcessRequest(BaseModel):
    """Запрос на обработку логов"""
    file_path: str = Field(..., description="Путь к файлу с логами")
    max_rows: Optional[int] = Field(None, description="Максимум строк")
    balance_domains: bool = Field(True, description="Балансировать домены")
    augment: bool = Field(True, description="Применять аугментацию")
    create_version: bool = Field(True, description="Создать версию в storage")


class ProcessResponse(BaseModel):
    """Результат обработки"""
    status: str
    message: str
    stats: dict
    train_path: Optional[str] = None
    eval_path: Optional[str] = None
    version_tag: Optional[str] = None


class ClassifyRequest(BaseModel):
    """Запрос на классификацию текстов"""
    texts: List[str] = Field(..., description="Список текстов для классификации")


class ClassifyResponse(BaseModel):
    """Результат классификации"""
    results: List[dict]
    stats: dict


class VersionInfo(BaseModel):
    """Информация о версии"""
    version_tag: str
    description: Optional[str]
    status: str
    created_at: str
    train_hash: str
    eval_hash: str


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Главная страница API"""
    return {
        "service": "ESK ML Data Pipeline API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "process": "/process",
            "classify": "/classify",
            "versions": "/versions",
        }
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "components": {
            "etl": "ok",
            "labeler": "ok" if labeler_agent else "not initialized",
            "labeler_validator": "ok" if labeler_validator else "not initialized",
            "augmenter": "ok" if augmenter_agent else "not initialized",
            "quality_control": "ok" if quality_control else "not initialized",
            "data_writer": "ok" if data_writer else "not initialized",
            "data_storage": "ok" if data_storage else "not initialized",
        }
    }


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Загрузка файла для обработки"""
    try:
        # Сохраняем файл
        upload_dir = settings.app.data_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / file.filename
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"File uploaded: {file_path}")
        
        return {
            "status": "success",
            "filename": file.filename,
            "path": str(file_path),
            "size": len(content)
        }
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process", response_model=ProcessResponse)
async def process_logs(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Полная обработка логов: ETL → Labeling → Augmentation → DataWriter → Storage
    """
    try:
        logger.info(f"Processing file: {request.file_path}")
        
        # 1. ETL
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        etl_config = ETLConfig(max_rows=request.max_rows)
        etl = ETLProcessor(etl_config)
        df = etl.process_file(file_path)
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No data to process")
        
        logger.info(f"ETL: processed {len(df)} rows")
        
        # 2. Labeling - валидация существующих меток (если есть) или новая разметка
        results = await labeler_agent.classify_dataframe(df)
        logger.info(f"Labeling: classified {len(results)} texts")
        
        # 2.1 Валидация существующей разметки (если логи уже с метками)
        if "domain" in df.columns or "label" in df.columns:
            original_items = []
            for idx, row in df.iterrows():
                original_items.append({
                    "text": row.get("text", ""),
                    "domain_id": row.get("domain") or row.get("label", "unknown")
                })
            
            validation_results = await quality_control.validate_existing_labels(
                original_items,
                labeler_agent
            )
            
            logger.info(f"Validation: checked {len(validation_results)} existing labels")
            
            # Используем валидированные домены
            for i, val_result in enumerate(validation_results):
                if i < len(results):
                    results[i].domain_true = val_result.validated_domain
        
        # 3. Augmentation (опционально)
        all_items = [r.dict() for r in results]
        synthetic_validated = []
        
        if request.augment:
            # 3.1 Генерируем синтетику из уверенных примеров
            high_conf_items = [r.dict() for r in results if r.confidence >= 0.7]
            
            synthetic = await augmenter_agent.augment_batch(high_conf_items)
            logger.info(f"Augmentation: generated {len(synthetic)} samples")
            
            # 3.2 Контроль качества синтетики (косинусное + Левенштейн)
            synthetic_validated = await quality_control.validate_and_label_synthetic(
                synthetic_items=[s.dict() for s in synthetic],
                original_items=high_conf_items,
                labeler_agent=labeler_agent
            )
            
            logger.info(
                f"Quality Control: {len(synthetic_validated)}/{len(synthetic)} synthetic samples passed "
                f"(pass rate: {len(synthetic_validated)/len(synthetic):.2%})"
            )
            
            all_items.extend(synthetic_validated)
        
        # 4. DataWriter
        writer_config = DataWriterConfig(
            output_dir=settings.app.data_dir / "artifacts",
            balance_domains=request.balance_domains,
        )
        writer = DataWriter(writer_config)
        
        train_path, eval_path, stats = writer.write_datasets(
            all_items,
            dataset_name="api_processing"
        )
        
        logger.info(f"DataWriter: train={stats.train_samples}, eval={stats.eval_samples}")
        
        # 5. Storage (опционально)
        version_tag = None
        if request.create_version:
            version = data_storage.commit_version(
                train_path=train_path,
                eval_path=eval_path,
                description=f"API processing of {file_path.name}",
                created_by="api_service"
            )
            version_tag = version.version_tag
            logger.info(f"Storage: created version {version_tag}")
        
        return ProcessResponse(
            status="success",
            message=f"Processed {len(df)} rows → {stats.train_samples} train / {stats.eval_samples} eval",
            stats={
                "total_rows": len(df),
                "classified": len(results),
                "synthetic": len(all_items) - len(results),
                "train_samples": stats.train_samples,
                "eval_samples": stats.eval_samples,
                "domain_distribution": stats.domain_distribution,
            },
            train_path=str(train_path),
            eval_path=str(eval_path),
            version_tag=version_tag
        )
    
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify", response_model=ClassifyResponse)
async def classify_texts(request: ClassifyRequest):
    """Классификация текстов"""
    try:
        results = await labeler_agent.classify_batch(request.texts)
        
        return ClassifyResponse(
            results=[r.dict() for r in results],
            stats=labeler_agent.get_stats()
        )
    
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/versions", response_model=List[VersionInfo])
async def list_versions(status: Optional[str] = None):
    """Список версий датасетов"""
    try:
        from .pipeline.data_storage import VersionStatus
        
        filter_status = None
        if status:
            filter_status = VersionStatus(status)
        
        versions = data_storage.list_versions(status=filter_status)
        
        return [
            VersionInfo(
                version_tag=v.version_tag,
                description=v.description,
                status=v.status.value,
                created_at=v.created_at.isoformat(),
                train_hash=v.train_hash or "",
                eval_hash=v.eval_hash or ""
            )
            for v in versions
        ]
    
    except Exception as e:
        logger.error(f"List versions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/versions/{version_tag}")
async def get_version(version_tag: str):
    """Информация о конкретной версии"""
    try:
        version = data_storage.get_version(version_tag)
        
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        
        return {
            "version_tag": version.version_tag,
            "description": version.description,
            "status": version.status.value,
            "created_at": version.created_at.isoformat(),
            "train_path": str(version.train_path) if version.train_path else None,
            "eval_path": str(version.eval_path) if version.eval_path else None,
            "metadata": version.metadata,
            "tags": version.tags,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get version failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/versions/{version_tag}/checkout")
async def checkout_version(version_tag: str):
    """Переключение на версию"""
    try:
        success = data_storage.checkout(version_tag)
        
        if not success:
            raise HTTPException(status_code=404, detail="Version not found")
        
        return {"status": "success", "message": f"Checked out version {version_tag}"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/train/{version_tag}")
async def download_train(version_tag: str):
    """Скачать train датасет версии"""
    try:
        version = data_storage.get_version(version_tag)
        
        if not version or not version.train_path:
            raise HTTPException(status_code=404, detail="Train dataset not found")
        
        return FileResponse(
            path=version.train_path,
            filename=f"{version_tag}_train.jsonl",
            media_type="application/jsonl"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/eval/{version_tag}")
async def download_eval(version_tag: str):
    """Скачать eval датасет версии"""
    try:
        version = data_storage.get_version(version_tag)
        
        if not version or not version.eval_path:
            raise HTTPException(status_code=404, detail="Eval dataset not found")
        
        return FileResponse(
            path=version.eval_path,
            filename=f"{version_tag}_eval.jsonl",
            media_type="application/jsonl"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Статистика всех компонентов"""
    try:
        return {
            "labeler": labeler_agent.get_stats() if labeler_agent else {},
            "labeler_validator": labeler_validator.get_stats() if labeler_validator else {},
            "augmenter": augmenter_agent.get_stats() if augmenter_agent else {},
            "quality_control": quality_control.get_stats() if quality_control else {},
            "storage": data_storage.get_stats() if data_storage else {},
        }
    
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=settings.telegram.port if hasattr(settings, 'telegram') else 8000,
        reload=settings.is_development()
    )


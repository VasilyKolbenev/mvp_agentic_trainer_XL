"""
ETL (Extract, Transform, Load) Component

Обработка входящих логов из различных источников:
- Чтение XLSX/CSV/JSON/Parquet
- Нормализация и очистка данных
- Дедупликация
- Валидация структуры
- Выходной формат: стандартизированный DataFrame
"""

from __future__ import annotations

import io
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import pandas as pd
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ETLConfig(BaseModel):
    """Конфигурация ETL процесса"""
    
    max_rows: Optional[int] = Field(None, description="Максимальное количество строк для обработки")
    deduplicate: bool = Field(True, description="Удалять дубликаты текстов")
    min_text_length: int = Field(3, description="Минимальная длина текста")
    max_text_length: int = Field(1000, description="Максимальная длина текста")
    remove_empty: bool = Field(True, description="Удалять пустые строки")
    normalize_whitespace: bool = Field(True, description="Нормализовать пробелы")
    
    @validator("min_text_length")
    def validate_min_length(cls, v):
        if v < 1:
            raise ValueError("min_text_length должен быть >= 1")
        return v


class ProcessedRecord(BaseModel):
    """Стандартизированная запись после ETL"""
    
    text: str = Field(..., description="Нормализованный текст запроса")
    ts: Optional[datetime] = Field(None, description="Временная метка")
    user_id: Optional[str] = Field(None, description="Идентификатор пользователя")
    source: str = Field("unknown", description="Источник данных")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")


class ETLProcessor:
    """
    Универсальный ETL процессор для входящих данных.
    
    Поддерживаемые форматы:
    - XLSX/XLS
    - CSV (с автодетекцией разделителя и кодировки)
    - JSON/JSONL
    - Parquet
    """
    
    # Кандидаты для колонки с текстом (в порядке приоритета)
    TEXT_COLUMN_CANDIDATES = [
        "text", "query_text", "message", "utterance", "request",
        "user_text", "question", "content", "msg", "query", "q",
    ]
    
    # Кандидаты для временной метки
    TS_COLUMN_CANDIDATES = [
        "ts", "timestamp", "time", "created_at", "datetime", "date", "dt",
    ]
    
    # Кандидаты для user_id
    USER_ID_COLUMN_CANDIDATES = [
        "user_id", "uid", "client_id", "cid", "user", "userid",
    ]
    
    def __init__(self, config: Optional[ETLConfig] = None):
        self.config = config or ETLConfig()
        self.stats = {
            "total_rows": 0,
            "processed_rows": 0,
            "filtered_rows": 0,
            "duplicates_removed": 0,
            "errors": 0,
        }
    
    def process_file(self, file_path: Path, source_name: Optional[str] = None) -> pd.DataFrame:
        """
        Обрабатывает файл и возвращает нормализованный DataFrame.
        
        Args:
            file_path: путь к файлу
            source_name: название источника (для метаданных)
            
        Returns:
            DataFrame с колонками: text, ts, user_id, source, metadata
        """
        logger.info(f"Processing file: {file_path}")
        
        # Определяем источник
        source = source_name or file_path.stem
        
        # Читаем файл
        try:
            raw_df = self._read_file(file_path)
            self.stats["total_rows"] = len(raw_df)
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            self.stats["errors"] += 1
            return pd.DataFrame(columns=["text", "ts", "user_id", "source", "metadata"])
        
        # Нормализуем колонки
        raw_df.columns = [str(c).strip().lower() for c in raw_df.columns]
        
        # Извлекаем данные
        processed_records = []
        
        for idx, row in raw_df.iterrows():
            try:
                record = self._process_row(row, source)
                if record:
                    processed_records.append(record)
            except Exception as e:
                logger.warning(f"Failed to process row {idx}: {e}")
                self.stats["errors"] += 1
                continue
        
        # Создаем DataFrame из обработанных записей
        if not processed_records:
            logger.warning("No valid records found")
            return pd.DataFrame(columns=["text", "ts", "user_id", "source", "metadata"])
        
        df = pd.DataFrame([record.dict() for record in processed_records])
        
        # Дополнительная обработка
        df = self._post_process(df)
        
        self.stats["processed_rows"] = len(df)
        self.stats["filtered_rows"] = self.stats["total_rows"] - self.stats["processed_rows"]
        
        logger.info(f"ETL Stats: {self.stats}")
        
        return df
    
    def _read_file(self, path: Path) -> pd.DataFrame:
        """Читает файл в зависимости от расширения"""
        
        suffix = path.suffix.lower()
        
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(path)
        
        elif suffix == ".csv":
            return self._read_csv_smart(path)
        
        elif suffix == ".json":
            return self._read_json(path)
        
        elif suffix == ".jsonl":
            return self._read_jsonl(path)
        
        elif suffix == ".parquet":
            return pd.read_parquet(path)
        
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    
    def _read_csv_smart(self, path: Path) -> pd.DataFrame:
        """Читает CSV с автодетекцией кодировки и разделителя"""
        
        raw_bytes = path.read_bytes()
        
        # Определяем кодировку
        encoding = self._detect_encoding(raw_bytes)
        
        # Пробуем разные разделители
        for sep in (",", ";", "\t", "|"):
            try:
                df = pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, sep=sep)
                if len(df.columns) > 1:  # Хотя бы 2 колонки
                    return df
            except Exception:
                continue
        
        # Последняя попытка: pandas сам угадывает
        return pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, engine="python")
    
    def _detect_encoding(self, data: bytes) -> str:
        """Определяет кодировку данных"""
        
        for enc in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
            try:
                data.decode(enc)
                return enc
            except UnicodeDecodeError:
                continue
        
        return "utf-8"  # fallback
    
    def _read_json(self, path: Path) -> pd.DataFrame:
        """Читает JSON файл"""
        
        try:
            # Пробуем как массив объектов
            return pd.read_json(path, orient="records")
        except ValueError:
            # Пробуем как объект с данными
            data = pd.read_json(path)
            if isinstance(data, pd.DataFrame):
                return data
            # Если это словарь, ищем ключ с данными
            for key in ["data", "records", "items", "rows"]:
                if key in data:
                    return pd.DataFrame(data[key])
            raise ValueError("Cannot parse JSON structure")
    
    def _read_jsonl(self, path: Path) -> pd.DataFrame:
        """Читает JSONL файл (JSON Lines)"""
        
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(pd.json_normalize(line))
                    except Exception:
                        continue
        
        if not records:
            raise ValueError("No valid JSON lines found")
        
        return pd.DataFrame(records)
    
    def _process_row(self, row: pd.Series, source: str) -> Optional[ProcessedRecord]:
        """Обрабатывает одну строку данных"""
        
        # Извлекаем текст
        text = self._extract_text(row)
        if not text:
            return None
        
        # Нормализуем текст
        text = self._normalize_text(text)
        
        # Валидация длины
        if len(text) < self.config.min_text_length:
            return None
        
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
        
        # Извлекаем временную метку
        ts = self._extract_timestamp(row)
        
        # Извлекаем user_id
        user_id = self._extract_user_id(row)
        
        # Собираем метаданные
        metadata = self._extract_metadata(row)
        
        return ProcessedRecord(
            text=text,
            ts=ts,
            user_id=user_id,
            source=source,
            metadata=metadata
        )
    
    def _extract_text(self, row: pd.Series) -> Optional[str]:
        """Извлекает текст из строки"""
        
        for candidate in self.TEXT_COLUMN_CANDIDATES:
            if candidate in row.index:
                value = row[candidate]
                if pd.notna(value):
                    return str(value)
        
        # Fallback: первая строковая колонка с достаточной длиной
        for col in row.index:
            value = row[col]
            if pd.notna(value) and isinstance(value, str) and len(value) >= 5:
                return value
        
        return None
    
    def _normalize_text(self, text: str) -> str:
        """Нормализует текст"""
        
        if self.config.normalize_whitespace:
            # Заменяем все виды пробелов на обычные
            text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_timestamp(self, row: pd.Series) -> Optional[datetime]:
        """Извлекает временную метку"""
        
        for candidate in self.TS_COLUMN_CANDIDATES:
            if candidate in row.index:
                value = row[candidate]
                if pd.notna(value):
                    try:
                        return pd.to_datetime(value, utc=True)
                    except Exception:
                        continue
        
        return None
    
    def _extract_user_id(self, row: pd.Series) -> Optional[str]:
        """Извлекает идентификатор пользователя"""
        
        for candidate in self.USER_ID_COLUMN_CANDIDATES:
            if candidate in row.index:
                value = row[candidate]
                if pd.notna(value):
                    return str(value)
        
        return None
    
    def _extract_metadata(self, row: pd.Series) -> Dict[str, Any]:
        """Извлекает дополнительные метаданные"""
        
        metadata = {}
        
        # Исключаем основные колонки
        excluded = set(
            self.TEXT_COLUMN_CANDIDATES + 
            self.TS_COLUMN_CANDIDATES + 
            self.USER_ID_COLUMN_CANDIDATES
        )
        
        for col in row.index:
            if col not in excluded:
                value = row[col]
                if pd.notna(value):
                    # Конвертируем в JSON-совместимый тип
                    if isinstance(value, (pd.Timestamp, datetime)):
                        metadata[col] = value.isoformat()
                    elif isinstance(value, (int, float, str, bool)):
                        metadata[col] = value
                    else:
                        metadata[col] = str(value)
        
        return metadata
    
    def _post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Пост-обработка DataFrame"""
        
        # Удаляем дубликаты
        if self.config.deduplicate:
            before = len(df)
            df = df.drop_duplicates(subset=["text"], keep="first")
            duplicates = before - len(df)
            self.stats["duplicates_removed"] = duplicates
            if duplicates > 0:
                logger.info(f"Removed {duplicates} duplicate texts")
        
        # Сортируем по временной метке если есть
        if "ts" in df.columns and df["ts"].notna().any():
            df = df.sort_values("ts")
        
        # Ограничиваем количество строк
        if self.config.max_rows and len(df) > self.config.max_rows:
            logger.info(f"Limiting to {self.config.max_rows} rows")
            df = df.head(self.config.max_rows)
        
        return df.reset_index(drop=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику обработки"""
        return self.stats.copy()


def normalize_file_to_df(path: Path, *, max_rows: int | None = None) -> pd.DataFrame:
    """
    Совместимость со старым API.
    Обрабатывает файл и возвращает DataFrame с колонкой 'text'.
    """
    config = ETLConfig(max_rows=max_rows)
    processor = ETLProcessor(config)
    df = processor.process_file(path)
    
    # Преобразуем в старый формат для обратной совместимости
    result = pd.DataFrame()
    result["text"] = df["text"]
    result["ts"] = df["ts"]
    result["user_id"] = df["user_id"]
    
    return result


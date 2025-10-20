"""
ClickHouse Connector для загрузки логов ESK

Подключение к ClickHouse и выгрузка логов для обработки в pipeline.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClickHouseConfig(BaseModel):
    """Конфигурация ClickHouse подключения"""
    
    host: str = Field(..., description="Хост ClickHouse")
    port: int = Field(8123, description="HTTP порт")
    username: str = Field("default", description="Имя пользователя")
    password: str = Field("", description="Пароль")
    database: str = Field("default", description="База данных")
    
    # Таблица с логами
    table_name: str = Field("esk_logs", description="Название таблицы с логами")
    
    # Колонки
    text_column: str = Field("text", description="Колонка с текстом запроса")
    domain_column: Optional[str] = Field("domain", description="Колонка с доменом (если есть)")
    timestamp_column: str = Field("timestamp", description="Колонка с временной меткой")
    user_id_column: Optional[str] = Field("user_id", description="Колонка с ID пользователя")


class ClickHouseConnector:
    """
    Коннектор для выгрузки логов из ClickHouse.
    
    Функции:
    - Подключение к ClickHouse
    - Выгрузка логов за период
    - Фильтрация по условиям
    - Экспорт в DataFrame для ETL
    """
    
    def __init__(self, config: ClickHouseConfig):
        self.config = config
        self.client = None
        
        # Статистика
        self.stats = {
            "total_queries": 0,
            "total_rows_fetched": 0,
            "errors": 0,
        }
    
    def connect(self):
        """Устанавливает подключение к ClickHouse"""
        
        try:
            import clickhouse_connect
            
            self.client = clickhouse_connect.get_client(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                database=self.config.database,
            )
            
            # Проверка подключения
            result = self.client.command("SELECT 1")
            
            logger.info(f"Connected to ClickHouse: {self.config.host}:{self.config.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            self.stats["errors"] += 1
            return False
    
    def fetch_logs(
        self,
        *,
        days: int = 7,
        limit: Optional[int] = None,
        where_clause: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Выгружает логи из ClickHouse.
        
        Args:
            days: количество дней для выгрузки (по умолчанию 7)
            limit: максимум строк (опционально)
            where_clause: дополнительное WHERE условие (опционально)
            
        Returns:
            DataFrame с логами
        """
        
        if not self.client:
            if not self.connect():
                return pd.DataFrame()
        
        try:
            # Строим SQL запрос
            columns = [
                f"{self.config.text_column} as text",
                f"{self.config.timestamp_column} as ts",
            ]
            
            if self.config.domain_column:
                columns.append(f"{self.config.domain_column} as domain")
            
            if self.config.user_id_column:
                columns.append(f"{self.config.user_id_column} as user_id")
            
            columns_str = ", ".join(columns)
            
            # WHERE условие
            where_parts = [
                f"{self.config.timestamp_column} >= today() - {days}"
            ]
            
            if where_clause:
                where_parts.append(where_clause)
            
            where_str = " AND ".join(where_parts)
            
            # LIMIT
            limit_str = f"LIMIT {limit}" if limit else ""
            
            # Полный запрос
            query = f"""
                SELECT {columns_str}
                FROM {self.config.database}.{self.config.table_name}
                WHERE {where_str}
                ORDER BY {self.config.timestamp_column} DESC
                {limit_str}
            """
            
            logger.info(f"Executing query: {query}")
            
            # Выполняем запрос
            df = self.client.query_df(query)
            
            logger.info(f"Fetched {len(df)} rows from ClickHouse")
            
            # Статистика
            self.stats["total_queries"] += 1
            self.stats["total_rows_fetched"] += len(df)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch logs from ClickHouse: {e}")
            self.stats["errors"] += 1
            return pd.DataFrame()
    
    def fetch_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Выгружает логи за указанный период.
        
        Args:
            start_date: начальная дата
            end_date: конечная дата
            limit: максимум строк
            
        Returns:
            DataFrame с логами
        """
        
        where_clause = (
            f"{self.config.timestamp_column} >= '{start_date.strftime('%Y-%m-%d')}' "
            f"AND {self.config.timestamp_column} < '{end_date.strftime('%Y-%m-%d')}'"
        )
        
        # Вычисляем количество дней (для основного условия ставим 0)
        return self.fetch_logs(days=0, limit=limit, where_clause=where_clause)
    
    def export_to_file(
        self,
        output_path: Path,
        days: int = 7,
        limit: Optional[int] = None,
        format: str = "csv",
    ) -> bool:
        """
        Экспортирует логи в файл.
        
        Args:
            output_path: путь для сохранения
            days: количество дней
            limit: максимум строк
            format: формат (csv, json, jsonl, parquet)
            
        Returns:
            True если успешно
        """
        
        df = self.fetch_logs(days=days, limit=limit)
        
        if df.empty:
            logger.warning("No data to export")
            return False
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == "csv":
                df.to_csv(output_path, index=False, encoding="utf-8")
            elif format == "json":
                df.to_json(output_path, orient="records", force_ascii=False, indent=2)
            elif format == "jsonl":
                df.to_json(output_path, orient="records", force_ascii=False, lines=True)
            elif format == "parquet":
                df.to_parquet(output_path, index=False)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            logger.info(f"Exported {len(df)} rows to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export: {e}")
            self.stats["errors"] += 1
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику коннектора"""
        return self.stats.copy()
    
    def close(self):
        """Закрывает подключение"""
        if self.client:
            self.client.close()
            logger.info("ClickHouse connection closed")


# Пример использования
"""
from src.clickhouse_connector import ClickHouseConnector, ClickHouseConfig

# Конфигурация
config = ClickHouseConfig(
    host="clickhouse.your-domain.local",
    port=8123,
    username="default",
    password="your-password",
    database="esk",
    table_name="logs",
    text_column="query_text",
    domain_column="domain",
    timestamp_column="created_at",
    user_id_column="user_id"
)

# Подключение
connector = ClickHouseConnector(config)

# Выгрузка логов за последние 7 дней
df = connector.fetch_logs(days=7, limit=10000)

# Экспорт в файл
connector.export_to_file(
    Path("data/uploads/logs_from_clickhouse.csv"),
    days=7,
    format="csv"
)

# Или передача напрямую в ETL
from src.pipeline import ETLProcessor

etl = ETLProcessor()
# df уже в нужном формате, можно передать в pipeline
```


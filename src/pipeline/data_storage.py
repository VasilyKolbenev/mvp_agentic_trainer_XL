"""
DataStorage Component - версионирование датасетов и артефактов

Управляет хранением и версионированием:
- Train/eval датасетов
- Промежуточных артефактов
- Моделей и чекпоинтов
- Метаданных и логов

Поддерживает:
- Семантическое версионирование (major.minor.patch)
- Git-like операции (commit, tag, checkout)
- Сравнение версий и diff
- Экспорт/импорт версий
"""

from __future__ import annotations

import json
import shutil
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class VersionStatus(str, Enum):
    """Статус версии"""
    DRAFT = "draft"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class Version(BaseModel):
    """Версия датасета"""
    
    version_id: str = Field(..., description="Уникальный ID версии")
    version_tag: str = Field(..., description="Тег версии (например, v1.2.3)")
    
    description: Optional[str] = Field(None, description="Описание версии")
    status: VersionStatus = Field(VersionStatus.DRAFT, description="Статус версии")
    
    train_path: Optional[Path] = Field(None, description="Путь к train датасету")
    eval_path: Optional[Path] = Field(None, description="Путь к eval датасету")
    
    train_hash: Optional[str] = Field(None, description="Hash train датасета")
    eval_hash: Optional[str] = Field(None, description="Hash eval датасета")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Метаданные версии")
    
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания")
    created_by: Optional[str] = Field(None, description="Создатель версии")
    
    parent_version: Optional[str] = Field(None, description="Родительская версия")
    tags: List[str] = Field(default_factory=list, description="Дополнительные теги")


class DataStorageConfig(BaseModel):
    """Конфигурация DataStorage"""
    
    storage_dir: Path = Field(..., description="Корневая директория хранилища")
    
    enable_compression: bool = Field(False, description="Сжимать датасеты")
    max_versions: int = Field(100, description="Максимум версий в хранилище", ge=1)
    auto_archive_old: bool = Field(True, description="Автоматически архивировать старые версии")


class DataStorage:
    """
    Компонент для версионирования и хранения датасетов.
    
    Структура:
    storage_dir/
        versions/
            v1.0.0/
                train.jsonl
                eval.jsonl
                metadata.json
            v1.1.0/
                ...
        current -> versions/v1.1.0  (symlink)
        versions.json  (реестр версий)
    """
    
    def __init__(self, config: DataStorageConfig):
        self.config = config
        
        # Создаем структуру директорий
        self.versions_dir = config.storage_dir / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_link = config.storage_dir / "current"
        self.registry_file = config.storage_dir / "versions.json"
        
        # Загружаем реестр версий
        self.versions: Dict[str, Version] = {}
        self._load_registry()
        
        # Текущая версия
        self.current_version: Optional[Version] = None
        self._detect_current_version()
    
    def _load_registry(self):
        """Загружает реестр версий"""
        
        if not self.registry_file.exists():
            return
        
        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for version_data in data.get("versions", []):
                version = Version(**version_data)
                self.versions[version.version_tag] = version
            
            logger.info(f"Loaded {len(self.versions)} versions from registry")
            
        except Exception as e:
            logger.error(f"Failed to load version registry: {e}")
    
    def _save_registry(self):
        """Сохраняет реестр версий"""
        
        try:
            data = {
                "versions": [v.dict(default=str) for v in self.versions.values()],
                "updated_at": datetime.now().isoformat(),
            }
            
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                
        except Exception as e:
            logger.error(f"Failed to save version registry: {e}")
    
    def _detect_current_version(self):
        """Определяет текущую версию"""
        
        if self.current_link.exists() and self.current_link.is_symlink():
            try:
                target = self.current_link.resolve()
                version_tag = target.name
                
                if version_tag in self.versions:
                    self.current_version = self.versions[version_tag]
                    logger.info(f"Current version: {version_tag}")
                    
            except Exception as e:
                logger.warning(f"Failed to detect current version: {e}")
    
    def _compute_hash(self, file_path: Path) -> str:
        """Вычисляет hash файла"""
        
        if not file_path.exists():
            return ""
        
        sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _generate_version_id(self) -> str:
        """Генерирует уникальный ID версии"""
        return hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:12]
    
    def _parse_version_tag(self, tag: str) -> Tuple[int, int, int]:
        """Парсит тег версии (v1.2.3 -> (1, 2, 3))"""
        
        tag = tag.lstrip("v")
        parts = tag.split(".")
        
        try:
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return (major, minor, patch)
        except ValueError:
            return (0, 0, 0)
    
    def _increment_version(self, current_tag: Optional[str], increment_type: str = "minor") -> str:
        """Инкрементирует версию"""
        
        if not current_tag:
            return "v1.0.0"
        
        major, minor, patch = self._parse_version_tag(current_tag)
        
        if increment_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif increment_type == "minor":
            minor += 1
            patch = 0
        elif increment_type == "patch":
            patch += 1
        else:
            minor += 1
            patch = 0
        
        return f"v{major}.{minor}.{patch}"
    
    def commit_version(
        self,
        train_path: Path,
        eval_path: Path,
        *,
        version_tag: Optional[str] = None,
        description: Optional[str] = None,
        status: VersionStatus = VersionStatus.DRAFT,
        metadata: Optional[Dict[str, Any]] = None,
        increment_type: str = "minor",
        created_by: Optional[str] = None,
    ) -> Version:
        """
        Создает новую версию датасета.
        
        Args:
            train_path: путь к train датасету
            eval_path: путь к eval датасету
            version_tag: тег версии (если не указан, автоинкремент)
            description: описание версии
            status: статус версии
            metadata: дополнительные метаданные
            increment_type: тип инкремента (major/minor/patch)
            created_by: создатель версии
            
        Returns:
            Version объект
        """
        
        # Генерируем тег версии
        if not version_tag:
            latest_tag = self._get_latest_version_tag()
            version_tag = self._increment_version(latest_tag, increment_type)
        
        # Проверяем уникальность
        if version_tag in self.versions:
            raise ValueError(f"Version {version_tag} already exists")
        
        # Создаем директорию версии
        version_dir = self.versions_dir / version_tag
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Копируем датасеты
        train_dest = version_dir / "train.jsonl"
        eval_dest = version_dir / "eval.jsonl"
        
        shutil.copy2(train_path, train_dest)
        shutil.copy2(eval_path, eval_dest)
        
        # Вычисляем хеши
        train_hash = self._compute_hash(train_dest)
        eval_hash = self._compute_hash(eval_dest)
        
        # Создаем объект версии
        version = Version(
            version_id=self._generate_version_id(),
            version_tag=version_tag,
            description=description,
            status=status,
            train_path=train_dest,
            eval_path=eval_dest,
            train_hash=train_hash,
            eval_hash=eval_hash,
            metadata=metadata or {},
            created_by=created_by,
            parent_version=self.current_version.version_tag if self.current_version else None,
        )
        
        # Сохраняем метаданные версии
        version_metadata_path = version_dir / "metadata.json"
        with open(version_metadata_path, "w", encoding="utf-8") as f:
            json.dump(version.dict(default=str), f, indent=2, ensure_ascii=False)
        
        # Добавляем в реестр
        self.versions[version_tag] = version
        self._save_registry()
        
        # Автоархивирование старых версий
        if self.config.auto_archive_old and len(self.versions) > self.config.max_versions:
            self._archive_old_versions()
        
        logger.info(f"Committed version: {version_tag}")
        
        return version
    
    def _get_latest_version_tag(self) -> Optional[str]:
        """Возвращает последнюю версию"""
        
        if not self.versions:
            return None
        
        # Сортируем по версии
        sorted_versions = sorted(
            self.versions.keys(),
            key=lambda tag: self._parse_version_tag(tag),
            reverse=True
        )
        
        return sorted_versions[0] if sorted_versions else None
    
    def checkout(self, version_tag: str) -> bool:
        """
        Переключается на указанную версию.
        
        Args:
            version_tag: тег версии
            
        Returns:
            True если успешно
        """
        
        if version_tag not in self.versions:
            logger.error(f"Version {version_tag} not found")
            return False
        
        version = self.versions[version_tag]
        version_dir = self.versions_dir / version_tag
        
        if not version_dir.exists():
            logger.error(f"Version directory not found: {version_dir}")
            return False
        
        # Обновляем symlink
        if self.current_link.exists():
            self.current_link.unlink()
        
        self.current_link.symlink_to(version_dir, target_is_directory=True)
        self.current_version = version
        
        logger.info(f"Checked out version: {version_tag}")
        
        return True
    
    def tag_version(self, version_tag: str, tag: str) -> bool:
        """
        Добавляет тег к версии (например, 'production', 'latest').
        
        Args:
            version_tag: тег версии
            tag: новый тег
            
        Returns:
            True если успешно
        """
        
        if version_tag not in self.versions:
            logger.error(f"Version {version_tag} not found")
            return False
        
        version = self.versions[version_tag]
        
        if tag not in version.tags:
            version.tags.append(tag)
            self._save_registry()
            logger.info(f"Tagged version {version_tag} with '{tag}'")
            return True
        
        return False
    
    def set_status(self, version_tag: str, status: VersionStatus) -> bool:
        """
        Устанавливает статус версии.
        
        Args:
            version_tag: тег версии
            status: новый статус
            
        Returns:
            True если успешно
        """
        
        if version_tag not in self.versions:
            logger.error(f"Version {version_tag} not found")
            return False
        
        version = self.versions[version_tag]
        version.status = status
        self._save_registry()
        
        logger.info(f"Set version {version_tag} status to {status}")
        
        return True
    
    def list_versions(
        self,
        status: Optional[VersionStatus] = None,
        tag: Optional[str] = None,
    ) -> List[Version]:
        """
        Возвращает список версий с опциональной фильтрацией.
        
        Args:
            status: фильтр по статусу
            tag: фильтр по тегу
            
        Returns:
            Список Version объектов
        """
        
        versions = list(self.versions.values())
        
        # Фильтрация
        if status:
            versions = [v for v in versions if v.status == status]
        
        if tag:
            versions = [v for v in versions if tag in v.tags]
        
        # Сортировка по времени создания (новые первые)
        versions.sort(key=lambda v: v.created_at, reverse=True)
        
        return versions
    
    def get_version(self, version_tag: str) -> Optional[Version]:
        """Возвращает версию по тегу"""
        return self.versions.get(version_tag)
    
    def compare_versions(self, version_tag1: str, version_tag2: str) -> Dict[str, Any]:
        """
        Сравнивает две версии.
        
        Args:
            version_tag1: первая версия
            version_tag2: вторая версия
            
        Returns:
            Словарь с результатами сравнения
        """
        
        v1 = self.versions.get(version_tag1)
        v2 = self.versions.get(version_tag2)
        
        if not v1 or not v2:
            return {"error": "One or both versions not found"}
        
        comparison = {
            "version1": version_tag1,
            "version2": version_tag2,
            "train_hash_match": v1.train_hash == v2.train_hash,
            "eval_hash_match": v1.eval_hash == v2.eval_hash,
            "metadata_diff": {},
        }
        
        # Сравниваем метаданные
        all_keys = set(v1.metadata.keys()) | set(v2.metadata.keys())
        
        for key in all_keys:
            val1 = v1.metadata.get(key)
            val2 = v2.metadata.get(key)
            
            if val1 != val2:
                comparison["metadata_diff"][key] = {
                    "v1": val1,
                    "v2": val2,
                }
        
        return comparison
    
    def _archive_old_versions(self):
        """Архивирует старые версии"""
        
        # Получаем версии в порядке от старых к новым
        versions_list = sorted(
            self.versions.values(),
            key=lambda v: v.created_at
        )
        
        # Оставляем max_versions самых новых
        to_archive = versions_list[:-self.config.max_versions]
        
        for version in to_archive:
            if version.status != VersionStatus.ARCHIVED:
                version.status = VersionStatus.ARCHIVED
                logger.info(f"Archived old version: {version.version_tag}")
        
        self._save_registry()
    
    def export_version(self, version_tag: str, export_dir: Path) -> bool:
        """
        Экспортирует версию в указанную директорию.
        
        Args:
            version_tag: тег версии
            export_dir: директория для экспорта
            
        Returns:
            True если успешно
        """
        
        version = self.versions.get(version_tag)
        if not version:
            logger.error(f"Version {version_tag} not found")
            return False
        
        version_dir = self.versions_dir / version_tag
        if not version_dir.exists():
            logger.error(f"Version directory not found: {version_dir}")
            return False
        
        # Копируем всю директорию
        export_path = export_dir / version_tag
        shutil.copytree(version_dir, export_path, dirs_exist_ok=True)
        
        logger.info(f"Exported version {version_tag} to {export_path}")
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику хранилища"""
        
        # Подсчет по статусам
        by_status = {}
        for status in VersionStatus:
            by_status[status.value] = sum(
                1 for v in self.versions.values() if v.status == status
            )
        
        # Размер хранилища
        total_size = 0
        for version_dir in self.versions_dir.iterdir():
            if version_dir.is_dir():
                total_size += sum(
                    f.stat().st_size for f in version_dir.rglob("*") if f.is_file()
                )
        
        return {
            "total_versions": len(self.versions),
            "current_version": self.current_version.version_tag if self.current_version else None,
            "latest_version": self._get_latest_version_tag(),
            "by_status": by_status,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }


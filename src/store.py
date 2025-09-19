# src/store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Dict, Any

import pandas as pd


class Store:
    """
    Хранилище артефактов бота.
    Структура:
      data/
        artifacts/
          chunks/               # сюда можно сливать промежуточные чанки при разметке
          logs_labeled.csv      # итоговая разметка (CSV)
          dataset_train.jsonl   # train
          dataset_eval.jsonl    # eval
          hitl_queue.jsonl      # очередь на ручное ревью
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.artifacts_dir = self.base_dir / "artifacts"
        self.chunks_dir = self.artifacts_dir / "chunks"
        self.hitl_dir = self.base_dir / "hitl"  # на будущее

        for d in [self.base_dir, self.artifacts_dir, self.chunks_dir, self.hitl_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ---------- пути ----------
    def path(self, rel: str) -> Path:
        """
        Удобный доступ к относительным путям внутри data/.
        Пример: store.path("artifacts/dataset_train.jsonl")
        """
        return (self.base_dir / rel).resolve()

    # ---------- CSV с разметкой ----------
    def save_labeled_csv(self, rows: List[Dict[str, Any]]) -> Path:
        """
        Сохраняет список словарей `rows` в artifacts/logs_labeled.csv.
        Нормализует поле top_candidates в строку (JSON), чтобы без ошибок писалось в CSV.
        Возвращает путь к файлу.
        """
        out_path = self.artifacts_dir / "logs_labeled.csv"

        norm_rows: List[Dict[str, Any]] = []
        for r in rows:
            r2 = dict(r)
            tc = r2.get("top_candidates")
            if isinstance(tc, (list, tuple, dict)):
                try:
                    r2["top_candidates"] = json.dumps(tc, ensure_ascii=False)
                except Exception:
                    r2["top_candidates"] = str(tc)
            norm_rows.append(r2)

        df = pd.DataFrame(norm_rows)

        # выведем “важные” колонки вперед, остальные — в хвосте
        preferred = ["text", "esk_domain_pred", "domain_true", "confidence", "top_candidates"]
        rest = [c for c in df.columns if c not in preferred]
        cols = [c for c in preferred if c in df.columns] + rest

        # даже если df пуст — создадим валидный CSV с заголовком
        if not df.empty:
            df = df[cols]
        else:
            df = pd.DataFrame(columns=preferred)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        return out_path

    # ---------- JSONL utility ----------
    def save_jsonl(self, name: str, items: Iterable[Dict[str, Any]]) -> Path:
        """
        Записывает jsonl в artifacts/<name>.
        Возвращает путь к файлу.
        """
        p = self.artifacts_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for it in items or []:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        return p

    # ---------- HITL очередь ----------
    def append_hitl_queue(self, items: Iterable[Dict[str, Any]]) -> Path:
        """
        Добавляет элементы в artifacts/hitl_queue.jsonl (по одному на строку).
        """
        p = self.artifacts_dir / "hitl_queue.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            for it in items or []:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        return p

    def read_hitl_queue(self, limit: int | None = None) -> List[Dict[str, Any]]:
        """
        Возвращает первые `limit` элементов из очереди (без удаления).
        Если файла нет — пустой список.
        """
        p = self.artifacts_dir / "hitl_queue.jsonl"
        if not p.exists():
            return []

        out: List[Dict[str, Any]] = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    # пропускаем битые строки
                    continue
                if limit and len(out) >= limit:
                    break
        return out

    # ---------- (необязательно) чанки промежуточных результатов ----------
    def write_chunk(self, prefix: str, idx: int, items: Iterable[Dict[str, Any]]) -> Path:
        """
        Пишет чанки в artifacts/chunks/<prefix>_<idx:04d>.jsonl
        Например: write_chunk("label", 3, rows)
        """
        p = self.chunks_dir / f"{prefix}_{idx:04d}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for it in items or []:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        return p

    def list_chunks(self, prefix: str) -> list[Path]:
        """
        Возвращает отсортированный список путей чанков по префиксу.
        """
        return sorted(self.chunks_dir.glob(f"{prefix}_*.jsonl"))

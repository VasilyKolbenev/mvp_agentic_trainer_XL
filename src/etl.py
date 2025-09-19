# src/etl.py
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

# -------- helpers --------

_CANDIDATE_TEXT_COLS = [
    "text", "query_text", "message", "utterance", "request",
    "user_text", "question", "content", "msg",
]

_TS_COLS = ["ts", "timestamp", "time", "created_at", "datetime", "date"]
_USER_COLS = ["user_id", "uid", "client_id", "cid"]


def _detect_encoding_bytes(b: bytes) -> str:
    """
    Пытаемся читать в UTF-8, если падает — пробуем cp1251.
    Без внешних либ вроде chardet.
    """
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            b.decode(enc)
            return enc
        except Exception:
            continue
    return "utf-8"


def _read_any_table(path: Path) -> pd.DataFrame:
    suf = path.suffix.lower()
    if suf in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suf in (".csv",):
        raw = path.read_bytes()
        enc = _detect_encoding_bytes(raw)
        # авто-разделитель: сначала запятая, потом ; таб
        for sep in (",", ";", "\t", "|"):
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=enc, sep=sep)
            except Exception:
                continue
        # последний шанс: пусть pandas сам угадает
        return pd.read_csv(io.BytesIO(raw), encoding=enc, engine="python")
    raise ValueError(f"Unsupported file type: {suf}")


def _pick_first_existing(cols: Iterable[str], df: pd.DataFrame) -> Optional[str]:
    for c in cols:
        if c in df.columns:
            return c
    return None


def _pick_text_column(df: pd.DataFrame) -> Optional[str]:
    # приоритет по списку
    col = _pick_first_existing(_CANDIDATE_TEXT_COLS, df)
    if col:
        return col
    # fallback: берём первый object/строковый столбец с “длинными” строками
    for c in df.columns:
        if pd.api.types.is_object_dtype(df[c]):
            try:
                sample = df[c].dropna().astype(str).head(50)
                if not sample.empty and sample.str.len().mean() >= 5:
                    return c
            except Exception:
                continue
    return None


# -------- public API --------

def normalize_file_to_df(path: Path, *, max_rows: int | None = None) -> pd.DataFrame:
    """
    Универсальная загрузка: .xlsx и .csv → нормализованный DF с колонкой `text`.
    Опционально обрезаем до max_rows.
    """
    df = _read_any_table(path)

    # нормализуем имена колонок
    df.columns = [str(c).strip().lower() for c in df.columns]

    # текст
    text_col = _pick_text_column(df)
    if not text_col:
        # пустая таблица — вернём df с нужной схемой
        return pd.DataFrame(columns=["text", "ts", "user_id"])

    out = pd.DataFrame()
    out["text"] = (
        df[text_col]
        .astype(str)
        .map(lambda s: re.sub(r"\s+", " ", s).strip())
    )
    out = out[out["text"] != ""]  # дроп пустых

    # ts (если есть)
    ts_col = _pick_first_existing(_TS_COLS, df)
    if ts_col:
        # оставим timezone-aware (UTC), чтобы не падать на astype
        out["ts"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    else:
        out["ts"] = pd.NaT

    # user_id (если есть)
    uid_col = _pick_first_existing(_USER_COLS, df)
    if uid_col:
        out["user_id"] = df[uid_col].astype(str)
    else:
        out["user_id"] = None

    if max_rows and max_rows > 0:
        out = out.head(max_rows)

    return out.reset_index(drop=True)


# совместимость со старым кодом
def normalize_xlsx_to_df(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    return normalize_file_to_df(path, max_rows=max_rows)


def save_parquet_or_csv(df: pd.DataFrame, *, base_dir: Path) -> tuple[Path, Path]:
    """
    Сохраняем нормализованные логи в data/artifacts как parquet и csv.
    Возвращаем пути (parquet_path, csv_path).
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    art = base_dir / "artifacts"
    art.mkdir(parents=True, exist_ok=True)

    p_parquet = art / "logs_norm.parquet"
    p_csv = art / "logs_norm.csv"

    try:
        df.to_parquet(p_parquet, index=False)
    except Exception:
        # если нет pyarrow/fastparquet — пропускаем
        p_parquet = art / "_skipped.parquet"

    df.to_csv(p_csv, index=False, encoding="utf-8")

    return p_parquet, p_csv


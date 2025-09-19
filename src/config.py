from __future__ import annotations
import os
from dataclasses import dataclass

# ⬇️ ВАЖНО: грузим .env из текущей папки проекта (или ближайшей вверх по дереву)
try:
    from dotenv import load_dotenv, find_dotenv  # python-dotenv
    _dotenv_path = find_dotenv(usecwd=True)
    load_dotenv(_dotenv_path or ".env", override=False)
except Exception:
    # если python-dotenv не установлен — просто пропускаем (переменные могут быть заданы в системе)
    pass


def _get_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def _get_int(name: str, default: int) -> int:
    v = os.getenv(name)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default

def _get_float(name: str, default: float) -> float:
    v = os.getenv(name)
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


@dataclass
class Settings:
    # Telegram
    bot_token: str
    public_url: str | None
    port: int

    # Global LLM
    llm_api_key: str
    llm_api_base: str
    llm_model: str

    # Role LLMs (optional)
    llm_api_key_labeler: str | None
    llm_api_base_labeler: str | None
    llm_model_labeler: str | None

    llm_api_key_augmenter: str | None
    llm_api_base_augmenter: str | None
    llm_model_augmenter: str | None

    # Behavior
    data_dir: str
    low_conf: float
    augment_include_lowconf: bool
    batch_size: int
    rate_limit: float
    max_batch: int
    log_level: str

    # Progress / sharding
    progress_chunk: int
    send_partials: bool
    shard_size: int
    row_offset: int

    @classmethod
    def load(cls) -> "Settings":
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в .env")

        return cls(
            bot_token=bot_token,
            public_url=os.getenv("PUBLIC_URL") or None,
            port=_get_int("PORT", 8080),

            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_api_base=os.getenv("LLM_API_BASE", "https://api.openai.com/v1"),
            llm_model=os.getenv("LLM_MODEL", "gpt-5-mini"),

            llm_api_key_labeler=os.getenv("LLM_API_KEY_LABELER") or None,
            llm_api_base_labeler=os.getenv("LLM_API_BASE_LABELER") or None,
            llm_model_labeler=os.getenv("LLM_MODEL_LABELER") or None,

            llm_api_key_augmenter=os.getenv("LLM_API_KEY_AUGMENTER") or None,
            llm_api_base_augmenter=os.getenv("LLM_API_BASE_AUGMENTER") or None,
            llm_model_augmenter=os.getenv("LLM_MODEL_AUGMENTER") or None,

            data_dir=os.getenv("DATA_DIR", "data"),
            low_conf=_get_float("LOW_CONF", 0.50),
            augment_include_lowconf=_get_bool("AUGMENT_INCLUDE_LOWCONF", False),
            batch_size=_get_int("BATCH_SIZE", 20),
            rate_limit=_get_float("RATE_LIMIT", 0.4),
            max_batch=_get_int("MAX_BATCH", 2000),
            log_level=os.getenv("LOG_LEVEL", "INFO"),

            progress_chunk=_get_int("PROGRESS_CHUNK", 100),
            send_partials=_get_bool("SEND_PARTIALS", True),
            shard_size=_get_int("SHARD_SIZE", 0),
            row_offset=_get_int("ROW_OFFSET", 0),
        )

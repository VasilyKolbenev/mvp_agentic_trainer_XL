from __future__ import annotations
import json, time, asyncio, re
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .llm import LLMClient
from .cache import get_cache
from .taxonomy import validate_domain, is_stop_word

RAW_LOG = Path("data/llm_raw.jsonl")

def _write_raw(payload: dict) -> None:
    try:
        RAW_LOG.parent.mkdir(parents=True, exist_ok=True)
        with RAW_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _embed_allowed(system_prompt: str, allowed_labels: List[str] | None) -> str:
    if not allowed_labels:
        return system_prompt
    bullet = "\n".join(f"- {x}" for x in allowed_labels)
    return system_prompt + "\n\nВозможные домены (label set):\n" + bullet + "\n"

def build_fewshot(system_prompt: str, fewshot: str, user_text: str, allowed_labels: List[str] | None=None) -> List[Dict[str, str]]:
    sys = _embed_allowed(system_prompt, allowed_labels)
    messages = [{"role": "system", "content": sys}]
    if fewshot:
        messages.append({"role": "user", "content": fewshot})
        messages.append({"role": "assistant", "content": "ОК"})
    messages.append({"role": "user", "content": user_text})
    return messages

def _extract_json(s: str) -> dict | None:
    # вытащим первый JSON-объект из текста
    try:
        start = s.index("{")
        end = s.rindex("}")
        return json.loads(s[start:end+1])
    except Exception:
        return None

def classify_one(
    client: LLMClient,
    system_prompt: str,
    fewshot: str,
    text: str,
    *,
    allowed_labels: List[str] | None = None,
    low_conf_threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Возвращает:
      {
        "text": ...,
        "domain_id": "house",
        "domain_true": "house" (на старте = domain_id),
        "confidence": 0.82,
        "top_candidates": [["house",0.82],["payments",0.12],...]
      }
    """
    # Проверяем стоп-слова
    if is_stop_word(text):
        return {
            "text": text,
            "domain_id": "oos",
            "domain_true": "oos", 
            "confidence": 0.95,
            "top_candidates": [["oos", 0.95]],
        }
    
    # Проверяем кэш
    cache = get_cache()
    if cache:
        cached_result = cache.get_classification(text, system_prompt, fewshot)
        if cached_result:
            return cached_result
    
    messages = build_fewshot(system_prompt, fewshot, text, allowed_labels)
    last_raw = None
    for attempt in range(3):
        # temperature=1.0 — совместимо с gpt-5-mini (без 400).
        resp = client.chat(messages, response_json=True, temperature=1.0)
        last_raw = resp
        data = None
        try:
            # если библиотека уже вернула JSON-строку — парсим
            data = json.loads(resp) if isinstance(resp, str) else resp
        except Exception:
            pass
        if not isinstance(data, dict):
            # попробуем выдрать JSON из текста
            data = _extract_json(str(resp)) or {}

        if "domain_id" in data:
            break
        time.sleep(0.3)

    # логируем сырые материалы
    _write_raw({
        "type": "labeler",
        "text": text,
        "allowed": allowed_labels,
        "raw": last_raw,
    })

    domain = str(data.get("domain_id") or data.get("label") or "oos").strip()
    conf = float(data.get("confidence") or data.get("score") or 0.5)
    cands = data.get("top_candidates") or data.get("candidates") or []

    # ВАЛИДАЦИЯ: проверяем что домен существует
    domain = validate_domain(domain)

    # нормализуем кандидатов и валидируем их
    norm_cands: List[List[Any]] = []
    if isinstance(cands, list):
        for c in cands:
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                validated_domain = validate_domain(str(c[0]))
                norm_cands.append([validated_domain, float(c[1])])
            elif isinstance(c, dict) and "label" in c and "score" in c:
                validated_domain = validate_domain(str(c["label"]))
                norm_cands.append([validated_domain, float(c["score"])])
    if not norm_cands:
        norm_cands = [[domain, conf]]

    # если в кандидатах есть уверенный ≠ oos, не форсируем "oos"
    best = max(norm_cands, key=lambda x: x[1]) if norm_cands else [domain, conf]
    if best[1] >= low_conf_threshold and best[0].lower() != "oos":
        domain = best[0]
        conf = best[1]

    result = {
        "text": text,
        "domain_id": domain,
        "domain_true": domain,
        "confidence": conf,
        "top_candidates": norm_cands,
    }
    
    # Сохраняем в кэш
    if cache:
        cache.set_classification(text, system_prompt, fewshot, result)
    
    return result

async def label_dataframe_batched(
    df: pd.DataFrame,
    client: LLMClient,
    system_prompt: str,
    fewshot: str,
    batch_size: int = 20,
    rate_limit: float = 0.4,
    *,
    allowed_labels: List[str] | None = None,
    low_conf_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Последовательно размечает строки df.
    Поддерживает rate_limit между вызовами.
    """
    rows: List[Dict[str, Any]] = []
    text_col = None
    for cand in ["text", "query_text", "message", "q", "request"]:
        if cand in df.columns:
            text_col = cand
            break
    if text_col is None:
        raise RuntimeError("Не найден столбец с текстом (ожидаю: text / query_text / message / q / request)")

    for i, val in enumerate(df[text_col].astype(str).tolist()):
        item = classify_one(
            client, system_prompt, fewshot, val,
            allowed_labels=allowed_labels, low_conf_threshold=low_conf_threshold
        )
        rows.append(item)
        await asyncio.sleep(rate_limit)
    return rows

async def label_dataframe_batched_with_progress(
    df: pd.DataFrame,
    client: LLMClient,
    system_prompt: str,
    fewshot: str,
    progress_tracker,
    batch_size: int = 20,
    rate_limit: float = 0.4,
    *,
    allowed_labels: List[str] | None = None,
    low_conf_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Последовательно размечает строки df с отслеживанием прогресса.
    """
    from .progress import ProgressTracker  # Импорт внутри функции для избежания циклических импортов
    
    rows: List[Dict[str, Any]] = []
    text_col = None
    for cand in ["text", "query_text", "message", "q", "request"]:
        if cand in df.columns:
            text_col = cand
            break
    if text_col is None:
        raise RuntimeError("Не найден столбец с текстом (ожидаю: text / query_text / message / q / request)")

    text_list = df[text_col].astype(str).tolist()
    
    await progress_tracker.start()
    
    try:
        for i, val in enumerate(text_list):
            item = classify_one(
                client, system_prompt, fewshot, val,
                allowed_labels=allowed_labels, low_conf_threshold=low_conf_threshold
            )
            rows.append(item)
            
            # Обновляем прогресс каждые 5 элементов или в конце
            if (i + 1) % 5 == 0 or i == len(text_list) - 1:
                await progress_tracker.update_progress(
                    i + 1, 
                    f"Классифицирован: {val[:50]}..."
                )
            
            await asyncio.sleep(rate_limit)
            
        await progress_tracker.complete(f"✅ Классифицировано {len(rows)} текстов")
        
    except Exception as e:
        await progress_tracker.error(f"Ошибка классификации: {str(e)}")
        raise
    
    return rows


def low_conf_items(rows: List[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    return [r for r in rows if float(r.get("confidence", 0.0)) < float(threshold)]




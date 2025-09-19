from __future__ import annotations
import asyncio, json, random, math, logging
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

from .llm import LLMClient
from .cache import get_cache

logger = logging.getLogger(__name__)

def _parse_lines(resp: str) -> list[str]:
    lines = [ln.strip("-• ").strip() for ln in str(resp).splitlines() if ln.strip()]
    # уберём дубликаты, ограничим
    out = []
    seen = set()
    for s in lines:
        if s and s not in seen:
            out.append(s)
            seen.add(s)
        if len(out) >= 4:
            break
    return out

async def _aug_one(llm: LLMClient, system_prompt: str, dom: str, text: str, *, only_pos: bool) -> list[Dict[str,Any]]:
    # Проверяем кэш
    cache = get_cache()
    if cache:
        cached_result = cache.get_augmentation(text, dom, system_prompt)
        if cached_result:
            return cached_result
    
    prompt = [
        {"role":"system","content": system_prompt},
        {"role":"user","content": f"Домен: {dom}\nФраза: {text}\n"
                                  f"Сгенерируй 3 перефраза{' (без hard-negative)' if only_pos else ' и 1 пограничный вариант'}."}
    ]
    try:
        resp = llm.chat(prompt, response_json=False, temperature=1.0)
    except Exception as e:
        es = str(e)
        if "unsupported_country_region_territory" in es or "request_forbidden" in es or "403" in es:
            logger.warning("LLM 403 forbidden on augment -> skip")
            return []
        logger.warning("augment call failed: %s", es)
        return []
    variants = _parse_lines(str(resp))
    out = []
    for v in variants:
        out.append({"text": v, "domain_id": dom, "source": "aug_llm"})
    
    # Сохраняем в кэш
    if cache:
        cache.set_augmentation(text, dom, system_prompt, out)
    
    return out

async def augment_dataset(
    llm: LLMClient,
    system_prompt: str,
    items: List[Dict[str,Any]],
    *,
    rate_limit: float = 0.1,
    include_low_conf: bool = False,
    low_conf_threshold: float = 0.5,
    only_positive: bool = False,
    concurrency: int = 8,
) -> List[Dict[str,Any]]:
    # 1) отбор
    if include_low_conf:
        base = items[:]
    else:
        base = [r for r in items if float(r.get("confidence",0.0)) >= low_conf_threshold]
    if not base:
        return []

    # 2) баланс по доменам и подготовка задач
    by_dom: Dict[str, list] = defaultdict(list)
    for r in base:
        dom = r.get("domain_true") or r.get("domain_id") or "unknown"
        text = r.get("text") or r.get("query") or ""
        if text:
            by_dom[dom].append(text)

    tasks = []
    for dom, texts in by_dom.items():
        seeds = texts[: min(30, len(texts))]
        for t in seeds:
            tasks.append((dom, t))

    # 3) контролируемая конкурентность
    sem = asyncio.Semaphore(max(1, concurrency))
    out: List[Dict[str,Any]] = []
    done = 0

    async def _worker(dom: str, t: str):
        nonlocal done
        async with sem:
            res = await _aug_one(llm, system_prompt, dom, t, only_pos=only_positive)
            out.extend(res)
            done += 1
            if done % 200 == 0 or done == len(tasks):
                logger.info("[AUG] %d/%d", done, len(tasks))
            await asyncio.sleep(rate_limit)

    await asyncio.gather(*[ _worker(dom,t) for dom,t in tasks ])
    return out

# ===== utils =====

def split_train_eval(items, eval_frac: float = 0.1, min_eval: int = 50):
    if not items:
        return [], []
    by_label = defaultdict(list)
    for it in items:
        label = it.get("label") or it.get("domain_true") or it.get("domain_id") or "NA"
        by_label[label].append(it)

    eval_set, train_set = [], []
    target_eval_total = max(min_eval, math.floor(len(items) * eval_frac))

    for label, group in by_label.items():
        if len(group) == 1:
            train_set.extend(group)
            continue
        random.shuffle(group)
        take = max(1, math.floor(len(group) * eval_frac))
        eval_set.extend(group[:take])
        train_set.extend(group[take:])

    if len(eval_set) < target_eval_total:
        deficit = target_eval_total - len(eval_set)
        train_by_label = defaultdict(list)
        for it in train_set:
            l = it.get("label") or it.get("domain_true") or it.get("domain_id") or "NA"
            train_by_label[l].append(it)
        for label, group in sorted(train_by_label.items(), key=lambda kv: len(kv[1]), reverse=True):
            if deficit <= 0:
                break
            if len(group) > 1:
                move = min(deficit, len(group) - 1)
                eval_set.extend(group[:move])
                train_by_label[label] = group[move:]
                deficit -= move
        train_set = [it for grp in train_by_label.values() for it in grp]
    return train_set, eval_set

def write_jsonl(path: Path, rows) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if path.exists():
            path.unlink()
        return False
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return True


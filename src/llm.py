# src/llm.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai import BadRequestError

import tiktoken

logger = logging.getLogger(__name__)


def _truncate_messages(messages: List[Dict[str, str]], max_tokens: int = 3500, model: str = "gpt-5-mini") -> List[Dict[str, str]]:
    """
    Грубое безопасное усечение последнего user-сообщения, если промпт слишком длинный.
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    def count(msgs: List[Dict[str, str]]) -> int:
        return sum(len(enc.encode(m.get("content", "") or "")) for m in msgs)

    total = count(messages)
    if total <= max_tokens:
        return messages

    # Усекать будем только последнее user-сообщение
    cut_messages = messages[:]
    for i in range(len(cut_messages) - 1, -1, -1):
        if cut_messages[i]["role"] == "user":
            over = total - max_tokens
            txt = cut_messages[i].get("content", "")
            toks = enc.encode(txt)
            if len(toks) > over + 100:  # оставим запас
                toks = toks[: (len(toks) - over - 100)]
                cut_messages[i]["content"] = enc.decode(toks) + "\n\n[TRUNCATED]"
            break
    return cut_messages


class LLMClient:
    def __init__(self, *, api_key: str, api_base: Optional[str], model: str):
        self.model = model
        if api_base:
            self.client = OpenAI(api_key=api_key, base_url=api_base)
        else:
            self.client = OpenAI(api_key=api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        response_json: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Делает вызов /chat/completions с авто-починкой типовых 400:
        - unsupported temperature -> убираем его и повторяем
        - unsupported response_format -> убираем JSON-режим и повторяем
        - context_length_exceeded -> подрезаем промпт и повторяем
        """
        kwargs: Dict[str, Any] = dict(model=self.model, messages=messages)
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}

        # 1-я попытка
        try:
            r = self.client.chat.completions.create(**kwargs)
            return (r.choices[0].message.content or "").strip()
        except BadRequestError as e:
            msg = (e.body or {}).get("error", {}).get("message", str(e))
            low = msg.lower()
            logger.warning("400 from OpenAI: %s", msg)

            # temperature unsupported
            if "temperature" in low and "unsupported" in low:
                kwargs.pop("temperature", None)

            # response_format unsupported
            if "response_format" in low and "unsupported" in low:
                kwargs.pop("response_format", None)

            # context too long
            if "context_length" in low or "maximum context length" in low:
                kwargs["messages"] = _truncate_messages(messages, model=self.model)

            # Повтор
            r = self.client.chat.completions.create(**kwargs)
            return (r.choices[0].message.content or "").strip()

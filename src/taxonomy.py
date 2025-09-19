from __future__ import annotations
from typing import List, Dict, Tuple

# Канонические домены (порядок = как показываем модели)
CANON_LABELS: List[str] = [
    "house",      # ЖКХ/показания/квитанции/тарифы
    "utilizer",   # вывоз/утилизация вещей
    "okc",        # городские инфосервисы: транспорт, расписания, статусы
    "payments",   # школьные/детсадовские платежи, оплата карт питания
    "boltalka",   # small talk / chit-chat
    "oos",        # вне области (out-of-scope)
]

# Короткие описания для человека/доков (опционально попадут в подсказку)
DESCRIPTIONS: Dict[str, str] = {
    "house":    "ЖКХ: передать показания, счетчики, квитанции, коммунальные услуги.",
    "utilizer": "Вывоз/утилизация старых вещей, мебели, техники.",
    "okc":      "Консультации и информация: транспорт, расписания, цены, как работает, где найти.",
    "payments": "ДЕЙСТВИЯ по оплате: пополнить карту питания, оплатить кружок, внести деньги.",
    "boltalka": "Небольшая беседа: шутки, приветствия, общение без услуги.",
    "oos":      "Запрос не относится к нашим доменам.",
}

# Лёгкие сигнальные токены (мягкий приор, НЕ правило)
KEYWORDS: Dict[str, List[str]] = {
    "house": [
        "показан", "водосч", "счетчик", "счётчик", "электр", "квитанц", "жкх",
        "тариф", "оплат", "передать показания", "передай показания", "воды",
        "джу", "дж у", "джуу", "дж уу",  # ДЖУ всегда house
    ],
    "utilizer": [
        "утилиз", "забер", "вывоз", "мебел", "шкаф", "диван", "холодильн", "стар",
        "заберите", "забрать", "перевезти", "утилизация", "телевизор",
    ],
    "okc": [
        "метро", "станц", "перекрыт", "расписан", "транспорт", "закрыт", "поезд",
        "маршрут", "работает ли", "новость", "инфо", "график",
        "сколько", "как работает", "где найти", "что такое", "как получить",
        "стоимост", "цена", "тариф", "расскажи", "объясни", "подскажи",
    ],
    "payments": [
        "оплат", "пополн", "внести", "заплат", "перевест", "доплат",
        "карт", "питан", "школ", "детск", "сад", "кружок", "секци", 
        "баланс", "счет", "деньги", "руб", "оплачу", "заплачу",
        # Фокус на ДЕЙСТВИЯХ, а не консультациях
    ],
    "boltalka": [
        "шутк", "расскажи", "привет", "пока", "как дела", "анекдот", "поговорим",
        "спасибо", "не смешно", "тест",
        # Убрали "хватит" - это стоп-слово, не болталка
    ],
    # для oos ключевые слова не задаём
}

ALIASES: Dict[str, str] = {
    # если где-то придёт старое имя — нормализуем:
    "HOUSE": "house",
    "UTILIZER": "utilizer",
    "OKC": "okc",
    "BOLTALKA": "boltalka",
    "OOS": "oos",
}

def normalize_label(label: str) -> str:
    """Нормализует ярлык к каноническому id (если это алиас)."""
    if not isinstance(label, str) or not label:
        return "oos"
    up = label.strip()
    if up in CANON_LABELS:
        return up
    return ALIASES.get(up.upper(), up.lower())

def labels_for_prompt(include_oos: bool = True) -> List[str]:
    """Глобальный мягкий список для подсказки в промте."""
    if include_oos:
        return CANON_LABELS[:]
    # иногда oos полезно уводить в конец — здесь он уже и так в конце
    return [x for x in CANON_LABELS if x != "oos"]

def is_stop_word(text: str) -> bool:
    """Проверяет, является ли текст стоп-словом (должен игнорироваться)"""
    if not isinstance(text, str):
        return False
    
    text_clean = text.strip().lower()
    
    # Стоп-слова которые не должны классифицироваться
    stop_words = {
        "хватит", "перестань", "достаточно", "стоп", "прекрати", 
        "остановись", "хватит уже", "перестаньте", "прекратите"
    }
    
    return text_clean in stop_words

def validate_domain(domain: str) -> str:
    """Валидирует домен и приводит к каноническому виду"""
    if not isinstance(domain, str) or not domain:
        return "oos"
    
    normalized = normalize_label(domain)
    
    # Если домен не в списке канонических - принудительно oos
    if normalized not in CANON_LABELS:
        return "oos"
    
    return normalized

def soft_candidates(text: str, k: int = 5, include_oos: bool = True) -> List[str]:
    """
    Мягкий отбор подсказок по ключевым словам: возвращает до k доменов.
    НЕ ограничение — только hint. Если совпадений нет, вернём глобальный список.
    """
    if not isinstance(text, str) or not text.strip():
        return labels_for_prompt(include_oos)

    t = text.lower()
    scores: List[Tuple[str, int]] = []
    for label, keys in KEYWORDS.items():
        s = 0
        for kw in keys:
            if kw in t:
                s += 1
        if s > 0:
            scores.append((label, s))

    if not scores:
        return labels_for_prompt(include_oos)

    # сортируем по убыванию попаданий, добавляем остальные в исходном порядке
    scores.sort(key=lambda x: (-x[1], CANON_LABELS.index(x[0]) if x[0] in CANON_LABELS else 999))
    ranked = [lab for lab, _ in scores]
    # дополняем недостающими доменами
    for lab in CANON_LABELS:
        if lab not in ranked:
            ranked.append(lab)

    if not include_oos and "oos" in ranked:
        ranked.remove("oos")

    return ranked[:k]


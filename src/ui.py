from __future__ import annotations
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    kb = [
        [InlineKeyboardButton("🧭 Классифицировать фразу", callback_data="menu_classify")],
        [InlineKeyboardButton("📤 Загрузить .xlsx логи", callback_data="menu_upload")],
        [InlineKeyboardButton("🧾 Очередь ревью (HITL)", callback_data="menu_hitl")],
        [InlineKeyboardButton("📦 Экспорт датасета", callback_data="menu_export")],
        [InlineKeyboardButton("📈 Метрики", callback_data="menu_metrics")],
    ]
    return InlineKeyboardMarkup(kb)

def top_candidates_buttons(cands):
    buttons = [[InlineKeyboardButton(f"{i+1}. {cid} ({p:.2f})", callback_data=f"pick_domain:{cid}")] 
               for i,(cid,p) in enumerate(cands[:3])]
    buttons.append([InlineKeyboardButton("❌ Не то / OOS", callback_data="pick_domain:oos")])
    return InlineKeyboardMarkup(buttons)

def hitl_item_buttons(domains):
    row = [InlineKeyboardButton(d, callback_data=f"hitl_choose:{d}") for d in domains[:3]]
    kb = [row, [InlineKeyboardButton("Пропустить", callback_data="hitl_skip")]]
    return InlineKeyboardMarkup(kb)

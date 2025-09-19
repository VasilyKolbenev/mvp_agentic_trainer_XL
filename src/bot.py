# src/bot.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from telegram import Update, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

from .config import Settings
from .llm import LLMClient
from .store import Store
from .labeler import label_dataframe_batched, classify_one, low_conf_items, label_dataframe_batched_with_progress
from .augmenter import augment_dataset, split_train_eval, write_jsonl
from .etl import normalize_file_to_df, save_parquet_or_csv  # <— CSV/XLSX universal
from .ui import main_menu, top_candidates_buttons, hitl_item_buttons
from .adaptive_learning import FeedbackLearner, PromptOptimizer
from .cache import init_cache
from .progress import ProgressTracker, BatchProcessor
from .context import ContextManager

# =========================
# Bootstrap
# =========================
settings = Settings.load()
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
store = Store(Path(settings.data_dir))

# Система активного обучения
feedback_learner = FeedbackLearner(Path(settings.data_dir))
prompt_optimizer = PromptOptimizer(feedback_learner)

# Инициализация кэша
llm_cache = init_cache(Path(settings.data_dir), ttl_hours=24)

# Менеджер контекстов пользователей
context_manager = ContextManager(Path(settings.data_dir))

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Ролевые LLM-клиенты с фоллбэком на глобальные ключи
def _mk_client(role: str) -> LLMClient:
    api_key = getattr(settings, f"llm_api_key_{role}", None) or settings.llm_api_key
    api_base = getattr(settings, f"llm_api_base_{role}", None) or settings.llm_api_base
    model   = getattr(settings, f"llm_model_{role}", None) or settings.llm_model
    return LLMClient(api_key=api_key, api_base=api_base, model=model)

label_llm = _mk_client("labeler")
aug_llm   = _mk_client("augmenter")

def get_optimized_prompts():
    """Получает оптимизированные промпты с учетом feedback"""
    base_system = Path("prompts/labeler_system.txt").read_text(encoding="utf-8")
    base_fewshot = Path("prompts/labeler_fewshot.txt").read_text(encoding="utf-8")
    
    # Оптимизированный системный промпт
    system_prompt = prompt_optimizer.get_optimized_system_prompt(base_system)
    
    # Добавляем динамические примеры к базовым
    dynamic_fewshot = feedback_learner.get_dynamic_fewshot()
    if dynamic_fewshot:
        fewshot_prompt = dynamic_fewshot + "\n" + base_fewshot
    else:
        fewshot_prompt = base_fewshot
        
    return system_prompt, fewshot_prompt

# Загружаем промпты
LABELER_SYSTEM, LABELER_FEWSHOT = get_optimized_prompts()
AUG_SYSTEM = Path("prompts/augmenter_system.txt").read_text(encoding="utf-8")

request = HTTPXRequest(
    connect_timeout=10.0, read_timeout=60.0, write_timeout=15.0, pool_timeout=10.0
)
application = Application.builder().token(settings.bot_token).request(request).build()


# =========================
# Helpers
# =========================
async def _send_file_if_nonempty(update: Update, path: Path, *, caption: str | None = None) -> bool:
    """Безопасная отправка файла: проверяем наличие и размер > 0."""
    try:
        if not path.exists():
            await update.message.reply_text(f"⚠️ Файл {path.name} не найден — пропускаю.")
            return False
        if path.stat().st_size == 0:
            await update.message.reply_text(f"⚠️ Файл {path.name} пуст (0 байт) — пропускаю.")
            return False
        with open(path, "rb") as f:
            await update.message.reply_document(document=InputFile(f, filename=path.name), caption=caption)
        return True
    except Exception as e:
        logger.exception("Failed to send file %s", path, exc_info=e)
        await update.message.reply_text(f"⚠️ Не удалось отправить {path.name}: {e!s}")
        return False


async def _send_files_batch(update: Update, paths: Iterable[Path]) -> int:
    sent = 0
    for p in paths:
        if await _send_file_if_nonempty(update, p):
            sent += 1
    return sent


# =========================
# Commands
# =========================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я LLM-бот для маршрутизации и подготовки датасетов. Что делаем?",
        reply_markup=main_menu(),
    )


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды: /menu /help\n"
        "— пришлите текст: классифицирую домен\n"
        "— пришлите .xlsx или .csv: соберу датасет (train/eval) и выгружу файлы",
    )


async def menu_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=main_menu())


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику feedback и качества модели"""
    stats = feedback_learner.get_feedback_stats()
    
    if stats["total_feedback"] == 0:
        await update.message.reply_text("📊 Статистика пуста - пока нет feedback от пользователей.")
        return
    
    # Формируем отчет
    report_lines = [
        f"📊 **Статистика качества модели**",
        f"",
        f"🔢 Всего feedback: {stats['total_feedback']}",
        f"✏️ Исправлений: {stats['corrections']}",
        f"📈 Процент исправлений: {stats['correction_rate']:.1%}",
        f"🆕 За последние 7 дней: {stats['recent_corrections']}",
        f""
    ]
    
    if stats["top_errors"]:
        report_lines.extend([
            f"🚨 **Топ ошибок классификации:**",
            ""
        ])
        for (predicted, corrected), count in list(stats["top_errors"].items())[:5]:
            report_lines.append(f"• `{predicted}` → `{corrected}` ({count} раз)")
        report_lines.append("")
    
    if stats["corrected_domains"]:
        report_lines.extend([
            f"🎯 **Правильные домены (по исправлениям):**",
            ""
        ])
        for domain, count in list(stats["corrected_domains"].items())[:5]:
            report_lines.append(f"• `{domain}`: {count}")
    
    # Добавляем статистику кэша
    cache_stats = llm_cache.get_stats()
    if cache_stats["total_entries"] > 0:
        report_lines.extend([
            f"",
            f"💾 **Кэш LLM:**",
            f"• Записей классификации: {cache_stats['classification_entries']}",
            f"• Записей аугментации: {cache_stats['augmentation_entries']}",
            f"• TTL: {cache_stats['ttl_hours']} часов"
        ])
    
    # Добавляем статистику контекстов пользователей
    context_stats = context_manager.get_stats()
    if context_stats["total_users"] > 0:
        report_lines.extend([
            f"",
            f"👥 **Контексты пользователей:**",
            f"• Всего пользователей: {context_stats['total_users']}",
            f"• Активных (24ч): {context_stats['active_users']}",
            f"• Всего сообщений: {context_stats['total_messages']}"
        ])
        
        if context_stats["top_domains"]:
            top_domains_text = ", ".join([f"`{domain}` ({count:.0f})" 
                                        for domain, count in list(context_stats["top_domains"].items())[:3]])
            report_lines.append(f"• Топ домены: {top_domains_text}")
    
    report_text = "\n".join(report_lines)
    await update.message.reply_text(report_text, parse_mode="Markdown")


# =========================
# Text classify
# =========================
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пустое сообщение. Введите фразу или используйте /menu.")
        return

    user_id = str(update.effective_user.id)
    
    # Получаем контекст пользователя для улучшения классификации
    user_context = context_manager.get_classification_context(user_id)
    preferred_domains = context_manager.get_preferred_domains(user_id)
    
    # Дополняем системный промпт контекстом если есть
    enhanced_system_prompt = LABELER_SYSTEM
    if user_context:
        enhanced_system_prompt = f"{LABELER_SYSTEM}\n\n{user_context}"
    
    try:
        data = classify_one(
            label_llm, 
            enhanced_system_prompt, 
            LABELER_FEWSHOT, 
            text,
            allowed_labels=preferred_domains if preferred_domains else None
        )
    except Exception as e:
        logger.exception("classify_one failed", exc_info=e)
        await update.message.reply_text(f"Ошибка классификации: {e!s}")
        return

    domain = data.get("domain_id") or "unknown"
    conf = data.get("confidence", 0.0)
    cands = data.get("top_candidates") or [[domain, conf]]
    
    # Сохраняем контекст для feedback
    ctx.user_data["last_classification"] = {
        "text": text,
        "predicted_domain": domain,
        "confidence": conf,
        "candidates": cands
    }
    
    # Обновляем контекст пользователя (пока без коррекции)
    context_manager.update_context(user_id, text, domain, confidence=conf)

    await update.message.reply_text(
        f"Предсказание: {domain} (≈{conf:.2f})\nВыберите правильный:",
        reply_markup=top_candidates_buttons(cands),
    )


# =========================
# Documents (.xlsx / .csv)
# =========================
async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    name = (doc.file_name or "").lower()

    # Теперь принимаем .xlsx И .csv
    if not (name.endswith(".xlsx") or name.endswith(".csv")):
        await update.message.reply_text(
            "Пришлите .xlsx или .csv с логами. Минимум — колонка текста (`text` / `query_text`)."
        )
        return

    # Скачиваем файл
    tg_file = await doc.get_file()
    buf = await tg_file.download_as_bytearray()
    upath = Path(settings.data_dir) / f"logs_{update.effective_user.id}{Path(name).suffix}"
    with open(upath, "wb") as f:
        f.write(buf)

    # ETL → DataFrame (универсальный парсер CSV/XLSX)
    await update.message.reply_text("Обрабатываю файл…")
    try:
        df = normalize_file_to_df(upath, max_rows=getattr(settings, "max_batch", None))
        save_parquet_or_csv(df, base_dir=Path(settings.data_dir))
    except Exception as e:
        logger.exception("ETL failed", exc_info=e)
        await update.message.reply_text(f"Ошибка при чтении файла: {e!s}")
        return

    if df.empty:
        await update.message.reply_text(
            "Не удалось обнаружить текстовые строки.\n"
            "Проверьте, чтобы колонка с запросами была названа `text` или `query_text` (или синоним из README)."
        )
        return

    # Batched LLM labeling с прогрессом
    progress = ProgressTracker(update, ctx, len(df), "Классификация текстов")
    
    try:
        rows = await label_dataframe_batched_with_progress(
            df,
            label_llm,
            LABELER_SYSTEM,
            LABELER_FEWSHOT,
            progress,
            getattr(settings, "batch_size", 20),
            getattr(settings, "rate_limit", 0.4),
        )
    except Exception as e:
        logger.exception("label_dataframe_batched failed", exc_info=e)
        await progress.error(f"Ошибка при разметке: {e!s}")
        return

    # Сохраняем CSV с разметкой
    try:
        labeled_csv = store.save_labeled_csv(rows)
    except Exception as e:
        logger.exception("save_labeled_csv failed", exc_info=e)
        await update.message.reply_text(f"Ошибка при сохранении CSV: {e!s}")
        return

    # HITL очередь (низкая уверенность)
    low = []
    try:
        low = low_conf_items(rows, getattr(settings, "low_conf", 0.5))
        store.append_hitl_queue(low)
    except Exception as e:
        logger.exception("HITL queue append failed", exc_info=e)

    # Аугментация
    try:
        aug_records = await augment_dataset(
            aug_llm,
            AUG_SYSTEM,
            rows,
            rate_limit=getattr(settings, "rate_limit", 0.4),
            include_low_conf=getattr(settings, "augment_include_lowconf", False),
            low_conf_threshold=getattr(settings, "low_conf", 0.5),
        )
    except Exception as e:
        logger.exception("augment_dataset failed", exc_info=e)
        await update.message.reply_text(f"Ошибка аугментации: {e!s}")
        return

    # Если аугментация ничего не дала — используем исходные размеченные
    base_records = aug_records if aug_records else rows

    # Сплит train/eval
    train, eval_ = split_train_eval(base_records, eval_frac=0.10, min_eval=50)

    # Пишем JSONL (без 0-байтных файлов)
    art = store.path("artifacts")
    train_p = art / "dataset_train.jsonl"
    eval_p  = art / "dataset_eval.jsonl"
    ok_train = write_jsonl(train_p, train)
    ok_eval  = write_jsonl(eval_p,  eval_)

    # Резюме и отправка
    msg = (
        f"Готово. Размечено: {len(rows)}; низкая уверенность: {len(low)}\n"
        f"train={len(train)}, eval={len(eval_)}\n"
        f"Отправляю файлы…"
    )
    await update.message.reply_text(msg)

    to_send = [labeled_csv]
    if ok_train: to_send.append(train_p)
    else: await update.message.reply_text("⚠️ Файл dataset_train.jsonl не создан — пропускаю.")
    if ok_eval: to_send.append(eval_p)
    else: await update.message.reply_text("⚠️ Файл dataset_eval.jsonl не создан — пропускаю.")
    await _send_files_batch(update, to_send)


# =========================
# Callbacks (inline buttons)
# =========================
async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    await q.answer()

    if data == "menu_classify":
        await q.edit_message_text("Напишите фразу одним сообщением — я классифицирую домен.")
        return

    if data == "menu_upload":
        await q.edit_message_text("Отправьте .xlsx или .csv файл с логами (колонка `text` или `query_text`).")
        return

    if data == "menu_export":
        tp = store.path("artifacts/dataset_train.jsonl")
        ep = store.path("artifacts/dataset_eval.jsonl")
        if (not tp.exists() or tp.stat().st_size == 0) and (not ep.exists() or ep.stat().st_size == 0):
            await q.edit_message_text("Датасеты ещё не готовы. Загрузите файл и дождитесь обработки.")
            return
        await q.edit_message_text("Отправляю датасеты…")
        chat_id = q.message.chat_id
        for p in [tp, ep]:
            try:
                if not p.exists():
                    await ctx.bot.send_message(chat_id, f"⚠️ Файл {p.name} не найден — пропускаю.")
                    continue
                if p.stat().st_size == 0:
                    await ctx.bot.send_message(chat_id, f"⚠️ Файл {p.name} пуст — пропускаю.")
                    continue
                with open(p, "rb") as f:
                    await ctx.bot.send_document(chat_id=chat_id, document=InputFile(f, filename=p.name))
            except Exception as e:
                await ctx.bot.send_message(chat_id, f"⚠️ Не удалось отправить {p.name}: {e!s}")
        return

    if data == "menu_hitl":
        items = store.read_hitl_queue(limit=10)
        if not items:
            await q.edit_message_text("Очередь ревью пуста. 👍")
            return
        item = items[0]
        text = item.get("text", "")
        cands = item.get("top_candidates", [])
        if isinstance(cands, str):
            try:
                cands = json.loads(cands)
            except Exception:
                cands = []
        doms = [d for d, _ in cands] or ["payments", "mfc", "housing", "transport", "health", "oos"]
        await q.edit_message_text(
            f"HITL #1/…\nТекст: {text}\nВыберите домен:",
            reply_markup=hitl_item_buttons(doms),
        )
        ctx.user_data["hitl_current"] = item
        return

    if data.startswith("pick_domain:"):
        dom = data.split(":", 1)[1]
        
        # Логируем feedback если есть контекст последней классификации
        if "last_classification" in ctx.user_data:
            last_class = ctx.user_data["last_classification"]
            user_id = str(q.from_user.id)
            
            # Логируем в систему активного обучения
            feedback_learner.log_feedback(
                text=last_class["text"],
                predicted_domain=last_class["predicted_domain"],
                corrected_domain=dom,
                confidence=last_class["confidence"],
                user_id=user_id
            )
            
            # Обновляем контекст пользователя с исправлением
            context_manager.update_context(
                user_id, 
                last_class["text"], 
                last_class["predicted_domain"],
                corrected_domain=dom,
                confidence=last_class["confidence"]
            )
            
            # Обновляем промпты если накопилось достаточно feedback
            if prompt_optimizer.should_retrain():
                global LABELER_SYSTEM, LABELER_FEWSHOT
                LABELER_SYSTEM, LABELER_FEWSHOT = get_optimized_prompts()
                logger.info("Промпты обновлены на основе feedback")
        
        await q.edit_message_text(f"Спасибо! Зафиксировал: {dom}. Можно присылать новую фразу или /menu.")
        return

    if data.startswith("hitl_choose:"):
        dom = data.split(":", 1)[1]
        item = ctx.user_data.get("hitl_current")
        if item:
            item["domain_true"] = dom
            store.append_hitl_queue([item])  # MVP: складываем вердикт туда же
        await q.edit_message_text(f"Пометил как: {dom}. /menu для продолжения.")
        return

    if data == "hitl_skip":
        await q.edit_message_text("Пропущено. /menu")
        return


# =========================
# Error handler
# =========================
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error", exc_info=ctx.error)


# =========================
# Wiring
# =========================
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(CommandHandler("menu", menu_cmd))
application.add_handler(CommandHandler("stats", stats_cmd))
application.add_handler(CallbackQueryHandler(on_cb))

# порядок важен: сначала документы, затем текст (чтобы подписи к файлам не ловились как текст)
application.add_handler(MessageHandler(filters.Document.ALL, on_document))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

application.add_error_handler(error_handler)

if __name__ == "__main__":
    if settings.public_url:
        logging.info("WEBHOOK mode")
        application.run_webhook(
            listen="0.0.0.0",
            port=settings.port,
            url_path=settings.bot_token,
            webhook_url=f"{settings.public_url}/{settings.bot_token}",
            drop_pending_updates=True,
        )
    else:
        logging.info("POLLING mode")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query", "chat_member"],
        )

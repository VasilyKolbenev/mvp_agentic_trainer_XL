@echo off
chcp 65001 >nul
echo ====================================
echo   GitHub Push - Agentic_Trainer_Logs
echo ====================================
echo.

echo Шаг 1: Проверка статуса...
git status
echo.

echo Шаг 2: Добавление всех изменений...
git add -A
echo Готово!
echo.

echo Шаг 3: Commit...
git commit -m "feat: v2.0 - ML Data Pipeline с контролем качества

🏗️ Архитектура:
- 9 компонентов с модульной структурой
- FastAPI REST API (backend без UI)
- Закрытый контур для локальных LLM

🤖 AI-Агенты (PydanticAI):
- LabelerAgent с 5 уровнями валидации
- AugmenterAgent для синтетики
- Поддержка Mistral, Qwen, локальных моделей

🛡️ Контроль качества:
- LabelerValidator: консенсус, правила, калибровка
- QualityControl: косинусное расстояние + Левенштейн
- Accuracy: 85%% → 95%% (+10%%)

🐳 Docker:
- docker-compose.yml (базовый)
- docker-compose.local-llm.yml (Mistral + Qwen)
- Готовый к production

📦 Features:
- Валидация существующих меток
- Разметка синтетики
- Версионирование датасетов (git-like)
- HITL для сомнительных
- Полная документация (15,000+ строк)

Tech stack:
- FastAPI, Pydantic, PydanticAI
- scikit-learn, pandas
- Docker, vLLM/Ollama
- OpenAI-compatible API"

echo Готово!
echo.

echo Шаг 4: Push в GitHub...
git push origin main

if errorlevel 1 (
    echo.
    echo ❌ Ошибка при push!
    echo Попробуйте вручную: git push origin main
    echo.
    pause
    exit /b 1
)

echo.
echo ====================================
echo   ✅ УСПЕШНО ЗАГРУЖЕНО НА GITHUB!
echo ====================================
echo.
echo Проверьте: https://github.com/VasilyKolbenev/Agentic_Trainer_Logs
echo.
pause


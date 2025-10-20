@echo off
chcp 65001 >nul
echo ============================================
echo   Перенос в новый репозиторий
echo   Agentic_Trainer_Logs
echo ============================================
echo.

echo Шаг 1: Проверка текущих remotes...
git remote -v
echo.

echo Шаг 2: Добавление нового репозитория...
git remote add new-repo https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git
echo ✅ Новый remote добавлен
echo.

echo Шаг 3: Удаление вложенной папки из Git...
git rm -rf esk-agent-llm-pro 2>nul
if exist .gitmodules (
    git rm .gitmodules
)
echo.

echo Шаг 4: Добавление всех изменений...
git add -A
echo ✅ Готово
echo.

echo Шаг 5: Commit финальной версии...
git commit -m "feat: v2.0 - ML Data Pipeline для Agentic_Trainer_Logs

🏗️ Complete rewrite:
- Backend ML Pipeline (FastAPI)
- 9 компонентов с модульной архитектурой
- 5 уровней контроля качества
- Закрытый контур для локальных LLM (Mistral/Qwen)

🤖 Features:
- LabelerAgent с консенсус валидацией
- AugmenterAgent для синтетики
- QualityControl: cosine + Levenshtein
- Версионирование датасетов
- Docker-ready

📚 Docs: 15,000+ строк документации"

echo ✅ Commit создан
echo.

echo Шаг 6: Push в НОВЫЙ репозиторий...
git push new-repo main

if errorlevel 1 (
    echo.
    echo ❌ Ошибка при push!
    echo.
    echo Возможные причины:
    echo - Нужна авторизация GitHub
    echo - Ветка называется master вместо main
    echo.
    echo Попробуйте вручную:
    echo   git push new-repo master
    echo   или
    echo   git push new-repo main --force
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   ✅ УСПЕШНО! Проект в новом репозитории!
echo ============================================
echo.
echo Откройте: https://github.com/VasilyKolbenev/Agentic_Trainer_Logs
echo.
echo Если хотите сделать новый репозиторий основным:
echo   git remote remove origin
echo   git remote rename new-repo origin
echo.
pause


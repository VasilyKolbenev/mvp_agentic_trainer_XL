@echo off
chcp 65001 >nul
echo ============================================
echo   Удаление вложенной папки и push в GitHub
echo ============================================
echo.

echo Шаг 1: Удаление из Git индекса...
git rm -rf esk-agent-llm-pro 2>nul
if errorlevel 1 (
    echo Папка уже удалена из Git или не найдена
) else (
    echo ✅ Удалено из Git индекса
)
echo.

echo Шаг 2: Удаление .gitmodules если есть...
if exist .gitmodules (
    git rm .gitmodules
    echo ✅ .gitmodules удален
) else (
    echo .gitmodules не найден - OK
)
echo.

echo Шаг 3: Добавление всех изменений...
git add -A
echo ✅ Изменения добавлены
echo.

echo Шаг 4: Commit...
git commit -m "fix: Remove nested esk-agent-llm-pro submodule directory"
if errorlevel 1 (
    echo Нет изменений для commit или ошибка
) else (
    echo ✅ Commit создан
)
echo.

echo Шаг 5: Push в GitHub...
git push origin main
if errorlevel 1 (
    echo.
    echo ❌ Ошибка при push!
    echo Попробуйте вручную: git push origin main --force
    pause
    exit /b 1
)

echo.
echo ============================================
echo   ✅ ГОТОВО! Папка удалена из GitHub
echo ============================================
echo.
echo Проверьте: https://github.com/VasilyKolbenev/Agentic_Trainer_Logs
echo Папка esk-agent-llm-pro должна исчезнуть
echo.
pause


@echo off
echo Fixing submodule issue...
echo.

echo Step 1: Remove submodule from git
git rm -r --cached esk-agent-llm-pro
if errorlevel 1 (
    echo Warning: git rm failed, trying manual cleanup
)

echo.
echo Step 2: Remove .gitmodules if exists
if exist .gitmodules (
    del .gitmodules
    echo Removed .gitmodules
)

echo.
echo Step 3: Remove physical directory
if exist esk-agent-llm-pro (
    rmdir /s /q esk-agent-llm-pro
    echo Removed esk-agent-llm-pro directory
)

echo.
echo Step 4: Commit changes
git add -A
git commit -m "fix: Remove nested submodule directory"

echo.
echo Step 5: Push changes
git push origin main

echo.
echo Done! Check GitHub - the folder should now be accessible.
pause


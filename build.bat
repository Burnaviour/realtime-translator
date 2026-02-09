@echo off
title Building Real-time Translator
echo ============================================================
echo   Building Real-time Voice Translator Executable
echo   This may take 5-10 minutes...
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/3] Running PyInstaller...
uv run pyinstaller build.spec --noconfirm

echo.
if exist "dist\RealtimeTranslator\RealtimeTranslator.exe" (
    echo [3/3] Copying extra files...
    copy /y settings.json "dist\RealtimeTranslator\" >nul 2>&1
    copy /y README.md "dist\RealtimeTranslator\" >nul 2>&1

    echo.
    echo ============================================================
    echo   BUILD SUCCESSFUL!
    echo   Output: dist\RealtimeTranslator\
    echo   Run:    dist\RealtimeTranslator\RealtimeTranslator.exe
    echo.
    echo   To distribute:
    echo     1. Zip the entire dist\RealtimeTranslator\ folder
    echo     2. Share the zip file
    echo     3. Target PC needs: NVIDIA GPU + drivers (no Python needed)
    echo     4. AI models download automatically on first run (~3 GB)
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo   BUILD FAILED - Check errors above
    echo ============================================================
)

echo.
pause

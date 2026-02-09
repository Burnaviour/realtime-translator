@echo off
title Real-time Voice Translator
echo ============================================================
echo   Real-time Voice Translator (RU ^<-^> EN)
echo   Starting... (first run may download AI models ~1-2 GB)
echo ============================================================
echo.

cd /d "%~dp0"
uv run main.py

echo.
echo Translator stopped.
pause

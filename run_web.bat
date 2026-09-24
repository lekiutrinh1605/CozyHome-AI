@echo off
title CozyHome Full-Stack Web App (FastAPI + Modern Web)
echo ===================================================
echo   Khoi chay CozyHome Full-Stack Web App
echo   Dia chi truy cap: http://localhost:8000
echo ===================================================
cd /d "%~dp0"
.venv\Scripts\python.exe server.py
pause

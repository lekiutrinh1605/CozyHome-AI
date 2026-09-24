@echo off
title CozyHome Prototype PoC (Streamlit)
echo ===================================================
echo   Khoi chay CozyHome Streamlit Prototype
echo   Dia chi truy cap: http://localhost:8501
echo ===================================================
cd /d "%~dp0"
.venv\Scripts\python.exe -m streamlit run app.py
pause

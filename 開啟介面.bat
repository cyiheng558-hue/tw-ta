@echo off
chcp 65001 >nul
set PYTHONUTF8=1
echo Starting Taiwan Stock TA web UI... browser will open automatically.
echo If not, open http://localhost:8501 manually.
echo To stop: press Ctrl+C in this window or just close it.
python -m streamlit run "%~dp0app.py"
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   把本機的修改更新到網站(GitHub - Streamlit)
echo ============================================
echo.

REM 先看看有沒有變更
git status --short
echo.

REM 全部加入、commit(用日期時間當訊息)、推送
git add -A
git commit -m "更新 %date% %time%"
echo.
echo --- 推送到 GitHub ---
git push origin main

echo.
echo ============================================
echo   完成!Streamlit 網站約 1 分鐘後會自動更新。
echo   (若顯示 nothing to commit,代表沒有新變更)
echo ============================================
pause

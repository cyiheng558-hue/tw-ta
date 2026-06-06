@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   把本機的修改更新到網站(GitHub - Streamlit)
echo ============================================
echo.

REM 1) 先看看有沒有變更
git status --short
echo.

REM 2) 全部加入並 commit(用日期時間當訊息;沒有變更時會略過)
git add -A
git commit -m "更新 %date% %time%"
echo.

REM 3) 先把遠端的變更拉下來合併(避免被擋),再推上去
echo --- 同步遠端 ---
git pull --rebase origin main
echo.
echo --- 推送到 GitHub ---
git push origin main

echo.
echo ============================================
echo   完成!Streamlit 網站約 1 分鐘後會自動更新。
echo   (若顯示 nothing to commit,代表沒有新變更)
echo   (若出現 CONFLICT 字樣,先別關,把畫面貼給 Claude)
echo ============================================
pause

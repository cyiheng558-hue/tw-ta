@echo off
chcp 65001 >nul
set PYTHONUTF8=1
if "%~1"=="" (
  set /p code=Enter stock code (e.g. 2330):
) else (
  set code=%~1
)
python "%~dp0plot.py" %code%

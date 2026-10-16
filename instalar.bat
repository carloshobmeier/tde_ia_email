@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts\install.py
if errorlevel 1 (
  echo.
  echo A instalacao precisa de atencao. Confira a mensagem acima.
)
pause

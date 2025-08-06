@echo off
chcp 65001 > nul
cls

echo.
echo ╔═══════════════════════════════════════════╗
echo ║            DOLPHA1 SYSTEM                ║
echo ║                                          ║
echo ║  🎯 KOSDAQ150 Futures Real-time Trading  ║
echo ║  📊 Data Collection + Signal Generation  ║
echo ╚═══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

echo 🚀 Starting dolpha1 system...
python dolpha1.py

pause
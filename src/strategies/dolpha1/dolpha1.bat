@echo off
chcp 65001 > nul
cls

echo 🚀 Starting dolpha1 system...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo 🔧 Activating conda environment...
call C:\Users\CHECK\anaconda3\Scripts\activate.bat

cd /d "%~dp0"

call conda activate myenv

echo 🐍 Python environment ready
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

python dolpha1.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Program exited with error code: %ERRORLEVEL%
    echo ⚠️  Check the logs for more details.
    echo.
)

echo.
echo ✅ Program execution completed.
pause
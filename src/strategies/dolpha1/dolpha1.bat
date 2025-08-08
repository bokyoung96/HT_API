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

echo Passing CLI args: %*
python dolpha1.py --symbol 106W09 --atr-period 10 --rolling-move 5 --band-multiplier 1.0 --use-vwap true --observe-interval 5

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Program exited with error code: %ERRORLEVEL%
    echo ⚠️  Check the logs for more details.
    echo.
)

echo.
echo ✅ Program execution completed.
pause
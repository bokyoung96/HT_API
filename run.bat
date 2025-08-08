@echo off
echo Starting korea_realtime_trading_module...

call C:\Users\CHECK\anaconda3\Scripts\activate.bat

cd /d "%~dp0src"

call conda activate myenv

set PYTHONPATH=%CD%;%PYTHONPATH%

python main.py

pause 
@echo off
echo Starting HT_API...

call C:\Users\CHECK\anaconda3\Scripts\activate.bat

cd /d "%~dp0src"

call conda activate myenv

python main.py

pause 
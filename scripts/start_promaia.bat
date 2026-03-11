@echo off
if "%~1"=="hidden" goto :hidden

:: If not hidden, bounce to VBScript which will run this file invisibly
wscript.exe "c:\Users\Zachary Turner\dev\promaia\scripts\start_promaia_hidden.vbs"
exit /b

:hidden
cd /d "c:\Users\Zachary Turner\dev\promaia"

:: Start Muninn in the background
start "MuninnDB" /B muninn start

:: Start Promaia server (blocks the batch script so it stays alive)
python -m uvicorn promaia.web.main:app --host 0.0.0.0 --port 8000

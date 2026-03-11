@echo off
if "%~1"=="hidden" goto :hidden

:: If not hidden, bounce to VBScript which will run this file invisibly
wscript.exe "c:\Users\Zachary Turner\dev\promaia\scripts\start_promaia_hidden.vbs"
exit /b

:hidden
cd /d "c:\Users\Zachary Turner\dev\promaia"

:: Start Promaia Unified Manager (handles Web, Telegram, Scheduler, MuninnDB)
python -m promaia.manager

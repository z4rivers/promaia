@echo off
if "%~1"=="hidden" goto :hidden

:: If not hidden, bounce to VBScript which will run this file invisibly
wscript.exe "%~dp0start_promaia_hidden.vbs"
exit /b

:hidden
cd /d "%~dp0.."

:: Start Promaia Unified Manager (handles Web, Telegram, Scheduler, MuninnDB)
python -m promaia.manager

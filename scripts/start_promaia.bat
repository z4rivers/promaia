@echo off
REM Interactive Promaia startup — use this from a terminal window.
REM For headless/auto-start, use Task Scheduler (see install_watchdog.ps1).

cd /d "%~dp0.."
set PYTHONPATH=.
python -m promaia.manager

@echo off
cd /d "c:\Users\Zachary Turner\dev\promaia"
python -m uvicorn promaia.web.main:app --host 0.0.0.0 --port 8000

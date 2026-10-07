@echo off
cd /d "%~dp0..\backend"
set ENABLE_LOCAL_DEMO_ACCESS=false
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 > server.out.log 2> server.err.log

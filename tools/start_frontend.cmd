@echo off
cd /d "%~dp0..\frontend"
..\node_modules\.bin\vite.cmd preview --host 127.0.0.1 --port 4173 > preview.out.log 2> preview.err.log

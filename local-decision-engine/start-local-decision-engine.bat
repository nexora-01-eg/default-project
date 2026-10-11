@echo off
REM Start the Local Decision Engine on localhost only (127.0.0.1:8765).
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
set "CLI=%ROOT%src\decision_engine\cli.py"
if not exist "%PY%" (
  echo [error] venv not found at "%PY%"
  echo Run: uv venv --python 3.12 "%ROOT%.venv" ^&^& uv pip install --python "%PY%" pytest psutil
  exit /b 1
)
echo Starting local-decision-engine on http://127.0.0.1:8765 ...
echo Logs: "%ROOT%logs\server.log"
if not exist "%ROOT%logs" mkdir "%ROOT%logs"
start "local-decision-engine" /min "%PY%" "%CLI%" serve --port 8765
timeout /t 3 /nobreak >nul
"%PY%" "%CLI%" status
endlocal

@echo off
REM Stop the Local Decision Engine (port 8765).
setlocal
set "ROOT=%~dp0"
echo Stopping local-decision-engine ...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*decision_engine*serve*' -or $_.CommandLine -like '*decision-engine*serve*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Output (\"stopped PID \" + $_.ProcessId) }"
powershell -NoProfile -Command "$s=New-Object Net.Sockets.TcpClient; try { $s.Connect('127.0.0.1',8765); Write-Output 'port 8765 still in use'; } catch { Write-Output 'port 8765 FREE - server stopped'; } finally { $s.Close() }"
endlocal

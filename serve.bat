@echo off
rem Double-click to serve the leaderboard at http://localhost:2000 and open it.
rem Close this window to stop the server.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\serve.py --open %*
) else (
  python scripts\serve.py --open %*
)
if errorlevel 1 pause

@echo off
rem Publishes this folder to https://github.com/hassanmunif/witsenhausen-leaderboard
rem First run: creates the git repository, makes the first commit and pushes it.
rem Later runs: saves whatever changed and pushes it. The site updates a few minutes later.
setlocal
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
  echo Git is not installed. Install Git for Windows from https://git-scm.com/download/win and run this again.
  pause
  exit /b 1
)
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"

echo [1/4] Copying the GitHub workflows into .github\workflows
%PY% scripts\install_workflows.py
if errorlevel 1 goto fail

if not exist ".git" (
  echo [2/4] Creating the git repository
  git init -b main
  if errorlevel 1 goto fail
  git remote add origin https://github.com/hassanmunif/witsenhausen-leaderboard.git
) else (
  echo [2/4] Git repository already set up
)
rem Commits made here use GitHub's private noreply address, so no personal email address becomes public.
git config user.name "hassanmunif"
git config user.email "89752430+hassanmunif@users.noreply.github.com"

echo [3/4] Saving the changes
git add -A
git diff --cached --quiet
if errorlevel 1 (
  git rev-parse --verify HEAD >nul 2>nul
  if errorlevel 1 (git commit -q -m "First public version") else (git commit -q -m "Update the leaderboard")
  if errorlevel 1 goto fail
) else (
  echo Nothing new to save.
)

echo [4/4] Sending to GitHub. The first time, a window asks you to sign in to GitHub.
git push -u origin main
if errorlevel 1 goto fail

echo.
echo Done. The site updates a few minutes after each push:
echo   https://hassanmunif.github.io/witsenhausen-leaderboard/
pause
exit /b 0

:fail
echo.
echo Stopped: see the message above.
pause
exit /b 1

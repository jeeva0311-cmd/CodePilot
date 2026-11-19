@echo off
setlocal

cd /d "%~dp0backend"
set PYTHONPATH=%~dp0backend

echo Running CodePilot Agent test suite...
echo.

C:\Python313\python.exe -m pytest tests/ -v --tb=short

echo.
pause

@echo off
cd /d "%~dp0"
echo Starting the video-studio dashboard. Close this window to stop it.
".venv\Scripts\python.exe" studio.py ui

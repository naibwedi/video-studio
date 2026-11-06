@echo off
cd /d "%~dp0"
if not exist "editor\dist\index.html" (
  echo Building the editor for the first time, this takes a minute...
  pushd editor
  call npm install --no-audit --no-fund
  call npm run build
  popd
)
echo Starting video-studio. Close this window to stop it.
".venv\Scripts\python.exe" studio.py ui

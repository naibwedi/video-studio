# One-time setup on a new PC:  powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

New-Item -ItemType Directory -Force tools\bin, library\stock, library\overlays, exports | Out-Null

if (-not (Test-Path tools\bin\ffmpeg.exe)) {
    Write-Host "Downloading ffmpeg (about 100 MB) ..."
    $zip = Join-Path $env:TEMP "ffmpeg-essentials.zip"
    try {
        Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
        $tmp = Join-Path $env:TEMP "ffmpeg-extract"
        Expand-Archive $zip -DestinationPath $tmp -Force
        Copy-Item (Get-ChildItem $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName tools\bin\ffmpeg.exe
    } catch {
        Write-Host "Could not download ffmpeg. Install it (winget install Gyan.FFmpeg) or copy ffmpeg.exe into tools\bin."
    }
}
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# the editor (needs Node 20+): install packages and build it once
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location editor
    npm install --no-audit --no-fund
    npm run build
    Pop-Location
} else {
    Write-Host "Node.js was not found, so the editor was not built. Install Node 20+ from nodejs.org and run setup.ps1 again."
}
.\.venv\Scripts\python.exe studio.py doctor

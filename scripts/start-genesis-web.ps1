# Genesis Web Launcher (PowerShell)
# Uses the real Python 3.11 and sets everything up so the 8080 + 3D UI works.
$ErrorActionPreference = "Stop"

$realPy = "C:\Users\Ozan\AppData\Local\Programs\Python\Python311\python.exe"
$projectRoot = Split-Path -Parent $PSScriptRoot   # goes up from scripts/ to genesis/

Write-Host "Genesis Web Launcher"
Write-Host "Project: $projectRoot"
Write-Host "Python:  $realPy"

if (-not (Test-Path $realPy)) {
    Write-Error "Real Python not found at $realPy. Please adjust the path in this script."
    exit 1
}

# Ensure editable install (safe to re-run, installs fastapi/uvicorn if missing)
Write-Host "Ensuring genesis-engine[web] is installed..."
& $realPy -m pip install -e "$projectRoot.[web]" --quiet

# Start on 8080 using direct uvicorn (more reliable, bypasses any entry-point/docstring issues)
$env:PYTHONPATH = Join-Path $projectRoot "src"
Write-Host ""
Write-Host "Starting GENESIS Web UI on http://127.0.0.1:8080"
Write-Host "3D demo (Three.js + provenance + layers + WebXR) should be active."
Write-Host "Press Ctrl+C to stop the server."
Write-Host ""

& $realPy -m uvicorn gen.web.app:create_app --host 127.0.0.1 --port 8080 --factory --log-level info

# Open browser after a short delay (non-blocking)
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:8080"

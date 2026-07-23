$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ProjectRoot "backend")
$env:PYTHONPATH = "."
Write-Host "Starting LapisAI backend build rag-multilingual-v4-20260723"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

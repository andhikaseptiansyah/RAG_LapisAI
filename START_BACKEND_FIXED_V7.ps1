$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExpectedBuild = "rag-multilingual-v7-20260723"
$HealthUrl = "http://127.0.0.1:8000/api/health"

Write-Host "Membersihkan proses backend lama pada port 8000..." -ForegroundColor Yellow
$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($connection in $connections) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
    $commandLine = [string]$process.CommandLine
    $processName = [string]$process.Name

    if (
        $commandLine -match "uvicorn" -or
        $commandLine -match "api\.main:app" -or
        $processName -match "python"
    ) {
        Write-Host "Menghentikan PID $($connection.OwningProcess): $processName" -ForegroundColor Yellow
        Stop-Process -Id $connection.OwningProcess -Force
    }
    else {
        throw "Port 8000 dipakai proses non-LapisAI PID $($connection.OwningProcess). Tutup proses tersebut terlebih dahulu."
    }
}

Start-Sleep -Milliseconds 800

Write-Host "Menghapus cache bytecode Python agar kode lama tidak ikut hidup kembali..." -ForegroundColor Yellow
Get-ChildItem -Path (Join-Path $ProjectRoot "backend") -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Set-Location (Join-Path $ProjectRoot "backend")
$env:PYTHONPATH = "."

$buildInfo = python -c "from api.build_info import public_build_info; import json; print(json.dumps(public_build_info()))"
Write-Host "Kode yang akan dijalankan: $buildInfo" -ForegroundColor Cyan

Write-Host "Starting LapisAI backend $ExpectedBuild pada http://127.0.0.1:8000" -ForegroundColor Green
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

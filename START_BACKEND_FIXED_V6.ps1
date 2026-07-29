$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExpectedBuild = "rag-multilingual-v6-20260723"
$HealthUrl = "http://127.0.0.1:8000/api/health"

function Get-ActiveBuild {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
        return [string]$response.buildVersion
    }
    catch {
        return ""
    }
}

$activeBuild = Get-ActiveBuild
if ($activeBuild) {
    if ($activeBuild -eq $ExpectedBuild) {
        Write-Host "Backend $ExpectedBuild sudah aktif di port 8000." -ForegroundColor Green
        exit 0
    }

    $connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
        $commandLine = [string]$process.CommandLine
        if ($commandLine -match "uvicorn" -and $commandLine -match "api\.main:app") {
            Write-Host "Menghentikan backend lama: $activeBuild (PID $($connection.OwningProcess))" -ForegroundColor Yellow
            Stop-Process -Id $connection.OwningProcess -Force
        }
        else {
            throw "Port 8000 digunakan proses lain. Tutup proses PID $($connection.OwningProcess), lalu jalankan skrip ini lagi."
        }
    }
    Start-Sleep -Seconds 1
}

Set-Location (Join-Path $ProjectRoot "backend")
$env:PYTHONPATH = "."
Write-Host "Starting LapisAI backend build $ExpectedBuild" -ForegroundColor Cyan
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

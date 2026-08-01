$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExpectedBuild = "rag-bilingual-eval-v16-20260802"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $PythonExecutable = $VenvPython
}
else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        throw "Python tidak ditemukan. Buat .venv atau instal Python terlebih dahulu."
    }
    $PythonExecutable = $PythonCommand.Source
    Write-Warning ".venv tidak ditemukan; menggunakan Python dari PATH."
}

Write-Host "Menghentikan backend lama pada port 8000..." -ForegroundColor Yellow
$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($connection in $connections) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
    $commandLine = [string]$process.CommandLine
    $processName = [string]$process.Name

    if ($commandLine -match "uvicorn.*api\.main:app" -or $commandLine -match "api\.main:app.*uvicorn") {
        Write-Host "Menghentikan PID $($connection.OwningProcess): $processName" -ForegroundColor Yellow
        Stop-Process -Id $connection.OwningProcess -Force
    }
    else {
        throw "Port 8000 dipakai proses lain PID $($connection.OwningProcess). Tutup proses tersebut terlebih dahulu."
    }
}

Start-Sleep -Milliseconds 800

Write-Host "Menghapus cache Python..." -ForegroundColor Yellow
Get-ChildItem -Path (Join-Path $ProjectRoot "backend") -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Set-Location (Join-Path $ProjectRoot "backend")
$env:PYTHONPATH = "."

$buildInfo = & $PythonExecutable -c "from api.build_info import public_build_info; import json; print(json.dumps(public_build_info()))"
if ($LASTEXITCODE -ne 0) {
    throw "Pemeriksaan versi backend gagal. Pastikan dependensi pada .venv sudah terpasang."
}
Write-Host "Kode aktif: $buildInfo" -ForegroundColor Cyan
if ($buildInfo -notmatch $ExpectedBuild) {
    throw "Versi backend aktif tidak sesuai. Diharapkan: $ExpectedBuild."
}

Write-Host "Menjalankan LapisAI $ExpectedBuild di http://127.0.0.1:8000" -ForegroundColor Green
& $PythonExecutable -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

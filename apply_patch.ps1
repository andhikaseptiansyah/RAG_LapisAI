param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [switch]$RunTests
)

$ErrorActionPreference = "Stop"
$project = (Resolve-Path $ProjectRoot).Path
$source = Join-Path $PSScriptRoot "files"

$required = @(
    "backend\api\main.py",
    "backend\retrieval\query_expansion.py",
    "evaluation\generation\build_generation_dataset.py"
)
foreach ($path in $required) {
    if (-not (Test-Path (Join-Path $project $path))) {
        throw "ProjectRoot tidak valid. File tidak ditemukan: $path"
    }
}

$files = @(
    "backend\api\build_info.py",
    "backend\api\chat_service.py",
    "backend\api\routes_compat.py",
    "backend\retrieval\query_expansion.py",
    "backend\retrieval\evidence_verifier.py",
    "backend\retrieval\answerability.py",
    "evaluation\generation\build_generation_dataset.py",
    "evaluation\generation\build_retrieval_snapshot.py",
    "backend\tests\test_multilingual_query_variants_v3.py",
    "backend\tests\test_bilingual_evaluation_v11.py"
)

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $project "backup_bilingual_eval_v11_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

foreach ($relative in $files) {
    $src = Join-Path $source $relative
    $dst = Join-Path $project $relative
    if (-not (Test-Path $src)) {
        throw "File patch tidak ditemukan: $src"
    }

    if (Test-Path $dst) {
        $backupPath = Join-Path $backup $relative
        New-Item -ItemType Directory -Force -Path (Split-Path $backupPath) | Out-Null
        Copy-Item $dst $backupPath -Force
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Copy-Item $src $dst -Force
    Write-Host "DIPASANG: $relative"
}

Get-ChildItem $project -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Push-Location $project
try {
    python -m compileall -q `
        backend\api\build_info.py `
        backend\api\chat_service.py `
        backend\api\routes_compat.py `
        backend\retrieval\query_expansion.py `
        backend\retrieval\evidence_verifier.py `
        backend\retrieval\answerability.py `
        evaluation\generation\build_generation_dataset.py `
        evaluation\generation\build_retrieval_snapshot.py
    if ($LASTEXITCODE -ne 0) {
        throw "Kompilasi Python gagal. Backup tersedia di: $backup"
    }

    if ($RunTests) {
        $env:PYTHONPATH = "$project\backend;$project"
        python -m pytest -q `
            backend\tests\test_bilingual_evaluation_v11.py `
            evaluation\test_answerability_gate.py `
            evaluation\test_generation_quality_v3.py
        if ($LASTEXITCODE -ne 0) {
            throw "Pengujian patch gagal. Backup tersedia di: $backup"
        }
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "PATCH BERHASIL DIPASANG" -ForegroundColor Green
Write-Host "Backup file lama : $backup"
Write-Host "Build baru       : rag-bilingual-eval-v11-20260729"
Write-Host ""
Write-Host "Selanjutnya: restart backend, hapus folder ollama_smoke lama, lalu jalankan smoke evaluation tanpa -Resume."

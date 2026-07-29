param(
    [int]$TopK = 5,
    [switch]$Resume,
    [switch]$SkipLlmJudge,
    [switch]$ValidateOnly,
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$arguments = @(
    ".\evaluation\run_user_100_evaluation.py",
    "--models", "ollama",
    "--top-k", "$TopK"
)

if ($Resume) { $arguments += "--resume" }
if ($SkipLlmJudge) { $arguments += "--skip-llm-judge" }
if ($ValidateOnly) { $arguments += "--validate-only" }
if ($OutputDir.Trim()) { $arguments += @("--output-dir", $OutputDir) }

Write-Host "Running Ollama-only evaluation..." -ForegroundColor Cyan
python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Evaluation failed with exit code $LASTEXITCODE"
}

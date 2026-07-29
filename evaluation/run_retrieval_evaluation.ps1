param(
    [ValidateSet("development", "test", "all")]
    [string]$Split = "development",

    [string]$K = "1,3,5",

    [int]$CandidateK = 20,

    [double]$MinScore = 0.30,

    [switch]$SkipIndexing,

    [switch]$InstallDependencies,

    [switch]$NoReranker,

    [switch]$NoEvidenceVerification
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Project root: $ProjectRoot"

if ($InstallDependencies) {
    Write-Host "Installing backend dependencies..."
    python -m pip install -r .\backend\requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Validating ground-truth dataset..."
python .\evaluation\validate_ground_truth.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Arguments = @(
    ".\evaluation\evaluate_retrieval.py",
    "--split", $Split,
    "--k", $K,
    "--candidate-k", $CandidateK,
    "--min-score", $MinScore
)

if (-not $SkipIndexing) {
    $Arguments += "--index-missing"
}
if ($NoReranker) {
    $Arguments += "--no-reranker"
}
if ($NoEvidenceVerification) {
    $Arguments += "--no-evidence-verification"
}

Write-Host "Running retrieval evaluation..."
python @Arguments
exit $LASTEXITCODE

param(
    [string]$English = ".\evaluation\datasets\qna_english_user.csv",
    [string]$Indonesian = ".\evaluation\datasets\qna_indonesia_user.csv",
    [int]$TopK = 5,
    [switch]$Resume,
    [switch]$SkipLlmJudge,
    [switch]$ValidateOnly,
    [ValidateSet("development", "holdout")]
    [string]$BenchmarkRole = "development",
    [switch]$RequireFinalReport,
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$arguments = @(
    ".\evaluation\generation\run_three_model_evaluation.py",
    "--english", $English,
    "--indonesian", $Indonesian,
    "--top-k", "$TopK",
    "--benchmark-role", $BenchmarkRole
)

if ($Resume) { $arguments += "--resume" }
if ($SkipLlmJudge) { $arguments += "--skip-llm-judge" }
if ($ValidateOnly) { $arguments += "--validate-only" }
if ($RequireFinalReport) { $arguments += "--require-final-report" }
if ($OutputDir.Trim()) { $arguments += @("--output-dir", $OutputDir) }

python @arguments

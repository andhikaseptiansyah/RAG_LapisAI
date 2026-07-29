param(
    [string]$English = ".\evaluation\datasets\qna_english_user.csv",
    [string]$Indonesian = ".\evaluation\datasets\qna_indonesia_user.csv",
    [int]$TopK = 5,
    [switch]$Resume,
    [switch]$SkipLlmJudge,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$arguments = @(
    ".\evaluation\generation\run_three_model_evaluation.py",
    "--english", $English,
    "--indonesian", $Indonesian,
    "--top-k", "$TopK"
)

if ($Resume) { $arguments += "--resume" }
if ($SkipLlmJudge) { $arguments += "--skip-llm-judge" }
if ($ValidateOnly) { $arguments += "--validate-only" }

python @arguments

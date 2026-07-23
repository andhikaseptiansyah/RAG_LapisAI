$ErrorActionPreference = "Stop"
$HealthUrl = "http://127.0.0.1:8000/api/health"
$ExpectedBuild = "rag-multilingual-v8-20260723"

$response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 10
$response | ConvertTo-Json -Depth 8

if ([string]$response.buildVersion -ne $ExpectedBuild) {
    throw "Backend aktif bukan V8. Build aktif: $($response.buildVersion)"
}
if (-not $response.chatServiceSha256 -or -not $response.answerFormatterSha256 -or -not $response.groundingValidatorSha256) {
    throw "Fingerprint file V8 tidak lengkap."
}

Write-Host "Backend V8 aktif." -ForegroundColor Green
Write-Host "chat_service=$($response.chatServiceSha256)" -ForegroundColor Green
Write-Host "answer_formatter=$($response.answerFormatterSha256)" -ForegroundColor Green
Write-Host "grounding_validator=$($response.groundingValidatorSha256)" -ForegroundColor Green

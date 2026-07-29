$ErrorActionPreference = "Stop"
$HealthUrl = "http://127.0.0.1:8000/api/health"
$ExpectedBuild = "rag-multilingual-v7-20260723"

$response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 5
$response | ConvertTo-Json -Depth 8

if ([string]$response.buildVersion -ne $ExpectedBuild) {
    throw "Backend aktif bukan V7. Build aktif: $($response.buildVersion)"
}
if (-not $response.chatServiceSha256) {
    throw "Fingerprint chat_service tidak tersedia. Backend yang berjalan tidak sesuai paket V7."
}

Write-Host "Backend V7 aktif. chatServiceSha256=$($response.chatServiceSha256)" -ForegroundColor Green

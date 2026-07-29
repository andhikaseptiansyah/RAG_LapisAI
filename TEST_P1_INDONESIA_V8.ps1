$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$ExpectedBuild = "rag-multilingual-v8-20260723"

$health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -Method Get -TimeoutSec 10
if ([string]$health.buildVersion -ne $ExpectedBuild) {
    throw "Backend aktif bukan V8. Build aktif: $($health.buildVersion)"
}
Write-Host "Backend: $($health.buildVersion)" -ForegroundColor Green

$username = Read-Host "Username LapisAI"
$securePassword = Read-Host "Password LapisAI" -AsSecureString
$credential = New-Object System.Management.Automation.PSCredential($username, $securePassword)
$password = $credential.GetNetworkCredential().Password

$loginBody = @{ username = $username; password = $password } | ConvertTo-Json
$login = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.token)" }

$chatBody = @{
    message = "Seberapa cepat insiden IT P1 harus diselesaikan?"
    language = "ID"
    model = "ollama"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "$BaseUrl/api/chat" -Method Post -Headers $headers -ContentType "application/json" -Body $chatBody -TimeoutSec 180
$response | ConvertTo-Json -Depth 10

if ([string]$response.buildVersion -ne $ExpectedBuild) {
    throw "Respons chat bukan dari V8. Build: $($response.buildVersion)"
}
if ([string]$response.answer -notmatch "4\s+jam") {
    throw "Jawaban belum benar. answer=$($response.answer); failure_stage=$($response.failure_stage); generation_mode=$($response.generation_mode)"
}
if ([string]$response.generation_mode -ne "verified_scalar") {
    throw "Jalur deterministik V8 tidak dipakai. generation_mode=$($response.generation_mode)"
}
if (-not $response.sources) {
    throw "Sumber dokumen tidak tersedia."
}

Write-Host "TES BERHASIL: $($response.answer)" -ForegroundColor Green
Write-Host "generation_mode=$($response.generation_mode)" -ForegroundColor Green
Write-Host "retrieval_mode=$($response.retrieval_mode)" -ForegroundColor Green

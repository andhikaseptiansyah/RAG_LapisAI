$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$ExpectedBuild = "rag-multilingual-v7-20260723"

$health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -Method Get -TimeoutSec 10
if ([string]$health.buildVersion -ne $ExpectedBuild) {
    throw "Backend aktif bukan V7. Build aktif: $($health.buildVersion)"
}
Write-Host "Backend: $($health.buildVersion) | chatService=$($health.chatServiceSha256)" -ForegroundColor Green

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

if (-not $response.sources -or $response.confidence -le 0) {
    throw "Masih terjadi penolakan. failure_stage=$($response.failure_stage), retrieval_mode=$($response.retrieval_mode), retrieval_query=$($response.retrieval_query)"
}

Write-Host "Tes berhasil: $($response.answer)" -ForegroundColor Green
Write-Host "Mode retrieval: $($response.retrieval_mode)" -ForegroundColor Green

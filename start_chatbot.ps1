# =============================================================
# bonded-exhibition-chatbot-data — 로컬 실행 + 브라우저 오픈
# 사용법: .\start_chatbot.ps1
# 정지:   Stop-Process -Id <PID>  (스크립트 끝에 출력됨)
# =============================================================

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"

$repo = "E:\GitHub\bonded-exhibition-chatbot-data"
$port = 5099
$logFile = "$repo\logs\chatbot_local.log"
$logErr  = "$repo\logs\chatbot_local.err"

Set-Location $repo

# 1. main 동기화 시도 (실패해도 계속)
Write-Host "=== 1/4 main 동기화 ===" -ForegroundColor Yellow
git fetch origin main 2>&1 | Out-Null
$pullResult = git pull --ff-only origin main 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  pull OK" -ForegroundColor Green
} else {
    Write-Host "  pull skip (working tree 변경 또는 fast-forward 불가):" -ForegroundColor DarkYellow
    Write-Host "  $pullResult" -ForegroundColor DarkGray
    Write-Host "  → working tree 그대로 진행" -ForegroundColor DarkGray
}

# 2. 핵심 의존성 보장 (working tree minimal이어도 동작)
Write-Host ""
Write-Host "=== 2/4 의존성 보장 ===" -ForegroundColor Yellow
$pkgs = @(
    "flask>=3.0,<4",
    "flask-cors>=4.0,<7",
    "gunicorn>=21.2,<26",
    "anthropic>=0.30,<1",
    "sentence-transformers>=2.7,<6",
    "torch>=2.0,<3",
    "pyjwt>=2.8,<3",
    "python-dotenv>=1.0,<2",
    "pyyaml>=6.0,<7",
    "requests>=2.31,<3"
)
python -m pip install -q --upgrade-strategy only-if-needed $pkgs 2>&1 | Select-Object -Last 3
Write-Host "  의존성 OK" -ForegroundColor Green

# 3. 백그라운드 봇 시작
Write-Host ""
Write-Host "=== 3/4 봇 시작 (port $port) ===" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$repo\logs" | Out-Null

# 기존 5099 점유 프로세스 정리 (있으면)
$existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  port $port 이미 사용 중 (PID $($existing.OwningProcess)). 정리 시도." -ForegroundColor DarkYellow
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

$proc = Start-Process -FilePath python `
    -ArgumentList @("web_server.py", "--port", "$port", "--host", "127.0.0.1") `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $logErr `
    -WindowStyle Hidden `
    -PassThru

Write-Host "  PID $($proc.Id) 시작" -ForegroundColor Green
Write-Host "  sentence-transformers 모델 로드 대기 (~30s)..." -ForegroundColor DarkGray

# 4. listen 준비 대기 (최대 60초)
Write-Host ""
Write-Host "=== 4/4 health check + 브라우저 오픈 ===" -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 3 -ErrorAction Stop
        $ready = $true
        break
    } catch {
        # 아직 listen 안 됨
    }
}

if ($ready) {
    Write-Host "  Health: $($health | ConvertTo-Json -Compress)" -ForegroundColor Cyan
    Start-Process "http://127.0.0.1:$port/"
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host " 챗봇 실행 중 — 브라우저 자동 오픈" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host " URL    : http://127.0.0.1:$port/"
    Write-Host " Health : http://127.0.0.1:$port/api/health"
    Write-Host " Stats  : http://127.0.0.1:$port/api/v1/stats"
    Write-Host " PID    : $($proc.Id)"
    Write-Host " 정지   : Stop-Process -Id $($proc.Id)"
    Write-Host " 로그   : Get-Content '$logFile' -Tail 30 -Wait"
    Write-Host " 에러   : Get-Content '$logErr' -Tail 30"
    Write-Host "================================================" -ForegroundColor Green
} else {
    Write-Host "  Health check 60s 타임아웃" -ForegroundColor Red
    Write-Host "  마지막 stdout (마지막 30줄):" -ForegroundColor DarkYellow
    if (Test-Path $logFile) { Get-Content $logFile -Tail 30 }
    Write-Host "  마지막 stderr (마지막 30줄):" -ForegroundColor DarkYellow
    if (Test-Path $logErr)  { Get-Content $logErr -Tail 30 }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  봇 프로세스 정리 완료" -ForegroundColor DarkGray
    exit 1
}

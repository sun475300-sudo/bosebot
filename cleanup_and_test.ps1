# =====================================================================
# bonded-exhibition-chatbot-data
#   Phase A: pytest 실행
#   Phase B: 브랜치 분석 (dry-run)
#   Phase C: -Execute 플래그 시 모든 비-main 브랜치를 main에 머지 + 로컬/원격 삭제
#
# 사용법:
#   1) 분석만 (안전):
#        powershell -ExecutionPolicy Bypass -File .\cleanup_and_test.ps1
#   2) 테스트만:
#        powershell -ExecutionPolicy Bypass -File .\cleanup_and_test.ps1 -SkipBranches
#   3) 실제 실행 (브랜치 머지/삭제):
#        powershell -ExecutionPolicy Bypass -File .\cleanup_and_test.ps1 -Execute
# =====================================================================

param(
    [switch]$Execute,        # 실제 머지/삭제 수행
    [switch]$SkipPytest,     # pytest 스킵
    [switch]$SkipBranches,   # 브랜치 처리 스킵
    [switch]$ForceDelete     # 머지 실패해도 브랜치 삭제 (위험)
)

$ErrorActionPreference = 'Continue'
$repo = 'E:\GitHub\bonded-exhibition-chatbot-data'
Set-Location $repo

function Section($title) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host $title -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

# ---------------------------------------------------------------------
# Phase A: pytest
# ---------------------------------------------------------------------
if (-not $SkipPytest) {
    Section "Phase A: pytest 실행"

    # python 확인
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) {
        Write-Host "[ERROR] python 또는 py 명령을 찾을 수 없습니다." -ForegroundColor Red
        exit 1
    }

    # pytest 설치 확인
    & $py.Source -m pytest --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pytest 미설치 - requirements.txt 설치 시도 중..." -ForegroundColor Yellow
        if (Test-Path "$repo\requirements.txt") {
            & $py.Source -m pip install -r "$repo\requirements.txt"
        } else {
            & $py.Source -m pip install pytest
        }
    }

    Write-Host "pytest 실행 중... (출력은 pytest_output.log 에도 저장됨)" -ForegroundColor Yellow
    & $py.Source -m pytest tests/ -v --tb=short 2>&1 | Tee-Object -FilePath "$repo\pytest_output.log"
    $pytestExit = $LASTEXITCODE
    Write-Host ""
    if ($pytestExit -eq 0) {
        Write-Host "[PASS] pytest 모든 테스트 통과" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] pytest 실패 (exit=$pytestExit). 자세한 내용은 pytest_output.log 참조." -ForegroundColor Red
        if ($Execute) {
            Write-Host "테스트가 실패한 상태에서 브랜치 머지를 진행하시겠습니까? (y/N)" -ForegroundColor Yellow
            $ans = Read-Host
            if ($ans -ne 'y' -and $ans -ne 'Y') {
                Write-Host "중단합니다." -ForegroundColor Red
                exit 1
            }
        }
    }
}

# ---------------------------------------------------------------------
# Phase B: 브랜치 분석
# ---------------------------------------------------------------------
if ($SkipBranches) { exit 0 }

Section "Phase B: 브랜치 분석"

git fetch --all --prune | Out-Null
git checkout main 2>&1 | Out-Null
git pull --ff-only 2>&1 | Out-Null

# 원격 브랜치 목록 (main 제외)
$remoteBranches = git branch -r |
    Where-Object { $_ -notmatch '->' -and $_ -notmatch 'origin/main\s*$' } |
    ForEach-Object { $_.Trim() -replace '^origin/', '' } |
    Sort-Object -Unique

# 로컬 브랜치 목록 (main 제외)
$localBranches = git branch |
    ForEach-Object { ($_ -replace '^\*', '').Trim() } |
    Where-Object { $_ -ne 'main' -and $_ -ne '' } |
    Sort-Object -Unique

$allBranches = ($remoteBranches + $localBranches) | Sort-Object -Unique

Write-Host "총 브랜치 수 (main 제외): $($allBranches.Count)" -ForegroundColor White
Write-Host ""

$report = @()
foreach ($b in $allBranches) {
    $ref = "origin/$b"
    git rev-parse --verify --quiet "refs/remotes/$ref" | Out-Null
    if ($LASTEXITCODE -ne 0) { $ref = $b }

    $ahead  = (git rev-list --count "main..$ref" 2>$null)
    $behind = (git rev-list --count "$ref..main" 2>$null)
    $merged = git branch -r --merged main | Select-String "origin/$b\s*$"
    $status = if ($merged) { 'MERGED' } elseif ([int]$ahead -eq 0) { 'NO-DIFF' } else { 'AHEAD' }
    $report += [pscustomobject]@{
        Branch  = $b
        Status  = $status
        Ahead   = $ahead
        Behind  = $behind
    }
}

$report | Format-Table -AutoSize

# ---------------------------------------------------------------------
# Phase C: 실제 머지 + 삭제
# ---------------------------------------------------------------------
if (-not $Execute) {
    Write-Host ""
    Write-Host "DRY-RUN 모드입니다. 실제 머지/삭제를 수행하려면 -Execute 옵션과 함께 다시 실행하세요." -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\cleanup_and_test.ps1 -Execute" -ForegroundColor Yellow
    exit 0
}

Section "Phase C: 머지 + 삭제 수행"

# git author 확인
$gitName  = git config user.name
$gitEmail = git config user.email
if (-not $gitName -or -not $gitEmail) {
    Write-Host "[ERROR] git user.name / user.email 미설정. 다음 명령으로 설정 후 다시 실행하세요:" -ForegroundColor Red
    Write-Host '  git config --global user.name "Your Name"' -ForegroundColor Red
    Write-Host '  git config --global user.email "you@example.com"' -ForegroundColor Red
    exit 1
}

$mergedOk     = @()
$mergedSkip   = @()
$conflicted   = @()

foreach ($row in $report) {
    $b = $row.Branch
    $ref = "origin/$b"
    git rev-parse --verify --quiet "refs/remotes/$ref" | Out-Null
    if ($LASTEXITCODE -ne 0) { $ref = $b }

    Write-Host ""
    Write-Host "--- $b ($($row.Status)) ---" -ForegroundColor White

    if ($row.Status -eq 'MERGED' -or $row.Status -eq 'NO-DIFF') {
        Write-Host "  이미 main에 반영됨 → 머지 스킵"
        $mergedSkip += $b
    } else {
        Write-Host "  main에 머지 시도..."
        git merge --no-ff $ref -m "Merge branch '$b' into main" 2>&1 | Write-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [CONFLICT] 충돌 발생 → abort" -ForegroundColor Red
            git merge --abort 2>$null
            $conflicted += $b
            if (-not $ForceDelete) {
                Write-Host "  -ForceDelete 미지정 → 이 브랜치는 보존합니다." -ForegroundColor Yellow
                continue
            }
            Write-Host "  -ForceDelete 지정됨 → 머지 실패해도 브랜치 삭제 진행." -ForegroundColor Yellow
        } else {
            $mergedOk += $b
        }
    }

    # 로컬 브랜치 삭제
    if ($localBranches -contains $b) {
        Write-Host "  로컬 삭제: $b"
        git branch -D $b 2>&1 | Write-Host
    }
    # 원격 브랜치 삭제
    if ($remoteBranches -contains $b) {
        Write-Host "  원격 삭제: origin/$b"
        git push origin --delete $b 2>&1 | Write-Host
    }
}

# main 푸시
Section "main 푸시"
git push origin main 2>&1 | Write-Host

# 최종 리포트
Section "결과 요약"
Write-Host "머지 성공  : $($mergedOk.Count)" -ForegroundColor Green
$mergedOk | ForEach-Object { Write-Host "  - $_" }
Write-Host "스킵(이미 머지됨): $($mergedSkip.Count)" -ForegroundColor Yellow
$mergedSkip | ForEach-Object { Write-Host "  - $_" }
Write-Host "충돌(보존)  : $($conflicted.Count)" -ForegroundColor Red
$conflicted | ForEach-Object { Write-Host "  - $_" }

git fetch --all --prune | Out-Null
$remaining = git branch -r | Where-Object { $_ -notmatch '->' } | ForEach-Object { $_.Trim() }
Write-Host ""
Write-Host "남은 원격 브랜치:" -ForegroundColor Cyan
$remaining | ForEach-Object { Write-Host "  - $_" }

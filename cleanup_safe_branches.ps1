# bonded-exhibition-chatbot-data branch cleanup script (ASCII only)

param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$repo = "https://github.com/sun475300-sudo/bonded-exhibition-chatbot-data.git"
$work = Join-Path $env:TEMP "becd-cleanup"
$logFile = "E:\GitHub\bonded-exhibition-chatbot-data\cleanup_log.txt"
Start-Transcript -Path $logFile -Force | Out-Null

# Add Git to PATH
$gitCandidates = @(
    "C:\Program Files\Git\cmd",
    "C:\Program Files\Git\bin",
    "C:\Program Files (x86)\Git\cmd",
    "$env:LOCALAPPDATA\Programs\Git\cmd"
)
foreach ($p in $gitCandidates) {
    if (Test-Path (Join-Path $p "git.exe")) {
        $env:PATH = "$p;$env:PATH"
        Write-Host "[INFO] git found at $p"
        break
    }
}
$gitVer = & git --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] git not found"
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host "[INFO] $gitVer"

if (Test-Path $work) { Remove-Item -Recurse -Force $work }

Write-Host ""
Write-Host "=== 1) Fresh clone ==="
git clone --quiet $repo $work
Set-Location $work

if (-not (git config user.email)) {
    git config user.email "sun475300@gmail.com"
    git config user.name  "jangsunwoo"
}

git fetch --all --prune --quiet

# List non-main branches
$branches = git branch -r | Where-Object { $_ -notmatch 'HEAD' -and $_ -notmatch 'origin/main\s*$' } |
    ForEach-Object { ($_ -replace '^\s*origin/', '').Trim() } | Sort-Object -Unique

Write-Host ""
Write-Host "=== 2) Branch analysis (total $($branches.Count)) ==="

$mergedDelete = @()
$ffMerge = @()
$conflicted = @()

foreach ($b in $branches) {
    git rev-parse --verify --quiet "refs/remotes/origin/$b" | Out-Null
    if ($LASTEXITCODE -ne 0) { continue }

    $merged = git branch -r --merged origin/main | Select-String "origin/$b\s*$"
    if ($merged) {
        $mergedDelete += $b
        Write-Host "  [MERGED] $b"
        continue
    }

    $behind = git rev-list --count "origin/$b..origin/main"
    if ([int]$behind -eq 0) {
        $ffMerge += $b
        Write-Host "  [FF]     $b"
    } else {
        $conflicted += $b
        Write-Host "  [KEEP]   $b (behind=$behind)"
    }
}

Write-Host ""
Write-Host "Plan:"
Write-Host "  FF merge + delete : $($ffMerge.Count)"
Write-Host "  Delete only       : $($mergedDelete.Count)"
Write-Host "  Keep              : $($conflicted.Count)"

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY-RUN: no push/delete performed"
    Set-Location $env:USERPROFILE
    Stop-Transcript | Out-Null
    exit 0
}

# FF merges
git checkout main 2>&1 | Out-Null
$actualFF = @()
foreach ($b in $ffMerge) {
    Write-Host ""
    Write-Host "=== FF merge: $b ==="
    git merge --ff-only "origin/$b"
    if ($LASTEXITCODE -eq 0) {
        $actualFF += $b
    } else {
        Write-Host "  [WARN] FF failed - keep"
        $conflicted += $b
    }
}

# Push main if anything was merged
if ($actualFF.Count -gt 0) {
    Write-Host ""
    Write-Host "=== Push main ==="
    git push origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] push main failed"
        Stop-Transcript | Out-Null
        exit 1
    }
}

# Delete branches (FF merged + already merged)
$toDelete = $actualFF + $mergedDelete
foreach ($b in $toDelete) {
    Write-Host ""
    Write-Host "=== Delete remote: $b ==="
    git push origin --delete $b
}

Write-Host ""
Write-Host "=== RESULT ==="
Write-Host "FF merged + deleted: $($actualFF.Count)"
$actualFF | ForEach-Object { Write-Host "  - $_" }
Write-Host "Deleted only: $($mergedDelete.Count)"
$mergedDelete | ForEach-Object { Write-Host "  - $_" }
Write-Host "Kept: $($conflicted.Count)"
$conflicted | ForEach-Object { Write-Host "  - $_" }

Write-Host ""
Write-Host "=== Remaining remote branches ==="
git fetch --prune --quiet
git branch -r | Where-Object { $_ -notmatch 'HEAD' }

Set-Location $env:USERPROFILE
Stop-Transcript | Out-Null

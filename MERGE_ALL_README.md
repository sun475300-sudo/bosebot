# 🚀 MERGE_ALL_AND_CLEAN — 1줄로 끝내기

## 사전 준비 (5분)

```bash
# 1) Repo 위치
cd E:\GitHub\bonded-exhibition-chatbot-data

# 2) Git index lock 정리 (혹시 있으면)
del .git\index.lock 2>nul

# 3) gh CLI 설치 + 로그인 (Windows)
winget install GitHub.cli
gh auth login    # GitHub.com → HTTPS → Login with web browser

# 4) outputs/pr-artifacts/ 가 repo 안에 있는지 확인
dir outputs\pr-artifacts\PR_BODY_C.md   :: 있어야 함
```

> 만약 `outputs/pr-artifacts/` 가 다른 경로 (예: 사용자 홈) 에 있다면, `MERGE_ALL_AND_CLEAN.bat` 의 `set ART=...` 줄을 그 절대 경로로 수정하세요.

## 실행 (1줄)

### Windows
```bat
MERGE_ALL_AND_CLEAN.bat
```

### Linux / macOS / WSL
```bash
bash MERGE_ALL_AND_CLEAN.sh
```

## 자동 동작

스크립트는 5단계 모두 자동으로 수행합니다:

| 단계 | 내용 |
|---|---|
| **0** | `gh auth status` 검사 — 인증 안 됐으면 즉시 종료 |
| **1** | `git fetch origin && git pull main` — 최신 main 동기화 |
| **2** | 20 브랜치를 bundle 에서 fetch 후 origin 에 push (priority 순서: D → G → C → H → J → E → F → I → K → L → M → N → O → P → Q → R → S → T → U → V) |
| **3** | 각 브랜치마다 `gh pr create` → `gh pr merge --squash --delete-branch` → 실패 시 `--merge` 폴백 → 다음 PR 시작 전 main 재동기화 (cumulative rebase) |
| **4** | 로컬 `claude/*` 브랜치 모두 삭제, `git remote prune origin` |
| **5** | `git log --oneline -5`, `git branch`, `gh pr list --state open`, `git rev-parse HEAD` 출력 |

## 예상 출력 (정상)

```
[0/5] gh CLI auth status
✓ Logged in to github.com as sun475300-sudo

[1/5] Sync main
From https://github.com/sun475300-sudo/bosebot
 * branch              main       -> FETCH_HEAD
Already up to date.

[2/5] Fetch + push 20 branches
  --- D  claude/ci-bootstrap-… ---
  Branch 'claude/ci-bootstrap-…' set up to track …
  ...
  --- V  claude/static-analysis-hardening-… ---

[3/5] Create PRs + auto-merge
  --- PR for D : claude/ci-bootstrap-… ---
  https://github.com/sun475300-sudo/bosebot/pull/4
  ✓ Squashed and merged pull request #4
  ...
  --- PR for V : claude/static-analysis-hardening-… ---
  ✓ Squashed and merged pull request #23

[4/5] Local branch cleanup
  deleting local claude/ci-bootstrap-…
  ...
  deleting local claude/static-analysis-hardening-…

[5/5] Final state
--- last 5 commits on main ---
abcdef1 [V] auto: …
abcdef2 [U] auto: …
…
--- local branches ---
* main
--- still-open PRs ---
(none — 사용자 PR #1/#2/#3 만 남음, 사용자 직접 처리)
=== main HEAD ===
<new SHA>
Done.
```

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `[ERR] gh CLI not authenticated` | `gh auth login` 실행 후 재시도 |
| `[ERR] PR artifacts not found` | bat 의 `set ART=` 를 outputs/pr-artifacts/ 의 절대 경로로 수정 |
| `gh: GraphQL error: ... cannot squash` | 저장소에서 squash merge 비활성화 — 스크립트가 자동으로 `--merge` 폴백 |
| `Pull request #N already exists` | 멱등 — 이미 존재하면 skip 후 진행 |
| `Required status check ... is expected` | 브랜치 보호 룰이 CI green 요구 — D 브랜치 (CI bootstrap) 가 먼저 머지되어야 동작. 정상적으로 D → G → C 순으로 진행되며 CI 가동 후 자동 진행됨. CI 실패 시 해당 PR 만 수동 처리 |
| `merge failed — try manually` 경고 | 일부 PR (Q, R, S 등 web_server.py 다중 변경 시) conflict 가능 → 해당 PR 페이지에서 수동 rebase + resolve |
| 일부 PR `--admin` 거부 | `--admin` 권한 없음 — 스크립트는 일반 머지만 시도하므로 영향 없음. branch protection 자체가 막으면 위 행 참조 |
| 스크립트가 너무 빨리 끝남 | gh auth 안 됐거나 ART 경로 못 찾음 — 출력 메시지 확인 |

## 안전 가드

스크립트는 **다음을 절대 하지 않습니다**:

- ❌ `git push --force` / `--force-with-lease`
- ❌ `git push origin :main` (main 삭제)
- ❌ `gh pr merge --admin` (관리자 우회 — 빌트인 fallback 에 의존)
- ❌ `gh pr close` (사용자 본인 PR #1/#2/#3 건드리지 않음)
- ❌ `git reset --hard origin/main` 같은 파괴적 작업

CI 실패 / branch protection / conflict 등으로 머지 안 되는 PR 은 **경고만 출력하고 다음으로 진행** — 사용자가 나중에 수동 처리.

## 부분 실행 (디버그)

원하는 단계만 따로:

```bash
# 단계 2만 (push)
bash outputs/pr-artifacts/PUSH_ALL.sh E:/GitHub/bonded-exhibition-chatbot-data

# 단계 3 일부 (특정 PR 만)
gh pr create --base main --head claude/ci-bootstrap-… --body-file outputs/pr-artifacts/PR_BODY_D.md
gh pr merge claude/ci-bootstrap-… --squash --delete-branch

# 단계 4 만 (로컬 정리)
git checkout main
for b in $(git branch | grep claude/); do git branch -D "$b"; done
```

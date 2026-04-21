# Git Lock 파일 해결 방법

## 증상
GitHub Desktop에서 **"A lock file already exists in the repository"** 에러 발생

## 원인
이전 git 작업(pull/push/merge 등)이 비정상 종료되면서 `.git/index.lock` 파일이 남아있음

## 해결 방법

### 방법 1: 파일 탐색기로 직접 삭제
1. `E:\GitHub\bonded-exhibition-chatbot-data\.git\` 폴더 열기
2. `index.lock` 파일 삭제
3. GitHub Desktop에서 다시 Pull/Push 시도

### 방법 2: PowerShell로 삭제 (관리자 권한)
```powershell
Remove-Item "E:\GitHub\bonded-exhibition-chatbot-data\.git\index.lock" -Force
```

### 방법 3: Git Bash / CMD
```bash
cd E:\GitHub\bonded-exhibition-chatbot-data
del .git\index.lock
```

## 주의사항
- lock 파일 삭제 전, 다른 git 작업이 실행 중인지 확인하세요
- GitHub Desktop, VS Code, 터미널 등 여러 곳에서 동시에 git 작업 시 발생할 수 있습니다

## 예방
- 한 번에 하나의 git 클라이언트만 사용하세요
- 작업 전 GitHub Desktop을 닫고 터미널에서 작업하거나, 반대로 하세요

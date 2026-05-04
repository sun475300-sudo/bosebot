# main 브랜치 push 가이드

이 저장소는 .bat 파일이 너무 많아서 어떤 걸 언제 실행해야 하는지 헷갈리기
쉽다. 이 문서는 그 결정 트리 한 장이다.

## 짧은 결론

평소에는 단 하나만 실행한다.

```
E:\GitHub\bonded-exhibition-chatbot-data\PUSH_EVERYTHING_TO_MAIN.bat
```

이 스크립트가 다음을 자동으로 수행한다.

1. `.git\*.lock` 정리 (`UNLOCK_REPO.bat` 호출)
2. 4종 회귀 테스트 실행 — 실패 시 중단
   - `tests/test_law_api_admrul.py` (행정규칙 fetcher + sync_one 회귀)
   - `tests/test_bonded_notice_qa.py` (보세전시장 고시 골든셋)
   - `tests/test_law_auto_updater.py` (백그라운드 자동 갱신)
   - `tests/test_patent_regression.py` (특허 질의 32케이스)
   - `tests/test_chatbot.py`
3. 안전한 변경분만 stage
   - 제외: `*.db`, `*.db-journal`, `*.db.test`, `*.bundle`, `logs/*`
4. 적절한 커밋 메시지로 commit
5. `git push origin main` (force push 하지 않음)

푸시 실패 시 스크립트가 원인을 출력하고 중단한다 (강제 push 시도하지 않음).

## .bat 파일별 역할

### 매일 쓰는 것
| 스크립트 | 용도 |
| --- | --- |
| **PUSH_EVERYTHING_TO_MAIN.bat** | 통합 push (이게 거의 전부) |
| UNLOCK_REPO.bat | GitHub Desktop 이 잡고 있는 `.git\*.lock` 강제 해제 |
| REFRESH_LAW_DATA.bat | 행정규칙/법령 본문을 즉시 새로 받아옴 |
| CHECK_LAW_API.bat | API 변경 여부만 확인 (캐시 미갱신) |
| start.bat | 챗봇 서버 기동 |

### 운영 (Task Scheduler)
| 스크립트 | 용도 |
| --- | --- |
| SCHEDULE_LAW_REFRESH.bat | 행정규칙 자동 갱신 작업을 schtasks 에 등록 |
| UNSCHEDULE_LAW_REFRESH.bat | 등록 해제 |

### 사용 금지 (DEPRECATED)
| 스크립트 | 사유 |
| --- | --- |
| PUSH_PATENT_FIX_TO_MAIN.bat | fcc3714 이전 작업 — 이미 origin/main 에 반영됨 |
| PUSH_LAW_API_TO_MAIN.bat    | fcc3714 와 충돌 — admRul 작업은 이미 main 에 있음 |
| PUSH_LAW_AUTO_UPDATE_TO_MAIN.bat | 통합 스크립트로 대체됨 |
| COMMIT_UI_READABILITY.bat   | 통합 스크립트로 대체됨 |
| MERGE_ALL_BRANCHES_TO_MAIN.bat | 사용 금지 — 직접 호출 시 위험 |

deprecated 스크립트들은 실행해도 첫 줄에 경고 메시지를 출력하고
즉시 종료하도록 처리되어 있다. 실수로 더블클릭해도 망가지지 않는다.

## 푸시 실패할 때

### `git push origin main` 이 거부됨
원격이 더 앞서 있는 경우다. 통합 스크립트가 이 상태를 감지하고 메시지로
알려준다.

```
git pull --ff-only origin main
```

위 명령으로 fast-forward 가능하면 그대로 진행, 아니면 충돌 해결 후 다시
회귀 테스트를 통과시키고 통합 스크립트를 재실행한다.

### `.git\index.lock` 이 풀리지 않음
GitHub Desktop 을 닫고 `UNLOCK_REPO.bat` 를 직접 실행한 다음 통합
스크립트를 다시 돌린다.

### Windows Credential Manager 의 stale GitHub 자격증명
자격증명을 한 번 삭제(`Windows Credential Manager` -> `windows 자격 증명`
-> `git:https://github.com` 항목 제거) 한 뒤 GitHub Desktop 으로 다시
로그인하고 통합 스크립트를 재실행한다.

## 절대 하지 말 것

- `git push --force origin main` (force push 금지)
- 위 deprecated 스크립트를 직접 호출
- `.db`, `.db-journal`, `*.bundle`, `logs/*` 를 commit
- 회귀 테스트가 실패한 상태에서 push

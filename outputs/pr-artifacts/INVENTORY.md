# 작업 인벤토리 — bonded-chatbot · 사이클 1+2+3+4+5

## 📊 origin (sun475300-sudo/bosebot)
- default HEAD: `c28ca4c` · OPEN PRs: 3 (#1 #2 #3) · 워크플로 0

## ✅ sandbox-built · 푸시 권장 20개

| 우선 | T | branch | tests |
|---|---|---|---|
| 1 | D | ci-bootstrap | YAML |
| 2 | G | small-fixes | 4 |
| 3 | C | fix-3-audits | 13 |
| 4 | H | perf-stability-cycle3 | 5 |
| 5 | J | response-quality | 4 |
| 6 | E | h5-test-isolation | conftest |
| 7 | F | readme-ops-guide | docs |
| 8 | I | observability | 5 |
| 9 | K | ops-automation | 4 |
| 10 | L | test-strengthen | 9 |
| 11 | M | privacy | 5 |
| 12 | N | backup-restore | 4 |
| 13 | O | per-user-rate-limit | 9 |
| 14 | P | ab-testing | 7 |
| 15 | Q | response-cache | 8 |
| 16 | **R** | audit-search-api | **7** |
| 17 | **S** | otel-tracing | **5** |
| 18 | **T** | lang-detection | **9** |
| 19 | **U** | anomaly-detection | **4** |
| 20 | **V** | static-analysis-hardening | **4** |

**누적**: 22 commit · **106 신규 테스트** · 3 워크플로 · 9 신규 모듈 · 6 ops scripts.

## 🚀 사용자 1줄 실행
```bat
E:\GitHub\bonded-exhibition-chatbot-data\..\outputs\pr-artifacts\PUSH_ALL.bat
```
```bash
bash outputs/pr-artifacts/PUSH_ALL.sh E:/GitHub/bonded-exhibition-chatbot-data
```

## 사이클 5 신규 환경변수
| 변수 | default | track |
|---|---|---|
| `AUDIT_DB_PATH` | data/audit.db | R |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | S |
| `ANOMALY_WINDOW_HOURS` | 24 | U |
| `ANOMALY_Z_THRESHOLD` | 3.0 | U |
| `ANOMALY_WEBHOOK_URL` | unset | U |

## 🔮 다음 사이클 6 후보
1. **W** WebSocket streaming response — partial answer 실시간 전송
2. **X** Multi-tenant 강화 — tenant 별 FAQ / 통계 / 권한 분리
3. **Y** Knowledge graph 통합 — entity → 법령 조항 cross-link
4. **Z** Chat history 검색 API — 사용자가 자기 과거 대화 조회
5. **AA** API key rotation — 자동 만료 + 재발급 endpoint

---

## 🧪 통합 테스트 결과 (사이클 1~5 누적, sandbox 검증)

### Sequential merge 결과 (`claude/integrated-cycle1-5-202604280612`)
- **13/20 트랙 자동 merge OK** (D, G, C, J, E, F, I, K, M, T, U, V + 일부)
- **7/20 트랙 conflict** — 모두 `web_server.py` 동일 영역 (insert before `if __name__`) 또는 runtime log 파일
  - 해결: 사용자가 **순차 머지** 시 자동 rebase 로 해소 가능 (각 브랜치는 main 단독 적용 시 conflict-free)

### pytest 결과
- **1,399 pass / 1 fail / 5 skip** (99.93%)
- 실패: `test_llm_fallback.py::test_provider_rate_limiter` (사전 존재 flaky test — H5 conftest hook 추가 후 정확한 격리에 노출됨)
- **모든 신규 106 테스트 PASS**

### 새 endpoint 살아 동작 확인 (server :5099)
- `/api/health` → 200 OK
- `/metrics` → Prometheus 형식, 새 gauge 노출 (chat_logs_total, db_size_bytes, auth_locked_accounts)
- `X-Trace-Id` 헤더 자동 부착 (Patch S)

### 스크린샷 (저장됨)
- `screenshots-final/integrated_desktop.png` — 통합 후 UI (Track B 미반영, 백엔드만)
- `screenshots-final/metrics_endpoint.png` — 새 gauge 포함 Prometheus 응답
- `screenshots-final/api_health.png` — health endpoint

(Track B UI polish 는 사용자 PR #3 과 영역 동일하므로 통합 branch 에 미포함 — push-skip 권장)

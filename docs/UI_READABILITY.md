# UI Readability Pass — 2026-05-04

## 목표
"눈이 아프지 않게" — 고채도 그라디언트와 글로우를 걷어내고, 본문 가독성과 시각 위계를 우선시하는 차분한 톤으로 정리.

## 적용 범위
- `web/index.html` — 메인 챗봇 (가장 큰 변경)
- `web/analytics-dashboard.html` — 분석 대시보드 (차트 색상/표/히트맵)
- `web/admin.html`, `web/admin_dashboard.html`, `web/faq-manager.html`, `web/notifications.html` — 가독성 패치 오버레이 주입
- `web/login.html` — 토큰 기반 디자인으로 재작성
- 회귀 위험을 피하기 위해 JS 동작은 변경하지 않음 (자동완성, 음성 입력, 내보내기, 테마 토글, FAQ, 자동 새로고침 등은 그대로)

## 색상 팔레트 (디자인 토큰)

### 다크 테마 (기본)
```
--bg            #0D1117   — 본문 배경
--bg-elev       #161B22   — 카드/메시지 표면
--bg-elev-2     #1C2128   — 헤더 우측 버튼 등 약간 더 밝은 표면
--fg            #E6EDF3   — 본문
--fg-strong     #F0F6FC   — 결론·KPI 값
--fg-muted      #8B949E   — 메타·라벨
--fg-subtle     #6E7681   — 시간 라벨, 보조 정보
--border        #30363D
--border-subtle #21262D
--accent        #58A6FF   — 액센트 (이전 #00D2FF에서 채도 ↓)
--user-bubble   #1F6FEB   — 사용자 버블 (그라디언트 → 솔리드)
--success       #3FB950
--warning       #D29922
--danger        #F85149
--mark          rgba(210,153,34,0.28)  — 키워드 하이라이트 (따뜻한 황갈)
```

### 라이트 테마 (시스템 환경 또는 수동)
```
--bg            #FAFAF7   — 따뜻한 오프화이트
--bg-elev       #FFFFFF
--bg-soft       #F1F2F4   — 차트 트랙 등
--fg            #1F2328
--fg-strong     #0B1221
--fg-muted      #57606A
--border        #D0D7DE
--accent        #0969DA   — 액센트 (이전 #1565C0보다 약간 부드러움)
--user-bubble   #0969DA
--mark          rgba(241,196,15,0.45)  — 황색 하이라이트
```

차트 전용 색은 라이트/다크 공통 — 막대 `#4C8DD3` (저채도 블루) / 호버 `#0969DA`/`#79B8FF`, 트렌드 스파크라인 `#2DA44E` / `#3FB950`.

## 타이포그래피
- 본문 폰트: **Pretendard** (CDN) → fallback `Noto Sans KR` → system-ui
- 코드/모노: **JetBrains Mono** → `D2Coding` → ui-monospace
- 본문 사이즈: 16px / line-height 1.65, 메시지 본문 15.5px / 1.7
- 메시지/답변 폭: `max-width: 72ch` (기존 80% → 가독선)
- 숫자 정렬: `font-variant-numeric: tabular-nums` (KPI 값, 표, 차트 라벨)
- 섹션 타이틀(결론/설명/근거 등)은 12px UPPERCASE + 액센트 색 + 미세 underline

## 핵심 변경

### 메인 챗봇
1. 다크 그라디언트 + radial highlight 제거 → 단색 표면
2. 사용자 버블 그라디언트(`#0084ff→#0056e0`) → 솔리드 (`#1F6FEB`)
3. `<style>` 블록의 누락 클래스(`.section`, `.section-title`, `.section-content`, `.legal-ref`, `.disclaimer`, `.cat-tag`, `.escalation-badge`, `.faq-item`, `.typing` 등)에 정식 스타일 정의 — 이전엔 브라우저 디폴트로 렌더링되고 있었음
4. **법적 근거 박스**: 좌측 3px 액센트 stripe + 부드러운 액센트 배경, 링크 underline-offset 정돈
5. 환영 메시지 line-height 1.8 → 1.7
6. 코드 블록/`<code>` 인라인 스타일 추가 (이전 정의 없었음)
7. 키워드 하이라이트 노란색 채도 ↓
8. 입력창 focus: 진한 박스 글로우 → `0 0 0 3px var(--accent-bg)` (얇은 후광)
9. 헤더 `theme-color` meta가 시스템 컬러스킴별로 분기됨
10. 테마 토글 사이클: **auto → light → dark → auto** (`force-dark` 클래스로 시스템 라이트 환경에서도 다크 강제 가능)
11. 스크롤바 thin + border 톤
12. `prefers-reduced-motion: reduce` 존중 — 애니메이션 비활성화
13. 답변 export HTML도 새 팔레트로 재작성

### 분석 대시보드 (`analytics-dashboard.html`)
1. KPI 카드: 이전 `#1a3a5c` 진한 네이비 → `--fg-strong`, 라벨 UPPERCASE + 작은 폰트
2. 막대 차트 fill: `#3498db` → `#4C8DD3` (호버 `#0969DA`)
3. 스파크라인: `#2ecc71` → `#2DA44E` (호버 `#1A7F37`)
4. 표: zebra 줄무늬 + sticky 헤더 + 헤더 UPPERCASE + 행 호버 액센트
5. 히트맵 RGB 보간: `prefers-color-scheme` 감지하여 라이트는 `#EBF1F7→#0969DA`, 다크는 `#161B22→#58A6FF`로 동적 계산
6. 셀 호버에 액센트 outline + 어두운 배경 툴팁

### admin/admin_dashboard/faq-manager/notifications
- 큰 회귀 위험 때문에 기존 룰을 그대로 두고 `<style>` 끝에 **가독성 패치 오버레이** 주입:
  - 헤더 `#1a3a5c` → `#1F2328`
  - 막대/시간/시간대 차트 fill을 `#4C8DD3`로 통일
  - 표 헤더 `#f8f9fa` 유지하되 UPPERCASE + sticky
  - 배지 (esc/ok/unmatched) 채도 ↓ + border 추가
  - 품질 게이지 `conic-gradient` 색을 부드럽게 (`#1A7F37`)
  - 다크 OS 환경에서 자동 다크 톤으로 매핑 (`@media (prefers-color-scheme: dark)`)

## WCAG 2.1 AA 대비 측정

### Before (회귀 가능성 있던 항목 위주)
| 조합 | 비율 | 등급 |
|---|---|---|
| 다크 사용자 버블 흰글씨 (`#0084ff`/`#fff`) | 3.66:1 | AA-large only (본문 FAIL) |
| 라이트 메타 `#999`/`#fff` | 2.85:1 | **FAIL** |

### After (대표 페어)
| 조합 | 비율 | 등급 |
|---|---|---|
| 다크 본문 (`#0D1117` / `#E6EDF3`) | 16.02:1 | AAA |
| 다크 muted (`#0D1117` / `#8B949E`) | 6.15:1 | AA |
| 다크 사용자 버블 (`#1F6FEB` / `#FFFFFF`) | **4.63:1** | **AA** ✅ |
| 다크 액센트 본문 (`#161B22` / `#58A6FF`) | 6.85:1 | AA |
| 다크 워닝 본문 (`#0D1117` / `#D29922`) | — (배경 위 6.88) | AA |
| 라이트 본문 (`#FAFAF7` / `#1F2328`) | 15.11:1 | AAA |
| 라이트 muted (`#FFFFFF` / `#57606A`) | **6.39:1** | **AA** ✅ |
| 라이트 사용자 버블 (`#0969DA` / `#FFFFFF`) | 5.19:1 | AA |
| 라이트 워닝 배지 (`#FFF7E0` / `#9A6700`) | 4.55:1 | AA |
| 라이트 차트 막대 vs bg-soft | 3.09:1 | AA-large (장식 요소) |

본문 텍스트 모두 AA 이상, 차트/장식 UI만 AA-large. 기존 FAIL 두 건 모두 해결.

## 스크린샷
`screenshots-final/`에 캡처:

| 파일 | 내용 |
|---|---|
| `readability_chatbot_desktop_light.png` | 챗봇 라이트, 답변 렌더 |
| `readability_chatbot_desktop_dark.png` | 챗봇 다크 |
| `readability_chatbot_mobile_light.png` | 챗봇 모바일 (390×844) |
| `readability_analytics_desktop_light.png` | 분석 대시보드 라이트 (full page) |
| `readability_analytics_desktop_dark.png` | 분석 대시보드 다크 (full page) |

기존 `before_*`/`after_*`도 같은 폴더에 그대로 보존.

## 회귀 점검
- JS 동작 그대로 (자동완성/마이크/내보내기/피드백/FAQ/세션 ID/타이핑 이펙트/접기 펼치기)
- DOM 구조/ID/이벤트 핸들러 미변경
- API endpoint 미변경
- 프린트/PWA manifest 영향 없음 (다만 메타 `theme-color`는 다크/라이트 분기됨 — 라이트 OS에서 새로 `#FAFAF7`)
- `body.light` 외에 `body.force-dark` 클래스가 추가됨 — 라이트 OS 환경에서 사용자가 수동으로 다크를 선택했을 때 사용

## 향후
- 차트 색맹 친화 검증 (특히 트렌드/막대를 동시에 비교할 때) — 현재는 같은 화면에 동시에 나오지 않아 큰 이슈는 없음
- 사이드바 카테고리별 아이콘 (현재는 텍스트 라벨만)
- 답변 본문에 `<ul>`/`<ol>` 마크다운 렌더링 (현재는 줄바꿈만)

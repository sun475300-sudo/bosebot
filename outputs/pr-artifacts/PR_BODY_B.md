## What
UI 토큰화 + 다크 모드 + 메시지 버블 비대칭 + 사이드바 검색/그룹화 + 입력 폴리시 + 반응형/접근성 일괄 정비.

## Changes (single file — `web/index.html`)

### Design tokens
- 6 brand colors (`--c-primary 1565C0`, secondary `00B8D4`, bg/surface/text/muted)
- 8px grid: `--space-1`(4) … `--space-12`(48)
- Radius (`--radius-xs/sm/md/lg/2xl/pill`) + shadow scale (1/2/3 + focus)
- Typography: Pretendard Variable + Noto Sans KR fallback (cdn jsdelivr)
- 다크 모드: `:root[data-theme="dark"]` 변형, `localStorage.bonded.theme` 영속화

### Layout
- Header 56px, surface bg, brand badge, theme toggle, hamburger (≤768)
- Sidebar 320px (≥1024) → 280px (768-1023) → 드로어 (<768) + overlay
- 검색 input + 그룹 타이틀 + active 상태 (FAQ 카테고리 그룹화)

### 메시지 버블
- 사용자: 우측 primary, `border-bottom-right: 4px` 비대칭, 우측 아바타
- 봇: 좌측 surface + border, `border-bottom-left: 4px`, 좌측 아바타 (B)
- 호버 시 상대 시간 (방금 전 / N분 전 / N시간 전) — 30초마다 자동 갱신

### 입력
- `<input>` → `<textarea>` 자동 grow 1→5줄, `max-height` 캡
- 글자수 카운터 `0/1000`, `>800` warn (cyan), `>1000` over (red, send 비활성)
- 빈 입력일 때 send `aria-disabled="true"`
- Enter 전송 / Shift+Enter 개행 / Esc 비우기 / `/` 포커스

### 상태
- empty-state: 아이콘 + 헤딩 + 추천 chip 3개 (설치/반입/관세)
- typing dots, toast helper `window.toast(msg, kind, ttl)` (info/error/success)
- prefers-reduced-motion 대응

### 반응형
- ≥1024 / 768-1023 / ≤768 / ≤480 토큰 오버라이드
- 768px 이하에서 sidebar 드로어 + 햄버거 노출, 480 이하에서 아바타 숨김

### A11y
- focus-visible 글로벌 ring, `:focus-visible { box-shadow: --shadow-focus }`
- skip-link 가시성 향상, aria-live 토스트 region, kbd hint 표시

## Screenshots (Launch preview)
- `outputs/before_desktop.png` / `outputs/before_mobile.png`
- `outputs/after_desktop.png` / `outputs/after_desktop_dark.png` / `outputs/after_mobile.png`

## Risk
- 단일 파일 변경 (`web/index.html`)
- 기존 ID/클래스 보존 → 기존 JS (sendQuery, setLanguage, exportConversation, toggleVoiceInput) 그대로 호출 가능
- 기존 `<input type="text">` → `<textarea>` 변경: `value`, `focus()`, `dispatchEvent('input')` 모두 textarea에서도 정상 동작
- 새 `<script>` 블록 추가: 기존 스크립트 ID 충돌 없음 (DOM ready 후 attachListeners)

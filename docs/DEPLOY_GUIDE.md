# 보세전시장 민원응대 챗봇 — 배포 가이드

이 문서는 **프로그래밍 경험이 없는 분**도 이 챗봇을 사이트에 적용할 수 있도록 단계별로 안내합니다.

---

## 준비물

시작하기 전에 아래 3가지가 필요합니다.

| 준비물 | 설명 | 어디서 구하나요? |
|--------|------|-----------------|
| 컴퓨터 1대 | 챗봇을 실행할 서버 (Windows/Mac/Linux 모두 가능) | 기존 PC 또는 클라우드 서버 |
| Python 3.11 이상 | 챗봇 프로그램 실행 환경 | [python.org](https://python.org) 에서 무료 다운로드 |
| 이 프로젝트 파일 | 챗봇 소스 코드 전체 | GitHub에서 다운로드 |

---

## 1단계: 프로젝트 다운로드

### 방법 A: GitHub에서 ZIP 다운로드 (가장 쉬운 방법)

1. 웹 브라우저에서 이 주소를 엽니다:
   ```
   https://github.com/sun475300-sudo/bonded-exhibition-chatbot-data
   ```
2. 초록색 **"Code"** 버튼을 클릭합니다
3. **"Download ZIP"** 을 클릭합니다
4. 다운로드된 ZIP 파일의 압축을 풀어줍니다
5. 압축을 푼 폴더 이름을 `chatbot` 으로 바꿔줍니다

### 방법 B: 터미널 사용 (Git이 설치된 경우)

```bash
git clone https://github.com/sun475300-sudo/bonded-exhibition-chatbot-data.git chatbot
```

---

## 2단계: Python 설치

### Windows

1. [python.org/downloads](https://www.python.org/downloads/) 에서 **"Download Python 3.11"** 클릭
2. 다운로드된 설치 파일 실행
3. **중요!** 설치 화면 맨 아래 **"Add Python to PATH"** 체크박스를 반드시 체크
4. "Install Now" 클릭

### Mac

1. 터미널 앱을 엽니다 (Spotlight에서 "터미널" 검색)
2. 아래 명령어를 입력합니다:
   ```bash
   brew install python@3.11
   ```
   (Homebrew가 없다면 먼저 [brew.sh](https://brew.sh) 에서 설치)

### 설치 확인

터미널(Windows는 명령 프롬프트)을 열고 아래를 입력합니다:

```bash
python --version
```

`Python 3.11.x` 같은 숫자가 나오면 성공입니다.

---

## 3단계: 챗봇 실행

### 3-1. 터미널에서 챗봇 폴더로 이동

```bash
cd chatbot
```

(Windows는 `cd` 명령어로 압축 푼 폴더 위치로 이동)

### 3-2. 필요한 프로그램 설치

```bash
pip install -r requirements.txt
```

이 명령어는 챗봇에 필요한 추가 프로그램을 자동으로 설치합니다.
약 1~2분 소요됩니다.

### 3-3. 챗봇 서버 시작

```bash
python web_server.py --port 8080
```

이렇게 나오면 성공입니다:
```
* Running on http://0.0.0.0:8080
```

### 3-4. 챗봇 확인

웹 브라우저를 열고 주소창에 입력합니다:

```
http://localhost:8080
```

챗봇 화면이 나타나면 성공!

- 챗봇 화면: `http://localhost:8080`
- 관리자 페이지: `http://localhost:8080/admin`
- API 문서: `http://localhost:8080/docs`

---

## 4단계: 사이트에 챗봇 붙이기

챗봇이 정상 작동하면, 기존 웹사이트에 붙일 수 있습니다.

### 방법 1: 팝업 위젯 (가장 쉬움 — 복붙 한 번이면 끝)

기존 사이트의 HTML 파일 맨 아래 `</body>` 바로 위에 아래 코드를 붙여넣기 합니다:

```html
<!-- 보세전시장 챗봇 위젯 -->
<div id="chatbot-widget" style="position:fixed;bottom:24px;right:24px;z-index:9999;">
  <iframe id="chatbot-frame" src="http://챗봇서버주소:8080"
    style="display:none;width:400px;height:600px;border:none;border-radius:12px;
           box-shadow:0 8px 32px rgba(0,0,0,0.3);"></iframe>
  <button onclick="var f=document.getElementById('chatbot-frame');f.style.display=f.style.display==='none'?'block':'none';"
    style="width:60px;height:60px;border-radius:50%;border:none;
           background:linear-gradient(135deg,#1565C0,#1E88E5);color:#fff;
           font-size:24px;cursor:pointer;box-shadow:0 4px 16px rgba(21,101,192,0.4);">B</button>
</div>
```

**`챗봇서버주소`** 부분을 실제 서버 주소로 바꿔주세요.
- 같은 컴퓨터: `localhost`
- 다른 컴퓨터: 서버의 IP 주소 (예: `192.168.1.100`)

### 방법 2: iframe 삽입 (특정 페이지에 넣기)

원하는 페이지의 HTML에 아래를 넣습니다:

```html
<iframe src="http://챗봇서버주소:8080" 
        width="400" height="600"
        style="border:none;border-radius:12px;"></iframe>
```

### 방법 3: 전체 페이지로 연결 (링크만 걸기)

기존 사이트에 "챗봇 상담" 링크를 추가합니다:

```html
<a href="http://챗봇서버주소:8080" target="_blank">챗봇 상담</a>
```

---

## 5단계: 관리자 설정

### 5-1. 관리자 로그인

1. 브라우저에서 `http://챗봇서버주소:8080/admin` 접속
2. 기본 로그인 정보:
   - 아이디: `admin`
   - 비밀번호: `admin123`
3. **중요!** 로그인 후 반드시 비밀번호를 변경하세요

### 5-2. 관리자 페이지에서 할 수 있는 것

| 기능 | 설명 |
|------|------|
| 통계 확인 | 오늘 질문 수, 많이 묻는 질문, 만족도 |
| FAQ 관리 | 질문-답변 추가/수정/삭제 |
| 미매칭 질문 | 챗봇이 답하지 못한 질문 확인 |
| 피드백 확인 | 사용자 만족도 확인 |
| 로그 확인 | 모든 대화 기록 조회 |

---

## 6단계: 항상 켜두기 (선택사항)

### 방법 A: 백그라운드 실행 (Linux/Mac)

서버를 끄지 않고 계속 실행하려면:

```bash
nohup python web_server.py --port 8080 &
```

### 방법 B: Docker 사용 (권장)

Docker가 설치되어 있다면 한 줄로 실행:

```bash
docker-compose up -d
```

이렇게 하면:
- 서버가 자동으로 시작됩니다
- 컴퓨터를 재시작해도 자동으로 켜집니다
- `docker-compose down` 으로 끌 수 있습니다

### 방법 C: 서비스 등록 (Linux)

```bash
# 서비스 파일 생성
sudo tee /etc/systemd/system/chatbot.service << 'EOF'
[Unit]
Description=보세전시장 챗봇
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/chatbot
ExecStart=/usr/bin/python3 web_server.py --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 서비스 시작
sudo systemctl enable chatbot
sudo systemctl start chatbot
```

`/path/to/chatbot` 을 실제 챗봇 폴더 경로로 바꿔주세요.

---

## 7단계: FAQ 수정하기

### 웹에서 수정 (가장 쉬움)

1. `http://챗봇서버주소:8080/admin/faq` 접속
2. 로그인
3. "FAQ 추가" 버튼 클릭
4. 질문, 답변, 카테고리 입력
5. 저장

### 파일에서 직접 수정

`data/faq.json` 파일을 메모장으로 열어서 수정할 수도 있습니다.

```json
{
  "id": "새로운ID",
  "category": "GENERAL",
  "question": "질문 내용",
  "answer": "답변 내용",
  "keywords": ["키워드1", "키워드2"]
}
```

수정 후 서버를 재시작하면 반영됩니다.

---

## 자주 묻는 질문

### Q: 챗봇이 안 켜져요
**A:** 터미널에서 오류 메시지를 확인하세요. 대부분 `pip install -r requirements.txt` 를 안 한 경우입니다.

### Q: 다른 컴퓨터에서 접속이 안 돼요
**A:** 방화벽에서 8080 포트를 열어야 합니다.
- Windows: 제어판 → Windows Defender 방화벽 → 고급 설정 → 인바운드 규칙 → 새 규칙 → 포트 8080
- Linux: `sudo ufw allow 8080`

### Q: 챗봇 주소를 바꾸고 싶어요
**A:** 포트 번호를 바꾸면 됩니다: `python web_server.py --port 원하는숫자`

### Q: 모바일에서도 되나요?
**A:** 네, 반응형 디자인이라 모바일 브라우저에서도 자동으로 맞춰집니다.

### Q: 동시에 몇 명이 사용할 수 있나요?
**A:** 기본 설정으로 50~100명 동시 접속 가능합니다. 더 많으면 Docker + nginx 구성을 권장합니다.

### Q: 데이터 백업은 어떻게 하나요?
**A:** `data/` 폴더 전체를 복사해두면 됩니다. 또는 관리자 페이지에서 백업 버튼을 사용하세요.

### Q: HTTPS(보안 연결)를 쓰고 싶어요
**A:** nginx를 앞에 두고 SSL 인증서를 설정하면 됩니다. `deploy/nginx.conf` 파일을 참고하세요.

---

## 기술 지원

| 항목 | 내용 |
|------|------|
| GitHub | https://github.com/sun475300-sudo/bonded-exhibition-chatbot-data |
| 이슈 등록 | GitHub Issues 탭에서 문의 |
| 테스트 | `python -m pytest tests/ -v` 로 2,081개 테스트 실행 |

---

## 파일 구조 간단 설명

```
chatbot/
├── web_server.py          ← 이것만 실행하면 챗봇이 켜집니다
├── data/faq.json          ← 질문-답변 데이터 (이것만 수정하면 FAQ 변경)
├── web/index.html         ← 챗봇 화면
├── web/admin.html         ← 관리자 화면
├── requirements.txt       ← 필요한 프로그램 목록
├── Dockerfile             ← Docker 배포용
└── docker-compose.yml     ← Docker 한 줄 실행용
```

핵심 정리:
1. `pip install -r requirements.txt` (한 번만)
2. `python web_server.py --port 8080` (서버 시작)
3. 브라우저에서 `http://localhost:8080` 접속
4. 끝!

"""모의 백엔드 + Playwright 스크린샷 도구 (분석 대시보드만 재캡처)."""
import asyncio, http.server, json, threading, time, urllib.parse, pathlib, socketserver

ROOT = pathlib.Path("/sessions/blissful-vibrant-clarke/mnt/bonded-exhibition-chatbot-data")
WEB = ROOT / "web"
OUT = ROOT / "screenshots-final"
OUT.mkdir(exist_ok=True)

ANALYTICS_METRICS = {
    "total_queries": 1247, "today_queries": 38, "unique_users": 421,
    "avg_response_ms": 320, "satisfaction_rate": 0.87, "escalation_rate": 0.06,
    "categories_count": 4, "active_sessions": 7,
}
ANALYTICS_DASHBOARD = {
    "charts": {
        "categories": {
            "labels": ["반출입","신고","운영","통관","행사 준비","사후관리"],
            "values": [342, 218, 187, 165, 92, 53],
        },
        "trends": {
            "labels": [f"2026-04-{d:02d}" for d in range(1,31)],
            "values": [12,18,9,22,17,11,14,20,25,19,15,12,28,32,26,18,21,17,30,34,29,22,27,33,38,31,24,28,35,30],
        },
        "top_queries": [
            {"query":"전시품 반입 시 통관 절차", "count": 56},
            {"query":"미신고 반출 시 처분", "count": 41},
            {"query":"운영 기간 연장 가능 여부", "count": 38},
            {"query":"보세전시장 등록 신청서", "count": 33},
            {"query":"전시 후 폐기 처리", "count": 27},
            {"query":"HS코드 조회", "count": 24},
        ],
        "heatmap": {
            "days": ["월","화","수","목","금","토","일"],
            "hours": list(range(24)),
            "data": [
                [0,0,0,0,0,1,2,5,12,18,22,28,15,21,25,22,18,12,8,5,3,2,1,0],
                [0,0,0,0,0,1,3,7,15,20,24,30,18,23,27,24,19,13,9,6,3,2,1,0],
                [0,0,0,0,0,1,2,6,14,19,23,29,17,22,26,23,18,12,8,5,3,2,1,0],
                [0,0,0,0,0,1,2,5,13,17,21,27,15,20,24,21,17,11,7,4,2,2,1,0],
                [0,0,0,0,0,1,3,6,14,18,22,28,16,21,25,22,17,12,8,5,3,2,1,0],
                [0,0,0,0,0,0,1,2,4,6,8,10,5,7,9,8,6,4,3,2,1,1,0,0],
                [0,0,0,0,0,0,0,1,2,3,4,5,3,4,5,4,3,2,1,1,0,0,0,0],
            ],
        },
    }
}

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k): pass
    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
    def _serve_file(self, p, ctype):
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); path = u.path
        if path in ("/", "/index.html"):
            return self._serve_file(WEB/"index.html","text/html; charset=utf-8")
        if path == "/admin/analytics":
            return self._serve_file(WEB/"analytics-dashboard.html","text/html; charset=utf-8")
        if path == "/admin":
            return self._serve_file(WEB/"admin.html","text/html; charset=utf-8")
        if path == "/login":
            return self._serve_file(WEB/"login.html","text/html; charset=utf-8")
        if path == "/manifest.json":
            return self._serve_file(WEB/"manifest.json","application/json")
        if path.startswith("/static/"):
            f = WEB / path[len("/static/"):]
            if f.exists() and f.is_file():
                return self._serve_file(f, "image/svg+xml" if f.suffix==".svg" else "application/octet-stream")
        if path == "/sw.js":
            self.send_response(404); self.end_headers(); return
        if path == "/api/auth/me":
            return self._json({"username":"demo"})
        if path == "/api/admin/analytics/metrics":
            return self._json(ANALYTICS_METRICS)
        if path == "/api/admin/charts/dashboard":
            return self._json(ANALYTICS_DASHBOARD)
        self.send_response(404); self.end_headers()
    def do_POST(self):
        ln = int(self.headers.get("Content-Length","0"))
        try: self.rfile.read(ln) if ln else b""
        except: pass
        if self.path == "/api/auth/login":
            return self._json({"token":"dev"})
        self.send_response(404); self.end_headers()

class TS(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True; daemon_threads = True

def serve(): TS(("127.0.0.1", 8765), Handler).serve_forever()
threading.Thread(target=serve, daemon=True).start()
time.sleep(0.6)
print("[mock] http://127.0.0.1:8765 up")

from playwright.async_api import async_playwright

INIT_TOKEN = """
try { localStorage.setItem('admin_token','dev'); } catch(e){}
"""

async def cap_dashboard(browser, prefers, name, viewport):
    ctx = await browser.new_context(viewport=viewport, color_scheme=prefers,
                                    locale="ko-KR", service_workers="block")
    await ctx.add_init_script(INIT_TOKEN)
    pg = await ctx.new_page()
    errs, reqs = [], []
    pg.on("pageerror", lambda e: errs.append(f"PAGE-ERR: {e}"))
    pg.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}") if m.type in ("error","warning") else None)
    pg.on("response", lambda r: reqs.append(f"{r.status} {r.url}") if "/api" in r.url else None)
    pg.on("requestfailed", lambda r: errs.append(f"REQ-FAIL: {r.url}"))
    await pg.goto("http://127.0.0.1:8765/admin/analytics", wait_until="domcontentloaded")
    try:
        await pg.wait_for_function("document.querySelectorAll('.heatmap-cell').length > 0", timeout=15000)
    except Exception:
        print("  [errs]:", errs[-6:])
        print("  [reqs]:", reqs[-6:])
        state = await pg.evaluate("({url: location.href, tok: localStorage.getItem('admin_token'), heat: document.querySelectorAll('.heatmap-cell').length, mc: document.querySelectorAll('.metric-card').length})")
        print("  [state]:", state)
    await pg.wait_for_timeout(1500)
    out = OUT / f"readability_analytics_{name}.png"
    await pg.screenshot(path=str(out), full_page=True)
    await ctx.close()
    print(f"  saved {out.name}")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
        await cap_dashboard(browser, "light", "desktop_light", {"width":1440,"height":900})
        await cap_dashboard(browser, "dark",  "desktop_dark",  {"width":1440,"height":900})
        await browser.close()

asyncio.run(main())
print("[done]")

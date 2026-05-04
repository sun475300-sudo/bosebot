"""국가법령정보센터 행정규칙(admRul) Open API 연동 모듈.

법률(law)을 다루는 :mod:`law_api_sync` 의 행정규칙 버전.
관세청 「보세전시장 운영에 관한 고시」 (admRulSeq=2100000276240) 와 같은
고시(notice)/훈령/예규 본문을 자동으로 가져온다.

국가법령정보센터 Open API:
- 행정규칙 검색: https://www.law.go.kr/DRF/lawSearch.do?target=admrul
- 행정규칙 본문: https://www.law.go.kr/DRF/lawService.do?target=admrul
- HTML 뷰어:    https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=...

응답 형식은 ``type=XML`` 권장. ``OC=`` (이메일 ID) 인증키가 있으면
요청량 제한이 완화되지만, 무인증으로도 기본 사용은 가능하다.

사용법::

    python -m src.law_api_admrul                # 시드 고시 동기화
    python -m src.law_api_admrul --check        # 변경 여부만 확인
    python -m src.law_api_admrul --history      # 동기화 이력
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Iterable, List, Optional
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "law_sync.db")
LEGAL_REF_PATH = os.path.join(BASE_DIR, "data", "legal_references.json")

ADMRUL_SERVICE_BASE = "https://www.law.go.kr/DRF/lawService.do"
ADMRUL_SEARCH_BASE = "https://www.law.go.kr/DRF/lawSearch.do"
ADMRUL_VIEWER_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do"

USER_AGENT = "BondedExhibitionChatbot/1.0 (admrul-sync)"

# 본문이 이 길이보다 짧으면 fetch 실패로 간주하고 캐시를 갱신하지 않는다.
# 행정규칙 본문은 통상 수천~수만 자이므로 이 정도면 메타텍스트만 걸린 경우를
# 안전하게 거른다. 너무 높이면 짧은 고시까지 fetch_failed 로 오판하므로 200 자.
MIN_VALID_FULL_TEXT_LEN = 200

# 조문 단위 추출 결과가 이 개수 미만이면 본문 인용에 쓸 수 없다고 본다.
# (HTML fallback 이 div 분리에 실패해 통째로 한 덩어리로 읽히는 경우 등)
MIN_VALID_ARTICLE_COUNT = 1

# ------------------------------------------------------------------
# 시드 목록 — 모니터링 대상 행정규칙(고시)
# ------------------------------------------------------------------
# admRulSeq 는 국가법령정보센터에서 부여하는 일련번호.
# 「보세전시장 운영에 관한 고시」 — 관세청고시 (사용자가 제공한 최신 URL 기반)
MONITORED_ADMRULS = [
    {
        "admrul_seq": "2100000276240",
        "name": "보세전시장 운영에 관한 고시",
        "agency": "관세청",
        # 본문에서 추출할 핵심 조문 — 챗봇 retrieval 에 사용된다
        "key_articles": [
            "제1조",   # 목적
            "제3조",   # 정의
            "제4조",   # 특허장소
            "제5조",   # 특허기간
            "제6조",   # 특허신청
            "제10조",  # 반출입의 신고
            "제11조",  # 물품검사
            "제15조",  # 폐쇄
        ],
    },
]


def _http_get(url: str, timeout: int = 30) -> Optional[str]:
    """HTTP GET 헬퍼. 실패 시 ``None``."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError):
        return None


class AdmRulAPIClient:
    """국가법령정보센터 행정규칙(admRul) Open API 클라이언트.

    공식 API ``lawService.do?target=admrul`` 로 XML 본문을 가져오고,
    실패할 경우 HTML 뷰어 페이지를 fallback 으로 가져와 본문을 추출한다.

    Parameters
    ----------
    oc : str | None
        법령 Open API 인증키(보통 사용자 이메일 ID). 비워두면 무인증 호출.
        환경변수 ``LAW_API_OC`` 에서도 자동으로 읽는다.
    """

    def __init__(self, oc: Optional[str] = None):
        self.oc = oc if oc is not None else os.environ.get("LAW_API_OC", "")

    # ------------------------------------------------------------------
    # 공식 Open API
    # ------------------------------------------------------------------

    def search_admrul(self, query: str) -> List[dict]:
        """행정규칙명으로 검색하여 후보 목록을 반환한다."""
        params = (
            f"OC={quote(self.oc)}&target=admrul&type=XML"
            f"&query={quote(query)}"
        )
        url = f"{ADMRUL_SEARCH_BASE}?{params}"
        xml_data = _http_get(url, timeout=15)
        if not xml_data:
            return []
        return self._parse_search_xml(xml_data)

    def get_admrul_xml(self, admrul_seq: str) -> Optional[str]:
        """행정규칙 본문을 XML 로 가져온다.

        ``admrul_seq`` 가 사람이 읽는 ``admRulSeq`` (예 ``2100000276240``).
        Open API 의 ID 파라미터에 그대로 사용한다.
        """
        if not admrul_seq:
            return None
        params = (
            f"OC={quote(self.oc)}&target=admrul&type=XML"
            f"&ID={quote(admrul_seq)}"
        )
        url = f"{ADMRUL_SERVICE_BASE}?{params}"
        return _http_get(url, timeout=30)

    def get_admrul_html(self, admrul_seq: str) -> Optional[str]:
        """공식 뷰어 페이지(HTML)를 fallback 으로 가져온다."""
        if not admrul_seq:
            return None
        url = f"{ADMRUL_VIEWER_URL}?admRulSeq={quote(admrul_seq)}"
        return _http_get(url, timeout=30)

    # ------------------------------------------------------------------
    # 파싱
    # ------------------------------------------------------------------

    @staticmethod
    def _get_text(elem: ET.Element, *tags: str) -> str:
        for tag in tags:
            child = elem.find(tag)
            if child is not None and (child.text or "").strip():
                return child.text.strip()
        return ""

    def _parse_search_xml(self, xml_data: str) -> List[dict]:
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return []
        out: List[dict] = []
        candidates: Iterable[ET.Element] = (
            list(root.findall(".//admrul"))
            + list(root.findall(".//AdmRul"))
            + list(root.findall(".//행정규칙"))
        )
        for item in candidates:
            seq = self._get_text(item, "행정규칙일련번호", "admRulSeq", "admrulSeq")
            name = self._get_text(item, "행정규칙명", "admRulNm", "admrulNm")
            agency = self._get_text(item, "소관부처명", "발령기관", "agency")
            if seq or name:
                out.append({
                    "admrul_seq": seq,
                    "name": name,
                    "agency": agency,
                })
        return out

    def parse_admrul_body(self, xml_data: Optional[str]) -> dict:
        """본문 XML 에서 메타데이터와 조문 본문을 추출한다.

        Returns
        -------
        dict
            ``{"name": ..., "agency": ..., "effective_date": ...,
              "articles": {"제1조": "내용", ...},
              "full_text": "..."}``
        """
        result = {
            "name": "",
            "agency": "",
            "effective_date": "",
            "articles": {},
            "full_text": "",
        }
        if not xml_data:
            return result
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return result

        # 메타데이터 — 다양한 변형 태그를 허용
        result["name"] = self._get_text(
            root, "행정규칙명", "admRulNm", "admrulNm",
        ) or self._find_text_anywhere(root, ("행정규칙명",))
        result["agency"] = self._get_text(
            root, "소관부처명", "발령기관", "agency",
        ) or self._find_text_anywhere(root, ("소관부처명", "발령기관"))
        result["effective_date"] = self._get_text(
            root, "시행일자", "발령일자", "effectiveDate",
        ) or self._find_text_anywhere(root, ("시행일자", "발령일자"))

        # 조문 — <조문단위> / <조문> / <Article> 등
        articles = {}
        full_chunks: List[str] = []
        for elem in root.iter():
            tag = elem.tag.lower()
            if tag in ("조문단위", "조문", "article"):
                no = (
                    self._get_text(elem, "조문번호", "조번호", "articleNo")
                    or ""
                )
                title = self._get_text(elem, "조문제목", "조제목", "articleTitle")
                content = (
                    self._get_text(elem, "조문내용", "조내용", "articleContent")
                    or ""
                )
                if not content:
                    content = " ".join(
                        (t.strip() for t in elem.itertext() if t and t.strip())
                    )
                if no:
                    key = no if no.startswith("제") else f"제{no}조"
                    if title and title not in content:
                        content = f"({title}) {content}"
                    articles[key] = content.strip()
                    full_chunks.append(f"{key} {content.strip()}")

        result["articles"] = articles
        if full_chunks:
            result["full_text"] = "\n".join(full_chunks)
        else:
            # 조문 단위 추출이 실패한 경우 전체 텍스트만이라도 모아 둔다
            result["full_text"] = " ".join(
                (t.strip() for t in root.itertext() if t and t.strip())
            )
        return result

    @staticmethod
    def _find_text_anywhere(root: ET.Element, names: Iterable[str]) -> str:
        wanted = set(names)
        for elem in root.iter():
            if elem.tag in wanted and (elem.text or "").strip():
                return elem.text.strip()
        return ""

    # ------------------------------------------------------------------
    # HTML fallback
    # ------------------------------------------------------------------

    _HTML_TAG_RE = re.compile(r"<[^>]+>")
    _ARTICLE_RE = re.compile(r"(제\s*\d+\s*조(?:의\d+)?)")

    def parse_html_body(self, html: Optional[str]) -> dict:
        """공식 뷰어 HTML 에서 본문을 거칠게 추출한다.

        XML API 가 실패한 경우의 fallback. 라이선스/이용약관을 위반하지 않도록
        `lawService.do` (공식 Open API)를 우선 사용해야 한다.
        """
        out = {"name": "", "agency": "", "effective_date": "",
               "articles": {}, "full_text": ""}
        if not html:
            return out
        # title
        m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m:
            out["name"] = re.sub(r"\s+", " ", m.group(1)).strip()
        text = self._HTML_TAG_RE.sub(" ", html)
        text = re.sub(r"\s+", " ", text).strip()
        # 조문 분할
        parts = self._ARTICLE_RE.split(text)
        if len(parts) >= 3:
            articles = {}
            it = iter(parts[1:])
            for marker, body in zip(it, it):
                key = re.sub(r"\s+", "", marker)
                articles[key] = body.strip()
            out["articles"] = articles
        out["full_text"] = text[:20000]
        return out


class AdmRulSyncManager:
    """행정규칙 변경 감지 + 캐시 매니저.

    SQLite 테이블:
      ``admrul_content_cache`` (admrul_seq, name, agency, effective_date,
      full_text, content_hash, fetched_at, articles_json)
      ``admrul_sync_log`` (id, admrul_seq, content_hash, previous_hash,
      changed, checked_at)
    """

    def __init__(self, api_client: Optional[AdmRulAPIClient] = None,
                 db_path: Optional[str] = None):
        self.client = api_client or AdmRulAPIClient()
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admrul_content_cache (
                    admrul_seq      TEXT PRIMARY KEY,
                    name            TEXT,
                    agency          TEXT,
                    effective_date  TEXT,
                    full_text       TEXT,
                    articles_json   TEXT,
                    content_hash    TEXT NOT NULL,
                    fetched_at      TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admrul_sync_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    admrul_seq      TEXT NOT NULL,
                    name            TEXT,
                    content_hash    TEXT NOT NULL,
                    previous_hash   TEXT,
                    changed         INTEGER DEFAULT 0,
                    checked_at      TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def sync_one(self, admrul_seq: str, allow_html_fallback: bool = True) -> dict:
        """단일 admRul 의 본문을 가져와 캐시한다.

        반환되는 ``status`` 의 의미:

        - ``"changed"``    : 캐시 갱신됨, 본문 hash 가 직전과 다르다.
        - ``"unchanged"``  : 캐시 갱신됨, 본문 hash 가 직전과 같다(또는 첫 동기화).
        - ``"fetch_failed"``: XML/HTML 둘 다 의미있는 본문을 받지 못했다.
                              **이 경우 DB 캐시는 갱신하지 않는다.** 직전 캐시를
                              그대로 보존해 챗봇 답변이 깨지지 않게 한다.
        - ``"no_credentials"``: ``LAW_API_OC`` 가 비어 있고 HTML fallback 마저
                              본문 추출에 실패한 경우. 운영자에게 OC 설정을
                              안내하기 위해 ``fetch_failed`` 와 분리한다.

        ``full_text`` 가 :data:`MIN_VALID_FULL_TEXT_LEN` 보다 짧거나 조문 단위
        추출 결과가 :data:`MIN_VALID_ARTICLE_COUNT` 미만이면 fetch 실패로 본다.
        이는 HTML fallback 이 메타 헤더만 긁어오는 케이스(약 50~150 byte)를
        막기 위함이다 — 그런 본문이 캐시되면 by_law_basis 가 비어 챗봇이
        본문을 인용하지 못한다.
        """
        had_oc = bool(self.client.oc)

        xml_data = self.client.get_admrul_xml(admrul_seq)
        parsed_xml = (
            self.client.parse_admrul_body(xml_data) if xml_data else None
        )
        parsed = parsed_xml
        used_fallback = False

        if not self._is_valid_parse(parsed):
            if allow_html_fallback:
                html = self.client.get_admrul_html(admrul_seq)
                parsed_html = self.client.parse_html_body(html)
                if self._is_valid_parse(parsed_html):
                    parsed = parsed_html
                    used_fallback = True
                else:
                    # HTML 도 실패 — XML 실패 시 받은 부분 메타데이터(이름 등)만
                    # 결과에 노출하고 캐시는 건드리지 않는다.
                    parsed = parsed_html or parsed or {
                        "name": "", "agency": "", "effective_date": "",
                        "articles": {}, "full_text": "",
                    }
            else:
                parsed = parsed or {
                    "name": "", "agency": "", "effective_date": "",
                    "articles": {}, "full_text": "",
                }

        if not self._is_valid_parse(parsed):
            # OC 미설정 + 모두 실패한 경우는 운영 메시지를 분리한다.
            status = "no_credentials" if not had_oc else "fetch_failed"
            return {
                "admrul_seq": admrul_seq,
                "status": status,
                "name": (parsed or {}).get("name", ""),
                "full_text_len": len((parsed or {}).get("full_text") or ""),
                "article_count": len((parsed or {}).get("articles") or {}),
                "used_fallback": used_fallback,
            }

        full_text = parsed.get("full_text") or ""
        content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        changed = self._record(
            admrul_seq=admrul_seq,
            name=parsed.get("name", ""),
            agency=parsed.get("agency", ""),
            effective_date=parsed.get("effective_date", ""),
            full_text=full_text,
            articles=parsed.get("articles") or {},
            content_hash=content_hash,
        )
        return {
            "admrul_seq": admrul_seq,
            "status": "changed" if changed else "unchanged",
            "name": parsed.get("name", ""),
            "agency": parsed.get("agency", ""),
            "effective_date": parsed.get("effective_date", ""),
            "content_hash": content_hash,
            "article_count": len(parsed.get("articles") or {}),
            "used_fallback": used_fallback,
        }

    @staticmethod
    def _is_valid_parse(parsed: Optional[dict]) -> bool:
        """parse 결과가 캐시 갱신에 쓸 만한 수준인지 검사."""
        if not parsed:
            return False
        full_text = parsed.get("full_text") or ""
        articles = parsed.get("articles") or {}
        if len(full_text) < MIN_VALID_FULL_TEXT_LEN:
            return False
        if len(articles) < MIN_VALID_ARTICLE_COUNT:
            return False
        return True

    def sync_all(self, allow_html_fallback: bool = True) -> dict:
        """모니터링 대상 행정규칙 전체 동기화."""
        result = {
            "checked_at": datetime.now().isoformat(),
            "total_checked": 0,
            "changes_detected": 0,
            "errors": 0,
            "details": [],
        }
        for entry in MONITORED_ADMRULS:
            seq = entry["admrul_seq"]
            detail = self.sync_one(
                seq, allow_html_fallback=allow_html_fallback
            )
            result["total_checked"] += 1
            if detail["status"] == "changed":
                result["changes_detected"] += 1
            elif detail["status"] in ("fetch_failed", "no_credentials"):
                result["errors"] += 1
            detail.setdefault("name", entry.get("name", ""))
            result["details"].append(detail)
        return result

    def _record(self, admrul_seq: str, name: str, agency: str,
                effective_date: str, full_text: str, articles: dict,
                content_hash: str) -> bool:
        import json as _json
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT content_hash FROM admrul_content_cache WHERE admrul_seq = ?",
                (admrul_seq,),
            )
            row = cursor.fetchone()
            previous = row[0] if row else None
            changed = previous is not None and previous != content_hash

            now = datetime.now().isoformat()
            conn.execute(
                """INSERT OR REPLACE INTO admrul_content_cache
                   (admrul_seq, name, agency, effective_date, full_text,
                    articles_json, content_hash, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (admrul_seq, name, agency, effective_date, full_text,
                 _json.dumps(articles, ensure_ascii=False),
                 content_hash, now),
            )
            conn.execute(
                """INSERT INTO admrul_sync_log
                   (admrul_seq, name, content_hash, previous_hash,
                    changed, checked_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (admrul_seq, name, content_hash, previous,
                 int(changed), now),
            )
            conn.commit()
            return changed
        finally:
            conn.close()

    def get_cached(self, admrul_seq: str) -> Optional[dict]:
        import json as _json
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """SELECT admrul_seq, name, agency, effective_date,
                          full_text, articles_json, content_hash, fetched_at
                   FROM admrul_content_cache WHERE admrul_seq = ?""",
                (admrul_seq,),
            )
            row = cur.fetchone()
            if not row:
                return None
            try:
                articles = _json.loads(row[5]) if row[5] else {}
            except Exception:
                articles = {}
            return {
                "admrul_seq": row[0], "name": row[1], "agency": row[2],
                "effective_date": row[3], "full_text": row[4],
                "articles": articles, "content_hash": row[6],
                "fetched_at": row[7],
            }
        finally:
            conn.close()

    def list_cached(self) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """SELECT admrul_seq, name, agency, effective_date,
                          content_hash, fetched_at
                   FROM admrul_content_cache ORDER BY fetched_at DESC"""
            )
            return [
                {"admrul_seq": r[0], "name": r[1], "agency": r[2],
                 "effective_date": r[3], "content_hash": r[4],
                 "fetched_at": r[5]}
                for r in cur.fetchall()
            ]
        finally:
            conn.close()

    def get_history(self, limit: int = 50) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """SELECT admrul_seq, name, content_hash, previous_hash,
                          changed, checked_at
                   FROM admrul_sync_log ORDER BY id DESC LIMIT ?""",
                (limit,),
            )
            return [
                {"admrul_seq": r[0], "name": r[1], "content_hash": r[2],
                 "previous_hash": r[3], "changed": bool(r[4]),
                 "checked_at": r[5]}
                for r in cur.fetchall()
            ]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # legal_references.json 통합
    # ------------------------------------------------------------------

    def update_legal_references(self) -> dict:
        """``legal_references.json`` 의 admRul 항목을 캐시 본문으로 갱신한다.

        - URL 의 ``admRulSeq`` 를 항상 시드 값으로 보정한다(과거 시퀀스 → 최신).
        - 본문이 캐시되어 있으면 ``summary`` 와 ``last_synced`` 를 업데이트한다.
        - 핵심 조문 본문이 캐시에 있으면 ``sub_articles`` 를 본문 발췌로 보강한다.
        """
        import json as _json
        if not os.path.exists(LEGAL_REF_PATH):
            return {"updated": 0, "total": 0}

        with open(LEGAL_REF_PATH, "r", encoding="utf-8") as f:
            data = _json.load(f)

        updated = 0
        for ref in data.get("references", []):
            url = ref.get("url", "")
            if "admRulLsInfoP" not in url and "admRulSeq" not in url:
                continue
            # 어떤 시드와 매칭되는지 판단 — 이름 기준
            seed = next(
                (s for s in MONITORED_ADMRULS
                 if s["name"] in ref.get("law_name", "")
                 or s["name"] in ref.get("title", "")),
                None,
            )
            if not seed:
                continue
            new_seq = seed["admrul_seq"]
            new_url = (
                f"{ADMRUL_VIEWER_URL}?admRulSeq={new_seq}"
            )
            if ref.get("url") != new_url:
                ref["url"] = new_url
                updated += 1
            cached = self.get_cached(new_seq)
            if not cached or not cached.get("full_text"):
                continue
            # summary 보강
            full_text = cached["full_text"]
            new_summary = full_text[:200].strip()
            if new_summary and new_summary != ref.get("summary"):
                ref["summary"] = new_summary
                updated += 1
            ref["last_synced"] = cached.get("fetched_at", "")
            # sub_articles 본문 발췌
            sub_articles = ref.get("sub_articles") or {}
            for art_no in list(sub_articles.keys()) + seed.get("key_articles", []):
                body = (cached.get("articles") or {}).get(art_no)
                if body:
                    sub_articles[art_no] = body[:300].strip()
            if sub_articles:
                ref["sub_articles"] = sub_articles

        with open(LEGAL_REF_PATH, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        return {"updated": updated, "total": len(data.get("references", []))}

    def get_monitored(self) -> List[dict]:
        return list(MONITORED_ADMRULS)


# ---------------------------------------------------------------------
# retrieval helper — 챗봇 prompt 컨텍스트용
# ---------------------------------------------------------------------

def build_chatbot_context_chunks(
    sync_manager: Optional[AdmRulSyncManager] = None,
    max_chars_per_chunk: int = 600,
) -> List[dict]:
    """캐시된 admRul 본문을 챗봇 retrieval 용 chunk 리스트로 변환한다.

    각 chunk: ``{"id": "admrul:<seq>:<art>", "law_name": ...,
    "article": ..., "text": ...}``
    """
    sync_manager = sync_manager or AdmRulSyncManager()
    chunks: List[dict] = []
    for entry in MONITORED_ADMRULS:
        cached = sync_manager.get_cached(entry["admrul_seq"])
        if not cached:
            continue
        articles = cached.get("articles") or {}
        for art_no, body in articles.items():
            text = body.strip()
            if not text:
                continue
            for offset in range(0, len(text), max_chars_per_chunk):
                piece = text[offset:offset + max_chars_per_chunk]
                chunks.append({
                    "id": f"admrul:{entry['admrul_seq']}:{art_no}:{offset}",
                    "law_name": cached.get("name") or entry["name"],
                    "agency": cached.get("agency") or entry["agency"],
                    "article": art_no,
                    "text": piece,
                    "admrul_seq": entry["admrul_seq"],
                })
    return chunks


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="국가법령정보센터 행정규칙(admRul) 동기화"
    )
    parser.add_argument("--check", action="store_true",
                        help="변경 확인만 수행")
    parser.add_argument("--sync", action="store_true",
                        help="동기화 + legal_references.json 업데이트")
    parser.add_argument("--history", action="store_true",
                        help="동기화 이력 조회")
    parser.add_argument("--no-html-fallback", action="store_true",
                        help="공식 API 실패 시 HTML fallback 비활성화")
    args = parser.parse_args()

    mgr = AdmRulSyncManager()

    if args.history:
        for h in mgr.get_history(limit=20):
            mark = "변경" if h["changed"] else "동일"
            print(f"[{mark}] {h['name']} ({h['admrul_seq']}) - "
                  f"{h['checked_at']}")
    elif args.sync:
        print("행정규칙 동기화 중...")
        res = mgr.sync_all(allow_html_fallback=not args.no_html_fallback)
        print(f"확인: {res['total_checked']}, 변경: {res['changes_detected']}, "
              f"오류: {res['errors']}")
        upd = mgr.update_legal_references()
        print(f"legal_references 업데이트: {upd['updated']}/{upd['total']}")
    else:
        print("행정규칙 변경 확인 중...")
        res = mgr.sync_all(allow_html_fallback=not args.no_html_fallback)
        print(f"확인: {res['total_checked']}, 변경: {res['changes_detected']}")
        for d in res["details"]:
            print(f"  {d.get('name', '')} ({d['admrul_seq']}): "
                  f"{d['status']}")

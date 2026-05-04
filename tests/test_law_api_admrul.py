"""행정규칙(admRul) Open API 연동 단위 테스트.

실제 외부 호출 없이 ``urlopen`` 을 mock 으로 대체하여 검증한다.
실제 fetch 통합 테스트는 ``test_law_api_admrul_integration``
(``RUN_LAW_API_INTEGRATION=1`` 환경변수가 설정된 경우에만 실행) 으로 분리.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import unittest.mock as mock
from typing import Optional
from urllib.error import URLError

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.law_api_admrul import (  # noqa: E402
    AdmRulAPIClient,
    AdmRulSyncManager,
    MONITORED_ADMRULS,
    build_chatbot_context_chunks,
)


# ---------------------------------------------------------------------
# Sample Open API XML responses
# ---------------------------------------------------------------------

ADMRUL_BODY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdmRulService>
  <행정규칙명>보세전시장 운영에 관한 고시</행정규칙명>
  <소관부처명>관세청</소관부처명>
  <시행일자>20251101</시행일자>
  <조문단위>
    <조문번호>1</조문번호>
    <조문제목>목적</조문제목>
    <조문내용>이 고시는 관세법 제190조 등에 따른 보세전시장의 운영에 관하여 필요한 사항을 정함을 목적으로 한다.</조문내용>
  </조문단위>
  <조문단위>
    <조문번호>5</조문번호>
    <조문제목>특허기간</조문제목>
    <조문내용>보세전시장의 특허기간은 해당 박람회 등의 회기 만료일까지로 한다.</조문내용>
  </조문단위>
  <조문단위>
    <조문번호>6</조문번호>
    <조문제목>특허신청</조문제목>
    <조문내용>운영인이 되려는 자는 특허신청서에 사업계획서를 첨부하여 세관장에게 제출한다.</조문내용>
  </조문단위>
  <조문단위>
    <조문번호>10</조문번호>
    <조문제목>반출입의 신고</조문제목>
    <조문내용>운영인은 보세전시장에 외국물품을 반출입할 때에는 세관장에게 신고하여야 한다.</조문내용>
  </조문단위>
  <조문단위>
    <조문번호>15</조문번호>
    <조문제목>폐쇄</조문제목>
    <조문내용>관세법 제178조 또는 동법 제179조의 사유에 해당하는 경우 세관장은 특허를 취소하거나 보세전시장을 폐쇄할 수 있다.</조문내용>
  </조문단위>
</AdmRulService>"""


ADMRUL_SEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdmRulSearch>
  <admrul>
    <행정규칙일련번호>2100000276240</행정규칙일련번호>
    <행정규칙명>보세전시장 운영에 관한 고시</행정규칙명>
    <소관부처명>관세청</소관부처명>
  </admrul>
</AdmRulSearch>"""


def _fake_urlopen_factory(payload: Optional[str], status_map: Optional[dict] = None):
    """``urlopen`` 을 흉내내는 컨텍스트매니저 mock.

    Parameters
    ----------
    payload : str | None
        ``read()`` 가 반환할 utf-8 문자열. ``None`` 이면 URLError 를 발생.
    status_map : dict | None
        URL substring → payload 매핑. ``payload`` 보다 우선 적용된다.
    """
    def _opener(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        chosen = payload
        if status_map:
            for needle, alt in status_map.items():
                if needle in url:
                    chosen = alt
                    break
        if chosen is None:
            raise URLError("mock failure")

        class _Ctx:
            def __enter__(self_inner):
                return io.BytesIO(chosen.encode("utf-8"))

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()

    return _opener


# ---------------------------------------------------------------------
# AdmRulAPIClient
# ---------------------------------------------------------------------

class TestAdmRulAPIClient:
    def test_init_defaults(self, monkeypatch):
        monkeypatch.delenv("LAW_API_OC", raising=False)
        c = AdmRulAPIClient()
        assert c.oc == ""

    def test_init_env_oc(self, monkeypatch):
        monkeypatch.setenv("LAW_API_OC", "myid")
        c = AdmRulAPIClient()
        assert c.oc == "myid"

    def test_explicit_oc_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LAW_API_OC", "envid")
        c = AdmRulAPIClient(oc="explicit")
        assert c.oc == "explicit"

    def test_get_admrul_xml_success(self):
        c = AdmRulAPIClient()
        opener = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            xml = c.get_admrul_xml("2100000276240")
        assert xml is not None
        assert "보세전시장 운영에 관한 고시" in xml

    def test_get_admrul_xml_empty_seq(self):
        c = AdmRulAPIClient()
        assert c.get_admrul_xml("") is None

    def test_get_admrul_xml_url_error(self):
        c = AdmRulAPIClient()
        opener = _fake_urlopen_factory(None)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            assert c.get_admrul_xml("2100000276240") is None

    def test_search_admrul_parses_results(self):
        c = AdmRulAPIClient()
        opener = _fake_urlopen_factory(ADMRUL_SEARCH_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            res = c.search_admrul("보세전시장")
        assert any(r.get("admrul_seq") == "2100000276240" for r in res)
        assert any("보세전시장" in (r.get("name") or "") for r in res)

    def test_parse_admrul_body_extracts_articles(self):
        c = AdmRulAPIClient()
        parsed = c.parse_admrul_body(ADMRUL_BODY_XML)
        assert parsed["name"] == "보세전시장 운영에 관한 고시"
        assert parsed["agency"] == "관세청"
        assert parsed["effective_date"] == "20251101"
        assert "제5조" in parsed["articles"]
        assert "특허기간" in parsed["articles"]["제5조"]
        assert "회기 만료일까지" in parsed["articles"]["제5조"]
        assert "제15조" in parsed["articles"]
        assert parsed["full_text"]
        assert "폐쇄" in parsed["full_text"]

    def test_parse_admrul_body_empty_input(self):
        c = AdmRulAPIClient()
        assert c.parse_admrul_body(None)["articles"] == {}
        assert c.parse_admrul_body("")["articles"] == {}
        assert c.parse_admrul_body("not xml")["articles"] == {}

    def test_parse_html_body_fallback(self):
        c = AdmRulAPIClient()
        html = (
            "<html><head><title>보세전시장 운영에 관한 고시</title></head>"
            "<body><div>제1조 (목적) 이 고시는...</div>"
            "<div>제5조 (특허기간) 회기 만료일까지로 한다.</div></body></html>"
        )
        parsed = c.parse_html_body(html)
        assert "보세전시장" in parsed["name"]
        # 조문 분할
        assert any(k.startswith("제5조") for k in parsed["articles"])


# ---------------------------------------------------------------------
# AdmRulSyncManager
# ---------------------------------------------------------------------

@pytest.fixture
def sync_manager(tmp_path):
    db_path = tmp_path / "sync.db"
    client = AdmRulAPIClient(oc="")
    return AdmRulSyncManager(api_client=client, db_path=str(db_path))


class TestAdmRulSyncManager:
    def test_init_creates_tables(self, sync_manager):
        conn = sqlite3.connect(sync_manager.db_path)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        finally:
            conn.close()
        assert "admrul_content_cache" in tables
        assert "admrul_sync_log" in tables

    def test_sync_one_writes_cache(self, sync_manager):
        opener = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            res = sync_manager.sync_one("2100000276240")
        assert res["status"] in ("changed", "unchanged")
        assert res["name"] == "보세전시장 운영에 관한 고시"
        assert res["agency"] == "관세청"
        cached = sync_manager.get_cached("2100000276240")
        assert cached is not None
        assert cached["full_text"]
        assert "제5조" in cached["articles"]

    def test_sync_one_change_detection(self, sync_manager):
        opener1 = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener1):
            r1 = sync_manager.sync_one("2100000276240")
        # 첫 동기화는 previous 가 없어 unchanged 로 기록 (changed=False).
        assert r1["status"] == "unchanged"

        # 동일한 본문 재동기화 → 여전히 unchanged
        with mock.patch("src.law_api_admrul.urlopen", opener1):
            r2 = sync_manager.sync_one("2100000276240")
        assert r2["status"] == "unchanged"

        # 본문이 바뀐 XML 로 호출 → changed
        modified = ADMRUL_BODY_XML.replace(
            "회기 만료일까지", "전시 종료일 다음 날까지"
        )
        opener2 = _fake_urlopen_factory(modified)
        with mock.patch("src.law_api_admrul.urlopen", opener2):
            r3 = sync_manager.sync_one("2100000276240")
        assert r3["status"] == "changed"

    def test_sync_one_fetch_failure_returns_status(self, sync_manager):
        # XML 도 HTML 도 둘 다 실패
        opener = _fake_urlopen_factory(None)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            res = sync_manager.sync_one("2100000276240")
        assert res["status"] == "fetch_failed"

    def test_sync_all_iterates_seeds(self, sync_manager):
        opener = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            res = sync_manager.sync_all()
        assert res["total_checked"] == len(MONITORED_ADMRULS)
        assert res["errors"] == 0
        assert res["details"]
        assert any(d["admrul_seq"] == "2100000276240" for d in res["details"])

    def test_history_log(self, sync_manager):
        opener = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            sync_manager.sync_one("2100000276240")
            sync_manager.sync_one("2100000276240")
        hist = sync_manager.get_history(limit=10)
        assert len(hist) >= 2
        assert all(h["admrul_seq"] == "2100000276240" for h in hist)

    def test_list_cached(self, sync_manager):
        opener = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            sync_manager.sync_one("2100000276240")
        cached = sync_manager.list_cached()
        assert len(cached) == 1
        assert cached[0]["admrul_seq"] == "2100000276240"

    def test_get_monitored_returns_seed(self, sync_manager):
        seeds = sync_manager.get_monitored()
        assert any(s["admrul_seq"] == "2100000276240" for s in seeds)
        assert any(s["name"] == "보세전시장 운영에 관한 고시" for s in seeds)


# ---------------------------------------------------------------------
# legal_references.json 통합
# ---------------------------------------------------------------------

class TestUpdateLegalReferences:
    def test_update_admrul_url_and_summary(self, sync_manager, tmp_path,
                                           monkeypatch):
        # 캐시 채우기
        opener = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            sync_manager.sync_one("2100000276240")

        # 임시 legal_references.json 생성 (구 admRulSeq=...92944)
        ref_path = tmp_path / "legal_ref.json"
        ref_path.write_text(json.dumps({
            "references": [
                {
                    "id": "bonded_exhibition_notice",
                    "law_name": "보세전시장 운영에 관한 고시",
                    "title": "보세전시장 운영에 관한 고시",
                    "summary": "(예전 요약)",
                    "url": "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000092944",
                    "sub_articles": {"제5조": "특허기간", "제10조": "반출입의 신고"},
                }
            ]
        }, ensure_ascii=False), encoding="utf-8")

        import src.law_api_admrul as mod
        monkeypatch.setattr(mod, "LEGAL_REF_PATH", str(ref_path))

        result = sync_manager.update_legal_references()
        assert result["updated"] >= 1
        data = json.loads(ref_path.read_text(encoding="utf-8"))
        ref = data["references"][0]
        assert "2100000276240" in ref["url"]
        assert ref["summary"] != "(예전 요약)"
        assert "제5조" in ref["sub_articles"]
        assert "회기 만료일까지" in ref["sub_articles"]["제5조"]


# ---------------------------------------------------------------------
# retrieval chunks
# ---------------------------------------------------------------------

class TestBuildContextChunks:
    def test_chunks_after_sync(self, sync_manager):
        opener = _fake_urlopen_factory(ADMRUL_BODY_XML)
        with mock.patch("src.law_api_admrul.urlopen", opener):
            sync_manager.sync_one("2100000276240")
        chunks = build_chatbot_context_chunks(sync_manager)
        assert chunks, "expected at least one chunk after sync"
        joined = " ".join(c["text"] for c in chunks)
        assert "특허기간" in joined
        assert "반출입" in joined
        assert any(c["article"] == "제5조" for c in chunks)

    def test_chunks_empty_without_cache(self, tmp_path):
        mgr = AdmRulSyncManager(
            api_client=AdmRulAPIClient(),
            db_path=str(tmp_path / "empty.db"),
        )
        chunks = build_chatbot_context_chunks(mgr)
        assert chunks == []


# ---------------------------------------------------------------------
# integration test (skip-by-default)
# ---------------------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("RUN_LAW_API_INTEGRATION") != "1",
    reason="set RUN_LAW_API_INTEGRATION=1 to hit the live law.go.kr endpoint",
)
def test_live_admrul_fetch(tmp_path):
    mgr = AdmRulSyncManager(db_path=str(tmp_path / "live.db"))
    res = mgr.sync_one("2100000276240")
    assert res["status"] in ("changed", "unchanged"), res
    assert "보세전시장" in (res.get("name") or "")

"""법령(law) + 행정규칙(admRul) 통합 갱신 스크립트.

사용자가 수동 또는 스케줄러로 실행하여 다음을 수행한다:
  1. 국가법령정보센터에서 모니터링 대상 법령 조문 변경 확인
  2. 모니터링 대상 행정규칙(고시) 본문 동기화
  3. data/legal_references.json 자동 업데이트

사용 예::

    python scripts/refresh_law_data.py            # 전체 갱신
    python scripts/refresh_law_data.py --laws     # 법령만
    python scripts/refresh_law_data.py --admrul   # 행정규칙만
    python scripts/refresh_law_data.py --check    # 변경 확인만 (write 없음)

환경변수:
  LAW_API_OC : 국가법령정보센터 Open API 인증키 (선택, 없으면 무인증).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.law_api_sync import LawSyncManager  # noqa: E402
from src.law_api_admrul import AdmRulSyncManager  # noqa: E402


def refresh_laws(check_only: bool = False, allow_html_fallback: bool = True) -> dict:
    mgr = LawSyncManager()
    print("[1/2] 법령 변경 확인 중...")
    res = mgr.check_all()
    print(f"      확인: {res['total_checked']}, 변경: {res['changes_detected']}, "
          f"오류: {res['errors']}")
    if not check_only:
        upd = mgr.update_legal_references()
        print(f"      legal_references 업데이트: "
              f"{upd['updated']}/{upd['total']}")
    return res


def refresh_admruls(check_only: bool = False,
                    allow_html_fallback: bool = True) -> dict:
    mgr = AdmRulSyncManager()
    print("[2/2] 행정규칙(고시) 동기화 중...")
    res = mgr.sync_all(allow_html_fallback=allow_html_fallback)
    print(f"      확인: {res['total_checked']}, 변경: {res['changes_detected']}, "
          f"오류: {res['errors']}")
    for d in res["details"]:
        print(f"        - {d.get('name', '')} ({d['admrul_seq']}): "
              f"{d['status']}")
    if not check_only:
        upd = mgr.update_legal_references()
        print(f"      legal_references admRul 업데이트: "
              f"{upd['updated']}/{upd['total']}")
    return res


def main() -> int:
    parser = argparse.ArgumentParser(
        description="법령 + 행정규칙 통합 갱신"
    )
    parser.add_argument("--laws", action="store_true",
                        help="법령(law)만 갱신")
    parser.add_argument("--admrul", action="store_true",
                        help="행정규칙(admRul)만 갱신")
    parser.add_argument("--check", action="store_true",
                        help="변경 확인만 (legal_references write 없음)")
    parser.add_argument("--no-html-fallback", action="store_true",
                        help="공식 API 실패 시 HTML fallback 비활성화")
    args = parser.parse_args()

    started = time.time()

    do_laws = args.laws or not (args.laws or args.admrul)
    do_admrul = args.admrul or not (args.laws or args.admrul)

    summary: dict = {}
    if do_laws:
        summary["laws"] = refresh_laws(check_only=args.check)
    if do_admrul:
        summary["admrul"] = refresh_admruls(
            check_only=args.check,
            allow_html_fallback=not args.no_html_fallback,
        )

    elapsed = time.time() - started
    print(f"\n완료 ({elapsed:.1f}s)")

    laws_changes = summary.get("laws", {}).get("changes_detected", 0)
    admrul_changes = summary.get("admrul", {}).get("changes_detected", 0)
    total_changes = laws_changes + admrul_changes
    print(f"총 변경 감지: {total_changes}건")

    return 0


if __name__ == "__main__":
    sys.exit(main())

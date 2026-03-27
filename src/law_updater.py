"""법령 업데이트 감지 모듈.

국가법령정보센터의 보세전시장 관련 법령 변경을 감지하는 유틸리티.
수동 또는 cron으로 실행하여 법령 변경 여부를 확인한다.

사용법:
    python -m src.law_updater          # 변경 감지 실행
    python -m src.law_updater --check  # 현재 상태만 확인
"""

import json
import hashlib
import os
from datetime import datetime

from src.utils import load_json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "data", "law_update_state.json")


def compute_data_hash() -> dict:
    """현재 데이터 파일들의 해시를 계산한다."""
    files_to_check = [
        "data/faq.json",
        "data/legal_references.json",
        "data/escalation_rules.json",
    ]
    hashes = {}
    for filepath in files_to_check:
        full_path = os.path.join(BASE_DIR, filepath)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                hashes[filepath] = hashlib.md5(f.read()).hexdigest()
    return hashes


def load_state() -> dict:
    """이전 상태를 로드한다."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    """현재 상태를 저장한다."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_for_updates() -> dict:
    """법령 데이터 변경 여부를 확인한다.

    Returns:
        {
            "has_changes": bool,
            "changed_files": list[str],
            "last_checked": str (ISO timestamp),
            "current_hashes": dict
        }
    """
    previous_state = load_state()
    previous_hashes = previous_state.get("hashes", {})
    current_hashes = compute_data_hash()

    changed_files = []
    for filepath, current_hash in current_hashes.items():
        prev_hash = previous_hashes.get(filepath)
        if prev_hash and prev_hash != current_hash:
            changed_files.append(filepath)
        elif not prev_hash:
            changed_files.append(filepath)

    result = {
        "has_changes": len(changed_files) > 0,
        "changed_files": changed_files,
        "last_checked": datetime.now().isoformat(),
        "current_hashes": current_hashes,
    }

    # 상태 저장
    save_state({
        "hashes": current_hashes,
        "last_checked": result["last_checked"],
    })

    return result


def get_legal_references_summary() -> list[dict]:
    """현재 법령 근거 요약을 반환한다."""
    data = load_json("data/legal_references.json")
    refs = data.get("references", [])
    return [
        {
            "law_name": ref.get("law_name", ""),
            "article": ref.get("article", ""),
            "title": ref.get("title", ""),
            "has_url": bool(ref.get("url", "")),
        }
        for ref in refs
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="법령 업데이트 감지")
    parser.add_argument("--check", action="store_true", help="현재 상태만 확인")
    args = parser.parse_args()

    if args.check:
        state = load_state()
        print(f"마지막 확인: {state.get('last_checked', '없음')}")
        refs = get_legal_references_summary()
        print(f"등록된 법령: {len(refs)}개")
        for ref in refs:
            url_mark = "O" if ref["has_url"] else "X"
            print(f"  [{url_mark}] {ref['law_name']} {ref['article']} - {ref['title']}")
    else:
        result = check_for_updates()
        if result["has_changes"]:
            print(f"변경 감지: {result['changed_files']}")
        else:
            print("변경 없음")
        print(f"확인 시각: {result['last_checked']}")

"""유틸리티 함수 모듈."""

import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(relative_path: str) -> dict:
    """프로젝트 루트 기준 상대 경로로 JSON 파일을 로드한다."""
    full_path = os.path.join(BASE_DIR, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(relative_path: str) -> str:
    """프로젝트 루트 기준 상대 경로로 텍스트 파일을 로드한다."""
    full_path = os.path.join(BASE_DIR, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def normalize_query(query: str) -> str:
    """사용자 질문을 정규화한다 (소문자 변환, 공백 정리)."""
    return " ".join(query.strip().lower().split())

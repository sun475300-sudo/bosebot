"""범용 도메인 설정 시스템.

챗봇을 보세전시장뿐 아니라 어떤 도메인에서도 재사용할 수 있도록
도메인 설정을 로드·검증·전환하는 기능을 제공한다.

사용법:
    from src.domain_config import DomainConfig, DomainInitializer

    config = DomainConfig()
    config.load("config/domain_bonded_exhibition.json")
    name = config.get("domain.name")
"""

import copy
import json
import os
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 도메인 설정 스키마 정의 – 각 최상위 키와 필수 하위 키
_SCHEMA: Dict[str, Dict[str, Any]] = {
    "domain": {
        "required_keys": ["name", "code", "description"],
        "type": dict,
    },
    "categories": {
        "required_keys": None,  # list – 각 항목에 code, name 필수
        "type": list,
        "item_required_keys": ["code", "name"],
    },
    "persona": {
        "required_keys": ["name", "greeting", "tone"],
        "type": dict,
    },
    "response_format": {
        "required_keys": ["sections"],
        "type": dict,
    },
    "escalation": {
        "required_keys": ["enabled", "default_contact"],
        "type": dict,
    },
    "legal_references": {
        "required_keys": ["enabled", "source"],
        "type": dict,
    },
    "features": {
        "required_keys": [],
        "type": dict,
    },
    "limits": {
        "required_keys": [],
        "type": dict,
    },
}

# 빈 템플릿 기본값
_TEMPLATE: Dict[str, Any] = {
    "domain": {"name": "", "code": "", "description": ""},
    "categories": [],
    "persona": {"name": "", "greeting": "", "tone": "formal"},
    "response_format": {"sections": ["conclusion", "explanation", "legal_basis", "disclaimer"]},
    "escalation": {"enabled": True, "default_contact": ""},
    "legal_references": {"enabled": True, "source": ""},
    "features": {
        "sentiment_analysis": True,
        "user_segmentation": True,
        "knowledge_graph": True,
        "ab_testing": False,
        "multi_language": False,
    },
    "limits": {
        "max_query_length": 2000,
        "session_timeout_min": 30,
        "faq_max_items": 500,
    },
}


class DomainConfig:
    """도메인 설정을 로드·조회·수정·검증한다."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._path: Optional[str] = None
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # 로드 / 저장
    # ------------------------------------------------------------------

    def load(self, config_path: str) -> "DomainConfig":
        """JSON 파일에서 도메인 설정을 로드한다.

        Args:
            config_path: JSON 설정 파일의 경로.

        Returns:
            self (체이닝 지원)

        Raises:
            FileNotFoundError: 파일이 없을 때.
            json.JSONDecodeError: JSON 파싱 실패 시.
        """
        resolved = config_path if os.path.isabs(config_path) else os.path.join(BASE_DIR, config_path)
        with open(resolved, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._path = resolved
        self._loaded = True
        return self

    def load_dict(self, data: Dict[str, Any]) -> "DomainConfig":
        """딕셔너리에서 직접 로드한다."""
        self._data = copy.deepcopy(data)
        self._path = None
        self._loaded = True
        return self

    def save(self, config_path: Optional[str] = None) -> None:
        """현재 설정을 JSON 파일로 저장한다."""
        target = config_path or self._path
        if target is None:
            raise ValueError("저장할 경로가 지정되지 않았습니다.")
        resolved = target if os.path.isabs(target) else os.path.join(BASE_DIR, target)
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # get / set (dot notation 지원)
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """점(.) 표기법으로 설정값을 가져온다.

        예: config.get("domain.name"), config.get("limits.max_query_length")

        Args:
            key: 점으로 구분된 키.
            default: 키가 없을 때 반환할 기본값.

        Returns:
            설정값 또는 default.
        """
        parts = key.split(".")
        current: Any = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return default
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        """점(.) 표기법으로 설정값을 설정한다.

        중간 경로가 없으면 자동으로 딕셔너리를 생성한다.

        Args:
            key: 점으로 구분된 키.
            value: 설정할 값.
        """
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    # ------------------------------------------------------------------
    # 검증
    # ------------------------------------------------------------------

    def validate(self) -> Dict[str, Any]:
        """설정의 완전성을 검증한다.

        Returns:
            {"valid": bool, "errors": list[str], "warnings": list[str]}
        """
        errors: List[str] = []
        warnings: List[str] = []

        for section, schema in _SCHEMA.items():
            value = self._data.get(section)
            if value is None:
                errors.append(f"필수 섹션 '{section}'이(가) 누락되었습니다.")
                continue

            expected_type = schema["type"]
            if not isinstance(value, expected_type):
                errors.append(
                    f"'{section}'의 타입이 올바르지 않습니다. "
                    f"예상: {expected_type.__name__}, 실제: {type(value).__name__}"
                )
                continue

            if expected_type is dict:
                required = schema.get("required_keys") or []
                for rk in required:
                    if rk not in value:
                        errors.append(f"'{section}.{rk}'이(가) 누락되었습니다.")

            elif expected_type is list:
                item_keys = schema.get("item_required_keys") or []
                for idx, item in enumerate(value):
                    if not isinstance(item, dict):
                        errors.append(f"'{section}[{idx}]'이(가) dict가 아닙니다.")
                        continue
                    for rk in item_keys:
                        if rk not in item:
                            errors.append(f"'{section}[{idx}].{rk}'이(가) 누락되었습니다.")

        # 경고: 빈 값 검사
        domain = self._data.get("domain", {})
        if isinstance(domain, dict):
            if not domain.get("name"):
                warnings.append("domain.name이 비어 있습니다.")
            if not domain.get("code"):
                warnings.append("domain.code가 비어 있습니다.")

        categories = self._data.get("categories", [])
        if isinstance(categories, list) and len(categories) == 0:
            warnings.append("categories가 비어 있습니다. 최소 1개 카테고리를 권장합니다.")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # 템플릿
    # ------------------------------------------------------------------

    @staticmethod
    def export_template() -> Dict[str, Any]:
        """새 도메인을 위한 빈 템플릿을 반환한다."""
        return copy.deepcopy(_TEMPLATE)

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------

    @property
    def data(self) -> Dict[str, Any]:
        """전체 설정 딕셔너리를 반환한다."""
        return self._data

    @property
    def loaded(self) -> bool:
        return self._loaded

    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 반환한다 (deepcopy)."""
        return copy.deepcopy(self._data)

    def __repr__(self) -> str:
        domain_code = self.get("domain.code", "unknown")
        return f"<DomainConfig domain={domain_code} loaded={self._loaded}>"


class DomainInitializer:
    """도메인 생성·목록·전환을 관리한다."""

    def __init__(self, config_dir: Optional[str] = None) -> None:
        self._config_dir = config_dir or os.path.join(BASE_DIR, "config", "domains")
        self._active_domain: Optional[str] = None
        self._active_config: Optional[DomainConfig] = None

    @property
    def config_dir(self) -> str:
        return self._config_dir

    @property
    def active_domain(self) -> Optional[str]:
        return self._active_domain

    @property
    def active_config(self) -> Optional[DomainConfig]:
        return self._active_config

    def create_domain(self, domain_code: str, config: Optional[Dict[str, Any]] = None) -> str:
        """새 도메인을 생성한다.

        Args:
            domain_code: 도메인 코드 (예: "bonded_exhibition")
            config: 도메인 설정 딕셔너리. None이면 기본 템플릿 사용.

        Returns:
            생성된 설정 파일 경로.

        Raises:
            FileExistsError: 이미 같은 코드의 도메인이 존재할 때.
        """
        os.makedirs(self._config_dir, exist_ok=True)
        filepath = os.path.join(self._config_dir, f"{domain_code}.json")

        if os.path.exists(filepath):
            raise FileExistsError(f"도메인 '{domain_code}'이(가) 이미 존재합니다: {filepath}")

        data = config if config is not None else DomainConfig.export_template()
        if isinstance(data, dict) and "domain" in data and isinstance(data["domain"], dict):
            data["domain"].setdefault("code", domain_code)

        dc = DomainConfig()
        dc.load_dict(data)
        dc.save(filepath)
        return filepath

    def list_domains(self) -> List[Dict[str, str]]:
        """사용 가능한 도메인 목록을 반환한다.

        Returns:
            [{"code": "...", "name": "...", "path": "..."}, ...]
        """
        if not os.path.isdir(self._config_dir):
            return []

        domains: List[Dict[str, str]] = []
        for fname in sorted(os.listdir(self._config_dir)):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(self._config_dir, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                domain_info = data.get("domain", {})
                domains.append({
                    "code": domain_info.get("code", fname.replace(".json", "")),
                    "name": domain_info.get("name", ""),
                    "path": filepath,
                })
            except (json.JSONDecodeError, OSError):
                continue
        return domains

    def switch_domain(self, domain_code: str) -> DomainConfig:
        """활성 도메인을 전환한다.

        Args:
            domain_code: 전환할 도메인 코드.

        Returns:
            로드된 DomainConfig.

        Raises:
            FileNotFoundError: 해당 도메인 설정 파일이 없을 때.
        """
        filepath = os.path.join(self._config_dir, f"{domain_code}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"도메인 '{domain_code}' 설정 파일을 찾을 수 없습니다: {filepath}")

        dc = DomainConfig()
        dc.load(filepath)
        self._active_domain = domain_code
        self._active_config = dc
        return dc

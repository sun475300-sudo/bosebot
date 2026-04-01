"""동적 응답 템플릿 엔진 모듈.

범용 챗봇 커스터마이징을 위한 템플릿 렌더링 엔진을 제공한다.
변수 치환, 조건문, 반복문, 기본값 등을 지원한다.
"""

import re
from typing import Any


BUILT_IN_TEMPLATES = {
    "standard_answer": (
        "문의하신 내용은 [{{topic}}]에 관한 사항입니다.\n"
        "\n"
        "{% if conclusion %}결론:\n- {{conclusion}}\n\n{% endif %}"
        "{% if explanation %}설명:\n"
        "{% for item in explanation %}{{item}}\n{% endfor %}\n{% endif %}"
        "{% if legal_basis %}근거:\n"
        "{% for basis in legal_basis %}- {{basis}}\n{% endfor %}\n{% endif %}"
        "안내:\n- {{disclaimer|default:\"본 답변은 일반적인 안내용 설명입니다.\"}}"
    ),
    "escalation": (
        "{{greeting|default:\"안녕하세요.\"}}\n"
        "\n"
        "문의하신 내용에 대해 보다 정확한 안내를 위해 "
        "담당 부서로 연결해 드리겠습니다.\n"
        "\n"
        "{% if contact %}연락처: {{contact}}\n{% endif %}"
        "{% if department %}담당 부서: {{department}}\n{% endif %}"
        "{% if reason %}에스컬레이션 사유: {{reason}}\n{% endif %}"
    ),
    "unknown_query": (
        "현재 확인한 공식 자료만으로는 단정하기 어렵습니다.\n"
        "\n"
        "{% if suggestions %}관련 질문:\n"
        "{% for s in suggestions %}- {{s}}\n{% endfor %}\n{% endif %}"
        "추가 안내:\n"
        "- 관세청 고객지원센터(125)로 문의하시거나,\n"
        "- 관할 세관에 직접 확인하시기 바랍니다."
    ),
    "welcome": (
        "{{greeting|default:\"안녕하세요!\"}} "
        "{{service_name|default:\"보세전시장 민원응대 챗봇\"}}입니다.\n"
        "\n"
        "{% if features %}이용 가능한 기능:\n"
        "{% for f in features %}- {{f}}\n{% endfor %}{% endif %}"
        "\n무엇을 도와드릴까요?"
    ),
    "error": (
        "죄송합니다. {{error_type|default:\"처리\"}} 중 오류가 발생했습니다.\n"
        "\n"
        "{% if error_message %}오류 내용: {{error_message}}\n{% endif %}"
        "{% if retry %}잠시 후 다시 시도해 주세요.\n{% endif %}"
        "문제가 지속되면 관리자에게 문의해 주세요."
    ),
}


class TemplateEngine:
    """템플릿 렌더링 엔진.

    변수 치환, 조건문, 반복문, 기본값을 지원한다.
    """

    def __init__(self):
        self._templates: dict[str, str] = dict(BUILT_IN_TEMPLATES)

    # ---- CRUD ----------------------------------------------------------

    def register_template(self, name: str, template_str: str) -> None:
        """커스텀 템플릿을 등록한다."""
        if not name or not isinstance(name, str):
            raise ValueError("템플릿 이름은 비어있지 않은 문자열이어야 합니다.")
        if not isinstance(template_str, str):
            raise ValueError("템플릿은 문자열이어야 합니다.")
        self._templates[name] = template_str

    def get_template(self, name: str) -> str:
        """템플릿 내용을 반환한다."""
        if name not in self._templates:
            raise KeyError(f"템플릿 '{name}'을(를) 찾을 수 없습니다.")
        return self._templates[name]

    def list_templates(self) -> list[str]:
        """등록된 모든 템플릿 이름 목록을 반환한다."""
        return sorted(self._templates.keys())

    def delete_template(self, name: str) -> None:
        """템플릿을 삭제한다."""
        if name not in self._templates:
            raise KeyError(f"템플릿 '{name}'을(를) 찾을 수 없습니다.")
        del self._templates[name]

    # ---- Rendering -----------------------------------------------------

    def render(self, template_name: str, context: dict[str, Any] | None = None) -> str:
        """템플릿을 렌더링한다.

        Args:
            template_name: 렌더링할 템플릿 이름.
            context: 변수 치환에 사용할 딕셔너리.

        Returns:
            렌더링된 문자열.
        """
        template_str = self.get_template(template_name)
        return self.render_string(template_str, context or {})

    def render_string(self, template_str: str, context: dict[str, Any]) -> str:
        """문자열 템플릿을 직접 렌더링한다."""
        result = template_str
        result = self._process_for_loops(result, context)
        result = self._process_conditionals(result, context)
        result = self._substitute_variables(result, context)
        return result

    # ---- Internal processing -------------------------------------------

    def _substitute_variables(self, text: str, context: dict[str, Any]) -> str:
        """{{variable}} 및 {{variable|default:"fallback"}} 처리."""

        def _replace(match: re.Match) -> str:
            expr = match.group(1).strip()
            # Check for default filter
            default_match = re.match(r'^(.+?)\|default:"(.*?)"$', expr)
            if default_match:
                var_name = default_match.group(1).strip()
                default_val = default_match.group(2)
                value = context.get(var_name)
                if value is None or value == "":
                    return default_val
                return str(value)
            # Simple variable
            value = context.get(expr)
            if value is None:
                return ""
            return str(value)

        return re.sub(r'\{\{(.+?)\}\}', _replace, text)

    def _process_conditionals(self, text: str, context: dict[str, Any]) -> str:
        """{% if condition %}...{% endif %} 처리."""

        def _replace_if(match: re.Match) -> str:
            condition = match.group(1).strip()
            body = match.group(2)
            # Evaluate condition: check if variable is truthy in context
            negate = False
            if condition.startswith("not "):
                negate = True
                condition = condition[4:].strip()
            value = context.get(condition)
            truthy = bool(value)
            if negate:
                truthy = not truthy
            return body if truthy else ""

        pattern = r'\{%\s*if\s+(.+?)\s*%\}(.*?)\{%\s*endif\s*%\}'
        return re.sub(pattern, _replace_if, text, flags=re.DOTALL)

    def _process_for_loops(self, text: str, context: dict[str, Any]) -> str:
        """{% for item in list %}...{% endfor %} 처리."""

        def _replace_for(match: re.Match) -> str:
            var_name = match.group(1).strip()
            list_name = match.group(2).strip()
            body = match.group(3)
            items = context.get(list_name, [])
            if not isinstance(items, (list, tuple)):
                return ""
            parts = []
            for item in items:
                loop_ctx = dict(context)
                loop_ctx[var_name] = item
                rendered = self._substitute_variables(body, loop_ctx)
                parts.append(rendered)
            return "".join(parts)

        pattern = r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}'
        return re.sub(pattern, _replace_for, text, flags=re.DOTALL)


class ResponseFormatter:
    """응답 포맷터.

    TemplateEngine을 사용하여 답변 데이터를 포맷팅한다.
    도메인별 설정으로 챗봇을 범용적으로 재사용할 수 있다.
    """

    def __init__(self, engine: TemplateEngine | None = None):
        self.engine = engine or TemplateEngine()
        self._domain_config: dict[str, Any] = {}

    def format_response(
        self,
        answer_data: dict[str, Any],
        template: str = "standard_answer",
        lang: str = "ko",
    ) -> str:
        """답변 데이터를 템플릿으로 포맷팅한다.

        Args:
            answer_data: 렌더링에 사용할 데이터 딕셔너리.
            template: 사용할 템플릿 이름.
            lang: 언어 코드 (현재 ko 지원).

        Returns:
            포맷팅된 답변 문자열.
        """
        context = dict(answer_data)
        # Merge domain config defaults
        for key, value in self._domain_config.items():
            if key not in context:
                context[key] = value
        if lang != "ko":
            context.setdefault("lang", lang)
        return self.engine.render(template, context)

    def customize_format(self, domain_config: dict[str, Any]) -> None:
        """도메인별 포맷팅 설정을 적용한다.

        Args:
            domain_config: 도메인별 설정 딕셔너리.
                - service_name: 서비스명
                - disclaimer: 면책 문구
                - greeting: 인사말
                - templates: 추가 템플릿 딕셔너리
        """
        self._domain_config = dict(domain_config)
        # Register any domain-specific templates
        templates = domain_config.get("templates", {})
        for name, tpl_str in templates.items():
            self.engine.register_template(name, tpl_str)

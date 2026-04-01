"""템플릿 엔진 테스트."""

import json

import pytest

from src.template_engine import TemplateEngine, ResponseFormatter, BUILT_IN_TEMPLATES


# ---- TemplateEngine unit tests -----------------------------------------

class TestTemplateEngineInit:
    """초기화 테스트."""

    def test_built_in_templates_loaded(self):
        engine = TemplateEngine()
        names = engine.list_templates()
        for expected in ["standard_answer", "escalation", "unknown_query", "welcome", "error"]:
            assert expected in names

    def test_list_templates_returns_sorted(self):
        engine = TemplateEngine()
        names = engine.list_templates()
        assert names == sorted(names)


class TestTemplateCRUD:
    """CRUD 작업 테스트."""

    def test_register_and_get(self):
        engine = TemplateEngine()
        engine.register_template("my_tpl", "Hello {{name}}")
        assert engine.get_template("my_tpl") == "Hello {{name}}"

    def test_register_overwrites(self):
        engine = TemplateEngine()
        engine.register_template("t", "v1")
        engine.register_template("t", "v2")
        assert engine.get_template("t") == "v2"

    def test_get_nonexistent_raises(self):
        engine = TemplateEngine()
        with pytest.raises(KeyError):
            engine.get_template("nonexistent_xyz")

    def test_delete_template(self):
        engine = TemplateEngine()
        engine.register_template("del_me", "bye")
        engine.delete_template("del_me")
        assert "del_me" not in engine.list_templates()

    def test_delete_nonexistent_raises(self):
        engine = TemplateEngine()
        with pytest.raises(KeyError):
            engine.delete_template("no_such_template")

    def test_register_empty_name_raises(self):
        engine = TemplateEngine()
        with pytest.raises(ValueError):
            engine.register_template("", "content")

    def test_register_non_string_content_raises(self):
        engine = TemplateEngine()
        with pytest.raises(ValueError):
            engine.register_template("t", 123)

    def test_list_includes_custom(self):
        engine = TemplateEngine()
        engine.register_template("zzz_custom", "hi")
        names = engine.list_templates()
        assert "zzz_custom" in names


class TestVariableSubstitution:
    """변수 치환 테스트."""

    def test_simple_variable(self):
        engine = TemplateEngine()
        engine.register_template("t", "Hello {{name}}!")
        result = engine.render("t", {"name": "World"})
        assert result == "Hello World!"

    def test_multiple_variables(self):
        engine = TemplateEngine()
        engine.register_template("t", "{{a}} and {{b}}")
        result = engine.render("t", {"a": "X", "b": "Y"})
        assert result == "X and Y"

    def test_missing_variable_renders_empty(self):
        engine = TemplateEngine()
        engine.register_template("t", "Hi {{name}}!")
        result = engine.render("t", {})
        assert result == "Hi !"

    def test_default_value(self):
        engine = TemplateEngine()
        engine.register_template("t", '{{name|default:"Guest"}}')
        result = engine.render("t", {})
        assert result == "Guest"

    def test_default_not_used_when_value_present(self):
        engine = TemplateEngine()
        engine.register_template("t", '{{name|default:"Guest"}}')
        result = engine.render("t", {"name": "Alice"})
        assert result == "Alice"

    def test_default_used_for_empty_string(self):
        engine = TemplateEngine()
        engine.register_template("t", '{{name|default:"Guest"}}')
        result = engine.render("t", {"name": ""})
        assert result == "Guest"

    def test_numeric_variable(self):
        engine = TemplateEngine()
        engine.register_template("t", "Count: {{count}}")
        result = engine.render("t", {"count": 42})
        assert result == "Count: 42"


class TestConditionals:
    """조건문 테스트."""

    def test_if_true(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if show %}visible{% endif %}")
        result = engine.render("t", {"show": True})
        assert result == "visible"

    def test_if_false(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if show %}visible{% endif %}")
        result = engine.render("t", {"show": False})
        assert result == ""

    def test_if_missing_variable(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if show %}visible{% endif %}")
        result = engine.render("t", {})
        assert result == ""

    def test_if_truthy_string(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if msg %}{{msg}}{% endif %}")
        result = engine.render("t", {"msg": "hello"})
        assert result == "hello"

    def test_if_truthy_list(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if items %}has items{% endif %}")
        result = engine.render("t", {"items": [1, 2]})
        assert result == "has items"

    def test_if_empty_list_falsy(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if items %}has items{% endif %}")
        result = engine.render("t", {"items": []})
        assert result == ""

    def test_if_not_condition(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if not hide %}shown{% endif %}")
        result = engine.render("t", {"hide": False})
        assert result == "shown"

    def test_if_not_true_hidden(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if not hide %}shown{% endif %}")
        result = engine.render("t", {"hide": True})
        assert result == ""

    def test_multiple_conditionals(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% if a %}A{% endif %}{% if b %}B{% endif %}")
        result = engine.render("t", {"a": True, "b": True})
        assert result == "AB"


class TestForLoops:
    """반복문 테스트."""

    def test_simple_loop(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% for item in items %}{{item}} {% endfor %}")
        result = engine.render("t", {"items": ["a", "b", "c"]})
        assert result == "a b c "

    def test_empty_loop(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% for item in items %}{{item}}{% endfor %}")
        result = engine.render("t", {"items": []})
        assert result == ""

    def test_missing_list(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% for item in items %}{{item}}{% endfor %}")
        result = engine.render("t", {})
        assert result == ""

    def test_loop_preserves_outer_context(self):
        engine = TemplateEngine()
        engine.register_template("t", "{{prefix}}: {% for x in items %}{{prefix}}-{{x}} {% endfor %}")
        result = engine.render("t", {"prefix": "P", "items": ["1", "2"]})
        assert result == "P: P-1 P-2 "

    def test_non_list_produces_empty(self):
        engine = TemplateEngine()
        engine.register_template("t", "{% for x in items %}{{x}}{% endfor %}")
        result = engine.render("t", {"items": "not_a_list"})
        assert result == ""


class TestBuiltInTemplateRendering:
    """내장 템플릿 렌더링 테스트."""

    def test_standard_answer(self):
        engine = TemplateEngine()
        result = engine.render("standard_answer", {
            "topic": "보세전시장",
            "conclusion": "가능합니다.",
            "explanation": ["설명1", "설명2"],
            "legal_basis": ["관세법 제190조"],
        })
        assert "보세전시장" in result
        assert "가능합니다." in result
        assert "설명1" in result
        assert "관세법 제190조" in result

    def test_welcome(self):
        engine = TemplateEngine()
        result = engine.render("welcome", {
            "features": ["FAQ 질문", "실시간 상담"],
        })
        assert "보세전시장 민원응대 챗봇" in result
        assert "FAQ 질문" in result

    def test_error_with_defaults(self):
        engine = TemplateEngine()
        result = engine.render("error", {})
        assert "처리" in result
        assert "오류가 발생했습니다" in result

    def test_unknown_query(self):
        engine = TemplateEngine()
        result = engine.render("unknown_query", {
            "suggestions": ["관련 질문 1"],
        })
        assert "단정하기 어렵습니다" in result
        assert "관련 질문 1" in result

    def test_escalation(self):
        engine = TemplateEngine()
        result = engine.render("escalation", {
            "contact": "125",
            "department": "통관과",
        })
        assert "담당 부서" in result
        assert "125" in result


class TestRenderString:
    """render_string 직접 렌더링 테스트."""

    def test_render_string_directly(self):
        engine = TemplateEngine()
        result = engine.render_string("Hello {{name}}!", {"name": "World"})
        assert result == "Hello World!"


# ---- ResponseFormatter tests -------------------------------------------

class TestResponseFormatter:
    """ResponseFormatter 테스트."""

    def test_format_with_default_template(self):
        fmt = ResponseFormatter()
        result = fmt.format_response({
            "topic": "수입",
            "conclusion": "허가 필요",
            "explanation": ["설명"],
            "legal_basis": ["관세법"],
        })
        assert "수입" in result
        assert "허가 필요" in result

    def test_format_with_custom_template(self):
        fmt = ResponseFormatter()
        fmt.engine.register_template("custom", "Answer: {{answer}}")
        result = fmt.format_response({"answer": "42"}, template="custom")
        assert result == "Answer: 42"

    def test_customize_format_sets_defaults(self):
        fmt = ResponseFormatter()
        fmt.customize_format({
            "service_name": "테스트 서비스",
            "greeting": "환영합니다",
        })
        result = fmt.format_response({}, template="welcome")
        assert "테스트 서비스" in result
        assert "환영합니다" in result

    def test_customize_format_registers_templates(self):
        fmt = ResponseFormatter()
        fmt.customize_format({
            "templates": {"domain_tpl": "Domain: {{domain}}"},
        })
        result = fmt.format_response({"domain": "customs"}, template="domain_tpl")
        assert result == "Domain: customs"

    def test_format_response_lang(self):
        fmt = ResponseFormatter()
        fmt.engine.register_template("lang_test", "Lang: {{lang}}")
        result = fmt.format_response({}, template="lang_test", lang="en")
        assert result == "Lang: en"

    def test_answer_data_overrides_domain_config(self):
        fmt = ResponseFormatter()
        fmt.customize_format({"greeting": "default hello"})
        result = fmt.format_response(
            {"greeting": "custom hello"},
            template="escalation",
        )
        assert "custom hello" in result
        assert "default hello" not in result


# ---- API endpoint tests ------------------------------------------------

@pytest.fixture
def client():
    """Flask test client with auth bypass."""
    import web_server
    web_server.app.config["TESTING"] = True
    # Reset template engine for each test
    web_server.template_engine = TemplateEngine()
    # Bypass JWT auth for testing
    original_require = web_server.jwt_auth.require_auth

    def _noop_auth():
        def decorator(f):
            return f
        return decorator

    web_server.jwt_auth.require_auth = _noop_auth
    with web_server.app.test_client() as c:
        yield c
    web_server.jwt_auth.require_auth = original_require


class TestTemplateAPI:
    """템플릿 관리 API 테스트."""

    def test_list_templates(self, client):
        resp = client.get("/api/admin/templates")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "templates" in data
        assert "standard_answer" in data["templates"]
        assert data["count"] == len(data["templates"])

    def test_create_template(self, client):
        resp = client.post(
            "/api/admin/templates",
            json={"name": "test_tpl", "content": "Hello {{who}}"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "test_tpl"

    def test_create_template_missing_name(self, client):
        resp = client.post(
            "/api/admin/templates",
            json={"content": "Hello"},
        )
        assert resp.status_code == 400

    def test_create_template_missing_content(self, client):
        resp = client.post(
            "/api/admin/templates",
            json={"name": "t"},
        )
        assert resp.status_code == 400

    def test_update_template(self, client):
        # Create first
        client.post(
            "/api/admin/templates",
            json={"name": "upd_tpl", "content": "v1"},
        )
        resp = client.put(
            "/api/admin/templates/upd_tpl",
            json={"content": "v2"},
        )
        assert resp.status_code == 200

    def test_update_nonexistent(self, client):
        resp = client.put(
            "/api/admin/templates/nonexistent_xyz",
            json={"content": "v2"},
        )
        assert resp.status_code == 404

    def test_update_missing_content(self, client):
        resp = client.put(
            "/api/admin/templates/standard_answer",
            json={},
        )
        assert resp.status_code == 400

    def test_delete_template(self, client):
        client.post(
            "/api/admin/templates",
            json={"name": "to_delete", "content": "bye"},
        )
        resp = client.delete("/api/admin/templates/to_delete")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/admin/templates/nonexistent_xyz")
        assert resp.status_code == 404

    def test_preview_with_template_name(self, client):
        resp = client.post(
            "/api/admin/templates/preview",
            json={
                "template_name": "welcome",
                "context": {"service_name": "Test Bot"},
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Test Bot" in data["rendered"]

    def test_preview_with_template_str(self, client):
        resp = client.post(
            "/api/admin/templates/preview",
            json={
                "template_str": "Hi {{name}}!",
                "context": {"name": "User"},
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()["rendered"] == "Hi User!"

    def test_preview_missing_both(self, client):
        resp = client.post(
            "/api/admin/templates/preview",
            json={"context": {}},
        )
        assert resp.status_code == 400

    def test_preview_nonexistent_template(self, client):
        resp = client.post(
            "/api/admin/templates/preview",
            json={"template_name": "nonexistent_xyz"},
        )
        assert resp.status_code == 404

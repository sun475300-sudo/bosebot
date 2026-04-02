"""Admin pages serving tests."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    os.environ["ADMIN_AUTH_DISABLED"] = "true"
    os.environ["TESTING"] = "true"
    from web_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    os.environ.pop("ADMIN_AUTH_DISABLED", None)
    os.environ.pop("TESTING", None)


class TestAdminPages:
    def test_notifications_page(self, client):
        res = client.get("/admin/notifications")
        assert res.status_code == 200
        assert b"html" in res.data.lower()

    def test_analytics_page(self, client):
        res = client.get("/admin/analytics")
        assert res.status_code == 200
        assert b"html" in res.data.lower()

    def test_admin_page(self, client):
        res = client.get("/admin")
        assert res.status_code == 200

    def test_faq_manager_page(self, client):
        res = client.get("/admin/faq")
        assert res.status_code == 200

    def test_health_dashboard(self, client):
        res = client.get("/health-dashboard")
        assert res.status_code == 200

    def test_swagger_docs(self, client):
        res = client.get("/docs")
        assert res.status_code == 200

    def test_login_page(self, client):
        res = client.get("/login")
        assert res.status_code == 200

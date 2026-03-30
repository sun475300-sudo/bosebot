"""작업 스케줄러 테스트."""

import os
import sys
import tempfile
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.task_scheduler import CronParser, TaskScheduler, create_default_scheduler


# ============================================================
# CronParser Tests
# ============================================================

class TestCronParserParse:
    """cron 표현식 파싱 테스트."""

    def test_all_wildcards(self):
        result = CronParser.parse("* * * * *")
        assert result["minute"] == set(range(0, 60))
        assert result["hour"] == set(range(0, 24))
        assert result["day"] == set(range(1, 32))
        assert result["month"] == set(range(1, 13))
        assert result["weekday"] == set(range(0, 7))

    def test_specific_values(self):
        result = CronParser.parse("30 2 15 6 3")
        assert result["minute"] == {30}
        assert result["hour"] == {2}
        assert result["day"] == {15}
        assert result["month"] == {6}
        assert result["weekday"] == {3}

    def test_step_values(self):
        result = CronParser.parse("*/15 */6 * * *")
        assert result["minute"] == {0, 15, 30, 45}
        assert result["hour"] == {0, 6, 12, 18}

    def test_range_values(self):
        result = CronParser.parse("1-5 9-17 * * *")
        assert result["minute"] == {1, 2, 3, 4, 5}
        assert result["hour"] == set(range(9, 18))

    def test_list_values(self):
        result = CronParser.parse("0,15,30,45 * * * *")
        assert result["minute"] == {0, 15, 30, 45}

    def test_range_with_step(self):
        result = CronParser.parse("1-10/2 * * * *")
        assert result["minute"] == {1, 3, 5, 7, 9}

    def test_combined_list_and_range(self):
        result = CronParser.parse("0,10-15 * * * *")
        assert result["minute"] == {0, 10, 11, 12, 13, 14, 15}

    def test_invalid_field_count(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            CronParser.parse("* * *")

    def test_invalid_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            CronParser.parse("60 * * * *")

    def test_daily_at_two_am(self):
        result = CronParser.parse("0 2 * * *")
        assert result["minute"] == {0}
        assert result["hour"] == {2}

    def test_monday_only(self):
        result = CronParser.parse("0 8 * * 0")
        assert result["weekday"] == {0}


class TestCronParserMatches:
    """cron 일치 확인 테스트."""

    def test_matches_every_minute(self):
        dt = datetime(2025, 6, 15, 10, 30)
        assert CronParser.matches("* * * * *", dt) is True

    def test_matches_specific_time(self):
        dt = datetime(2025, 6, 15, 2, 0)
        assert CronParser.matches("0 2 * * *", dt) is True

    def test_does_not_match_wrong_hour(self):
        dt = datetime(2025, 6, 15, 3, 0)
        assert CronParser.matches("0 2 * * *", dt) is False

    def test_does_not_match_wrong_minute(self):
        dt = datetime(2025, 6, 15, 2, 30)
        assert CronParser.matches("0 2 * * *", dt) is False

    def test_matches_step(self):
        dt = datetime(2025, 6, 15, 10, 15)
        assert CronParser.matches("*/15 * * * *", dt) is True

    def test_does_not_match_step(self):
        dt = datetime(2025, 6, 15, 10, 7)
        assert CronParser.matches("*/15 * * * *", dt) is False

    def test_matches_weekday(self):
        # 2025-06-16 is a Monday (weekday=0)
        dt = datetime(2025, 6, 16, 8, 0)
        assert CronParser.matches("0 8 * * 0", dt) is True

    def test_does_not_match_weekday(self):
        # 2025-06-17 is a Tuesday (weekday=1)
        dt = datetime(2025, 6, 17, 8, 0)
        assert CronParser.matches("0 8 * * 0", dt) is False

    def test_matches_day_of_month(self):
        dt = datetime(2025, 1, 1, 3, 0)
        assert CronParser.matches("0 3 1 * *", dt) is True

    def test_does_not_match_day_of_month(self):
        dt = datetime(2025, 1, 2, 3, 0)
        assert CronParser.matches("0 3 1 * *", dt) is False


class TestCronParserNextRun:
    """다음 실행 시각 계산 테스트."""

    def test_next_run_every_minute(self):
        after = datetime(2025, 6, 15, 10, 30, 0)
        result = CronParser.next_run("* * * * *", after)
        assert result == datetime(2025, 6, 15, 10, 31, 0)

    def test_next_run_specific_time_same_day(self):
        after = datetime(2025, 6, 15, 1, 0, 0)
        result = CronParser.next_run("0 2 * * *", after)
        assert result == datetime(2025, 6, 15, 2, 0, 0)

    def test_next_run_specific_time_next_day(self):
        after = datetime(2025, 6, 15, 3, 0, 0)
        result = CronParser.next_run("0 2 * * *", after)
        assert result == datetime(2025, 6, 16, 2, 0, 0)

    def test_next_run_step(self):
        after = datetime(2025, 6, 15, 10, 14, 0)
        result = CronParser.next_run("*/15 * * * *", after)
        assert result == datetime(2025, 6, 15, 10, 15, 0)

    def test_next_run_monthly(self):
        after = datetime(2025, 6, 2, 0, 0, 0)
        result = CronParser.next_run("0 3 1 * *", after)
        assert result == datetime(2025, 7, 1, 3, 0, 0)

    def test_next_run_default_after_is_now(self):
        result = CronParser.next_run("* * * * *")
        now = datetime.now()
        # Result should be within 2 minutes of now
        assert result >= now
        assert result <= now + timedelta(minutes=2)

    def test_next_run_weekday(self):
        # 2025-06-15 is Sunday (weekday=6), next Monday is 2025-06-16
        after = datetime(2025, 6, 15, 10, 0, 0)
        result = CronParser.next_run("0 8 * * 0", after)
        assert result == datetime(2025, 6, 16, 8, 0, 0)


# ============================================================
# TaskScheduler Tests
# ============================================================

class TestTaskRegistration:
    """작업 등록/제거 테스트."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.scheduler = TaskScheduler(db_path=self.tmp.name)

    def teardown_method(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_register_task(self):
        self.scheduler.register_task("test", lambda: None, "* * * * *")
        tasks = self.scheduler.list_tasks()
        assert len(tasks) == 1
        assert tasks[0]["name"] == "test"
        assert tasks[0]["enabled"] is True

    def test_register_task_disabled(self):
        self.scheduler.register_task("test", lambda: None, "* * * * *", enabled=False)
        tasks = self.scheduler.list_tasks()
        assert tasks[0]["enabled"] is False

    def test_register_invalid_cron(self):
        with pytest.raises(ValueError):
            self.scheduler.register_task("test", lambda: None, "bad cron")

    def test_unregister_task(self):
        self.scheduler.register_task("test", lambda: None, "* * * * *")
        self.scheduler.unregister_task("test")
        assert len(self.scheduler.list_tasks()) == 0

    def test_unregister_nonexistent(self):
        with pytest.raises(KeyError):
            self.scheduler.unregister_task("nonexistent")

    def test_list_tasks_multiple(self):
        self.scheduler.register_task("a", lambda: None, "0 * * * *")
        self.scheduler.register_task("b", lambda: None, "30 * * * *")
        tasks = self.scheduler.list_tasks()
        names = {t["name"] for t in tasks}
        assert names == {"a", "b"}

    def test_list_tasks_has_next_run(self):
        self.scheduler.register_task("test", lambda: None, "0 2 * * *")
        tasks = self.scheduler.list_tasks()
        assert tasks[0]["next_run"] is not None


class TestTaskExecution:
    """수동 실행 테스트."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.scheduler = TaskScheduler(db_path=self.tmp.name)

    def teardown_method(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_run_task_success(self):
        self.scheduler.register_task("test", lambda: "ok", "* * * * *")
        result = self.scheduler.run_task("test")
        assert result["status"] == "success"
        assert result["result"] == "ok"

    def test_run_task_failure(self):
        def failing():
            raise RuntimeError("boom")

        self.scheduler.register_task("test", failing, "* * * * *")
        result = self.scheduler.run_task("test")
        assert result["status"] == "error"
        assert "boom" in result["error"]

    def test_run_task_nonexistent(self):
        with pytest.raises(KeyError):
            self.scheduler.run_task("nonexistent")

    def test_run_updates_counts(self):
        self.scheduler.register_task("test", lambda: "ok", "* * * * *")
        self.scheduler.run_task("test")
        status = self.scheduler.get_task_status("test")
        assert status["success_count"] == 1
        assert status["fail_count"] == 0
        assert status["last_run"] is not None

    def test_run_failure_updates_fail_count(self):
        self.scheduler.register_task("test", lambda: 1 / 0, "* * * * *")
        self.scheduler.run_task("test")
        status = self.scheduler.get_task_status("test")
        assert status["fail_count"] == 1
        assert status["success_count"] == 0


class TestExecutionLog:
    """실행 이력 테스트."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.scheduler = TaskScheduler(db_path=self.tmp.name)

    def teardown_method(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_log_after_success(self):
        self.scheduler.register_task("test", lambda: "done", "* * * * *")
        self.scheduler.run_task("test")
        logs = self.scheduler.get_execution_log(task_name="test")
        assert len(logs) == 1
        assert logs[0]["status"] == "success"
        assert logs[0]["task_name"] == "test"

    def test_log_after_failure(self):
        self.scheduler.register_task("test", lambda: 1 / 0, "* * * * *")
        self.scheduler.run_task("test")
        logs = self.scheduler.get_execution_log(task_name="test")
        assert len(logs) == 1
        assert logs[0]["status"] == "error"
        assert logs[0]["error"] is not None

    def test_log_limit(self):
        self.scheduler.register_task("test", lambda: "ok", "* * * * *")
        for _ in range(10):
            self.scheduler.run_task("test")
        logs = self.scheduler.get_execution_log(task_name="test", limit=5)
        assert len(logs) == 5

    def test_log_all_tasks(self):
        self.scheduler.register_task("a", lambda: "a", "* * * * *")
        self.scheduler.register_task("b", lambda: "b", "* * * * *")
        self.scheduler.run_task("a")
        self.scheduler.run_task("b")
        logs = self.scheduler.get_execution_log()
        assert len(logs) == 2
        names = {log["task_name"] for log in logs}
        assert names == {"a", "b"}


class TestTaskStatus:
    """작업 상태 조회 테스트."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.scheduler = TaskScheduler(db_path=self.tmp.name)

    def teardown_method(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_get_status(self):
        self.scheduler.register_task("test", lambda: None, "0 2 * * *")
        status = self.scheduler.get_task_status("test")
        assert status["name"] == "test"
        assert status["cron_expr"] == "0 2 * * *"
        assert status["enabled"] is True
        assert status["next_run"] is not None

    def test_get_status_nonexistent(self):
        with pytest.raises(KeyError):
            self.scheduler.get_task_status("nonexistent")

    def test_set_enabled(self):
        self.scheduler.register_task("test", lambda: None, "* * * * *")
        self.scheduler.set_task_enabled("test", False)
        status = self.scheduler.get_task_status("test")
        assert status["enabled"] is False

    def test_set_enabled_nonexistent(self):
        with pytest.raises(KeyError):
            self.scheduler.set_task_enabled("nonexistent", True)


class TestStartStop:
    """스케줄러 시작/중지 테스트."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.scheduler = TaskScheduler(db_path=self.tmp.name)

    def teardown_method(self):
        self.scheduler.stop()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_start_creates_thread(self):
        self.scheduler.start()
        assert self.scheduler._running is True
        assert self.scheduler._thread is not None
        assert self.scheduler._thread.is_alive()

    def test_stop_terminates_thread(self):
        self.scheduler.start()
        self.scheduler.stop()
        assert self.scheduler._running is False

    def test_double_start_is_safe(self):
        self.scheduler.start()
        thread1 = self.scheduler._thread
        self.scheduler.start()
        assert self.scheduler._thread is thread1


class TestDefaultScheduler:
    """기본 스케줄러 생성 테스트."""

    def test_default_tasks_registered(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            scheduler = create_default_scheduler(db_path=tmp.name)
            tasks = scheduler.list_tasks()
            names = {t["name"] for t in tasks}
            assert "daily_backup" in names
            assert "weekly_report" in names
            assert "law_check" in names
            assert "cleanup_old_logs" in names
            assert "faq_quality_check" in names
            assert len(tasks) == 5
        finally:
            os.unlink(tmp.name)


# ============================================================
# API Endpoint Tests
# ============================================================

from web_server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_header():
    """유효한 JWT 토큰으로 인증 헤더를 생성한다."""
    from src.auth import JWTAuth
    jwt = JWTAuth()
    token = jwt.generate_token("admin", role="admin")
    return {"Authorization": f"Bearer {token}"}


class TestSchedulerAPI:
    """스케줄러 API 엔드포인트 테스트."""

    def test_list_tasks(self, client, auth_header):
        res = client.get("/api/admin/scheduler/tasks", headers=auth_header)
        assert res.status_code == 200
        data = res.get_json()
        assert "tasks" in data
        assert "count" in data
        assert data["count"] >= 5

    def test_run_task(self, client, auth_header):
        res = client.post(
            "/api/admin/scheduler/tasks/cleanup_old_logs/run",
            headers=auth_header,
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] in ("success", "error")

    def test_run_task_not_found(self, client, auth_header):
        res = client.post(
            "/api/admin/scheduler/tasks/nonexistent/run",
            headers=auth_header,
        )
        assert res.status_code == 404

    def test_update_task_disable(self, client, auth_header):
        res = client.put(
            "/api/admin/scheduler/tasks/daily_backup",
            headers=auth_header,
            json={"enabled": False},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["enabled"] is False

        # Re-enable
        client.put(
            "/api/admin/scheduler/tasks/daily_backup",
            headers=auth_header,
            json={"enabled": True},
        )

    def test_update_task_not_found(self, client, auth_header):
        res = client.put(
            "/api/admin/scheduler/tasks/nonexistent",
            headers=auth_header,
            json={"enabled": False},
        )
        assert res.status_code == 404

    def test_execution_log(self, client, auth_header):
        # Run a task first to ensure there's a log entry
        client.post(
            "/api/admin/scheduler/tasks/cleanup_old_logs/run",
            headers=auth_header,
        )
        res = client.get("/api/admin/scheduler/log", headers=auth_header)
        assert res.status_code == 200
        data = res.get_json()
        assert "logs" in data
        assert "count" in data

    def test_execution_log_with_filter(self, client, auth_header):
        res = client.get(
            "/api/admin/scheduler/log?task_name=cleanup_old_logs&limit=5",
            headers=auth_header,
        )
        assert res.status_code == 200
        data = res.get_json()
        for log_entry in data["logs"]:
            assert log_entry["task_name"] == "cleanup_old_logs"

    def test_list_tasks_unauthenticated(self, client):
        # Enable AUTH_TESTING so Flask TESTING mode doesn't bypass auth
        app.config["AUTH_TESTING"] = True
        try:
            res = client.get("/api/admin/scheduler/tasks")
            assert res.status_code in (401, 403)
        finally:
            app.config.pop("AUTH_TESTING", None)

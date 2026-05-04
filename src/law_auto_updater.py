"""법령/행정규칙 자동 업데이트 백그라운드 스케줄러.

챗봇이 시작될 때 :func:`start_auto_updater` 가 호출되면, daemon 스레드가
주기적으로 :class:`~src.law_api_admrul.AdmRulSyncManager` 와
:class:`~src.law_api_sync.LawSyncManager` 를 실행해 국가법령정보센터
변경사항을 감지하고, 변경이 있을 때만 챗봇 인덱스를 다시 빌드하도록
사용자 콜백을 호출한다.

환경변수
~~~~~~~~
``LAW_AUTO_UPDATE_ENABLED``
    ``true`` (기본) 면 활성화. ``false`` 면 :func:`start_auto_updater` 가
    no-op 으로 즉시 반환한다.
``LAW_AUTO_UPDATE_INTERVAL_HOURS``
    실행 간격(시간 단위, float). 기본 ``6``. 최소 ``0.05`` (3분).
``LAW_AUTO_UPDATE_INITIAL_DELAY``
    부팅 후 첫 실행까지 지연(초). 기본 ``5``.
``LAW_AUTO_UPDATE_LOG``
    로그 파일 경로. 기본 ``<repo>/logs/law_auto_update.log``.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional

# Lazy import 가능하지만, 모듈 로딩 단계에서 즉시 발견 가능하도록 명시 import.
from src.law_api_admrul import AdmRulSyncManager
from src.law_api_sync import LawSyncManager

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOG_PATH = os.path.join(REPO_ROOT, "logs", "law_auto_update.log")

ChangeCallback = Callable[[dict], None]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        v = float(raw)
    except ValueError:
        return default
    return max(v, minimum)


def _ensure_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger("law_auto_updater")
    if getattr(logger, "_law_auto_updater_configured", False):
        return logger
    logger.setLevel(logging.INFO)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(handler)
    logger._law_auto_updater_configured = True  # type: ignore[attr-defined]
    return logger


class LawAutoUpdater:
    """주기적 법령/행정규칙 동기화 매니저.

    Parameters
    ----------
    interval_hours : float
        실행 간격(시간). 환경변수가 우선.
    initial_delay : float
        부팅 후 첫 실행까지 지연(초). 환경변수가 우선.
    on_change : callable
        변경이 감지될 때마다 호출되는 콜백.
        ``{"laws": ..., "admrul": ..., "checked_at": ...}`` 를 받음.
    enabled : bool
        ``False`` 면 :meth:`start` 가 no-op.
    log_path : str
        로그 파일 경로.
    admrul_manager / law_manager : 매니저 인스턴스 주입(테스트용).
    """

    def __init__(
        self,
        interval_hours: Optional[float] = None,
        initial_delay: Optional[float] = None,
        on_change: Optional[ChangeCallback] = None,
        enabled: Optional[bool] = None,
        log_path: Optional[str] = None,
        admrul_manager: Optional[AdmRulSyncManager] = None,
        law_manager: Optional[LawSyncManager] = None,
    ):
        self.interval_hours = (
            interval_hours
            if interval_hours is not None
            else _float_env("LAW_AUTO_UPDATE_INTERVAL_HOURS", 6.0, minimum=0.05)
        )
        self.initial_delay = (
            initial_delay
            if initial_delay is not None
            else _float_env("LAW_AUTO_UPDATE_INITIAL_DELAY", 5.0, minimum=0.0)
        )
        self.enabled = (
            enabled
            if enabled is not None
            else _bool_env("LAW_AUTO_UPDATE_ENABLED", True)
        )
        self.log_path = log_path or os.environ.get(
            "LAW_AUTO_UPDATE_LOG", DEFAULT_LOG_PATH
        )
        self.on_change = on_change
        self._admrul = admrul_manager
        self._law = law_manager
        self._stop_event = threading.Event()
        self._run_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._logger = _ensure_logger(self.log_path)

        # 상태 정보 (모니터링 엔드포인트에서 조회)
        self.last_run_at: Optional[str] = None
        self.last_status: str = "never_run"
        self.last_error: Optional[str] = None
        self.last_changes: int = 0
        self.last_details: List[dict] = []
        self.total_runs: int = 0
        self.total_changes: int = 0

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """백그라운드 스레드를 시작한다.

        Returns
        -------
        bool
            실제로 시작된 경우 ``True``. 비활성화/이미 실행 중이면 ``False``.
        """
        if not self.enabled:
            self._logger.info(
                "auto-updater disabled via LAW_AUTO_UPDATE_ENABLED"
            )
            return False
        if self._thread is not None and self._thread.is_alive():
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="LawAutoUpdater",
            daemon=True,
        )
        self._thread.start()
        self._logger.info(
            "auto-updater started: interval=%.2fh delay=%.1fs",
            self.interval_hours,
            self.initial_delay,
        )
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """스레드를 정지 신호 후 join."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._logger.info("auto-updater stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # core
    # ------------------------------------------------------------------

    def run_once(self) -> dict:
        """1회 동기화 실행. 동시 실행 방지 lock 적용.

        다른 스레드가 실행 중이면 ``{"status": "skipped_locked"}`` 를 반환.
        """
        if not self._run_lock.acquire(blocking=False):
            return {"status": "skipped_locked"}
        try:
            return self._sync_now()
        finally:
            self._run_lock.release()

    def _sync_now(self) -> dict:
        started = datetime.now()
        result: dict = {
            "status": "ok",
            "started_at": started.isoformat(),
            "laws": {},
            "admrul": {},
            "changes_detected": 0,
            "error": None,
        }
        admrul_changes = 0
        law_changes = 0
        try:
            admrul = self._admrul or AdmRulSyncManager()
            admrul_res = admrul.sync_all(allow_html_fallback=True)
            try:
                admrul.update_legal_references()
            except Exception as e:  # noqa: BLE001
                self._logger.warning(
                    "update_legal_references(admrul) failed: %s", e
                )
            result["admrul"] = admrul_res
            admrul_changes = admrul_res.get("changes_detected", 0)
        except Exception as e:  # noqa: BLE001
            self._logger.exception("admrul sync failed")
            result["status"] = "error"
            result["error"] = f"admrul: {e}"

        try:
            law = self._law or LawSyncManager()
            law_res = law.check_all() if hasattr(law, "check_all") else {}
            try:
                if hasattr(law, "update_legal_references"):
                    law.update_legal_references()
            except Exception as e:  # noqa: BLE001
                self._logger.warning(
                    "update_legal_references(law) failed: %s", e
                )
            result["laws"] = law_res
            law_changes = (law_res or {}).get("changes_detected", 0)
        except Exception as e:  # noqa: BLE001
            self._logger.exception("law sync failed")
            result["status"] = "error"
            result["error"] = (result["error"] or "") + f" laws: {e}"

        total_changes = int(admrul_changes) + int(law_changes)
        result["changes_detected"] = total_changes
        result["finished_at"] = datetime.now().isoformat()

        # 상태 갱신
        self.last_run_at = result["finished_at"]
        self.last_status = result["status"]
        self.last_error = result["error"]
        self.last_changes = total_changes
        self.last_details = (result.get("admrul") or {}).get("details", [])
        self.total_runs += 1
        self.total_changes += total_changes

        self._logger.info(
            "sync complete: status=%s changes=%d admrul_changes=%d law_changes=%d",
            result["status"], total_changes, admrul_changes, law_changes,
        )

        # 콜백 — 변경이 있을 때만 호출
        if total_changes > 0 and self.on_change is not None:
            try:
                self.on_change(result)
                self._logger.info("on_change callback invoked")
            except Exception as e:  # noqa: BLE001
                self._logger.exception("on_change callback failed: %s", e)

        return result

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """모니터링 엔드포인트용 상태 dict."""
        next_run_at = None
        if self.last_run_at:
            try:
                last = datetime.fromisoformat(self.last_run_at)
                nxt = last + timedelta(hours=self.interval_hours)
                next_run_at = nxt.isoformat()
            except Exception:  # noqa: BLE001
                next_run_at = None
        return {
            "enabled": self.enabled,
            "running": self.is_running(),
            "interval_hours": self.interval_hours,
            "initial_delay_seconds": self.initial_delay,
            "last_run_at": self.last_run_at,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_changes": self.last_changes,
            "last_details": self.last_details,
            "next_run_at": next_run_at,
            "total_runs": self.total_runs,
            "total_changes": self.total_changes,
            "log_path": self.log_path,
        }

    # ------------------------------------------------------------------
    # internal loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        # initial delay (interruptible)
        if self._stop_event.wait(timeout=self.initial_delay):
            return
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:  # noqa: BLE001
                self._logger.exception("unhandled error in run_once")
            # 다음 실행까지 대기 (interruptible)
            interval_sec = max(self.interval_hours * 3600.0, 1.0)
            if self._stop_event.wait(timeout=interval_sec):
                return


# ---------------------------------------------------------------------
# 싱글톤 헬퍼
# ---------------------------------------------------------------------

_singleton: Optional[LawAutoUpdater] = None
_singleton_lock = threading.Lock()


def start_auto_updater(
    on_change: Optional[ChangeCallback] = None,
    **kwargs,
) -> Optional[LawAutoUpdater]:
    """전역 싱글톤 자동 업데이터를 시작한다.

    이미 실행 중이면 기존 인스턴스를 반환하고 시작은 하지 않는다.
    비활성화 상태(``LAW_AUTO_UPDATE_ENABLED=false``) 일 때는 ``None`` 반환.
    """
    global _singleton
    with _singleton_lock:
        if _singleton is not None and _singleton.is_running():
            return _singleton
        updater = LawAutoUpdater(on_change=on_change, **kwargs)
        if not updater.enabled:
            return None
        if updater.start():
            _singleton = updater
            return updater
        return _singleton


def get_auto_updater() -> Optional[LawAutoUpdater]:
    """현재 등록된 싱글톤 인스턴스(없으면 ``None``)."""
    return _singleton


def stop_auto_updater(timeout: float = 5.0) -> None:
    """싱글톤 인스턴스를 정지한다."""
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            _singleton.stop(timeout=timeout)
            _singleton = None


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="Law auto-updater (background scheduler)"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run a single sync cycle and exit")
    parser.add_argument("--status", action="store_true",
                        help="Print current status (singleton must be running)")
    args = parser.parse_args()

    if args.status:
        upd = get_auto_updater()
        if upd is None:
            print("no auto-updater running")
        else:
            import json as _json
            print(_json.dumps(upd.status(), ensure_ascii=False, indent=2))
    else:
        updater = LawAutoUpdater()
        if args.once or not updater.enabled:
            res = updater.run_once()
            print(res)
        else:
            updater.start()
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                updater.stop()

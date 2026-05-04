# Law Auto-Update — Operations Guide

The chatbot ships with a built-in **background scheduler** that keeps the
admRul (행정규칙) and law (법령) caches in sync with the official
국가법령정보센터 Open API. The headline target is the customs notice
**「보세전시장 운영에 관한 고시」 (admRulSeq=2100000276240)**, but every
entry registered in `MONITORED_ADMRULS` and the law sync seed list is
refreshed on the same schedule.

## How it works

When the chatbot starts, call:

```python
from src.chatbot import BondedExhibitionChatbot
bot = BondedExhibitionChatbot()
bot.enable_auto_law_updates()
```

This kicks off a daemon `threading.Thread` that:

1. Waits `LAW_AUTO_UPDATE_INITIAL_DELAY` seconds (default 5) so chatbot
   warm-up is not blocked.
2. Calls `AdmRulSyncManager.sync_all()` — fetches the latest admRul body
   from the official Open API (XML), falls back to the HTML viewer if
   needed, and stores everything in
   `data/law_sync.db::admrul_content_cache`.
3. Calls `LawSyncManager.check_all()` for monitored laws.
4. Compares the fresh content hash with the previous cached hash. **If
   anything changed**, the registered `on_change` callback fires —
   which in turn calls `BondedExhibitionChatbot.refresh_admrul_index()`
   so the live retrieval index reflects the new text without a
   restart.
5. Sleeps `LAW_AUTO_UPDATE_INTERVAL_HOURS` hours (default 6) and
   repeats.

All sync activity is appended to `logs/law_auto_update.log`.

## Environment variables

| Variable                         | Default                              | Notes                                                                |
|----------------------------------|--------------------------------------|----------------------------------------------------------------------|
| `LAW_AUTO_UPDATE_ENABLED`        | `true`                               | Set to `false` to disable the in-app scheduler entirely.            |
| `LAW_AUTO_UPDATE_INTERVAL_HOURS` | `6`                                  | Float; minimum 0.05 (3 minutes).                                    |
| `LAW_AUTO_UPDATE_INITIAL_DELAY`  | `5`                                  | Seconds to wait before the first run after process start.          |
| `LAW_AUTO_UPDATE_LOG`            | `<repo>/logs/law_auto_update.log`    | Plain text log appended by the scheduler.                          |
| `LAW_API_OC`                     | unset                                | Optional API key (email ID) for higher-rate access to law.go.kr.   |
| `ADMIN_TOKEN`                    | unset                                | Required to call the admin endpoints below.                         |

## Admin endpoints

Wire the routes onto your Flask app:

```python
from src.law_sync_admin import register_law_sync_routes
register_law_sync_routes(app)
```

| Method | Path                              | Purpose                                          |
|--------|-----------------------------------|--------------------------------------------------|
| GET    | `/api/admin/law-sync/status`      | Current scheduler state, last/next run, errors. |
| POST   | `/api/admin/law-sync/refresh`     | Trigger one sync cycle immediately.             |

Both routes require `Authorization: Bearer <ADMIN_TOKEN>`. If
`ADMIN_TOKEN` is unset the endpoints return **503** (locked).

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:5000/api/admin/law-sync/status
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:5000/api/admin/law-sync/refresh
```

## Windows Task Scheduler (external scheduler)

Prefer this when you do not run the chatbot 24/7. Set
`LAW_AUTO_UPDATE_ENABLED=false`, then double-click
`SCHEDULE_LAW_REFRESH.bat` from the repo root. It registers a per-user
HOURLY task (every 6 hours) that calls
`scripts/scheduled_refresh.py`. Logs append to
`logs/law_auto_update.log`.

To remove the task, run `UNSCHEDULE_LAW_REFRESH.bat`.

To verify the registration:

```cmd
schtasks /Query /TN BondedChatbotLawRefresh
```

## Manual one-shot refresh

```bash
python scripts/scheduled_refresh.py        # human-readable
python scripts/scheduled_refresh.py --json # machine-readable
```

Exit code is `0` on success, `1` on any sync error (logged).

## Verifying a change was picked up

1. Run `python -m src.law_api_admrul --history` — every checked seq
   shows whether the body hash changed.
2. `GET /api/admin/law-sync/status` reports `last_changes` and
   `last_details`.
3. `data/legal_references.json` has its `summary` and `last_synced`
   fields refreshed for the matching admRul entries.

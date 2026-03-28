"""자동화된 대화 분석 리포트 생성기.

일별/주별/월별 분석 리포트를 생성하고 HTML 또는 JSON으로 내보낸다.
"""

import json
import os
from collections import Counter
from datetime import datetime, timedelta


class ReportGenerator:
    """대화 로그와 피드백 데이터를 기반으로 분석 리포트를 생성하는 클래스."""

    def __init__(self, logger_db, feedback_db=None):
        """ChatLogger와 선택적 FeedbackManager 인스턴스를 받아 초기화한다.

        Args:
            logger_db: ChatLogger 인스턴스
            feedback_db: FeedbackManager 인스턴스 (선택)
        """
        self.logger_db = logger_db
        self.feedback_db = feedback_db

    def _query_logs(self, start_date, end_date):
        """지정된 기간의 로그를 조회한다.

        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD, 포함)

        Returns:
            list[dict]: 로그 레코드 리스트
        """
        conn = self.logger_db._get_conn()
        end_date_next = (
            datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT * FROM chat_logs
               WHERE timestamp >= ? AND timestamp < ?
               ORDER BY id""",
            (start_date, end_date_next),
        ).fetchall()
        return [dict(row) for row in rows]

    def _query_feedback(self, start_date, end_date):
        """지정된 기간의 피드백을 조회한다.

        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD, 포함)

        Returns:
            list[dict]: 피드백 레코드 리스트
        """
        if not self.feedback_db:
            return []
        conn = self.feedback_db._get_conn()
        end_date_next = (
            datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT * FROM feedback
               WHERE timestamp >= ? AND timestamp < ?
               ORDER BY id""",
            (start_date, end_date_next),
        ).fetchall()
        return [dict(row) for row in rows]

    def _build_report(self, logs, feedback, period_label, start_date, end_date):
        """로그와 피드백 데이터로 리포트 데이터를 구성한다.

        Args:
            logs: 로그 레코드 리스트
            feedback: 피드백 레코드 리스트
            period_label: 기간 레이블 (예: "2024-01-01 daily")
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            dict: 리포트 데이터
        """
        total_queries = len(logs)

        # Unique sessions - chat_logs 테이블에 session_id가 없으므로
        # timestamp 기반 근사치 사용 (같은 시간대 = 같은 세션으로 추정)
        # 여기서는 IP/세션이 없으므로 일별 질문 그룹을 세션으로 근사
        session_dates = set()
        for log in logs:
            ts = log.get("timestamp", "")
            if len(ts) >= 10:
                session_dates.add(ts[:10])
        unique_sessions = max(len(session_dates), 1) if logs else 0
        avg_queries_per_session = (
            round(total_queries / unique_sessions, 1) if unique_sessions > 0 else 0
        )

        # Category distribution
        category_counter = Counter()
        for log in logs:
            cat = log.get("category") or "UNKNOWN"
            category_counter[cat] += 1
        category_distribution = []
        for cat, count in category_counter.most_common():
            pct = round(count / total_queries * 100, 1) if total_queries > 0 else 0
            category_distribution.append({
                "category": cat,
                "count": count,
                "percentage": pct,
            })

        # Top 10 most asked questions
        query_counter = Counter()
        for log in logs:
            q = log.get("query", "").strip()
            if q:
                query_counter[q] += 1
        top_questions = [
            {"query": q, "count": c}
            for q, c in query_counter.most_common(10)
        ]

        # Escalation rate and reasons
        escalation_count = sum(
            1 for log in logs if log.get("is_escalation")
        )
        escalation_rate = (
            round(escalation_count / total_queries * 100, 1)
            if total_queries > 0 else 0
        )
        # Escalation queries breakdown by category
        escalation_categories = Counter()
        for log in logs:
            if log.get("is_escalation"):
                cat = log.get("category") or "UNKNOWN"
                escalation_categories[cat] += 1
        escalation_reasons = [
            {"category": cat, "count": c}
            for cat, c in escalation_categories.most_common()
        ]

        # Match rate (keyword/TF-IDF vs unmatched)
        matched_count = sum(1 for log in logs if log.get("faq_id"))
        unmatched_count = total_queries - matched_count
        matched_rate = (
            round(matched_count / total_queries * 100, 1)
            if total_queries > 0 else 0
        )
        unmatched_rate = (
            round(unmatched_count / total_queries * 100, 1)
            if total_queries > 0 else 0
        )
        match_rate = {
            "matched": matched_count,
            "matched_rate": matched_rate,
            "unmatched": unmatched_count,
            "unmatched_rate": unmatched_rate,
        }

        # Satisfaction score
        satisfaction = None
        if feedback:
            helpful_count = sum(
                1 for fb in feedback if fb.get("rating") == "helpful"
            )
            unhelpful_count = sum(
                1 for fb in feedback if fb.get("rating") == "unhelpful"
            )
            total_feedback = len(feedback)
            helpful_rate = (
                round(helpful_count / total_feedback * 100, 1)
                if total_feedback > 0 else 0
            )
            satisfaction = {
                "total_feedback": total_feedback,
                "helpful_count": helpful_count,
                "unhelpful_count": unhelpful_count,
                "helpful_rate": helpful_rate,
            }

        # Peak hours analysis
        hour_counter = Counter()
        for log in logs:
            ts = log.get("timestamp", "")
            if len(ts) >= 13:
                try:
                    hour = int(ts[11:13])
                    if 0 <= hour <= 23:
                        hour_counter[hour] += 1
                except (ValueError, IndexError):
                    pass
        hours_list = [
            {"hour": h, "count": hour_counter.get(h, 0)} for h in range(24)
        ]
        peak_hour = max(range(24), key=lambda h: hour_counter.get(h, 0)) if logs else 0
        peak_count = hour_counter.get(peak_hour, 0)
        peak_hours = {
            "hours": hours_list,
            "peak_hour": peak_hour,
            "peak_count": peak_count,
        }

        # Unmatched queries summary
        unmatched_queries = []
        unmatched_query_counter = Counter()
        for log in logs:
            if not log.get("faq_id"):
                q = log.get("query", "").strip()
                if q:
                    unmatched_query_counter[q] += 1
        unmatched_queries = [
            {"query": q, "count": c}
            for q, c in unmatched_query_counter.most_common(20)
        ]

        return {
            "period": period_label,
            "start_date": start_date,
            "end_date": end_date,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_queries": total_queries,
            "unique_sessions": unique_sessions,
            "avg_queries_per_session": avg_queries_per_session,
            "category_distribution": category_distribution,
            "top_questions": top_questions,
            "escalation_rate": escalation_rate,
            "escalation_count": escalation_count,
            "escalation_reasons": escalation_reasons,
            "match_rate": match_rate,
            "satisfaction": satisfaction,
            "peak_hours": peak_hours,
            "unmatched_queries": unmatched_queries,
        }

    def generate_daily_report(self, date=None):
        """일별 리포트를 생성한다.

        Args:
            date: 날짜 문자열 (YYYY-MM-DD). None이면 오늘.

        Returns:
            dict: 리포트 데이터
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        logs = self._query_logs(date, date)
        feedback = self._query_feedback(date, date)
        return self._build_report(logs, feedback, "daily", date, date)

    def generate_weekly_report(self, week_start=None):
        """주별 리포트를 생성한다.

        Args:
            week_start: 주 시작 날짜 (YYYY-MM-DD). None이면 이번 주 월요일.

        Returns:
            dict: 리포트 데이터
        """
        if week_start is None:
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            week_start = monday.strftime("%Y-%m-%d")
        start_dt = datetime.strptime(week_start, "%Y-%m-%d")
        week_end = (start_dt + timedelta(days=6)).strftime("%Y-%m-%d")
        logs = self._query_logs(week_start, week_end)
        feedback = self._query_feedback(week_start, week_end)
        return self._build_report(logs, feedback, "weekly", week_start, week_end)

    def generate_monthly_report(self, year, month):
        """월별 리포트를 생성한다.

        Args:
            year: 연도 (정수)
            month: 월 (정수, 1-12)

        Returns:
            dict: 리포트 데이터
        """
        start_date = f"{year:04d}-{month:02d}-01"
        # 다음 달 1일에서 하루 전 = 해당 월 마지막 날
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1)
        else:
            next_month_start = datetime(year, month + 1, 1)
        end_date = (next_month_start - timedelta(days=1)).strftime("%Y-%m-%d")
        logs = self._query_logs(start_date, end_date)
        feedback = self._query_feedback(start_date, end_date)
        return self._build_report(logs, feedback, "monthly", start_date, end_date)

    def export_json(self, report_data, output_path):
        """리포트 데이터를 JSON 파일로 내보낸다.

        Args:
            report_data: 리포트 데이터 딕셔너리
            output_path: 출력 파일 경로
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

    def export_html(self, report_data, output_path):
        """리포트 데이터를 자체 포함 HTML 파일로 내보낸다.

        인라인 CSS를 사용한 바 차트와 파이 차트 스타일 표시를 포함한다.

        Args:
            report_data: 리포트 데이터 딕셔너리
            output_path: 출력 파일 경로
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        html = self._render_html(report_data)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _render_html(self, data):
        """리포트 데이터를 HTML 문자열로 렌더링한다."""
        period = data.get("period", "report")
        start = data.get("start_date", "")
        end = data.get("end_date", "")
        generated = data.get("generated_at", "")
        total_q = data.get("total_queries", 0)
        sessions = data.get("unique_sessions", 0)
        avg_qps = data.get("avg_queries_per_session", 0)
        esc_rate = data.get("escalation_rate", 0)
        esc_count = data.get("escalation_count", 0)
        match = data.get("match_rate", {})
        satisfaction = data.get("satisfaction")

        # Build category bar chart
        cat_dist = data.get("category_distribution", [])
        max_cat = max((c["count"] for c in cat_dist), default=1)
        cat_bars = ""
        for item in cat_dist:
            pct = item["count"] / max_cat * 100 if max_cat > 0 else 0
            cat_bars += (
                f'<div style="display:flex;align-items:center;margin-bottom:6px;">'
                f'<span style="width:130px;text-align:right;padding-right:8px;'
                f'font-size:13px;color:#555;">{_esc(item["category"])}</span>'
                f'<div style="flex:1;background:#e9ecef;border-radius:4px;height:22px;overflow:hidden;">'
                f'<div style="width:{pct:.1f}%;height:100%;background:#3498db;border-radius:4px;"></div>'
                f'</div>'
                f'<span style="width:70px;padding-left:8px;font-size:13px;color:#555;">'
                f'{item["count"]} ({item["percentage"]}%)</span>'
                f'</div>\n'
            )

        # Build top questions table
        top_q = data.get("top_questions", [])
        top_rows = ""
        for i, item in enumerate(top_q, 1):
            top_rows += (
                f'<tr><td style="padding:6px 10px;">{i}</td>'
                f'<td style="padding:6px 10px;">{_esc(item["query"])}</td>'
                f'<td style="padding:6px 10px;text-align:center;">{item["count"]}</td></tr>\n'
            )

        # Build escalation reasons
        esc_reasons = data.get("escalation_reasons", [])
        esc_rows = ""
        for item in esc_reasons:
            esc_rows += (
                f'<tr><td style="padding:6px 10px;">{_esc(item["category"])}</td>'
                f'<td style="padding:6px 10px;text-align:center;">{item["count"]}</td></tr>\n'
            )

        # Build match rate pie-chart-like display
        matched_rate = match.get("matched_rate", 0)
        unmatched_rate = match.get("unmatched_rate", 0)
        match_display = (
            f'<div style="display:flex;gap:20px;align-items:center;margin-top:10px;">'
            f'<div style="width:100px;height:100px;border-radius:50%;'
            f'background:conic-gradient(#27ae60 0% {matched_rate}%, #e74c3c {matched_rate}% 100%);'
            f'display:flex;align-items:center;justify-content:center;">'
            f'<div style="width:70px;height:70px;border-radius:50%;background:#fff;'
            f'display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;">'
            f'{matched_rate}%</div></div>'
            f'<div><div style="margin-bottom:4px;">'
            f'<span style="display:inline-block;width:12px;height:12px;background:#27ae60;'
            f'border-radius:2px;margin-right:6px;"></span>Matched: {match.get("matched", 0)}'
            f' ({matched_rate}%)</div>'
            f'<div><span style="display:inline-block;width:12px;height:12px;background:#e74c3c;'
            f'border-radius:2px;margin-right:6px;"></span>Unmatched: {match.get("unmatched", 0)}'
            f' ({unmatched_rate}%)</div></div></div>'
        )

        # Satisfaction section
        sat_section = ""
        if satisfaction:
            sat_rate = satisfaction.get("helpful_rate", 0)
            sat_section = (
                f'<div class="section">'
                f'<h2>Satisfaction Score</h2>'
                f'<div style="display:flex;gap:20px;align-items:center;">'
                f'<div style="width:100px;height:100px;border-radius:50%;'
                f'background:conic-gradient(#27ae60 0% {sat_rate}%, #e9ecef {sat_rate}% 100%);'
                f'display:flex;align-items:center;justify-content:center;">'
                f'<div style="width:70px;height:70px;border-radius:50%;background:#fff;'
                f'display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;">'
                f'{sat_rate}%</div></div>'
                f'<div>'
                f'<div>Total Feedback: {satisfaction.get("total_feedback", 0)}</div>'
                f'<div>Helpful: {satisfaction.get("helpful_count", 0)}</div>'
                f'<div>Unhelpful: {satisfaction.get("unhelpful_count", 0)}</div>'
                f'</div></div></div>'
            )

        # Peak hours bar chart
        peak = data.get("peak_hours", {})
        hours = peak.get("hours", [])
        max_h = max((h["count"] for h in hours), default=1)
        hour_bars = ""
        for h in hours:
            h_pct = h["count"] / max_h * 100 if max_h > 0 else 0
            hour_bars += (
                f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;">'
                f'<div style="width:100%;background:#e9ecef;height:80px;border-radius:2px;'
                f'position:relative;overflow:hidden;">'
                f'<div style="position:absolute;bottom:0;width:100%;height:{h_pct:.1f}%;'
                f'background:#3498db;border-radius:2px 2px 0 0;"></div></div>'
                f'<span style="font-size:10px;color:#999;margin-top:2px;">{h["hour"]}</span></div>'
            )

        # Unmatched queries
        unmatched_q = data.get("unmatched_queries", [])
        unmatched_rows = ""
        for i, item in enumerate(unmatched_q[:20], 1):
            unmatched_rows += (
                f'<tr><td style="padding:6px 10px;">{i}</td>'
                f'<td style="padding:6px 10px;">{_esc(item["query"])}</td>'
                f'<td style="padding:6px 10px;text-align:center;">{item["count"]}</td></tr>\n'
            )

        period_label = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}.get(
            period, period.capitalize()
        )

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chatbot Analytics Report - {period_label}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #f5f6fa; color: #333; line-height: 1.6; padding: 20px; }}
  .report {{ max-width: 900px; margin: 0 auto; }}
  .header {{ background: #1a3a5c; color: #fff; padding: 20px 30px; border-radius: 8px 8px 0 0; }}
  .header h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .header .meta {{ font-size: 0.85rem; color: #a8d0f0; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                  gap: 12px; padding: 20px; background: #fff; }}
  .stat-card {{ background: #f8f9fa; border-radius: 8px; padding: 16px; text-align: center; }}
  .stat-card .label {{ font-size: 0.8rem; color: #666; margin-bottom: 4px; }}
  .stat-card .value {{ font-size: 1.8rem; font-weight: 700; color: #1a3a5c; }}
  .section {{ background: #fff; padding: 20px; margin-top: 2px; }}
  .section h2 {{ font-size: 1.1rem; color: #1a3a5c; margin-bottom: 12px;
                  padding-bottom: 8px; border-bottom: 2px solid #e9ecef; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ background: #f8f9fa; text-align: left; padding: 8px 10px; border-bottom: 2px solid #dee2e6; color: #555; }}
  td {{ border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #f8f9fa; }}
  .footer {{ background: #f8f9fa; padding: 12px 20px; border-radius: 0 0 8px 8px;
             font-size: 0.8rem; color: #999; text-align: center; }}
</style>
</head>
<body>
<div class="report">
  <div class="header">
    <h1>Chatbot Analytics Report - {period_label}</h1>
    <div class="meta">Period: {start} ~ {end} | Generated: {generated}</div>
  </div>

  <div class="stats-grid">
    <div class="stat-card"><div class="label">Total Queries</div><div class="value">{total_q}</div></div>
    <div class="stat-card"><div class="label">Unique Sessions</div><div class="value">{sessions}</div></div>
    <div class="stat-card"><div class="label">Avg Queries/Session</div><div class="value">{avg_qps}</div></div>
    <div class="stat-card"><div class="label">Escalation Rate</div><div class="value">{esc_rate}%</div></div>
    <div class="stat-card"><div class="label">Matched Rate</div><div class="value">{matched_rate}%</div></div>
  </div>

  <div class="section">
    <h2>Category Distribution</h2>
    {cat_bars if cat_bars else '<div style="color:#999;">No data</div>'}
  </div>

  <div class="section">
    <h2>Top 10 Most Asked Questions</h2>
    <table>
      <thead><tr><th>#</th><th>Question</th><th>Count</th></tr></thead>
      <tbody>{top_rows if top_rows else '<tr><td colspan="3" style="padding:10px;color:#999;">No data</td></tr>'}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Escalation Analysis</h2>
    <p style="margin-bottom:10px;">Total escalations: {esc_count} ({esc_rate}%)</p>
    <table>
      <thead><tr><th>Category</th><th>Count</th></tr></thead>
      <tbody>{esc_rows if esc_rows else '<tr><td colspan="2" style="padding:10px;color:#999;">No escalations</td></tr>'}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Match Rate</h2>
    {match_display}
  </div>

  {sat_section}

  <div class="section">
    <h2>Peak Hours</h2>
    <p style="margin-bottom:8px;">Peak hour: {peak.get("peak_hour", 0)}:00 ({peak.get("peak_count", 0)} queries)</p>
    <div style="display:flex;gap:2px;align-items:flex-end;">
      {hour_bars}
    </div>
  </div>

  <div class="section">
    <h2>Unmatched Queries</h2>
    <table>
      <thead><tr><th>#</th><th>Query</th><th>Count</th></tr></thead>
      <tbody>{unmatched_rows if unmatched_rows else '<tr><td colspan="3" style="padding:10px;color:#999;">No unmatched queries</td></tr>'}</tbody>
    </table>
  </div>

  <div class="footer">Bonded Exhibition Chatbot Analytics Report</div>
</div>
</body>
</html>"""
        return html


def _esc(text):
    """HTML 이스케이프 처리."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

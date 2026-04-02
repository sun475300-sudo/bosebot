"""고급 대화 분석 및 패턴 탐지 모듈.

대화 로그와 피드백 데이터에서 반복 패턴, 이탈률, 해결률,
세션 지속 시간, 재방문율, 질문 난이도, 피크 시간대 등을 분석한다.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta


class PatternDetector:
    """대화 패턴을 탐지하는 클래스."""

    def __init__(self, logger_db):
        """ChatLogger 인스턴스를 받아 초기화한다.

        Args:
            logger_db: ChatLogger 인스턴스
        """
        self.logger_db = logger_db

    def find_common_sequences(self, min_length=2):
        """자주 등장하는 카테고리 시퀀스를 찾는다.

        연속된 질문의 카테고리 패턴(최소 min_length 길이)을 추출하여
        빈도 순으로 반환한다.

        Args:
            min_length: 최소 시퀀스 길이 (기본 2)

        Returns:
            list[dict]: sequence, count 쌍 목록 (빈도 내림차순)
        """
        conn = self.logger_db._get_conn()
        rows = conn.execute(
            """SELECT category FROM chat_logs
               ORDER BY id ASC"""
        ).fetchall()

        categories = [row["category"] or "UNKNOWN" for row in rows]

        if len(categories) < min_length:
            return []

        sequence_counter = Counter()
        for length in range(min_length, min(min_length + 3, len(categories) + 1)):
            for i in range(len(categories) - length + 1):
                seq = tuple(categories[i : i + length])
                sequence_counter[seq] += 1

        # 2회 이상 등장한 시퀀스만 반환
        results = [
            {"sequence": list(seq), "count": count}
            for seq, count in sequence_counter.most_common()
            if count >= 2
        ]
        return results

    def find_question_pairs(self):
        """자주 함께 등장하는 질문 카테고리 쌍을 찾는다.

        인접한 두 질문의 카테고리 쌍을 추출하여 빈도 순으로 반환한다.

        Returns:
            list[dict]: pair, count 쌍 목록 (빈도 내림차순)
        """
        conn = self.logger_db._get_conn()
        rows = conn.execute(
            """SELECT category FROM chat_logs
               ORDER BY id ASC"""
        ).fetchall()

        categories = [row["category"] or "UNKNOWN" for row in rows]

        if len(categories) < 2:
            return []

        pair_counter = Counter()
        for i in range(len(categories) - 1):
            pair = (categories[i], categories[i + 1])
            pair_counter[pair] += 1

        results = [
            {"pair": list(pair), "count": count}
            for pair, count in pair_counter.most_common()
            if count >= 1
        ]
        return results

    def detect_seasonality(self):
        """요일별/주별 패턴을 탐지한다.

        Returns:
            dict: weekday_distribution (요일별 질문 수),
                  weekly_trend (주차별 질문 수),
                  busiest_day (가장 바쁜 요일),
                  quietest_day (가장 한산한 요일)
        """
        conn = self.logger_db._get_conn()
        rows = conn.execute(
            """SELECT timestamp FROM chat_logs
               WHERE timestamp LIKE '____-__-__ __:__:__'"""
        ).fetchall()

        day_names = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]
        weekday_counts = {day: 0 for day in day_names}
        weekly_counts = defaultdict(int)

        for row in rows:
            try:
                dt = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                weekday_counts[day_names[dt.weekday()]] += 1
                week_key = dt.strftime("%Y-W%W")
                weekly_counts[week_key] += 1
            except (ValueError, IndexError):
                continue

        total = sum(weekday_counts.values())

        if total == 0:
            return {
                "weekday_distribution": weekday_counts,
                "weekly_trend": [],
                "busiest_day": None,
                "quietest_day": None,
            }

        busiest_day = max(weekday_counts, key=weekday_counts.get)
        quietest_day = min(weekday_counts, key=weekday_counts.get)

        weekly_trend = [
            {"week": week, "count": count}
            for week, count in sorted(weekly_counts.items())
        ]

        return {
            "weekday_distribution": weekday_counts,
            "weekly_trend": weekly_trend,
            "busiest_day": busiest_day,
            "quietest_day": quietest_day,
        }


class ConversationAnalytics:
    """고급 대화 분석 클래스."""

    def __init__(self, logger_db, feedback_db):
        """ChatLogger와 FeedbackManager 인스턴스를 받아 초기화한다.

        Args:
            logger_db: ChatLogger 인스턴스
            feedback_db: FeedbackManager 인스턴스
        """
        self.logger_db = logger_db
        self.feedback_db = feedback_db
        self.pattern_detector = PatternDetector(logger_db)

    def detect_patterns(self, days=30):
        """지정 기간 내 반복되는 질문 패턴을 탐지한다.

        Args:
            days: 분석 기간 (일 단위, 기본 30일)

        Returns:
            dict: recurring_queries (반복 질문), category_patterns (카테고리 패턴),
                  top_queries (상위 질문)
        """
        conn = self.logger_db._get_conn()
        start_date = (datetime.now() - timedelta(days=days)).strftime(
            "%Y-%m-%d"
        )

        # 반복 질문 탐지
        rows = conn.execute(
            """SELECT query, COUNT(*) as count, category
               FROM chat_logs
               WHERE timestamp >= ?
               GROUP BY query
               HAVING count >= 2
               ORDER BY count DESC
               LIMIT 20""",
            (start_date,),
        ).fetchall()

        recurring_queries = [
            {"query": row["query"], "count": row["count"],
             "category": row["category"] or "UNKNOWN"}
            for row in rows
        ]

        # 카테고리별 패턴
        cat_rows = conn.execute(
            """SELECT category, COUNT(*) as count
               FROM chat_logs
               WHERE timestamp >= ?
               GROUP BY category
               ORDER BY count DESC""",
            (start_date,),
        ).fetchall()

        category_patterns = [
            {"category": row["category"] or "UNKNOWN", "count": row["count"]}
            for row in cat_rows
        ]

        # 상위 질문
        top_rows = conn.execute(
            """SELECT query, COUNT(*) as count
               FROM chat_logs
               WHERE timestamp >= ?
               GROUP BY query
               ORDER BY count DESC
               LIMIT 10""",
            (start_date,),
        ).fetchall()

        top_queries = [
            {"query": row["query"], "count": row["count"]}
            for row in top_rows
        ]

        return {
            "days": days,
            "recurring_queries": recurring_queries,
            "category_patterns": category_patterns,
            "top_queries": top_queries,
        }

    def get_abandon_rate(self):
        """이탈률을 계산한다.

        타임스탬프 기준으로 30분 내 연속 질문을 하나의 세션으로 간주하고,
        질문이 1개뿐인 세션의 비율을 이탈률로 계산한다.

        Returns:
            dict: abandon_rate (%), total_sessions, abandoned_sessions
        """
        sessions = self._build_sessions()

        if not sessions:
            return {
                "abandon_rate": 0.0,
                "total_sessions": 0,
                "abandoned_sessions": 0,
            }

        abandoned = sum(1 for s in sessions if s["query_count"] == 1)
        total = len(sessions)

        return {
            "abandon_rate": round(abandoned / total * 100, 1),
            "total_sessions": total,
            "abandoned_sessions": abandoned,
        }

    def get_resolution_rate(self):
        """해결률을 계산한다.

        'helpful' 피드백으로 끝난 세션의 비율을 해결률로 계산한다.

        Returns:
            dict: resolution_rate (%), total_feedback, helpful_count
        """
        feedback_stats = self.feedback_db.get_feedback_stats()
        total = feedback_stats.get("total", 0)
        helpful = feedback_stats.get("helpful_count", 0)

        return {
            "resolution_rate": round(helpful / total * 100, 1) if total > 0 else 0.0,
            "total_feedback": total,
            "helpful_count": helpful,
        }

    def get_avg_session_duration(self):
        """평균 세션 지속 시간을 초 단위로 반환한다.

        타임스탬프 기반으로 세션을 구성하여 첫 질문부터 마지막 질문까지의
        시간 차이를 계산한다.

        Returns:
            dict: avg_duration_seconds, total_sessions, max_duration, min_duration
        """
        sessions = self._build_sessions()

        if not sessions:
            return {
                "avg_duration_seconds": 0.0,
                "total_sessions": 0,
                "max_duration": 0.0,
                "min_duration": 0.0,
            }

        durations = [s["duration_seconds"] for s in sessions]

        return {
            "avg_duration_seconds": round(sum(durations) / len(durations), 1),
            "total_sessions": len(sessions),
            "max_duration": round(max(durations), 1),
            "min_duration": round(min(durations), 1),
        }

    def get_repeat_visitor_rate(self):
        """재방문율을 계산한다.

        chat_logs에는 user_id가 없으므로, 동일 질문을 여러 번 한 사용자를
        기준으로 근사한다 (같은 쿼리 텍스트가 다른 날에 등장하면 재방문).

        Returns:
            dict: repeat_rate (%), total_unique_queries, repeat_queries
        """
        conn = self.logger_db._get_conn()

        rows = conn.execute(
            """SELECT query, COUNT(DISTINCT DATE(timestamp)) as day_count
               FROM chat_logs
               GROUP BY query"""
        ).fetchall()

        total_unique = len(rows)
        repeat_count = sum(1 for row in rows if row["day_count"] > 1)

        return {
            "repeat_rate": round(repeat_count / total_unique * 100, 1) if total_unique > 0 else 0.0,
            "total_unique_queries": total_unique,
            "repeat_queries": repeat_count,
        }

    def get_question_difficulty_ranking(self):
        """질문 난이도를 응답 품질 기준으로 순위를 매긴다.

        카테고리별로 FAQ 매칭률과 에스컬레이션 비율을 기반으로
        난이도를 계산한다 (매칭률이 낮고 에스컬레이션이 많으면 어려운 질문).

        Returns:
            list[dict]: category, difficulty_score, match_rate, escalation_rate
        """
        conn = self.logger_db._get_conn()

        rows = conn.execute(
            """SELECT
                 category,
                 COUNT(*) as total,
                 SUM(CASE WHEN faq_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
                 SUM(CASE WHEN is_escalation = 1 THEN 1 ELSE 0 END) as escalated
               FROM chat_logs
               GROUP BY category
               ORDER BY total DESC"""
        ).fetchall()

        rankings = []
        for row in rows:
            cat = row["category"] or "UNKNOWN"
            total = row["total"]
            match_rate = round(row["matched"] / total * 100, 1) if total > 0 else 0
            esc_rate = round(row["escalated"] / total * 100, 1) if total > 0 else 0

            # 난이도 점수: 매칭률이 낮을수록, 에스컬레이션이 높을수록 어렵다
            difficulty = round((100 - match_rate) * 0.7 + esc_rate * 0.3, 1)

            rankings.append({
                "category": cat,
                "difficulty_score": difficulty,
                "match_rate": match_rate,
                "escalation_rate": esc_rate,
                "total_queries": total,
            })

        rankings.sort(key=lambda x: x["difficulty_score"], reverse=True)
        return rankings

    def get_peak_usage_patterns(self):
        """피크 시간대를 요일별로 분석한다.

        Returns:
            dict: hourly (시간대별 질문 수), by_day_of_week (요일별 시간대별),
                  peak_hour, peak_day, heatmap
        """
        conn = self.logger_db._get_conn()

        rows = conn.execute(
            """SELECT timestamp FROM chat_logs
               WHERE timestamp LIKE '____-__-__ __:__:__'"""
        ).fetchall()

        day_names = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]

        hourly = {h: 0 for h in range(24)}
        by_day = {day: {h: 0 for h in range(24)} for day in day_names}
        day_totals = {day: 0 for day in day_names}

        for row in rows:
            try:
                dt = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                hour = dt.hour
                day_name = day_names[dt.weekday()]
                hourly[hour] += 1
                by_day[day_name][hour] += 1
                day_totals[day_name] += 1
            except (ValueError, IndexError):
                continue

        total = sum(hourly.values())
        peak_hour = max(range(24), key=lambda h: hourly[h]) if total > 0 else 0
        peak_day = max(day_names, key=lambda d: day_totals[d]) if total > 0 else day_names[0]

        # 히트맵 데이터 생성
        heatmap = []
        for day in day_names:
            for hour in range(24):
                heatmap.append({
                    "day": day,
                    "hour": hour,
                    "count": by_day[day][hour],
                })

        return {
            "hourly": hourly,
            "by_day_of_week": by_day,
            "peak_hour": peak_hour,
            "peak_day": peak_day,
            "day_totals": day_totals,
            "heatmap": heatmap,
        }

    def generate_insights(self, days=30):
        """데이터 기반 텍스트 인사이트를 자동 생성한다.

        Args:
            days: 분석 기간 (일 단위, 기본 30일)

        Returns:
            dict: insights (인사이트 텍스트 목록), generated_at, summary
        """
        insights = []

        # 이탈률 분석
        abandon = self.get_abandon_rate()
        if abandon["total_sessions"] > 0:
            rate = abandon["abandon_rate"]
            if rate > 50:
                insights.append(
                    f"High abandon rate ({rate}%): More than half of sessions "
                    f"end after a single query. Consider improving initial responses."
                )
            elif rate > 30:
                insights.append(
                    f"Moderate abandon rate ({rate}%): Consider adding "
                    f"follow-up suggestions to retain users."
                )
            else:
                insights.append(
                    f"Low abandon rate ({rate}%): Users are engaging "
                    f"well with the chatbot."
                )

        # 해결률 분석
        resolution = self.get_resolution_rate()
        if resolution["total_feedback"] > 0:
            rate = resolution["resolution_rate"]
            if rate >= 80:
                insights.append(
                    f"Excellent resolution rate ({rate}%): Users find "
                    f"responses helpful."
                )
            elif rate >= 50:
                insights.append(
                    f"Moderate resolution rate ({rate}%): There is room "
                    f"for improvement in response quality."
                )
            else:
                insights.append(
                    f"Low resolution rate ({rate}%): Response quality "
                    f"needs significant improvement."
                )

        # 난이도 분석
        difficulty = self.get_question_difficulty_ranking()
        hard_categories = [
            d for d in difficulty if d["difficulty_score"] > 50
        ]
        if hard_categories:
            cats = ", ".join(c["category"] for c in hard_categories[:3])
            insights.append(
                f"Difficult categories detected: {cats}. "
                f"Consider adding more FAQ entries for these topics."
            )

        # 패턴 분석
        patterns = self.detect_patterns(days=days)
        if patterns["recurring_queries"]:
            top = patterns["recurring_queries"][0]
            insights.append(
                f"Most recurring question: \"{top['query']}\" "
                f"(asked {top['count']} times). Ensure FAQ coverage."
            )

        # 피크 시간 분석
        peak = self.get_peak_usage_patterns()
        total_queries = sum(peak["hourly"].values())
        if total_queries > 0:
            insights.append(
                f"Peak usage at {peak['peak_hour']}:00 on {peak['peak_day']}. "
                f"Ensure adequate system capacity during these times."
            )

        summary = (
            f"Analysis covers {days} days with "
            f"{abandon.get('total_sessions', 0)} sessions detected."
        )

        return {
            "insights": insights,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "metrics": {
                "abandon_rate": abandon.get("abandon_rate", 0),
                "resolution_rate": resolution.get("resolution_rate", 0),
                "total_sessions": abandon.get("total_sessions", 0),
            },
        }

    def get_all_metrics(self):
        """모든 분석 지표를 한 번에 반환한다.

        Returns:
            dict: abandon, resolution, session_duration, repeat_visitor,
                  difficulty_ranking, peak_usage
        """
        return {
            "abandon": self.get_abandon_rate(),
            "resolution": self.get_resolution_rate(),
            "session_duration": self.get_avg_session_duration(),
            "repeat_visitor": self.get_repeat_visitor_rate(),
            "difficulty_ranking": self.get_question_difficulty_ranking(),
            "peak_usage": self.get_peak_usage_patterns(),
        }

    def _build_sessions(self, gap_minutes=30):
        """타임스탬프 기반으로 세션을 구성한다.

        gap_minutes 이내의 연속 질문은 같은 세션으로 분류한다.

        Args:
            gap_minutes: 세션 간격 기준 (분)

        Returns:
            list[dict]: session_start, session_end, query_count, duration_seconds
        """
        conn = self.logger_db._get_conn()
        rows = conn.execute(
            """SELECT timestamp FROM chat_logs
               WHERE timestamp LIKE '____-__-__ __:__:__'
               ORDER BY timestamp ASC"""
        ).fetchall()

        if not rows:
            return []

        timestamps = []
        for row in rows:
            try:
                dt = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                timestamps.append(dt)
            except ValueError:
                continue

        if not timestamps:
            return []

        gap = timedelta(minutes=gap_minutes)
        sessions = []
        session_start = timestamps[0]
        session_queries = 1

        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i - 1] > gap:
                # 새 세션 시작
                duration = (timestamps[i - 1] - session_start).total_seconds()
                sessions.append({
                    "session_start": session_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "session_end": timestamps[i - 1].strftime("%Y-%m-%d %H:%M:%S"),
                    "query_count": session_queries,
                    "duration_seconds": duration,
                })
                session_start = timestamps[i]
                session_queries = 1
            else:
                session_queries += 1

        # 마지막 세션
        duration = (timestamps[-1] - session_start).total_seconds()
        sessions.append({
            "session_start": session_start.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end": timestamps[-1].strftime("%Y-%m-%d %H:%M:%S"),
            "query_count": session_queries,
            "duration_seconds": duration,
        })

        return sessions

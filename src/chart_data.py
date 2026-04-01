"""대시보드 차트 데이터 생성 모듈.

Chart.js 호환 형식으로 카테고리 분포, 일별 트렌드, 시간대 히트맵 등
각종 시각화용 데이터를 생성한다.
"""

from datetime import datetime, timedelta


class ChartDataGenerator:
    """로그 DB와 피드백 DB를 기반으로 Chart.js 호환 차트 데이터를 생성하는 클래스."""

    def __init__(self, logger_db, feedback_db, sentiment_analyzer=None, user_segmenter=None):
        """초기화.

        Args:
            logger_db: ChatLogger 인스턴스
            feedback_db: FeedbackManager 인스턴스
            sentiment_analyzer: SentimentAnalyzer 인스턴스 (선택)
            user_segmenter: UserSegmenter 인스턴스 (선택)
        """
        self.logger_db = logger_db
        self.feedback_db = feedback_db
        self.sentiment_analyzer = sentiment_analyzer
        self.user_segmenter = user_segmenter

    def category_distribution(self):
        """카테고리별 질문 분포를 파이 차트 데이터로 반환한다.

        Returns:
            dict: Chart.js 호환 파이 차트 데이터
        """
        conn = self.logger_db._get_conn()
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM chat_logs GROUP BY category"
        ).fetchall()

        labels = []
        data = []
        total = sum(row["cnt"] for row in rows)
        for row in rows:
            cat = row["category"] or "UNKNOWN"
            labels.append(cat)
            data.append(row["cnt"])

        percentages = [
            round(d / total * 100, 1) if total > 0 else 0 for d in data
        ]

        return {
            "type": "pie",
            "title": "카테고리별 질문 분포",
            "labels": labels,
            "datasets": [
                {"label": "질문 수", "data": data},
                {"label": "비율(%)", "data": percentages},
            ],
        }

    def daily_query_trend(self, days=30):
        """일별 질문 수 추이를 라인 차트 데이터로 반환한다.

        Args:
            days: 조회 기간 (일)

        Returns:
            dict: Chart.js 호환 라인 차트 데이터
        """
        conn = self.logger_db._get_conn()
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """SELECT DATE(timestamp) as date, COUNT(*) as count
               FROM chat_logs
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp)
               ORDER BY date""",
            (start_date,),
        ).fetchall()

        date_counts = {row["date"]: row["count"] for row in rows}

        labels = []
        data = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            labels.append(d)
            data.append(date_counts.get(d, 0))

        return {
            "type": "line",
            "title": f"일별 질문 추이 (최근 {days}일)",
            "labels": labels,
            "datasets": [{"label": "질문 수", "data": data}],
        }

    def hourly_heatmap(self, days=7):
        """시간대 x 요일 히트맵 데이터를 반환한다.

        Args:
            days: 조회 기간 (일)

        Returns:
            dict: Chart.js 호환 히트맵 데이터
        """
        conn = self.logger_db._get_conn()
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """SELECT timestamp FROM chat_logs
               WHERE timestamp >= ?""",
            (start_date,),
        ).fetchall()

        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        # matrix[hour][weekday] = count
        matrix = [[0] * 7 for _ in range(24)]

        for row in rows:
            try:
                ts = row["timestamp"]
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                matrix[dt.hour][dt.weekday()] += 1
            except (ValueError, TypeError):
                continue

        # Flatten for chart data: list of {x: weekday, y: hour, v: count}
        data = []
        for hour in range(24):
            for wd in range(7):
                data.append({"x": weekday_names[wd], "y": hour, "v": matrix[hour][wd]})

        return {
            "type": "heatmap",
            "title": f"시간대별 질문 히트맵 (최근 {days}일)",
            "labels": weekday_names,
            "datasets": [{"label": "질문 수", "data": data}],
        }

    def response_time_histogram(self, bins=10):
        """응답 시간 히스토그램 데이터를 반환한다.

        chat_logs 테이블에 response_time 컬럼이 없으므로,
        타임스탬프 간격으로 추정하거나 빈 데이터를 반환한다.

        Args:
            bins: 히스토그램 구간 수

        Returns:
            dict: Chart.js 호환 바 차트 데이터
        """
        # chat_logs has no response_time column; return empty histogram structure
        bin_labels = [f"{i * 100}-{(i + 1) * 100}ms" for i in range(bins)]
        data = [0] * bins

        return {
            "type": "bar",
            "title": "응답 시간 분포",
            "labels": bin_labels,
            "datasets": [{"label": "응답 수", "data": data}],
        }

    def satisfaction_trend(self, days=30):
        """일별 만족도 추이를 라인 차트 데이터로 반환한다.

        Args:
            days: 조회 기간 (일)

        Returns:
            dict: Chart.js 호환 라인 차트 데이터
        """
        conn = self.feedback_db._get_conn()
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """SELECT DATE(timestamp) as date,
                      SUM(CASE WHEN rating = 'helpful' THEN 1 ELSE 0 END) as helpful,
                      COUNT(*) as total
               FROM feedback
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp)
               ORDER BY date""",
            (start_date,),
        ).fetchall()

        date_rates = {}
        for row in rows:
            total = row["total"]
            rate = round(row["helpful"] / total * 100, 1) if total > 0 else 0
            date_rates[row["date"]] = rate

        labels = []
        data = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            labels.append(d)
            data.append(date_rates.get(d, 0))

        return {
            "type": "line",
            "title": f"일별 만족도 추이 (최근 {days}일)",
            "labels": labels,
            "datasets": [{"label": "만족도(%)", "data": data}],
        }

    def top_queries(self, limit=20):
        """상위 질문을 바 차트 데이터로 반환한다.

        Args:
            limit: 상위 질문 수

        Returns:
            dict: Chart.js 호환 바 차트 데이터
        """
        conn = self.logger_db._get_conn()
        rows = conn.execute(
            """SELECT query, COUNT(*) as cnt
               FROM chat_logs
               GROUP BY query
               ORDER BY cnt DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        labels = [row["query"] for row in rows]
        data = [row["cnt"] for row in rows]

        return {
            "type": "bar",
            "title": f"상위 질문 TOP {limit}",
            "labels": labels,
            "datasets": [{"label": "질문 수", "data": data}],
        }

    def escalation_trend(self, days=30):
        """일별 에스컬레이션 추이를 라인 차트 데이터로 반환한다.

        Args:
            days: 조회 기간 (일)

        Returns:
            dict: Chart.js 호환 라인 차트 데이터
        """
        conn = self.logger_db._get_conn()
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """SELECT DATE(timestamp) as date,
                      SUM(CASE WHEN is_escalation = 1 THEN 1 ELSE 0 END) as escalations
               FROM chat_logs
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp)
               ORDER BY date""",
            (start_date,),
        ).fetchall()

        date_esc = {row["date"]: row["escalations"] for row in rows}

        labels = []
        data = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            labels.append(d)
            data.append(date_esc.get(d, 0))

        return {
            "type": "line",
            "title": f"에스컬레이션 추이 (최근 {days}일)",
            "labels": labels,
            "datasets": [{"label": "에스컬레이션 수", "data": data}],
        }

    def match_rate_trend(self, days=30):
        """일별 FAQ 매칭률 추이를 라인 차트 데이터로 반환한다.

        Args:
            days: 조회 기간 (일)

        Returns:
            dict: Chart.js 호환 라인 차트 데이터
        """
        conn = self.logger_db._get_conn()
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """SELECT DATE(timestamp) as date,
                      SUM(CASE WHEN faq_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
                      COUNT(*) as total
               FROM chat_logs
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp)
               ORDER BY date""",
            (start_date,),
        ).fetchall()

        date_rates = {}
        for row in rows:
            total = row["total"]
            rate = round(row["matched"] / total * 100, 1) if total > 0 else 0
            date_rates[row["date"]] = rate

        labels = []
        data = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            labels.append(d)
            data.append(date_rates.get(d, 0))

        return {
            "type": "line",
            "title": f"FAQ 매칭률 추이 (최근 {days}일)",
            "labels": labels,
            "datasets": [{"label": "매칭률(%)", "data": data}],
        }

    def user_segment_distribution(self):
        """사용자 세그먼트 분포를 파이 차트 데이터로 반환한다.

        Returns:
            dict: Chart.js 호환 파이 차트 데이터
        """
        if self.user_segmenter is None:
            return {
                "type": "pie",
                "title": "사용자 세그먼트 분포",
                "labels": [],
                "datasets": [{"label": "사용자 수", "data": []}],
            }

        stats = self.user_segmenter.get_segment_stats()
        segment_counts = stats.get("segment_counts", {})

        labels = list(segment_counts.keys())
        data = list(segment_counts.values())

        return {
            "type": "pie",
            "title": "사용자 세그먼트 분포",
            "labels": labels,
            "datasets": [{"label": "사용자 수", "data": data}],
        }

    def sentiment_distribution(self):
        """감정 분포를 파이 차트 데이터로 반환한다.

        Returns:
            dict: Chart.js 호환 파이 차트 데이터
        """
        if self.sentiment_analyzer is None:
            return {
                "type": "pie",
                "title": "감정 분포",
                "labels": [],
                "datasets": [{"label": "질문 수", "data": []}],
            }

        stats = self.sentiment_analyzer.get_sentiment_stats()
        distribution = stats.get("distribution", {})

        labels = list(distribution.keys())
        data = list(distribution.values())

        return {
            "type": "pie",
            "title": "감정 분포",
            "labels": labels,
            "datasets": [{"label": "질문 수", "data": data}],
        }

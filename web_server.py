"""ë³´ì„¸?„ì‹œ??ë¯¼ì›?‘ë? ì±—ë´‡ ???œë²„.

Flask ê¸°ë°˜ REST API + ??UIë¥??œê³µ?œë‹¤.

?¬ìš©ë²?
    python web_server.py              # ê¸°ë³¸ ?¬íŠ¸ 5000
    python web_server.py --port 8080  # ?¬íŠ¸ ì§€??
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from datetime import datetime
from collections import defaultdict
from functools import wraps
import json as json_module

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, Response, request, jsonify, send_from_directory, make_response
from src.chatbot import BondedExhibitionChatbot
from src.metrics import metrics as metrics_collector
from src.classifier import classify_query
from src.conversation_export import ConversationExporter
from src.conversation_summary import ConversationSummarizer
from src.escalation import check_escalation, get_escalation_contact
from src.analytics import QueryAnalytics
from src.auto_faq_pipeline import AutoFAQPipeline
from src.faq_quality_checker import FAQQualityChecker
from src.faq_recommender import FAQRecommender
from src.feedback import FeedbackManager
from src.kakao_adapter import (
    build_skill_response,
    format_carousel,
    format_escalation_card,
    format_quick_replies,
    format_simple_text,
    init_kakao_routes,
    parse_kakao_request,
)
from src.naver_adapter import NaverTalkTalkAdapter, EVENT_SEND, EVENT_OPEN
from src.logger_db import ChatLogger
from src.report_generator import ReportGenerator
from src.realtime_monitor import RealtimeMonitor
from src.satisfaction_tracker import SatisfactionTracker
from src.security import APIKeyAuth, RateLimiter, sanitize_input
from src.rate_limiter_v2 import AdvancedRateLimiter
from src.translator import SimpleTranslator
from src.auth import JWTAuth, authenticate_user
from src.law_updater import LawUpdateScheduler, LawVersionTracker, FAQUpdateNotifier
from src.backup_manager import BackupManager
from src.faq_manager import FAQManager
from src.faq_io import FAQImporter, FAQExporter
from src.faq_diff import FAQDiffEngine
from src.tenant_manager import TenantManager
from src.webhook_manager import WebhookManager
from src.audit_logger import AuditLogger
from src.alert_center import AlertCenter, AlertRuleEngine
from src.profiler import Profiler, RequestProfiler, ComponentBenchmark
from src.health_monitor import HealthMonitor
from src.i18n import I18nManager
from src.db_migration import MigrationManager
from src.ab_testing import ABTestManager
from src.user_recommender import UserRecommender
from src.flow_analyzer import FlowAnalyzer
from src.sentiment_analyzer import SentimentAnalyzer
from src.question_cluster import QuestionClusterer, DuplicateDetector
from src.task_scheduler import TaskScheduler, create_default_scheduler
from src.knowledge_graph import KnowledgeGraph
from src.template_engine import TemplateEngine, ResponseFormatter
from src.context_memory import ContextMemory, ConversationMemoryManager
from src.user_segment import UserSegmenter
from src.domain_config import DomainConfig, DomainInitializer
from src.utils import load_json
from src.api_gateway import APIGateway, PaginationHelper, SortHelper
from src.quality_scorer import ResponseQualityScorer, QualityReport
from src.conversation_analytics import ConversationAnalytics
from src.error_recovery import ErrorRecovery, CircuitBreakerOpenError
from src.smart_suggestions import SmartSuggestionEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_QUERY_LENGTH = 500  # Production: reduced from 2000 to 500 chars for better security
APP_VERSION = "4.0.0"

# logs ?”ë ‰? ë¦¬ ?ë™ ?ì„±
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "web"), static_url_path="/static")

# Production configuration
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("chatbot")

# Production request logging setup
_request_log_handler = logging.FileHandler(os.path.join(BASE_DIR, "logs", "requests.log"))
_request_log_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
_request_logger = logging.getLogger("requests")
_request_logger.addHandler(_request_log_handler)
_request_logger.setLevel(logging.INFO)

chatbot = BondedExhibitionChatbot()
chat_logger = ChatLogger(db_path=os.path.join(BASE_DIR, "logs", "chat_logs.db"))
feedback_manager = FeedbackManager(db_path=os.path.join(BASE_DIR, "logs", "feedback.db"))
translator = SimpleTranslator()
i18n_manager = I18nManager()
faq_recommender = FAQRecommender(chat_logger)
query_analytics = QueryAnalytics(chat_logger, feedback_manager)
conversation_analytics = ConversationAnalytics(chat_logger, feedback_manager)
report_generator = ReportGenerator(chat_logger, feedback_manager)
auto_faq_pipeline = AutoFAQPipeline(
    faq_recommender, faq_path=os.path.join(BASE_DIR, "data", "faq.json")
)

# ë³´ì•ˆ ë¯¸ë“¤?¨ì–´ ì´ˆê¸°??
api_key_auth = APIKeyAuth(app)
rate_limit_value = int(os.environ.get("CHATBOT_RATE_LIMIT", "60"))
rate_limiter = RateLimiter(max_requests=rate_limit_value)
advanced_rate_limiter = AdvancedRateLimiter()

# Phase 13-18 ëª¨ë“ˆ ì´ˆê¸°??
realtime_monitor = RealtimeMonitor()
conversation_exporter = ConversationExporter()
conversation_summarizer = ConversationSummarizer(chatbot.session_manager)
legal_refs = load_json("data/legal_references.json")
faq_quality_checker = FAQQualityChecker(chatbot.faq_items, legal_refs)
satisfaction_tracker = SatisfactionTracker()

# ?‘ë‹µ ?ˆì§ˆ ?¤ì½”?´ëŸ¬ ì´ˆê¸°??
quality_scorer = ResponseQualityScorer(chat_logger)
quality_report = QualityReport(quality_scorer)

# JWT ?¸ì¦ ì´ˆê¸°??
jwt_auth = JWTAuth()

# ë²•ë ¹ ?…ë°?´íŠ¸ ëª¨ë“ˆ ì´ˆê¸°??
law_version_tracker = LawVersionTracker()
faq_update_notifier = FAQUpdateNotifier()
law_update_scheduler = LawUpdateScheduler(law_version_tracker, faq_update_notifier)

# ë°±ì—… ê´€ë¦¬ì ì´ˆê¸°??
backup_manager = BackupManager()

# ?¹í›… ê´€ë¦¬ì ì´ˆê¸°??
webhook_manager = WebhookManager()

# ë©€???Œë„Œ??ê´€ë¦¬ì ì´ˆê¸°??
tenant_manager = TenantManager()

# FAQ ê´€ë¦¬ì ì´ˆê¸°??
faq_manager = FAQManager()
faq_importer = FAQImporter(faq_manager)
faq_exporter = FAQExporter(faq_manager)
faq_diff_engine = FAQDiffEngine(faq_manager)

# ê°ì‚¬ ë¡œê±° ì´ˆê¸°??
audit_logger = AuditLogger()

# ?Œë¦¼ ?¼í„° ì´ˆê¸°??
alert_center = AlertCenter()
alert_rule_engine = AlertRuleEngine(
    alert_center,
    realtime_monitor=realtime_monitor,
    satisfaction_tracker=satisfaction_tracker,
    faq_quality_checker=faq_quality_checker,
)

# ?„ë¡œ?Œì¼??ì´ˆê¸°??
request_profiler = RequestProfiler()
component_benchmark = ComponentBenchmark()

# ë§ˆì´ê·¸ë ˆ?´ì…˜ ê´€ë¦¬ì ì´ˆê¸°??
migration_manager = MigrationManager()

# ?¬ìŠ¤ ëª¨ë‹ˆ??ì´ˆê¸°??
health_monitor = HealthMonitor(
    base_dir=BASE_DIR,
    faq_items=chatbot.faq_items,
    chat_logger=chat_logger,
)

# A/B ?ŒìŠ¤??ê´€ë¦¬ì ì´ˆê¸°??
ab_test_manager = ABTestManager()

# ?€???ë¦„ ë¶„ì„ê¸?ì´ˆê¸°??
flow_analyzer = FlowAnalyzer(db_path=os.path.join(BASE_DIR, "logs", "flow_analysis.db"))

# ?¬ìš©??ì¶”ì²œ ?œìŠ¤??ì´ˆê¸°??
user_recommender = UserRecommender(
    db_path=os.path.join(BASE_DIR, "data", "user_profiles.db")
)

# ê°ì • ë¶„ì„ê¸?ì´ˆê¸°??
sentiment_analyzer = SentimentAnalyzer(
    db_path=os.path.join(BASE_DIR, "data", "sentiment.db")
)

# ì§ˆë¬¸ ?´ëŸ¬?¤í„°ë§?ì´ˆê¸°??
question_clusterer = QuestionClusterer(chatbot.faq_items)
duplicate_detector = DuplicateDetector(chatbot.faq_items)

# ?‘ì—… ?¤ì?ì¤„ëŸ¬ ì´ˆê¸°??
task_scheduler = create_default_scheduler()

# ?œí”Œë¦??”ì§„ ì´ˆê¸°??
template_engine = TemplateEngine()
response_formatter = ResponseFormatter(template_engine)

# ì§€??ê·¸ë˜??ì´ˆê¸°??
knowledge_graph = KnowledgeGraph.build_from_faq(chatbot.faq_items)

# ?¤ë§ˆ???œì•ˆ ?”ì§„ ì´ˆê¸°??
smart_suggestion_engine = SmartSuggestionEngine(
    faq_items=chatbot.faq_items,
    knowledge_graph=knowledge_graph,
    question_clusterer=question_clusterer,
    related_faq_finder=chatbot.related_faq_finder,
)

# ì»¨í…?¤íŠ¸ ë©”ëª¨ë¦?ì´ˆê¸°??
context_memory = ContextMemory(db_path=os.path.join(BASE_DIR, "data", "memory.db"))
conversation_memory_manager = ConversationMemoryManager(context_memory)

# ?¬ìš©???¸ë¶„??ì´ˆê¸°??
user_segmenter = UserSegmenter(db_path=os.path.join(BASE_DIR, "data", "segments.db"))

# ?„ë©”???¤ì • ì´ˆê¸°??
domain_initializer = DomainInitializer()
_domain_config = DomainConfig()

# API ê²Œì´?¸ì›¨??ì´ˆê¸°??
api_gateway = APIGateway()
api_gateway.register_version("v1", status="active")
api_gateway.register_version("v2", status="active")
pagination_helper = PaginationHelper()
sort_helper = SortHelper()

# ?ëŸ¬ ë³µêµ¬ ?œìŠ¤??ì´ˆê¸°??
error_recovery = ErrorRecovery(db_path=os.path.join(BASE_DIR, "logs", "error_logs.db"))

# --- Production: Simple in-memory rate limiter (60 requests/min per IP) ---
class ProductionRateLimiter:
    """Simple in-memory rate limiter for production."""
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)  # IP -> list of timestamps

    def is_allowed(self, client_ip):
        """Check if request is allowed for the client IP."""
        now = time.time()
        # Clean old requests
        self.requests[client_ip] = [ts for ts in self.requests[client_ip]
                                   if now - ts < self.window_seconds]

        if len(self.requests[client_ip]) < self.max_requests:
            self.requests[client_ip].append(now)
            return True
        return False

    def get_stats(self, client_ip):
        """Get current request stats for IP."""
        now = time.time()
        self.requests[client_ip] = [ts for ts in self.requests[client_ip]
                                   if now - ts < self.window_seconds]
        return {
            'requests': len(self.requests[client_ip]),
            'limit': self.max_requests,
            'window': self.window_seconds
        }

_production_rate_limiter = ProductionRateLimiter(
    max_requests=int(os.environ.get("PRODUCTION_RATE_LIMIT", "60")),
    window_seconds=60
)

# --- Request usage statistics ---
_usage_stats = {
    'total_queries': 0,
    'start_time': time.time(),
    'errors': defaultdict(int),
}

# --- FAQ in-memory cache ---
_faq_cache: dict = {}


def _refresh_faq_cache():
    """Load FAQ data into memory and pre-build TF-IDF index."""
    _faq_cache["items"] = list(chatbot.faq_items)
    _faq_cache["tfidf_matcher"] = chatbot.tfidf_matcher


_refresh_faq_cache()


def _get_audit_actor():
    """Extract actor username from JWT payload or return default."""
    payload = getattr(request, "jwt_payload", None)
    if payload:
        return payload.get("sub", "unknown")
    return "admin"


def _get_client_ip():
    """Extract client IP from request."""
    return request.remote_addr or "unknown"


# --- Production: CORS Configuration ---
def _get_cors_origins():
    """Get allowed CORS origins from environment variable."""
    default_origins = ["http://localhost:5000", "http://localhost:8080", "http://localhost:3000"]
    cors_origins = os.environ.get("CHATBOT_CORS_ORIGINS", ",".join(default_origins))
    return [origin.strip() for origin in cors_origins.split(",")]

_CORS_ORIGINS = _get_cors_origins()

@app.before_request
def _add_cors_headers():
    """Add CORS headers to request."""
    if request.method == 'OPTIONS':
        response = make_response()
        origin = request.headers.get('Origin')
        if origin in _CORS_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Tenant-Id'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 200

@app.after_request
def _apply_cors_headers(response):
    """Apply CORS headers to response."""
    origin = request.headers.get('Origin')
    if origin in _CORS_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

# --- Production: Request logging middleware ---
@app.before_request
def _log_request_start():
    """Log request start with timestamp."""
    request._start_time = time.time()
    client_ip = _get_client_ip()
    _request_logger.info(f"[START] {request.method} {request.path} from {client_ip}")

@app.after_request
def _log_request_end(response):
    """Log request completion with response time."""
    if hasattr(request, '_start_time'):
        elapsed = time.time() - request._start_time
        status_code = response.status_code
        client_ip = _get_client_ip()
        _request_logger.info(
            f"[END] {request.method} {request.path} "
            f"status={status_code} time={elapsed:.3f}s from {client_ip}"
        )
    return response

# --- Advanced rate limiting middleware ---
_RATE_LIMIT_EXEMPT_PATHS = {"/", "/api/health", "/static", "/manifest.json", "/sw.js"}


@app.before_request
def _check_advanced_rate_limit():
    """Apply per-endpoint rate limits via AdvancedRateLimiter."""
    if app.config.get("TESTING") and not app.config.get("RATE_LIMIT_TESTING"):
        return None
    path = request.path
    # Skip static / health endpoints
    for exempt in _RATE_LIMIT_EXEMPT_PATHS:
        if path == exempt or path.startswith(exempt + "/"):
            return None

    client_ip = request.remote_addr or "unknown"
    allowed, remaining, reset_time = advanced_rate_limiter.check_rate_limit(
        client_ip, path
    )
    # Store for after_request header injection
    request._rl_remaining = remaining
    request._rl_reset = reset_time

    if not allowed:
        retry_after = max(1, reset_time - int(time.time()))
        response = jsonify({
            "error": "?”ì²­???ˆë¬´ ë§ìŠµ?ˆë‹¤. ? ì‹œ ???¤ì‹œ ?œë„??ì£¼ì„¸??"
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response

    return None


@app.after_request
def _add_rate_limit_headers(response):
    """Inject X-RateLimit-* headers on every response."""
    remaining = getattr(request, "_rl_remaining", None)
    reset_time = getattr(request, "_rl_reset", None)
    if remaining is not None and remaining >= 0:
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    if reset_time:
        response.headers["X-RateLimit-Reset"] = str(reset_time)
    return response


# --- Response time middleware ---
@app.before_request
def _record_start_time():
    request._start_time = time.monotonic()


@app.after_request
def _add_response_time_header(response):
    start = getattr(request, "_start_time", None)
    if start is not None:
        elapsed_ms = (time.monotonic() - start) * 1000
        elapsed_s = elapsed_ms / 1000.0
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        if elapsed_ms > 500:
            logger.warning(
                f"Slow request: {request.method} {request.path} took {elapsed_ms:.1f}ms"
            )
        # --- Prometheus metrics instrumentation ---
        endpoint = request.path
        method = request.method
        status = str(response.status_code)
        metrics_collector.increment(
            "request_count",
            {"endpoint": endpoint, "method": method, "status": status},
        )
        metrics_collector.observe(
            "request_duration_seconds",
            elapsed_s,
            {"endpoint": endpoint},
        )
        # Update gauges
        try:
            metrics_collector.set_gauge("active_sessions", chatbot.session_manager.active_count())
            metrics_collector.set_gauge("faq_count", len(chatbot.faq_items))
        except (AttributeError, TypeError) as e:
            logger.debug(f"Metrics gauge update skipped: {e}")
    return response


# --- Static asset caching ---
@app.after_request
def _add_cache_headers(response):
    """Add Cache-Control and ETag headers for static files."""
    if request.path.startswith("/static/") or request.path in (
        "/manifest.json",
        "/sw.js",
    ):
        # Determine cache duration by file extension
        path_lower = request.path.lower()
        if path_lower.endswith(".html"):
            max_age = 3600  # 1 hour
        elif path_lower.endswith((".css", ".js", ".svg")):
            max_age = 604800  # 1 week
        else:
            max_age = 3600  # default 1 hour

        response.headers["Cache-Control"] = f"public, max-age={max_age}"

        # ETag support based on response data
        if response.data:
            etag = hashlib.md5(response.data).hexdigest()
            response.headers["ETag"] = f'"{etag}"'

            # Handle If-None-Match
            if_none_match = request.headers.get("If-None-Match")
            if if_none_match and if_none_match.strip('"') == etag:
                response.status_code = 304
                response.data = b""

    return response


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "?˜ëª»???”ì²­?…ë‹ˆ??"}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "?”ì²­??ë¦¬ì†Œ?¤ë? ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"?´ë? ?œë²„ ?¤ë¥˜: {e}")
    return jsonify({"error": "?´ë? ?œë²„ ?¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/")
def index():
    """??ì±—ë´‡ UI ?˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "index.html")


@app.route("/docs")
@app.route("/swagger")
def swagger_ui():
    """Swagger UI ?˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "swagger.html")


@app.route("/api/openapi.yaml")
def openapi_spec():
    """OpenAPI ëª…ì„¸ ?Œì¼??ë°˜í™˜?œë‹¤."""
    return send_from_directory(
        os.path.join(BASE_DIR, "docs"), "openapi.yaml", mimetype="text/yaml"
    )


@app.route("/manifest.json")
def manifest():
    """PWA ë§¤ë‹ˆ?˜ìŠ¤???Œì¼??ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "manifest.json")


@app.route("/sw.js")
def service_worker():
    """Service Worker ?Œì¼??ë°˜í™˜?œë‹¤."""
    response = send_from_directory(os.path.join(BASE_DIR, "web"), "sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/api/chat", methods=["POST"])
def chat():
    """Production chat endpoint with comprehensive error handling."""
    try:
        # Production: Simple rate limiting per IP (60 req/min)
        client_ip = request.remote_addr or "unknown"
        if not app.config.get("TESTING") and not os.environ.get("TESTING"):
            if not _production_rate_limiter.is_allowed(client_ip):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return jsonify({
                    "error": "?”ì²­???ˆë¬´ ë§ìŠµ?ˆë‹¤. ? ì‹œ ???¤ì‹œ ?œë„??ì£¼ì„¸??",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }), 429

        # Validate request JSON
        data = request.get_json(silent=True)
        if not data:
            logger.warning(f"Invalid JSON from {client_ip}")
            return jsonify({
                "error": "?”ì²­ ?•ì‹???¬ë°”ë¥´ì? ?ŠìŠµ?ˆë‹¤.",
                "error_code": "INVALID_JSON"
            }), 400

        if "query" not in data:
            return jsonify({
                "error": "query ?„ë“œê°€ ?„ìš”?©ë‹ˆ??",
                "error_code": "MISSING_FIELD"
            }), 400

        raw_query = data["query"]
        if not isinstance(raw_query, str):
            return jsonify({
                "error": "query??ë¬¸ì?´ì´?´ì•¼ ?©ë‹ˆ??",
                "error_code": "INVALID_TYPE"
            }), 400

        # Production: Input validation (max 500 chars)
        if len(raw_query) > MAX_QUERY_LENGTH:
            return jsonify({
                "error": f"ì§ˆë¬¸?€ {MAX_QUERY_LENGTH}???´ë‚´ë¡??…ë ¥??ì£¼ì„¸??",
                "error_code": "QUERY_TOO_LONG",
                "max_length": MAX_QUERY_LENGTH
            }), 400

        if not raw_query.strip():
            return jsonify({
                "error": "ì§ˆë¬¸???…ë ¥??ì£¼ì„¸??",
                "error_code": "EMPTY_QUERY"
            }), 400

        # ?…ë ¥ ?´ê·  ?ìš©
        query = sanitize_input(raw_query, max_length=MAX_QUERY_LENGTH)

        # ë©€???Œë„Œ??ì§€?? X-Tenant-Id ?¤ë” (? íƒ, ê¸°ë³¸ê°?"default")
        tenant_id = request.headers.get("X-Tenant-Id", "default")
        tenant = tenant_manager.get_tenant(tenant_id)
        if tenant is None:
            return jsonify({
                "error": f"?Œë„Œ??'{tenant_id}'ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.",
                "error_code": "TENANT_NOT_FOUND"
            }), 404
        if not tenant.get("active", True):
            return jsonify({
                "error": f"?Œë„Œ??'{tenant_id}'ê°€ ë¹„í™œ???íƒœ?…ë‹ˆ??",
                "error_code": "TENANT_INACTIVE"
            }), 403

        categories = classify_query(query)
        escalation = check_escalation(query)
        # ?¸ì…˜ ID ì²˜ë¦¬ (? íƒ??
        session_id = data.get("session_id")

        # ê°ì • ë¶„ì„
        sentiment_result = sentiment_analyzer.analyze_and_store(query, session_id=session_id)

        answer = chatbot.process_query(query, session_id=session_id)

        # ê°ì •???°ë¥¸ ?µë? ??ì¡°ì ˆ
        answer = sentiment_analyzer.adjust_response_tone(answer, sentiment_result)

        # ë§¤ìš° ë¶€?•ì  ê°ì • ???ë™ ?ìŠ¤ì»¬ë ˆ?´ì…˜
        sentiment_escalation = sentiment_analyzer.should_escalate(sentiment_result)
        if sentiment_escalation and escalation is None:
            escalation = {"target": "customer_support", "reason": "negative_sentiment"}

        logger.info(f"ì§ˆë¬¸: {query[:50]}... | ë¶„ë¥˜: {categories[0]} | ?ìŠ¤ì»¬ë ˆ?´ì…˜: {escalation is not None}")

        primary_category = categories[0] if categories else "GENERAL"
        is_escalation = escalation is not None

        # FAQ ë§¤ì¹­ ê²°ê³¼?ì„œ faq_id ì¶”ì¶œ
        faq_match = chatbot.find_matching_faq(query, primary_category)
        faq_id = faq_match.get("id") if faq_match else None

        # ë¡œê·¸ ?€??+ ëª¨ë‹ˆ?°ë§ ?´ë²¤??
        try:
            chat_logger.log_query(
                query=query,
                category=primary_category,
                faq_id=faq_id,
                is_escalation=is_escalation,
                response_preview=answer,
            )
            event_type = "escalation" if is_escalation else ("query" if faq_match else "unmatched")
            realtime_monitor.record_event(event_type, {"query": query, "category": primary_category})
            # ?¬ìš©??ì¶”ì²œ ?œìŠ¤?œì— ì§ˆë¬¸ ê¸°ë¡
            if session_id:
                user_recommender.record_query(session_id, query, primary_category, faq_id)
        except Exception as e:
            logger.error(f"ë¡œê·¸ ?€???¤íŒ¨: {e}")

        # ?¬ìš©???¸ë¶„??ë¶„ë¥˜ ë°??µë? ê¹Šì´ ì¡°ì ˆ
        user_segment = None
        if session_id:
            try:
                user_segment = user_segmenter.classify_user(session_id, query)
                answer = user_segmenter.adjust_response_depth(answer, user_segment)
            except Exception as e:
                logger.error(f"?¬ìš©???¸ë¶„???¤íŒ¨: {e}")

        # ?¤êµ­??ì§€?? lang ?Œë¼ë¯¸í„°???°ë¼ ?µë? ?¤ë” ë²ˆì—­
        lang = data.get("lang", "ko")
        if lang and lang != "ko" and translator.is_supported(lang):
            translated_answer = translator.translate_response(answer, lang)
        else:
            translated_answer = answer
            lang = "ko"

        # ê´€??ì§ˆë¬¸ ì¶”ì²œ
        related = []
        if faq_id:
            try:
                related = chatbot.related_faq_finder.find_related(faq_id, top_k=3)
            except (AttributeError, KeyError, ValueError) as e:
                logger.debug(f"Related FAQ lookup skipped: {e}")

        # ?¤ë§ˆ???œì•ˆ ?ì„±
        suggestions = []
        try:
            session_history = []
            if session_id:
                ctx = chatbot.session_manager.get_context(session_id) if hasattr(chatbot.session_manager, "get_context") else {}
                session_history = ctx.get("queries", []) if isinstance(ctx, dict) else []
            suggestions = smart_suggestion_engine.get_follow_up_suggestions(
                query, translated_answer, primary_category, session_history=session_history,
            )
        except Exception as e:
            logger.error(f"?¤ë§ˆ???œì•ˆ ?ì„± ?¤íŒ¨: {e}")

        response = {
            "answer": translated_answer,
            "category": primary_category,
            "categories": categories,
            "is_escalation": is_escalation,
            "escalation_target": escalation.get("target") if escalation else None,
            "lang": lang,
            "related_questions": [{"id": r["id"], "question": r["question"]} for r in related],
            "suggestions": suggestions,
            "tenant_id": tenant_id,
            "sentiment": sentiment_result,
            "user_segment": user_segment,
        }

        if session_id:
            response["session_id"] = session_id
            # ê°œì¸??ì¶”ì²œ ì¶”ê?
            try:
                recommended = user_recommender.get_recommendations(session_id, top_n=3)
                response["recommended"] = recommended
            except Exception:
                response["recommended"] = []

            # ì»¨í…?¤íŠ¸ ë©”ëª¨ë¦? ? í”½ ?€??ë°??¬ë°©ë¬??¬ìš©??resume ?œê³µ
            try:
                conversation_memory_manager.remember_topic(session_id, query, primary_category)
                resume = conversation_memory_manager.get_conversation_resume(session_id)
                if resume and conversation_memory_manager.is_returning_user(session_id):
                    response["conversation_resume"] = resume
            except Exception as e:
                logger.error(f"ì»¨í…?¤íŠ¸ ë©”ëª¨ë¦??€???¤íŒ¨: {e}")

        _usage_stats['total_queries'] += 1
        return jsonify(response)

    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        _usage_stats['errors']['processing'] = _usage_stats['errors'].get('processing', 0) + 1
        return jsonify({
            "error": "?µë? ì²˜ë¦¬ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤.",
            "error_code": "PROCESSING_ERROR"
        }), 500


@app.route("/api/recommendations", methods=["GET"])
def api_recommendations():
    """ê°œì¸??FAQ ì¶”ì²œ??ë°˜í™˜?œë‹¤."""
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??"}), 400
    try:
        recommendations = user_recommender.get_recommendations(session_id)
        return jsonify({"session_id": session_id, "recommendations": recommendations})
    except Exception as e:
        logger.error(f"ì¶”ì²œ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ì¶”ì²œ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/popular", methods=["GET"])
def api_popular():
    """?„ì²´ ?¸ê¸° FAQë¥?ë°˜í™˜?œë‹¤."""
    try:
        limit = request.args.get("limit", 10, type=int)
        popular = user_recommender.get_popular_faqs(limit=limit)
        return jsonify({"popular": popular})
    except Exception as e:
        logger.error(f"?¸ê¸° FAQ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¸ê¸° FAQ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/trending", methods=["GET"])
def api_trending():
    """?¸ë Œ??? í”½??ë°˜í™˜?œë‹¤."""
    try:
        hours = request.args.get("hours", 24, type=int)
        limit = request.args.get("limit", 5, type=int)
        trending = user_recommender.get_trending_topics(hours=hours, limit=limit)
        return jsonify({"trending": trending})
    except Exception as e:
        logger.error(f"?¸ë Œ??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¸ë Œ??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/session/new", methods=["POST"])
def session_new():
    """???¸ì…˜???ì„±?œë‹¤."""
    session = chatbot.session_manager.create_session()
    return jsonify({
        "session_id": session.session_id,
        "created_at": session.created_at,
    }), 201


@app.route("/api/session/<session_id>", methods=["GET"])
def session_status(session_id):
    """?¸ì…˜ ?íƒœë¥?ì¡°íšŒ?œë‹¤."""
    session = chatbot.session_manager.get_session(session_id)
    if session is None:
        return jsonify({"error": "?¸ì…˜??ì°¾ì„ ???†ê±°??ë§Œë£Œ?˜ì—ˆ?µë‹ˆ??"}), 404
    return jsonify(session.to_dict())


@app.route("/api/session/<session_id>/context", methods=["GET"])
def session_context(session_id):
    """?¸ì…˜??ì»¨í…?¤íŠ¸ ë©”ëª¨ë¦¬ë? ì¡°íšŒ?œë‹¤."""
    key = request.args.get("key")
    try:
        entries = context_memory.get_context(session_id, key=key)
        return jsonify({"session_id": session_id, "context": entries})
    except Exception as e:
        logger.error(f"ì»¨í…?¤íŠ¸ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ì»¨í…?¤íŠ¸ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/session/<session_id>/profile", methods=["GET"])
def session_profile(session_id):
    """?¸ì…˜???¬ìš©???„ë¡œ?„ì„ ì¡°íšŒ?œë‹¤."""
    try:
        profile = context_memory.get_user_profile(session_id)
        return jsonify(profile)
    except Exception as e:
        logger.error(f"?„ë¡œ??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?„ë¡œ??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/session/<session_id>/context", methods=["DELETE"])
def session_context_delete(session_id):
    """?¸ì…˜??ì»¨í…?¤íŠ¸ë¥??? œ?œë‹¤."""
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    try:
        deleted = context_memory.forget(session_id, key=key)
        return jsonify({"session_id": session_id, "deleted": deleted})
    except Exception as e:
        logger.error(f"ì»¨í…?¤íŠ¸ ?? œ ?¤íŒ¨: {e}")
        return jsonify({"error": "ì»¨í…?¤íŠ¸ ?? œ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/faq", methods=["GET"])
def faq_list():
    """FAQ ëª©ë¡??ë°˜í™˜?œë‹¤."""
    items = []
    for item in chatbot.faq_items:
        items.append({
            "id": item.get("id", ""),
            "category": item.get("category", ""),
            "question": item.get("question", ""),
        })
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/config", methods=["GET"])
def config():
    """ì±—ë´‡ ?¤ì • ?•ë³´ë¥?ë°˜í™˜?œë‹¤."""
    return jsonify({
        "persona": chatbot.get_persona(),
        "categories": chatbot.config.get("categories", []),
        "contacts": chatbot.config.get("contacts", {}),
    })


@app.route("/api/autocomplete", methods=["GET"])
def autocomplete():
    """ê²€???ë™?„ì„±: FAQ ì§ˆë¬¸ ì¤?ì¿¼ë¦¬ ë¬¸ì?´ì„ ?¬í•¨?˜ëŠ” ?ìœ„ 5ê°œë? ë°˜í™˜?œë‹¤."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"suggestions": []})

    q_lower = q.lower()
    suggestions = []
    for item in chatbot.faq_items:
        question = item.get("question", "")
        if q_lower in question.lower():
            suggestions.append({
                "id": item.get("id", ""),
                "question": question,
                "category": item.get("category", ""),
            })
            if len(suggestions) >= 5:
                break

    return jsonify({"suggestions": suggestions})


@app.route("/api/health", methods=["GET"])
def health():
    """Production health check endpoint with version and FAQ count."""
    try:
        faq_count = len(chatbot.faq_items) if hasattr(chatbot, 'faq_items') else 0
        return jsonify({
            "status": "ok",
            "version": APP_VERSION,
            "faq_count": faq_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "version": APP_VERSION,
            "error": str(e)
        }), 500


@app.route("/api/v1/stats", methods=["GET"])
def api_stats():
    """Production API stats endpoint returning basic usage statistics."""
    try:
        uptime_seconds = time.time() - _usage_stats['start_time']
        uptime_hours = uptime_seconds / 3600

        return jsonify({
            "total_queries": _usage_stats['total_queries'],
            "uptime_seconds": round(uptime_seconds, 2),
            "uptime_hours": round(uptime_hours, 2),
            "version": APP_VERSION,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 200
    except Exception as e:
        logger.error(f"Stats endpoint failed: {e}")
        return jsonify({"error": "Failed to retrieve statistics"}), 500


@app.route("/metrics", methods=["GET"])
def prometheus_metrics():
    """Prometheus metrics endpoint (no auth required)."""
    # Update cache hit rate gauge from FAQ cache state
    try:
        cache_items = _faq_cache.get("items")
        if cache_items is not None and len(chatbot.faq_items) > 0:
            metrics_collector.set_gauge("cache_hit_rate", 1.0)
        else:
            metrics_collector.set_gauge("cache_hit_rate", 0.0)
    except Exception:
        pass
    body = metrics_collector.collect()
    return Response(body, mimetype="text/plain; charset=utf-8")


@app.route("/api/admin/cache/clear", methods=["POST"])
@jwt_auth.require_auth()
def admin_cache_clear():
    """FAQ ìºì‹œë¥?ë¬´íš¨?”í•˜ê³??¤ì‹œ ë¡œë“œ?œë‹¤."""
    try:
        # Reload FAQ data from disk
        chatbot.faq_data = load_json("data/faq.json")
        chatbot.faq_items = chatbot.faq_data.get("items", [])
        chatbot.tfidf_matcher = __import__(
            "src.similarity", fromlist=["TFIDFMatcher"]
        ).TFIDFMatcher(chatbot.faq_items)
        chatbot.related_faq_finder = __import__(
            "src.related_faq", fromlist=["RelatedFAQFinder"]
        ).RelatedFAQFinder(chatbot.faq_items)
        _refresh_faq_cache()
        logger.info("FAQ cache cleared and reloaded")
        return jsonify({"success": True, "faq_count": len(chatbot.faq_items)})
    except Exception as e:
        logger.error(f"ìºì‹œ ì´ˆê¸°???¤íŒ¨: {e}")
        return jsonify({"error": "ìºì‹œ ì´ˆê¸°??ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/login")
def login_page():
    """ë¡œê·¸???˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "login.html")


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """?¬ìš©??ë¡œê·¸??ì²˜ë¦¬."""
    data = request.get_json(silent=True)
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "usernameê³?password ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    user = authenticate_user(data["username"], data["password"])
    if user is None:
        try:
            audit_logger.log(
                actor=data["username"], action="login", resource_type="session",
                details={"success": False}, ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"error": "?˜ëª»???¬ìš©?ëª… ?ëŠ” ë¹„ë?ë²ˆí˜¸?…ë‹ˆ??"}), 401

    token = jwt_auth.generate_token(user["username"], role=user["role"])
    try:
        audit_logger.log(
            actor=user["username"], action="login", resource_type="session",
            details={"success": True}, ip=_get_client_ip(),
        )
    except Exception:
        pass
    return jsonify({"token": token, "expires_in": 86400})


@app.route("/api/auth/me", methods=["GET"])
@jwt_auth.require_auth()
def auth_me():
    """?„ì¬ ?¬ìš©???•ë³´ë¥?ë°˜í™˜?œë‹¤."""
    payload = getattr(request, "jwt_payload", None)
    if payload:
        return jsonify({
            "username": payload.get("sub"),
            "role": payload.get("role"),
        })
    # When auth is disabled (TESTING/ADMIN_AUTH_DISABLED), return default
    return jsonify({"username": "admin", "role": "admin"})


@app.route("/admin")
def admin():
    """ê´€ë¦¬ì ?€?œë³´???˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "admin.html")


@app.route("/api/admin/stats", methods=["GET"])
@jwt_auth.require_auth()
def admin_stats():
    """?µê³„ JSON??ë°˜í™˜?œë‹¤."""
    return jsonify(chat_logger.get_stats())


@app.route("/api/admin/logs", methods=["GET"])
@jwt_auth.require_auth()
def admin_logs():
    """ìµœê·¼ ë¡œê·¸ JSON??ë°˜í™˜?œë‹¤."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"logs": chat_logger.get_recent_logs(limit=limit)})


@app.route("/api/admin/unmatched", methods=["GET"])
@jwt_auth.require_auth()
def admin_unmatched():
    """ë¯¸ë§¤ì¹?ì§ˆë¬¸ JSON??ë°˜í™˜?œë‹¤."""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({"queries": chat_logger.get_unmatched_queries(limit=limit)})


@app.route("/api/admin/recommendations", methods=["GET"])
@jwt_auth.require_auth()
def admin_recommendations():
    """ë¯¸ë§¤ì¹?ì§ˆë¬¸ ê¸°ë°˜ FAQ ì¶”ê? ?„ë³´ ì¶”ì²œ ëª©ë¡??ë°˜í™˜?œë‹¤."""
    top_k = request.args.get("top_k", 10, type=int)
    try:
        recommendations = faq_recommender.get_recommendations(top_k=top_k)
        return jsonify({"recommendations": recommendations, "count": len(recommendations)})
    except Exception as e:
        logger.error(f"FAQ ì¶”ì²œ ?ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "ì¶”ì²œ ?ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/feedback", methods=["POST"])
def feedback():
    """?¬ìš©???¼ë“œë°±ì„ ?€?¥í•œ??"""
    data = request.get_json(silent=True)
    if not data or "query_id" not in data or "rating" not in data:
        return jsonify({"error": "query_id?€ rating ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    query_id = data["query_id"]
    rating = data["rating"]
    comment = data.get("comment", "")

    if rating not in ("helpful", "unhelpful"):
        return jsonify({"error": "rating?€ 'helpful' ?ëŠ” 'unhelpful'?´ì–´???©ë‹ˆ??"}), 400

    try:
        feedback_id = feedback_manager.save_feedback(
            query_id=query_id, rating=rating, comment=comment
        )
        return jsonify({"success": True, "feedback_id": feedback_id}), 201
    except Exception as e:
        logger.error(f"?¼ë“œë°??€???¤íŒ¨: {e}")
        return jsonify({"error": "?¼ë“œë°??€?¥ì— ?¤íŒ¨?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/feedback", methods=["GET"])
@jwt_auth.require_auth()
def admin_feedback():
    """?¼ë“œë°??µê³„ë¥?ë°˜í™˜?œë‹¤."""
    stats = feedback_manager.get_feedback_stats()
    low_rated = feedback_manager.get_low_rated_queries(limit=20)
    return jsonify({"stats": stats, "low_rated_queries": low_rated})


@app.route("/api/admin/analytics", methods=["GET"])
@jwt_auth.require_auth()
def admin_analytics():
    """ë¶„ì„ ë¦¬í¬?¸ë? ë°˜í™˜?œë‹¤."""
    try:
        days = request.args.get("days", 7, type=int)
        trend = query_analytics.get_trend_report(days=days)
        quality = query_analytics.get_quality_score()
        peak_hours = query_analytics.get_peak_hours()
        return jsonify({
            "trend": trend,
            "quality": quality,
            "peak_hours": peak_hours,
        })
    except Exception as e:
        logger.error(f"ë¶„ì„ ë¦¬í¬???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "ë¶„ì„ ë¦¬í¬???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/report", methods=["GET"])
@jwt_auth.require_auth()
def admin_report():
    """ì£¼ê°„ ë¦¬í¬???ìŠ¤?¸ë? ë°˜í™˜?œë‹¤."""
    try:
        report_text = query_analytics.generate_report_text()
        return jsonify({"report": report_text})
    except Exception as e:
        logger.error(f"ì£¼ê°„ ë¦¬í¬???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "ì£¼ê°„ ë¦¬í¬???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/reports/daily", methods=["GET"])
@jwt_auth.require_auth()
def admin_report_daily():
    """?¼ë³„ ë¦¬í¬??JSON??ë°˜í™˜?œë‹¤."""
    try:
        date = request.args.get("date", None)
        report_data = report_generator.generate_daily_report(date=date)
        return jsonify(report_data)
    except Exception as e:
        logger.error(f"?¼ë³„ ë¦¬í¬???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "?¼ë³„ ë¦¬í¬???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/reports/weekly", methods=["GET"])
@jwt_auth.require_auth()
def admin_report_weekly():
    """ì£¼ë³„ ë¦¬í¬??JSON??ë°˜í™˜?œë‹¤."""
    try:
        start = request.args.get("start", None)
        report_data = report_generator.generate_weekly_report(week_start=start)
        return jsonify(report_data)
    except Exception as e:
        logger.error(f"ì£¼ë³„ ë¦¬í¬???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "ì£¼ë³„ ë¦¬í¬???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/reports/monthly", methods=["GET"])
@jwt_auth.require_auth()
def admin_report_monthly():
    """?”ë³„ ë¦¬í¬??JSON??ë°˜í™˜?œë‹¤."""
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
        if not year or not month:
            return jsonify({"error": "year?€ month ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??"}), 400
        if month < 1 or month > 12:
            return jsonify({"error": "month??1-12 ?¬ì´?¬ì•¼ ?©ë‹ˆ??"}), 400
        report_data = report_generator.generate_monthly_report(year, month)
        return jsonify(report_data)
    except Exception as e:
        logger.error(f"?”ë³„ ë¦¬í¬???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "?”ë³„ ë¦¬í¬???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/reports/html", methods=["GET"])
@jwt_auth.require_auth()
def admin_report_html():
    """HTML ë¦¬í¬???Œì¼???¤ìš´ë¡œë“œ?œë‹¤."""
    import tempfile
    try:
        report_type = request.args.get("type", "daily")
        if report_type == "daily":
            date = request.args.get("date", None)
            report_data = report_generator.generate_daily_report(date=date)
        elif report_type == "weekly":
            start = request.args.get("start", None)
            report_data = report_generator.generate_weekly_report(week_start=start)
        elif report_type == "monthly":
            year = request.args.get("year", type=int)
            month = request.args.get("month", type=int)
            if not year or not month:
                return jsonify({"error": "year?€ month ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??"}), 400
            report_data = report_generator.generate_monthly_report(year, month)
        else:
            return jsonify({"error": "? íš¨?˜ì? ?Šì? ë¦¬í¬???€?…ì…?ˆë‹¤."}), 400

        tmp = tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, dir=os.path.join(BASE_DIR, "logs")
        )
        tmp.close()
        report_generator.export_html(report_data, tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            html_content = f.read()
        os.unlink(tmp.name)

        filename = f"report_{report_type}_{report_data.get('start_date', 'unknown')}.html"
        return Response(
            html_content,
            mimetype="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error(f"HTML ë¦¬í¬???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "HTML ë¦¬í¬???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq-pipeline", methods=["GET"])
@jwt_auth.require_auth()
def admin_faq_pipeline():
    """FAQ ?„ë³´ ëª©ë¡??ë°˜í™˜?œë‹¤."""
    try:
        min_freq = request.args.get("min_frequency", 3, type=int)
        candidates = auto_faq_pipeline.get_pending_candidates(min_frequency=min_freq)
        return jsonify({"candidates": candidates, "count": len(candidates)})
    except Exception as e:
        logger.error(f"FAQ ?Œì´?„ë¼??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?Œì´?„ë¼??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq-pipeline/approve", methods=["POST"])
@jwt_auth.require_auth()
def admin_faq_approve():
    """FAQ ?„ë³´ë¥??¹ì¸?œë‹¤."""
    data = request.get_json(silent=True)
    if not data or "candidate_id" not in data:
        return jsonify({"error": "candidate_id ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    try:
        result = auto_faq_pipeline.approve_candidate(data["candidate_id"])
        return jsonify({"success": True, "candidate": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"FAQ ?„ë³´ ?¹ì¸ ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?„ë³´ ?¹ì¸ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq-pipeline/reject", methods=["POST"])
@jwt_auth.require_auth()
def admin_faq_reject():
    """FAQ ?„ë³´ë¥?ê±°ë??œë‹¤."""
    data = request.get_json(silent=True)
    if not data or "candidate_id" not in data:
        return jsonify({"error": "candidate_id ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    try:
        result = auto_faq_pipeline.reject_candidate(data["candidate_id"])
        return jsonify({"success": True, "candidate": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"FAQ ?„ë³´ ê±°ë? ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?„ë³´ ê±°ë? ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/monitor", methods=["GET"])
@jwt_auth.require_auth()
def admin_monitor():
    """?¤ì‹œê°?ëª¨ë‹ˆ?°ë§ ?°ì´?°ë? ë°˜í™˜?œë‹¤."""
    try:
        stats = realtime_monitor.get_live_stats()
        alerts = realtime_monitor.get_alerts()
        return jsonify({"stats": stats, "alerts": alerts})
    except Exception as e:
        logger.error(f"ëª¨ë‹ˆ?°ë§ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ëª¨ë‹ˆ?°ë§ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/quality", methods=["GET"])
@jwt_auth.require_auth()
def admin_quality():
    """FAQ ?ˆì§ˆ ê²€??ê²°ê³¼ë¥?ë°˜í™˜?œë‹¤."""
    try:
        result = faq_quality_checker.check_all()
        return jsonify(result)
    except Exception as e:
        logger.error(f"?ˆì§ˆ ê²€???¤íŒ¨: {e}")
        return jsonify({"error": "?ˆì§ˆ ê²€??ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/realtime", methods=["GET"])
@jwt_auth.require_auth()
def admin_realtime():
    """?¤ì‹œê°?ëª¨ë‹ˆ?°ë§ ?¼ì´ë¸??µê³„ë¥?ë°˜í™˜?œë‹¤."""
    try:
        stats = realtime_monitor.get_live_stats()
        alerts = realtime_monitor.get_alerts()

        # Build hourly query counts for the last 24 hours
        import time as _time
        now = _time.time()
        hourly_counts: list[dict] = []
        with realtime_monitor._lock:
            events = list(realtime_monitor._buffer)
        for h in range(23, -1, -1):
            start = now - (h + 1) * 3600
            end = now - h * 3600
            count = sum(
                1 for e in events
                if e["event_type"] in ("query", "unmatched")
                and start <= e["timestamp"] < end
            )
            hour_label = _time.strftime("%H", _time.localtime(end))
            hourly_counts.append({"hour": hour_label, "count": count})

        return jsonify({
            "queries_per_minute": stats["queries_last_minute"],
            "avg_response_time_ms": stats["avg_response_time_ms"],
            "active_sessions": stats["active_sessions"],
            "error_rate": stats["error_rate"],
            "unmatched_rate": stats["unmatched_rate"],
            "queries_last_hour": stats["queries_last_hour"],
            "top_categories": stats["top_categories"],
            "alerts": alerts,
            "hourly_counts": hourly_counts,
        })
    except Exception as e:
        logger.error(f"?¤ì‹œê°?ëª¨ë‹ˆ?°ë§ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¤ì‹œê°?ëª¨ë‹ˆ?°ë§ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq-quality", methods=["GET"])
@jwt_auth.require_auth()
def admin_faq_quality():
    """FAQ ?ˆì§ˆ ?€?œë³´???°ì´?°ë? ë°˜í™˜?œë‹¤."""
    try:
        result = faq_quality_checker.check_all()
        # Enrich each issue with severity level
        for issue in result.get("issues", []):
            check_type = issue.get("check", "")
            count = issue.get("count", 0)
            if check_type == "duplicates" or (check_type == "keyword_coverage" and count > 5):
                issue["severity"] = "critical"
            elif count > 2:
                issue["severity"] = "warning"
            else:
                issue["severity"] = "good"
        return jsonify(result)
    except Exception as e:
        logger.error(f"FAQ ?ˆì§ˆ ?€?œë³´??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?ˆì§ˆ ?€?œë³´??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/satisfaction", methods=["GET"])
@jwt_auth.require_auth()
def admin_satisfaction():
    """ë§Œì¡±???¸ë Œ???°ì´?°ë? ë°˜í™˜?œë‹¤."""
    try:
        stats = satisfaction_tracker.get_satisfaction_stats()
        low_queries = satisfaction_tracker.get_low_satisfaction_queries(limit=10)

        # Determine trend direction based on recent vs overall score
        avg_score = stats.get("avg_satisfaction_score", 0.0)
        if avg_score >= 0.7:
            trend = "up"
        elif avg_score >= 0.4:
            trend = "stable"
        else:
            trend = "down"

        return jsonify({
            "overall_score": avg_score,
            "trend": trend,
            "total_queries": stats.get("total_queries", 0),
            "re_ask_rate": stats.get("re_ask_rate", 0.0),
            "response_type_distribution": stats.get("response_type_distribution", {}),
            "lowest_rated": low_queries,
        })
    except Exception as e:
        logger.error(f"ë§Œì¡±???¸ë Œ??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ë§Œì¡±???¸ë Œ??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/export", methods=["POST"])
def export_conversation():
    """?€???´ì—­???Œì¼ë¡??´ë³´?¸ë‹¤.

    ?”ì²­ ë³¸ë¬¸: {"session_id": "...", "format": "text|json|csv|html"}
    """
    data = request.get_json(silent=True)
    if not data or "session_id" not in data:
        return jsonify({"error": "session_id ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    session_id = data["session_id"]
    fmt = data.get("format", "text")
    if fmt not in ("text", "json", "csv", "html"):
        return jsonify({"error": "format?€ text, json, csv, html ì¤??˜ë‚˜?¬ì•¼ ?©ë‹ˆ??"}), 400

    session = chatbot.session_manager.get_session(session_id)
    if session is None:
        return jsonify({"error": "?¸ì…˜??ì°¾ì„ ???†ê±°??ë§Œë£Œ?˜ì—ˆ?µë‹ˆ??"}), 404

    history = session.history

    ext_map = {"text": "txt", "json": "json", "csv": "csv", "html": "html"}
    mime_map = {
        "text": "text/plain; charset=utf-8",
        "json": "application/json",
        "csv": "text/csv; charset=utf-8",
        "html": "text/html; charset=utf-8",
    }
    filename = f"conversation_export.{ext_map[fmt]}"

    if fmt == "json":
        content = conversation_exporter.export_json(history, session_id)
    elif fmt == "csv":
        content = conversation_exporter.export_csv(history, session_id)
    elif fmt == "html":
        content = conversation_exporter.export_html(history, session_id)
    else:
        content = conversation_exporter.export_text(history, session_id)

    resp = app.response_class(content, mimetype=mime_map[fmt])
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@app.route("/api/session/<session_id>/export", methods=["GET"])
def session_export(session_id):
    """?¸ì…˜ ?€?”ë? ?´ë³´?¸ë‹¤."""
    session = chatbot.session_manager.get_session(session_id)
    if session is None:
        return jsonify({"error": "?¸ì…˜??ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404

    fmt = request.args.get("format", "text")
    history = session.history

    if fmt == "json":
        content = conversation_exporter.export_json(history, session_id)
        return app.response_class(content, mimetype="application/json")
    elif fmt == "csv":
        content = conversation_exporter.export_csv(history, session_id)
        return app.response_class(content, mimetype="text/csv")
    elif fmt == "html":
        content = conversation_exporter.export_html(history, session_id)
        return app.response_class(content, mimetype="text/html")
    else:
        content = conversation_exporter.export_text(history, session_id)
        return app.response_class(content, mimetype="text/plain; charset=utf-8")


@app.route("/api/related/<faq_id>", methods=["GET"])
def related_faq(faq_id):
    """ê´€??FAQë¥?ë°˜í™˜?œë‹¤."""
    top_k = request.args.get("top_k", 3, type=int)
    try:
        related = chatbot.related_faq_finder.find_related(faq_id, top_k=top_k)
        return jsonify({"related": related, "count": len(related)})
    except Exception as e:
        logger.error(f"ê´€??FAQ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ê´€??FAQ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


# ì¹´ì¹´??i ?¤í”ˆë¹Œë” ë¸”ë£¨?„ë¦°???±ë¡
kakao_blueprint = init_kakao_routes(chatbot, chat_logger)
app.register_blueprint(kakao_blueprint)


@app.route("/api/kakao/chat", methods=["POST"])
def api_kakao_chat():
    """ì¹´ì¹´??i ?¤í”ˆë¹Œë” ?¤í‚¬ ?”ì²­??ì²˜ë¦¬?œë‹¤ (API ê²½ë¡œ).

    ì¹´ì¹´???”ì²­ ?•ì‹:
    {
        "userRequest": {"utterance": "...", "user": {"id": "..."}},
        "bot": {"id": "..."},
        "action": {"name": "..."}
    }

    ì¹´ì¹´???‘ë‹µ ?•ì‹: simpleText + quickReplies
    """
    data = request.get_json(silent=True)
    if not data:
        resp = build_skill_response([format_simple_text("?”ì²­??ì²˜ë¦¬?????†ìŠµ?ˆë‹¤.")])
        return jsonify(resp), 200

    parsed = parse_kakao_request(data)
    utterance = parsed["utterance"]

    if not utterance:
        resp = build_skill_response([
            format_simple_text("ì§ˆë¬¸???…ë ¥??ì£¼ì„¸??\n\n?? ë³´ì„¸?„ì‹œ?¥ì´ ë¬´ì—‡?¸ê???")
        ])
        return jsonify(resp), 200

    # ì±—ë´‡ ?‘ë‹µ ?ì„±
    answer = chatbot.process_query(utterance)
    categories = classify_query(utterance)
    primary_category = categories[0] if categories else "GENERAL"
    escalation = check_escalation(utterance)

    outputs = [format_simple_text(answer)]

    # ?ìŠ¤ì»¬ë ˆ?´ì…˜ ?„ìš” ???°ë½ì²?ì¹´ë“œ ì¶”ê?
    if escalation is not None:
        contact = get_escalation_contact(escalation)
        if contact:
            outputs.append(format_escalation_card(contact))

    # ë°”ë¡œê°€ê¸?ë²„íŠ¼: FAQ ì¹´í…Œê³ ë¦¬
    config_categories = chatbot.config.get("categories", [])
    category_names = [
        c["name"] if isinstance(c, dict) else str(c)
        for c in config_categories
    ]
    if category_names:
        quick_replies = format_quick_replies(category_names[:5])
    else:
        quick_replies = format_quick_replies([
            "ë³´ì„¸?„ì‹œ?¥ì´?€?",
            "ë¬¼í’ˆ ë°˜ì… ?ˆì°¨",
            "?„ì¥ ?ë§¤ ê°€??",
            "ë¬¸ì˜ì²??ˆë‚´",
        ])

    # ë¡œê¹…
    try:
        faq_match = chatbot.find_matching_faq(utterance, primary_category)
        chat_logger.log_query(
            query=utterance,
            category=primary_category,
            faq_id=faq_match.get("id") if faq_match else None,
            is_escalation=escalation is not None,
            response_preview=answer[:200],
        )
    except Exception:
        pass

    resp = build_skill_response(outputs, quick_replies)
    return jsonify(resp), 200


@app.route("/api/kakao/faq", methods=["POST"])
def api_kakao_faq():
    """FAQ ëª©ë¡??ì¹´ì¹´??ìºëŸ¬?€ ì¹´ë“œ ?•ì‹?¼ë¡œ ë°˜í™˜?œë‹¤.

    ì¹´ì¹´???”ì²­ ?•ì‹ (?œì? ?¤í‚¬ ?”ì²­):
    {
        "userRequest": {"utterance": "...", "user": {"id": "..."}},
        "bot": {"id": "..."},
        "action": {"name": "..."}
    }

    ?‘ë‹µ: ì¹´ì¹´??carousel ì¹´ë“œ (FAQ ??ª©)
    """
    data = request.get_json(silent=True)

    # ì¹´í…Œê³ ë¦¬ ?„í„°ë§?(action params?ì„œ category ì¶”ì¶œ)
    category_filter = None
    if data:
        action = data.get("action", {})
        params = action.get("params", {})
        category_filter = params.get("category", "").strip() or None

    faq_items = chatbot.faq_items
    if category_filter:
        faq_items = [
            item for item in faq_items
            if item.get("category", "") == category_filter
        ]

    # ìµœë? 10ê°?ì¹´ë“œë¡??œí•œ (ì¹´ì¹´??ìºëŸ¬?€ ?œí•œ)
    faq_items = faq_items[:10]

    if not faq_items:
        resp = build_skill_response([
            format_simple_text("?´ë‹¹ ì¹´í…Œê³ ë¦¬??FAQê°€ ?†ìŠµ?ˆë‹¤.")
        ])
        return jsonify(resp), 200

    carousel = format_carousel(faq_items)

    # ì¹´í…Œê³ ë¦¬ ë°”ë¡œê°€ê¸?ë²„íŠ¼
    all_categories = sorted(set(
        item.get("category", "") for item in chatbot.faq_items if item.get("category")
    ))
    quick_replies = format_quick_replies(all_categories[:5])

    resp = build_skill_response([carousel], quick_replies)
    return jsonify(resp), 200


@app.route("/api/admin/law-updates", methods=["GET"])
def admin_law_updates():
    """ìµœê·¼ ë²•ë ¹ ë³€ê²½ê³¼ ?í–¥ ë°›ëŠ” FAQë¥?ë°˜í™˜?œë‹¤."""
    try:
        since = request.args.get("since", "1970-01-01")
        changes = law_version_tracker.get_changes_since(since)
        pending = faq_update_notifier.get_pending_notifications()
        history = law_update_scheduler.get_update_history()
        return jsonify({
            "changes": changes,
            "pending_notifications": pending,
            "update_history": history,
        })
    except Exception as e:
        logger.error(f"ë²•ë ¹ ?…ë°?´íŠ¸ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ë²•ë ¹ ?…ë°?´íŠ¸ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/law-updates/check", methods=["POST"])
def admin_law_updates_check():
    """?˜ë™ ë²•ë ¹ ?…ë°?´íŠ¸ ?•ì¸???¸ë¦¬ê±°í•œ??"""
    try:
        result = law_update_scheduler.check_for_updates()
        return jsonify(result)
    except Exception as e:
        logger.error(f"ë²•ë ¹ ?…ë°?´íŠ¸ ?•ì¸ ?¤íŒ¨: {e}")
        return jsonify({"error": "ë²•ë ¹ ?…ë°?´íŠ¸ ?•ì¸ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/law-updates/acknowledge", methods=["POST"])
def admin_law_updates_acknowledge():
    """ë²•ë ¹ ë³€ê²??Œë¦¼???•ì¸ ì²˜ë¦¬?œë‹¤."""
    data = request.get_json(silent=True)
    if not data or "notification_id" not in data:
        return jsonify({"error": "notification_id ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    try:
        success = faq_update_notifier.acknowledge(data["notification_id"])
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "?Œë¦¼??ì°¾ì„ ???†ê±°???´ë? ?•ì¸?˜ì—ˆ?µë‹ˆ??"}), 404
    except Exception as e:
        logger.error(f"?Œë¦¼ ?•ì¸ ì²˜ë¦¬ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë¦¼ ?•ì¸ ì²˜ë¦¬ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/backup", methods=["POST"])
@jwt_auth.require_auth()
def admin_backup_create():
    """?˜ë™ ë°±ì—…???¸ë¦¬ê±°í•œ??"""
    try:
        backup_path = backup_manager.create_backup()
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="backup", resource_type="backup",
                resource_id=os.path.basename(backup_path), ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({
            "success": True,
            "backup_path": backup_path,
            "filename": os.path.basename(backup_path),
        }), 201
    except Exception as e:
        logger.error(f"ë°±ì—… ?ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "ë°±ì—… ?ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/backups", methods=["GET"])
@jwt_auth.require_auth()
def admin_backup_list():
    """?¬ìš© ê°€?¥í•œ ë°±ì—… ëª©ë¡??ë°˜í™˜?œë‹¤."""
    try:
        backups = backup_manager.list_backups()
        return jsonify({"backups": backups, "count": len(backups)})
    except Exception as e:
        logger.error(f"ë°±ì—… ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ë°±ì—… ëª©ë¡ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/restore", methods=["POST"])
@jwt_auth.require_auth()
def admin_restore():
    """?¹ì • ë°±ì—…?ì„œ ë³µì›?œë‹¤."""
    data = request.get_json(silent=True)
    if not data or "filename" not in data:
        return jsonify({"error": "filename ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    filename = data["filename"]
    backup_path = os.path.join(BASE_DIR, "backups", filename)

    if not os.path.isfile(backup_path):
        return jsonify({"error": "ë°±ì—… ?Œì¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404

    try:
        result = backup_manager.restore_from_backup(backup_path)
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="restore", resource_type="backup",
                resource_id=filename, ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.error(f"ë³µì› ?¤íŒ¨: {e}")
        return jsonify({"error": "ë³µì› ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/backup/<backup_id>", methods=["DELETE"])
@jwt_auth.require_auth()
def admin_backup_delete(backup_id):
    """?¹ì • ë°±ì—…???? œ?œë‹¤."""
    backup_path = os.path.join(BASE_DIR, "backups", backup_id)

    if not os.path.isfile(backup_path):
        return jsonify({"error": "ë°±ì—… ?Œì¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404

    try:
        os.remove(backup_path)
        enc_path = backup_path + ".enc"
        if os.path.isfile(enc_path):
            os.remove(enc_path)
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="delete", resource_type="backup",
                resource_id=backup_id, ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, "deleted": backup_id})
    except Exception as e:
        logger.error(f"ë°±ì—… ?? œ ?¤íŒ¨: {e}")
        return jsonify({"error": "ë°±ì—… ?? œ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


# ?¤ì´ë²??¡í†¡ ?´ëŒ‘???¸ìŠ¤?´ìŠ¤
naver_adapter = NaverTalkTalkAdapter()

NAVER_WELCOME_MESSAGE = (
    "?ˆë…•?˜ì„¸?? ë³´ì„¸?„ì‹œ??ë¯¼ì›?‘ë? ì±—ë´‡?…ë‹ˆ??\n\n"
    "ë³´ì„¸?„ì‹œ?¥ì— ê´€??ì§ˆë¬¸???…ë ¥??ì£¼ì„¸??\n"
    "?? ë³´ì„¸?„ì‹œ?¥ì´ ë¬´ì—‡?¸ê???"
)


@app.route("/api/naver/webhook", methods=["POST"])
def naver_webhook_post():
    """?¤ì´ë²??¡í†¡ ?¹í›… ?˜ì‹  ?”ë“œ?¬ì¸??

    ?¤ì´ë²??¡í†¡ ?¹í›… ?•ì‹:
    {
        "event": "send",
        "user": "? ì??ë³„ê°?,
        "textContent": {"text": "?¬ìš©??ë©”ì‹œì§€"}
    }

    ?´ë²¤???€?…ë³„ ì²˜ë¦¬:
    - send: ?¬ìš©??ë©”ì‹œì§€ë¥?ì±—ë´‡?¼ë¡œ ì²˜ë¦¬?˜ì—¬ ?‘ë‹µ
    - open: ?˜ì˜ ë©”ì‹œì§€ ë°˜í™˜
    - leave, friend: 200 OK ë°˜í™˜
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": True}), 200

    parsed = naver_adapter.parse_webhook(data)
    event = parsed["event"]
    user_id = parsed["user_id"]

    if event == EVENT_SEND:
        text = parsed["text"]
        if not text:
            response = naver_adapter.build_response(event, {
                "user_id": user_id,
                "text": "ì§ˆë¬¸???…ë ¥??ì£¼ì„¸??\n\n?? ë³´ì„¸?„ì‹œ?¥ì´ ë¬´ì—‡?¸ê???",
            })
            return jsonify(response), 200

        # ì±—ë´‡ ?‘ë‹µ ?ì„±
        answer = chatbot.process_query(text)

        # ë°”ë¡œê°€ê¸?ë²„íŠ¼ ì¶”ê?
        buttons = [
            {"label": "ë³´ì„¸?„ì‹œ?¥ì´?€?", "value": "ë³´ì„¸?„ì‹œ?¥ì´?€?"},
            {"label": "ë¬¼í’ˆ ë°˜ì… ?ˆì°¨", "value": "ë¬¼í’ˆ ë°˜ì… ?ˆì°¨"},
            {"label": "?„ì¥ ?ë§¤ ê°€??", "value": "?„ì¥ ?ë§¤ ê°€??"},
            {"label": "ë¬¸ì˜ì²??ˆë‚´", "value": "ë¬¸ì˜ì²??ˆë‚´"},
        ]

        response = naver_adapter.build_response(event, {
            "user_id": user_id,
            "text": answer,
            "buttons": buttons,
        })

        # ë¡œê¹…
        try:
            categories = classify_query(text)
            primary_category = categories[0] if categories else "GENERAL"
            faq_match = chatbot.find_matching_faq(text, primary_category)
            chat_logger.log_query(
                query=text,
                category=primary_category,
                faq_id=faq_match.get("id") if faq_match else None,
                is_escalation=False,
                response_preview=answer[:200],
            )
        except Exception:
            pass

        return jsonify(response), 200

    elif event == EVENT_OPEN:
        response = naver_adapter.build_response(event, {
            "user_id": user_id,
            "text": NAVER_WELCOME_MESSAGE,
        })
        return jsonify(response), 200

    # leave, friend ??ê¸°í? ?´ë²¤?¸ëŠ” 200 OK ë°˜í™˜
    return jsonify({"success": True}), 200


@app.route("/api/naver/webhook", methods=["GET"])
def naver_webhook_get():
    """?¤ì´ë²??¡í†¡ ?¹í›… ê²€ì¦??”ë“œ?¬ì¸??

    ?¤ì´ë²??¡í†¡???¹í›… URL ?±ë¡ ??GET ?”ì²­?¼ë¡œ ê²€ì¦í•œ??
    challenge ?Œë¼ë¯¸í„°ë¥?ê·¸ë?ë¡?ë°˜í™˜?˜ì—¬ ?¸ì¦???„ë£Œ?œë‹¤.
    """
    challenge = request.args.get("challenge", "")
    return challenge, 200


# --- ë©€???Œë„Œ??ê´€ë¦?API ---


@app.route("/api/admin/tenants", methods=["GET"])
@jwt_auth.require_auth()
def admin_list_tenants():
    """?Œë„Œ??ëª©ë¡??ë°˜í™˜?œë‹¤."""
    try:
        tenants = tenant_manager.list_tenants()
        return jsonify({"tenants": tenants, "count": len(tenants)})
    except Exception as e:
        logger.error(f"?Œë„Œ??ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë„Œ??ëª©ë¡ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/tenants", methods=["POST"])
@jwt_auth.require_auth()
def admin_create_tenant():
    """???Œë„Œ?¸ë? ?ì„±?œë‹¤."""
    data = request.get_json(silent=True)
    if not data or "tenant_id" not in data or "name" not in data:
        return jsonify({"error": "tenant_id?€ name ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    try:
        tenant = tenant_manager.create_tenant(
            tenant_id=data["tenant_id"],
            name=data["name"],
            config=data.get("config"),
        )
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="create", resource_type="tenant",
                resource_id=data["tenant_id"], details={"name": data["name"]},
                ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, "tenant": tenant}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"?Œë„Œ???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë„Œ???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/tenants/<tenant_id>", methods=["PUT"])
@jwt_auth.require_auth()
def admin_update_tenant(tenant_id):
    """?Œë„Œ???¤ì •???…ë°?´íŠ¸?œë‹¤."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "?…ë°?´íŠ¸???°ì´?°ê? ?„ìš”?©ë‹ˆ??"}), 400

    try:
        tenant = tenant_manager.update_tenant(tenant_id, data)
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="update", resource_type="tenant",
                resource_id=tenant_id, details={"fields": list(data.keys())},
                ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, "tenant": tenant})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"?Œë„Œ???…ë°?´íŠ¸ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë„Œ???…ë°?´íŠ¸ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/tenants/<tenant_id>", methods=["DELETE"])
@jwt_auth.require_auth()
def admin_delete_tenant(tenant_id):
    """?Œë„Œ?¸ë? ?? œ?œë‹¤."""
    try:
        tenant_manager.delete_tenant(tenant_id)
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="delete", resource_type="tenant",
                resource_id=tenant_id, ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"?Œë„Œ???? œ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë„Œ???? œ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/tenants/<tenant_id>/faq", methods=["GET"])
@jwt_auth.require_auth()
def admin_tenant_faq(tenant_id):
    """?Œë„Œ?¸ë³„ FAQ ?°ì´?°ë? ë°˜í™˜?œë‹¤."""
    try:
        faq = tenant_manager.get_tenant_faq(tenant_id)
        return jsonify(faq)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"?Œë„Œ??FAQ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë„Œ??FAQ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500



# --- FAQ Manager CRUD API ---

@app.route("/admin/faq")
def admin_faq_page():
    """FAQ ê´€ë¦??˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "faq-manager.html")


@app.route("/api/admin/faq", methods=["GET"])
@jwt_auth.require_auth()
def admin_faq_list():
    """ëª¨ë“  FAQ ??ª©??ë©”í??°ì´?°ì? ?¨ê»˜ ë°˜í™˜?œë‹¤."""
    try:
        category = request.args.get("category", "").strip()
        search = request.args.get("search", "").strip().lower()
        items = faq_manager.list_all()

        if category:
            items = [it for it in items if it.get("category") == category]
        if search:
            items = [
                it for it in items
                if search in it.get("question", "").lower()
                or search in it.get("answer", "").lower()
                or search in it.get("id", "").lower()
            ]

        return jsonify({"items": items, "count": len(items)})
    except Exception as e:
        logger.error(f"FAQ ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ëª©ë¡ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq", methods=["POST"])
@jwt_auth.require_auth()
def admin_faq_create():
    """??FAQ ??ª©??ì¶”ê??œë‹¤."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "?”ì²­ ë³¸ë¬¸???„ìš”?©ë‹ˆ??"}), 400

    try:
        item = faq_manager.create(data)
        _reload_chatbot_faq()
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="create", resource_type="faq",
                resource_id=item.get("id"), details={"question": data.get("question", "")},
                ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, "item": item}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"FAQ ?ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq/<faq_id>", methods=["PUT"])
@jwt_auth.require_auth()
def admin_faq_update(faq_id):
    """FAQ ??ª©???˜ì •?œë‹¤."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "?”ì²­ ë³¸ë¬¸???„ìš”?©ë‹ˆ??"}), 400

    try:
        item = faq_manager.update(faq_id, data)
        _reload_chatbot_faq()
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="update", resource_type="faq",
                resource_id=faq_id, details={"fields": list(data.keys())},
                ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, "item": item})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"FAQ ?˜ì • ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?˜ì • ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq/<faq_id>", methods=["DELETE"])
@jwt_auth.require_auth()
def admin_faq_delete(faq_id):
    """FAQ ??ª©???? œ?œë‹¤."""
    try:
        deleted = faq_manager.delete(faq_id)
        _reload_chatbot_faq()
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="delete", resource_type="faq",
                resource_id=faq_id, ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, "deleted": deleted})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"FAQ ?? œ ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?? œ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/faq/<faq_id>/history", methods=["GET"])
@jwt_auth.require_auth()
def admin_faq_history(faq_id):
    """FAQ ??ª©??ë³€ê²??´ë ¥??ë°˜í™˜?œë‹¤."""
    try:
        history = faq_manager.get_history(faq_id)
        return jsonify({"faq_id": faq_id, "history": history, "count": len(history)})
    except Exception as e:
        logger.error(f"FAQ ?´ë ¥ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "FAQ ?´ë ¥ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


def _reload_chatbot_faq():
    """Reload chatbot FAQ data after a CRUD operation."""
    try:
        chatbot.faq_data = load_json("data/faq.json")
        chatbot.faq_items = chatbot.faq_data.get("items", [])
        chatbot.tfidf_matcher = __import__(
            "src.similarity", fromlist=["TFIDFMatcher"]
        ).TFIDFMatcher(chatbot.faq_items)
        chatbot.related_faq_finder = __import__(
            "src.related_faq", fromlist=["RelatedFAQFinder"]
        ).RelatedFAQFinder(chatbot.faq_items)
        _refresh_faq_cache()
        logger.info("FAQ data reloaded after CRUD operation")
    except Exception as e:
        logger.error(f"FAQ ë¦¬ë¡œ???¤íŒ¨: {e}")



# --- FAQ Import/Export endpoints ---

@app.route("/api/admin/faq/import", methods=["POST"])
@jwt_auth.require_auth()
def admin_faq_import():
    """Upload a CSV or JSON file and import FAQ items."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    strategy = request.form.get("strategy", "skip")
    fmt = request.form.get("format", "")
    if not fmt:
        if file.filename.endswith(".json"):
            fmt = "json"
        else:
            fmt = "csv"

    import tempfile as _tempfile
    tmp_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(tmp_dir, exist_ok=True)
    suffix = ".json" if fmt == "json" else ".csv"
    fd, tmp_path = _tempfile.mkstemp(dir=tmp_dir, suffix=suffix)
    try:
        file.save(tmp_path)
        os.close(fd)

        if fmt == "json":
            items = faq_importer.import_json(tmp_path)
        else:
            items = faq_importer.import_csv(tmp_path)

        result = faq_importer.merge_import(items, strategy=strategy)
        _reload_chatbot_faq()

        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="import", resource_type="faq",
                details={"format": fmt, "strategy": strategy, **{k: v for k, v in result.items() if k != "errors"}},
                ip=_get_client_ip(),
            )
        except Exception:
            pass

        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"FAQ import failed: {e}")
        return jsonify({"error": "FAQ import failed"}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.route("/api/admin/faq/import/preview", methods=["POST"])
@jwt_auth.require_auth()
def admin_faq_import_preview():
    """Preview a file import without applying changes."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    fmt = request.form.get("format", "")
    if not fmt:
        if file.filename.endswith(".json"):
            fmt = "json"
        else:
            fmt = "csv"

    import tempfile as _tempfile
    tmp_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(tmp_dir, exist_ok=True)
    suffix = ".json" if fmt == "json" else ".csv"
    fd, tmp_path = _tempfile.mkstemp(dir=tmp_dir, suffix=suffix)
    try:
        file.save(tmp_path)
        os.close(fd)
        preview = faq_importer.preview_import(tmp_path, format=fmt)
        return jsonify(preview)
    except Exception as e:
        logger.error(f"FAQ import preview failed: {e}")
        return jsonify({"error": "Preview failed"}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.route("/api/admin/faq/export", methods=["GET"])
@jwt_auth.require_auth()
def admin_faq_export():
    """Export FAQ items as a downloadable CSV or JSON file."""
    fmt = request.args.get("format", "csv").lower()

    import tempfile as _tempfile
    tmp_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        if fmt == "json":
            fd, tmp_path = _tempfile.mkstemp(dir=tmp_dir, suffix=".json")
            os.close(fd)
            faq_exporter.export_json(tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            os.unlink(tmp_path)
            return Response(
                content,
                mimetype="application/json",
                headers={"Content-Disposition": "attachment; filename=faq_export.json"},
            )
        else:
            fd, tmp_path = _tempfile.mkstemp(dir=tmp_dir, suffix=".csv")
            os.close(fd)
            faq_exporter.export_csv(tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            os.unlink(tmp_path)
            return Response(
                content,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=faq_export.csv"},
            )
    except Exception as e:
        logger.error(f"FAQ export failed: {e}")
        return jsonify({"error": "FAQ export failed"}), 500


# --- FAQ Snapshot / Diff API endpoints ---

@app.route("/api/admin/faq/snapshot", methods=["POST"])
@jwt_auth.require_auth()
def admin_faq_snapshot():
    """Create a snapshot of the current FAQ state."""
    data = request.get_json(silent=True) or {}
    label = data.get("label")
    try:
        result = faq_diff_engine.snapshot(label=label)
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"FAQ snapshot failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/faq/snapshots", methods=["GET"])
@jwt_auth.require_auth()
def admin_faq_snapshots():
    """List all FAQ snapshots."""
    try:
        snapshots = faq_diff_engine.list_snapshots()
        return jsonify({"snapshots": snapshots})
    except Exception as e:
        logger.error(f"FAQ snapshot listing failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/faq/diff", methods=["GET"])
@jwt_auth.require_auth()
def admin_faq_diff():
    """Compare two FAQ snapshots."""
    a = request.args.get("a")
    b = request.args.get("b")
    if not a or not b:
        return jsonify({"error": "Both 'a' and 'b' snapshot IDs are required"}), 400
    try:
        a_id = int(a)
        b_id = int(b)
    except (ValueError, TypeError):
        return jsonify({"error": "Snapshot IDs must be integers"}), 400
    try:
        diff_result = faq_diff_engine.diff(a_id, b_id)
        summary = faq_diff_engine.get_change_summary(diff_result)
        return jsonify({"diff": diff_result, "summary": summary})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"FAQ diff failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/faq/rollback", methods=["POST"])
@jwt_auth.require_auth()
def admin_faq_rollback():
    """Rollback FAQ data to a specific snapshot."""
    data = request.get_json(silent=True) or {}
    snapshot_id = data.get("snapshot_id")
    if snapshot_id is None:
        return jsonify({"error": "snapshot_id is required"}), 400
    try:
        snapshot_id = int(snapshot_id)
    except (ValueError, TypeError):
        return jsonify({"error": "snapshot_id must be an integer"}), 400
    try:
        count = faq_diff_engine.rollback_to(snapshot_id)
        return jsonify({"restored_items": count, "snapshot_id": snapshot_id})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"FAQ rollback failed: {e}")
        return jsonify({"error": str(e)}), 500


# --- Webhook API endpoints ---

@app.route("/api/admin/webhooks", methods=["POST"])
@jwt_auth.require_auth()
def admin_webhook_register():
    """Register a new webhook subscription."""
    data = request.get_json(silent=True)
    if not data or "url" not in data or "events" not in data:
        return jsonify({"error": "urlê³?events ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    url = data["url"]
    events = data["events"]
    secret = data.get("secret")

    if not isinstance(events, list) or not events:
        return jsonify({"error": "events??ë¹„ì–´ ?ˆì? ?Šì? ë°°ì—´?´ì–´???©ë‹ˆ??"}), 400

    try:
        subscription_id = webhook_manager.register(url, events, secret)
        try:
            audit_logger.log(
                actor=_get_audit_actor(), action="create", resource_type="webhook",
                resource_id=subscription_id, details={"url": url, "events": events},
                ip=_get_client_ip(),
            )
        except Exception:
            pass
        return jsonify({"success": True, "subscription_id": subscription_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"?¹í›… ?±ë¡ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¹í›… ?±ë¡ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/webhooks", methods=["GET"])
@jwt_auth.require_auth()
def admin_webhook_list():
    """List all active webhook subscriptions."""
    try:
        subscriptions = webhook_manager.list_subscriptions()
        return jsonify({"subscriptions": subscriptions, "count": len(subscriptions)})
    except Exception as e:
        logger.error(f"?¹í›… ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¹í›… ëª©ë¡ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/webhooks/<subscription_id>", methods=["DELETE"])
@jwt_auth.require_auth()
def admin_webhook_unregister(subscription_id):
    """Unregister a webhook subscription."""
    try:
        removed = webhook_manager.unregister(subscription_id)
        if removed:
            try:
                audit_logger.log(
                    actor=_get_audit_actor(), action="delete", resource_type="webhook",
                    resource_id=subscription_id, ip=_get_client_ip(),
                )
            except Exception:
                pass
            return jsonify({"success": True, "subscription_id": subscription_id})
        else:
            return jsonify({"error": "êµ¬ë…??ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
    except Exception as e:
        logger.error(f"?¹í›… ?´ì œ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¹í›… ?´ì œ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/webhooks/<subscription_id>/deliveries", methods=["GET"])
@jwt_auth.require_auth()
def admin_webhook_deliveries(subscription_id):
    """Get delivery log for a webhook subscription."""
    try:
        limit = request.args.get("limit", 50, type=int)
        deliveries = webhook_manager.get_delivery_log(subscription_id=subscription_id, limit=limit)
        return jsonify({"deliveries": deliveries, "count": len(deliveries)})
    except Exception as e:
        logger.error(f"?¹í›… ë°°ë‹¬ ë¡œê·¸ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¹í›… ë°°ë‹¬ ë¡œê·¸ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/webhooks/test", methods=["POST"])
@jwt_auth.require_auth()
def admin_webhook_test():
    """Send a test event to all subscribers of the given event type."""
    data = request.get_json(silent=True)
    event_type = data.get("event_type", "query.received") if data else "query.received"

    test_payload = {
        "test": True,
        "message": "This is a test webhook delivery.",
    }

    try:
        count = webhook_manager.emit(event_type, test_payload)
        return jsonify({"success": True, "subscribers_notified": count, "event_type": event_type})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"?ŒìŠ¤???¹í›… ?„ì†¡ ?¤íŒ¨: {e}")
        return jsonify({"error": "?ŒìŠ¤???¹í›… ?„ì†¡ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


# --- Alert Center API endpoints ---

@app.route("/api/admin/alerts", methods=["GET"])
@jwt_auth.require_auth()
def admin_alerts_list():
    """List alerts with optional filters."""
    try:
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        severity = request.args.get("severity")
        category = request.args.get("category")
        limit = int(request.args.get("limit", "50"))
        alerts = alert_center.get_alerts(
            unread_only=unread_only, severity=severity, category=category, limit=limit,
        )
        return jsonify({"alerts": alerts, "count": len(alerts)})
    except Exception as e:
        logger.error(f"?Œë¦¼ ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë¦¼ ëª©ë¡ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/alerts/count", methods=["GET"])
@jwt_auth.require_auth()
def admin_alerts_count():
    """Get unread alert count."""
    try:
        count = alert_center.get_unread_count()
        return jsonify({"unread_count": count})
    except Exception as e:
        logger.error(f"?Œë¦¼ ì¹´ìš´??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë¦¼ ì¹´ìš´??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/alerts/<alert_id>/read", methods=["POST"])
@jwt_auth.require_auth()
def admin_alert_mark_read(alert_id):
    """Mark a single alert as read."""
    try:
        found = alert_center.mark_read(alert_id)
        if not found:
            return jsonify({"error": "?Œë¦¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"?Œë¦¼ ?½ìŒ ì²˜ë¦¬ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë¦¼ ?½ìŒ ì²˜ë¦¬ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/alerts/read-all", methods=["POST"])
@jwt_auth.require_auth()
def admin_alerts_mark_all_read():
    """Mark all alerts as read."""
    try:
        count = alert_center.mark_all_read()
        return jsonify({"success": True, "updated_count": count})
    except Exception as e:
        logger.error(f"?„ì²´ ?Œë¦¼ ?½ìŒ ì²˜ë¦¬ ?¤íŒ¨: {e}")
        return jsonify({"error": "?„ì²´ ?Œë¦¼ ?½ìŒ ì²˜ë¦¬ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/alerts/<alert_id>", methods=["DELETE"])
@jwt_auth.require_auth()
def admin_alert_delete(alert_id):
    """Delete an alert."""
    try:
        found = alert_center.delete_alert(alert_id)
        if not found:
            return jsonify({"error": "?Œë¦¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"?Œë¦¼ ?? œ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë¦¼ ?? œ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/alerts/check", methods=["POST"])
@jwt_auth.require_auth()
def admin_alerts_run_checks():
    """Manually run all alert rule checks."""
    try:
        new_alerts = alert_rule_engine.run_all_checks()
        return jsonify({"success": True, "new_alerts": new_alerts, "count": len(new_alerts)})
    except Exception as e:
        logger.error(f"?Œë¦¼ ê·œì¹™ ?¤í–‰ ?¤íŒ¨: {e}")
        return jsonify({"error": "?Œë¦¼ ê·œì¹™ ?¤í–‰ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


# --- Audit Log API endpoints ---


@app.route("/api/admin/audit", methods=["GET"])
@jwt_auth.require_auth()
def admin_audit_logs():
    """Query audit logs with optional filters."""
    try:
        actor = request.args.get("actor")
        action = request.args.get("action")
        resource_type = request.args.get("resource_type")
        since = request.args.get("since")
        limit = request.args.get("limit", 100, type=int)

        logs = audit_logger.get_logs(
            actor=actor, action=action, resource_type=resource_type,
            since=since, limit=limit,
        )
        return jsonify({"logs": logs, "count": len(logs)})
    except Exception as e:
        logger.error(f"ê°ì‚¬ ë¡œê·¸ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ê°ì‚¬ ë¡œê·¸ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/audit/stats", methods=["GET"])
@jwt_auth.require_auth()
def admin_audit_stats():
    """Get audit statistics (actions per day, top actors)."""
    try:
        since = request.args.get("since")
        stats = audit_logger.get_stats(since=since)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"ê°ì‚¬ ?µê³„ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ê°ì‚¬ ?µê³„ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500




# --- Profiler API endpoints ---

@app.route("/api/admin/profiler/start", methods=["POST"])
def admin_profiler_start():
    """Enable request profiling."""
    if request_profiler.is_profiling:
        return jsonify({"message": "Profiling is already active."}), 200
    request_profiler.start_profiling()
    return jsonify({"success": True, "message": "Profiling started."})


@app.route("/api/admin/profiler/stop", methods=["POST"])
def admin_profiler_stop():
    """Disable request profiling and return accumulated results."""
    if not request_profiler.is_profiling:
        return jsonify({"error": "Profiling is not active."}), 400
    results = request_profiler.stop_profiling()
    return jsonify({"success": True, "results": results})


@app.route("/api/admin/profiler/benchmark", methods=["GET"])
def admin_profiler_benchmark():
    """Run component benchmarks with small iteration counts."""
    iterations = request.args.get("iterations", 5, type=int)
    iterations = max(1, min(iterations, 1000))
    try:
        results = {
            "classifier": component_benchmark.benchmark_classifier(iterations=iterations),
            "tfidf": component_benchmark.benchmark_tfidf(iterations=iterations),
            "bm25": component_benchmark.benchmark_bm25(iterations=iterations),
            "full_pipeline": component_benchmark.benchmark_full_pipeline(iterations=max(1, iterations // 2)),
        }
        return jsonify({"success": True, "benchmarks": results})
    except Exception as e:
        logger.error(f"ë²¤ì¹˜ë§ˆí¬ ?¤í–‰ ?¤íŒ¨: {e}")
        return jsonify({"error": "ë²¤ì¹˜ë§ˆí¬ ?¤í–‰ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/profiler/status", methods=["GET"])
def admin_profiler_status():
    """Return current profiling status."""
    return jsonify({
        "profiling": request_profiler.is_profiling,
        "summary": request_profiler.get_summary(),
    })


# --- I18n API endpoints ---

@app.route("/api/i18n/languages", methods=["GET"])
def i18n_languages():
    """ì§€???¸ì–´ ëª©ë¡??ë°˜í™˜?œë‹¤."""
    return jsonify({"languages": i18n_manager.get_supported_languages()})


@app.route("/api/i18n/<lang>", methods=["GET"])
def i18n_locale(lang):
    """?¹ì • ?¸ì–´??ë²ˆì—­ ?Œì¼??ë°˜í™˜?œë‹¤."""
    data = i18n_manager.load_locale(lang)
    if not data:
        return jsonify({"error": f"Locale '{lang}' not found"}), 404
    return jsonify(data)


# --- Advanced Rate Limit admin endpoints ---

@app.route("/api/admin/rate-limits", methods=["GET"])
def admin_rate_limits_get():
    """Return current rate limit configuration."""
    stats = advanced_rate_limiter.get_usage_stats()
    return jsonify({
        "endpoint_limits": stats["endpoint_limits"],
        "default_daily_quota": stats["default_daily_quota"],
    })


@app.route("/api/admin/rate-limits", methods=["PUT"])
def admin_rate_limits_update():
    """Update rate limit configuration."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    updated = []
    if "endpoint_limits" in data:
        for pattern, rpm in data["endpoint_limits"].items():
            if not isinstance(rpm, (int, float)) or rpm <= 0:
                return jsonify({"error": f"Invalid limit for {pattern}"}), 400
            advanced_rate_limiter.set_endpoint_limit(pattern, int(rpm))
            updated.append(pattern)

    if "default_daily_quota" in data:
        quota = data["default_daily_quota"]
        if not isinstance(quota, (int, float)) or quota <= 0:
            return jsonify({"error": "Invalid daily quota"}), 400
        advanced_rate_limiter._default_daily_quota = int(quota)

    if "user_quotas" in data:
        for api_key, limit in data["user_quotas"].items():
            if not isinstance(limit, (int, float)) or limit <= 0:
                return jsonify({"error": f"Invalid quota for {api_key}"}), 400
            advanced_rate_limiter.set_user_quota(api_key, int(limit))

    return jsonify({"status": "updated", "updated_endpoints": updated})


@app.route("/api/admin/usage", methods=["GET"])
def admin_usage():
    """Return usage dashboard data: top users and endpoint stats."""
    limit = request.args.get("limit", 10, type=int)
    api_key = request.args.get("api_key")

    stats = advanced_rate_limiter.get_usage_stats(api_key=api_key)
    top_users = advanced_rate_limiter.get_top_users(limit=limit)

    return jsonify({
        "stats": stats,
        "top_users": top_users,
    })


# --- Conversation Summary API endpoints ---

@app.route("/api/session/<session_id>/summary", methods=["GET"])
def session_summary(session_id):
    """?¸ì…˜ ?€???”ì•½??ë°˜í™˜?œë‹¤."""
    summary = conversation_summarizer.summarize_session(session_id)
    if summary is None:
        return jsonify({"error": "?¸ì…˜??ì°¾ì„ ???†ê±°??ë§Œë£Œ?˜ì—ˆ?µë‹ˆ??"}), 404
    return jsonify(summary)


@app.route("/api/admin/sessions/summaries", methods=["GET"])
def admin_sessions_summaries():
    """?¹ì • ? ì§œ???¸ì…˜ ?¼ê´„ ?”ì•½??ë°˜í™˜?œë‹¤."""
    date_str = request.args.get("date", "")
    # Collect all active session IDs
    all_sessions = chatbot.session_manager._sessions
    session_ids = []
    for sid, session in all_sessions.items():
        if date_str:
            session_date = datetime.fromtimestamp(session.created_at).strftime("%Y-%m-%d")
            if session_date == date_str:
                session_ids.append(sid)
        else:
            session_ids.append(sid)
    summaries = conversation_summarizer.summarize_batch(session_ids)
    return jsonify({"date": date_str, "count": len(summaries), "summaries": summaries})


@app.route("/api/admin/sessions/topics", methods=["GET"])
def admin_sessions_topics():
    """?„ì²´ ?¸ì…˜?ì„œ ?ìœ„ ?€??? í”½??ë°˜í™˜?œë‹¤."""
    all_sessions = chatbot.session_manager._sessions
    all_messages = []
    for session in all_sessions.values():
        all_messages.extend(session.history)
    keyword_extractor = conversation_summarizer.keyword_extractor
    topics = keyword_extractor.extract_topics(all_messages)
    return jsonify({"count": len(topics), "topics": topics})


# --- Database Migration API endpoints ---

@app.route("/api/admin/migrations", methods=["GET"])
def admin_migrations_status():
    """Return current migration version and pending migrations."""
    current = migration_manager.get_current_version()
    pending = migration_manager.get_pending_migrations()
    history = migration_manager.get_migration_history()
    validation = migration_manager.validate_migrations()
    return jsonify({
        "current_version": current,
        "pending": [{"version": v, "name": n} for v, n, _ in pending],
        "history": history,
        "valid": validation["valid"],
        "errors": validation["errors"],
    })


@app.route("/api/admin/migrations/apply", methods=["POST"])
def admin_migrations_apply():
    """Apply pending migrations."""
    data = request.get_json(silent=True) or {}
    target_version = data.get("target_version")
    try:
        applied = migration_manager.migrate(target_version=target_version)
        return jsonify({
            "success": True,
            "applied": applied,
            "current_version": migration_manager.get_current_version(),
        })
    except Exception as e:
        logger.error(f"Migration apply failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/migrations/rollback", methods=["POST"])
def admin_migrations_rollback():
    """Rollback the last N migrations."""
    data = request.get_json(silent=True) or {}
    steps = data.get("steps", 1)
    try:
        rolled_back = migration_manager.rollback(steps=steps)
        return jsonify({
            "success": True,
            "rolled_back": rolled_back,
            "current_version": migration_manager.get_current_version(),
        })
    except Exception as e:
        logger.error(f"Migration rollback failed: {e}")
        return jsonify({"error": str(e)}), 500


# --- Health Monitor API endpoints ---


@app.route("/api/admin/health/detailed", methods=["GET"])
def admin_health_detailed():
    """?„ì²´ ?¬ìŠ¤ ë¦¬í¬?¸ë? ë°˜í™˜?œë‹¤."""
    try:
        report = health_monitor.check_all()
        report["system_info"] = health_monitor.get_system_info()
        return jsonify(report)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"error": "?¬ìŠ¤ ì²´í¬ ?¤í–‰ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/health/components", methods=["GET"])
def admin_health_components():
    """ê°œë³„ êµ¬ì„± ?”ì†Œ???íƒœë¥?ë°˜í™˜?œë‹¤."""
    try:
        component = request.args.get("component")
        if component:
            check_map = {
                "database": health_monitor.check_database,
                "faq_data": health_monitor.check_faq_data,
                "disk_space": health_monitor.check_disk_space,
                "memory_usage": health_monitor.check_memory_usage,
                "response_times": health_monitor.check_response_times,
                "error_rate": health_monitor.check_error_rate,
            }
            check_fn = check_map.get(component)
            if not check_fn:
                return jsonify({"error": f"Unknown component: {component}"}), 400
            return jsonify({component: check_fn()})
        report = health_monitor.check_all()
        return jsonify(report["components"])
    except Exception as e:
        logger.error(f"Component health check failed: {e}")
        return jsonify({"error": "êµ¬ì„± ?”ì†Œ ?íƒœ ?•ì¸ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/health-dashboard")
def health_dashboard():
    """?¬ìŠ¤ ëª¨ë‹ˆ?°ë§ ?€?œë³´???˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "health.html")


@app.route("/admin/notifications")
def admin_notifications_page():
    """ê´€ë¦¬ì ?Œë¦¼ ?¼í„° ?˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "notifications.html")


@app.route("/admin/analytics")
def admin_analytics_page():
    """ê´€ë¦¬ì ë¶„ì„ ?€?œë³´???˜ì´ì§€ë¥?ë°˜í™˜?œë‹¤."""
    return send_from_directory(os.path.join(BASE_DIR, "web"), "analytics-dashboard.html")


# ?€?€ A/B Testing API ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

@app.route("/api/admin/ab-tests", methods=["POST"])
@jwt_auth.require_auth()
def create_ab_test():
    """A/B ?ŒìŠ¤?¸ë? ?ì„±?œë‹¤."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "?”ì²­ ë³¸ë¬¸???„ìš”?©ë‹ˆ??"}), 400

    name = data.get("name")
    faq_id = data.get("faq_id")
    variants = data.get("variants")

    try:
        result = ab_test_manager.create_test(name, faq_id, variants)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"A/B ?ŒìŠ¤???ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "A/B ?ŒìŠ¤???ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/ab-tests", methods=["GET"])
@jwt_auth.require_auth()
def list_ab_tests():
    """A/B ?ŒìŠ¤??ëª©ë¡??ë°˜í™˜?œë‹¤."""
    active_only = request.args.get("active_only", "true").lower() == "true"
    try:
        tests = ab_test_manager.list_tests(active_only=active_only)
        return jsonify({"tests": tests, "count": len(tests)})
    except Exception as e:
        logger.error(f"A/B ?ŒìŠ¤??ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "A/B ?ŒìŠ¤??ëª©ë¡ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/ab-tests/<test_id>/results", methods=["GET"])
@jwt_auth.require_auth()
def get_ab_test_results(test_id):
    """A/B ?ŒìŠ¤??ê²°ê³¼ë¥?ë°˜í™˜?œë‹¤."""
    try:
        results = ab_test_manager.get_results(test_id)
        if not results:
            return jsonify({"error": "?ŒìŠ¤?¸ë? ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
        return jsonify(results)
    except Exception as e:
        logger.error(f"A/B ?ŒìŠ¤??ê²°ê³¼ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "A/B ?ŒìŠ¤??ê²°ê³¼ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/ab-tests/<test_id>/stop", methods=["POST"])
@jwt_auth.require_auth()
def stop_ab_test(test_id):
    """A/B ?ŒìŠ¤?¸ë? ì¤‘ì??œë‹¤."""
    try:
        stopped = ab_test_manager.stop_test(test_id)
        if not stopped:
            return jsonify({"error": "?œì„± ?ŒìŠ¤?¸ë? ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
        return jsonify({"success": True, "test_id": test_id})
    except Exception as e:
        logger.error(f"A/B ?ŒìŠ¤??ì¤‘ì? ?¤íŒ¨: {e}")
        return jsonify({"error": "A/B ?ŒìŠ¤??ì¤‘ì? ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/ab-tests/<test_id>/apply-winner", methods=["POST"])
@jwt_auth.require_auth()
def apply_ab_test_winner(test_id):
    """A/B ?ŒìŠ¤???°ìŠ¹ ë³€?•ì„ FAQ???ìš©?œë‹¤."""
    try:
        result = ab_test_manager.apply_winner(test_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"A/B ?ŒìŠ¤???°ìŠ¹ ?ìš© ?¤íŒ¨: {e}")
        return jsonify({"error": "A/B ?ŒìŠ¤???°ìŠ¹ ?ìš© ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/flow/sankey", methods=["GET"])
@jwt_auth.require_auth()
def flow_sankey():
    """Sankey diagram data for conversation flows."""
    try:
        data = flow_analyzer.generate_sankey_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Flow sankey data error: {e}")
        return jsonify({"error": "Failed to generate Sankey data."}), 500


@app.route("/api/admin/flow/paths", methods=["GET"])
@jwt_auth.require_auth()
def flow_paths():
    """Common conversation paths."""
    try:
        top_n = request.args.get("top_n", 10, type=int)
        data = flow_analyzer.get_common_paths(top_n=top_n)
        return jsonify({"paths": data})
    except Exception as e:
        logger.error(f"Flow paths error: {e}")
        return jsonify({"error": "Failed to get conversation paths."}), 500


@app.route("/api/admin/flow/dropoff", methods=["GET"])
@jwt_auth.require_auth()
def flow_dropoff():
    """Drop-off analysis for conversation flows."""
    try:
        data = flow_analyzer.get_drop_off_points()
        return jsonify({"drop_off_points": data})
    except Exception as e:
        logger.error(f"Flow drop-off error: {e}")
        return jsonify({"error": "Failed to get drop-off analysis."}), 500


@app.route("/api/admin/flow/transitions", methods=["GET"])
@jwt_auth.require_auth()
def flow_transitions():
    """Transition matrix for conversation flows."""
    try:
        data = flow_analyzer.get_transition_matrix()
        return jsonify({"transitions": data})
    except Exception as e:
        logger.error(f"Flow transitions error: {e}")
        return jsonify({"error": "Failed to get transition matrix."}), 500


@app.route("/api/admin/sentiment", methods=["GET"])
@jwt_auth.require_auth()
def admin_sentiment_stats():
    """ê°ì • ë¶„ì„ ?µê³„ë¥?ë°˜í™˜?œë‹¤."""
    try:
        session_id = request.args.get("session_id")
        stats = sentiment_analyzer.get_sentiment_stats(session_id=session_id)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"ê°ì • ë¶„ì„ ?µê³„ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ê°ì • ë¶„ì„ ?µê³„ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/sentiment/history", methods=["GET"])
@jwt_auth.require_auth()
def admin_sentiment_history():
    """ê°ì • ë¶„ì„ ?´ë ¥??ë°˜í™˜?œë‹¤."""
    try:
        session_id = request.args.get("session_id")
        limit = request.args.get("limit", 50, type=int)
        history = sentiment_analyzer.get_sentiment_history(session_id=session_id, limit=limit)
        return jsonify({"history": history, "count": len(history)})
    except Exception as e:
        logger.error(f"ê°ì • ë¶„ì„ ?´ë ¥ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ê°ì • ë¶„ì„ ?´ë ¥ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/clusters", methods=["GET"])
@jwt_auth.require_auth()
def admin_clusters():
    """ì§ˆë¬¸ ?´ëŸ¬?¤í„°ë¥?ë°˜í™˜?œë‹¤."""
    try:
        threshold = request.args.get("threshold", 0.5, type=float)
        clusters = question_clusterer.cluster_questions(threshold=threshold)
        stats = question_clusterer.get_cluster_stats()
        return jsonify({"clusters": clusters, "stats": stats})
    except Exception as e:
        logger.error(f"?´ëŸ¬?¤í„° ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?´ëŸ¬?¤í„° ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/duplicates", methods=["GET"])
@jwt_auth.require_auth()
def admin_duplicates():
    """ì¤‘ë³µ ê°ì? ë¦¬í¬?¸ë? ë°˜í™˜?œë‹¤."""
    try:
        report = duplicate_detector.generate_report()
        return jsonify(report)
    except Exception as e:
        logger.error(f"ì¤‘ë³µ ê°ì? ?¤íŒ¨: {e}")
        return jsonify({"error": "ì¤‘ë³µ ê°ì? ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/similar", methods=["GET"])
@jwt_auth.require_auth()
def admin_similar():
    """? ì‚¬ ì§ˆë¬¸??ê²€?‰í•œ??"""
    try:
        query = request.args.get("q", "")
        top_k = request.args.get("top_k", 5, type=int)
        if not query:
            return jsonify({"error": "q ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??"}), 400
        results = question_clusterer.find_similar_to(query, top_k=top_k)
        return jsonify({"query": query, "results": results, "count": len(results)})
    except Exception as e:
        logger.error(f"? ì‚¬ ì§ˆë¬¸ ê²€???¤íŒ¨: {e}")
        return jsonify({"error": "? ì‚¬ ì§ˆë¬¸ ê²€??ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/clusters/refresh", methods=["POST"])
@jwt_auth.require_auth()
def admin_clusters_refresh():
    """?´ëŸ¬?¤í„°ë¥??¬ê³„?°í•œ??"""
    global question_clusterer, duplicate_detector
    try:
        question_clusterer = QuestionClusterer(chatbot.faq_items)
        duplicate_detector = DuplicateDetector(chatbot.faq_items)
        threshold = request.args.get("threshold", 0.5, type=float)
        clusters = question_clusterer.cluster_questions(threshold=threshold)
        stats = question_clusterer.get_cluster_stats()
        return jsonify({"message": "?´ëŸ¬?¤í„°ê°€ ?¬ê³„?°ë˜?ˆìŠµ?ˆë‹¤.", "clusters": clusters, "stats": stats})
    except Exception as e:
        logger.error(f"?´ëŸ¬?¤í„° ?¬ê³„???¤íŒ¨: {e}")
        return jsonify({"error": "?´ëŸ¬?¤í„° ?¬ê³„??ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


# --- Task Scheduler API ---

@app.route("/api/admin/scheduler/tasks", methods=["GET"])
@jwt_auth.require_auth()
def scheduler_list_tasks():
    """?±ë¡???¤ì?ì¤„ëŸ¬ ?‘ì—… ëª©ë¡??ë°˜í™˜?œë‹¤."""
    try:
        tasks = task_scheduler.list_tasks()
        return jsonify({"tasks": tasks, "count": len(tasks)})
    except Exception as e:
        logger.error(f"?¤ì?ì¤„ëŸ¬ ?‘ì—… ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¤ì?ì¤„ëŸ¬ ?‘ì—… ëª©ë¡ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/scheduler/tasks/<name>/run", methods=["POST"])
@jwt_auth.require_auth()
def scheduler_run_task(name):
    """?¤ì?ì¤„ëŸ¬ ?‘ì—…???˜ë™ ?¤í–‰?œë‹¤."""
    try:
        result = task_scheduler.run_task(name)
        return jsonify(result)
    except KeyError:
        return jsonify({"error": f"Task not found: {name}"}), 404
    except Exception as e:
        logger.error(f"?¤ì?ì¤„ëŸ¬ ?‘ì—… ?¤í–‰ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¤ì?ì¤„ëŸ¬ ?‘ì—… ?¤í–‰ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/scheduler/tasks/<name>", methods=["PUT"])
@jwt_auth.require_auth()
def scheduler_update_task(name):
    """?¤ì?ì¤„ëŸ¬ ?‘ì—…???œì„±??ë¹„í™œ?±í™”?œë‹¤."""
    try:
        data = request.get_json() or {}
        if "enabled" in data:
            task_scheduler.set_task_enabled(name, bool(data["enabled"]))
        status = task_scheduler.get_task_status(name)
        return jsonify(status)
    except KeyError:
        return jsonify({"error": f"Task not found: {name}"}), 404
    except Exception as e:
        logger.error(f"?¤ì?ì¤„ëŸ¬ ?‘ì—… ?…ë°?´íŠ¸ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¤ì?ì¤„ëŸ¬ ?‘ì—… ?…ë°?´íŠ¸ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/scheduler/log", methods=["GET"])
@jwt_auth.require_auth()
def scheduler_execution_log():
    """?¤ì?ì¤„ëŸ¬ ?¤í–‰ ?´ë ¥??ë°˜í™˜?œë‹¤."""
    try:
        task_name = request.args.get("task_name")
        limit = request.args.get("limit", 50, type=int)
        logs = task_scheduler.get_execution_log(task_name=task_name, limit=limit)
        return jsonify({"logs": logs, "count": len(logs)})
    except Exception as e:
        logger.error(f"?¤ì?ì¤„ëŸ¬ ?¤í–‰ ?´ë ¥ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¤ì?ì¤„ëŸ¬ ?¤í–‰ ?´ë ¥ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500



# ---------------------------------------------------------------------------
# Knowledge Graph API
# ---------------------------------------------------------------------------


@app.route("/api/admin/knowledge/graph", methods=["GET"])
@jwt_auth.require_auth()
def admin_knowledge_graph():
    """?„ì²´ ì§€??ê·¸ë˜?„ë? ë°˜í™˜?œë‹¤."""
    try:
        data = knowledge_graph.export_graph()
        stats = knowledge_graph.get_graph_stats()
        return jsonify({"graph": data, "stats": stats})
    except Exception as e:
        logger.error(f"ì§€??ê·¸ë˜??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ì§€??ê·¸ë˜??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/knowledge/node/<node_id>", methods=["GET"])
@jwt_auth.require_auth()
def admin_knowledge_node(node_id):
    """?¸ë“œ ?•ë³´ ë°??´ì›ƒ ?¸ë“œë¥?ë°˜í™˜?œë‹¤."""
    try:
        if node_id not in knowledge_graph.nodes:
            return jsonify({"error": f"Node '{node_id}' not found"}), 404
        node = knowledge_graph.nodes[node_id]
        neighbors = knowledge_graph.get_neighbors(node_id, depth=1)
        return jsonify({"node": node, "neighbors": neighbors})
    except Exception as e:
        logger.error(f"?¸ë“œ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¸ë“œ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/knowledge/path", methods=["GET"])
@jwt_auth.require_auth()
def admin_knowledge_path():
    """???¸ë“œ ?¬ì´??ìµœë‹¨ ê²½ë¡œë¥?ë°˜í™˜?œë‹¤."""
    try:
        source = request.args.get("from")
        target = request.args.get("to")
        if not source or not target:
            return jsonify({"error": "'from' and 'to' parameters are required"}), 400
        if source not in knowledge_graph.nodes:
            return jsonify({"error": f"Node '{source}' not found"}), 404
        if target not in knowledge_graph.nodes:
            return jsonify({"error": f"Node '{target}' not found"}), 404
        path = knowledge_graph.find_path(source, target)
        return jsonify({"path": path, "length": len(path)})
    except Exception as e:
        logger.error(f"ê²½ë¡œ ?ìƒ‰ ?¤íŒ¨: {e}")
        return jsonify({"error": "ê²½ë¡œ ?ìƒ‰ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/knowledge/rebuild", methods=["POST"])
@jwt_auth.require_auth()
def admin_knowledge_rebuild():
    """ì§€??ê·¸ë˜?„ë? ?¬êµ¬ì¶•í•œ??"""
    global knowledge_graph
    try:
        knowledge_graph = KnowledgeGraph.build_from_faq(chatbot.faq_items)
        stats = knowledge_graph.get_graph_stats()
        return jsonify({"message": "ì§€??ê·¸ë˜?„ê? ?¬êµ¬ì¶•ë˜?ˆìŠµ?ˆë‹¤.", "stats": stats})
    except Exception as e:
        logger.error(f"ì§€??ê·¸ë˜???¬êµ¬ì¶??¤íŒ¨: {e}")
        return jsonify({"error": "ì§€??ê·¸ë˜???¬êµ¬ì¶?ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/segments", methods=["GET"])
@jwt_auth.require_auth()
def admin_segment_stats():
    """?¬ìš©???¸ê·¸ë¨¼íŠ¸ ë¶„í¬ ?µê³„ë¥?ë°˜í™˜?œë‹¤."""
    try:
        stats = user_segmenter.get_segment_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"?¸ê·¸ë¨¼íŠ¸ ?µê³„ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¸ê·¸ë¨¼íŠ¸ ?µê³„ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/segments/<session_id>", methods=["GET"])
@jwt_auth.require_auth()
def admin_segment_info(session_id):
    """?¹ì • ?¬ìš©?ì˜ ?¸ê·¸ë¨¼íŠ¸ ?•ë³´ë¥?ë°˜í™˜?œë‹¤."""
    try:
        info = user_segmenter.get_segment_info(session_id)
        if info is None:
            return jsonify({"error": "?¸ê·¸ë¨¼íŠ¸ ?•ë³´ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
        return jsonify(info)
    except Exception as e:
        logger.error(f"?¸ê·¸ë¨¼íŠ¸ ?•ë³´ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¸ê·¸ë¨¼íŠ¸ ?•ë³´ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500



# ---- Template Admin API ------------------------------------------------

@app.route('/api/admin/templates', methods=['GET'])
@jwt_auth.require_auth()
def list_templates_api():
    """?±ë¡???œí”Œë¦?ëª©ë¡??ë°˜í™˜?œë‹¤."""
    names = template_engine.list_templates()
    return jsonify({'templates': names, 'count': len(names)})


@app.route('/api/admin/templates', methods=['POST'])
@jwt_auth.require_auth()
def create_template_api():
    """???œí”Œë¦¿ì„ ?±ë¡?œë‹¤."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    tpl_content = data.get('content', '')
    if not name:
        return jsonify({'error': '?œí”Œë¦??´ë¦„???„ìš”?©ë‹ˆ??'}), 400
    if not tpl_content:
        return jsonify({'error': '?œí”Œë¦??´ìš©???„ìš”?©ë‹ˆ??'}), 400
    try:
        template_engine.register_template(name, tpl_content)
        return jsonify({'message': f"?œí”Œë¦?'{name}' ?ì„± ?„ë£Œ.", 'name': name}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/admin/templates/<name>', methods=['PUT'])
@jwt_auth.require_auth()
def update_template_api(name):
    """ê¸°ì¡´ ?œí”Œë¦¿ì„ ?˜ì •?œë‹¤."""
    data = request.get_json(silent=True) or {}
    tpl_content = data.get('content', '')
    if not tpl_content:
        return jsonify({'error': '?œí”Œë¦??´ìš©???„ìš”?©ë‹ˆ??'}), 400
    try:
        template_engine.get_template(name)
    except KeyError:
        return jsonify({'error': f"?œí”Œë¦?'{name}'??ë¥? ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
    template_engine.register_template(name, tpl_content)
    return jsonify({'message': f"?œí”Œë¦?'{name}' ?˜ì • ?„ë£Œ.", 'name': name})


@app.route('/api/admin/templates/<name>', methods=['DELETE'])
@jwt_auth.require_auth()
def delete_template_api(name):
    """?œí”Œë¦¿ì„ ?? œ?œë‹¤."""
    try:
        template_engine.delete_template(name)
        return jsonify({'message': f"?œí”Œë¦?'{name}' ?? œ ?„ë£Œ."})
    except KeyError:
        return jsonify({'error': f"?œí”Œë¦?'{name}'??ë¥? ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404


@app.route('/api/admin/templates/preview', methods=['POST'])
@jwt_auth.require_auth()
def preview_template_api():
    """?œí”Œë¦?ë¯¸ë¦¬ë³´ê¸°ë¥??Œë”ë§í•œ??"""
    data = request.get_json(silent=True) or {}
    template_name = data.get('template_name')
    template_str = data.get('template_str')
    ctx = data.get('context', {})
    if not template_name and not template_str:
        return jsonify({'error': 'template_name ?ëŠ” template_str???„ìš”?©ë‹ˆ??'}), 400
    try:
        if template_str:
            result = template_engine.render_string(template_str, ctx)
        else:
            result = template_engine.render(template_name, ctx)
        return jsonify({'rendered': result})
    except KeyError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ---------------------------------------------------------------------------
# ?„ë©”???¤ì • API
# ---------------------------------------------------------------------------

@app.route("/api/admin/domain", methods=["GET"])
@jwt_auth.require_auth()
def get_domain_config_api():
    """?„ì¬ ?„ë©”???¤ì •??ë°˜í™˜?œë‹¤."""
    if _domain_config.loaded:
        return jsonify(_domain_config.to_dict())
    return jsonify({"error": "?„ë©”???¤ì •??ë¡œë“œ?˜ì? ?Šì•˜?µë‹ˆ??"}), 404


@app.route("/api/admin/domain", methods=["PUT"])
@jwt_auth.require_auth()
def update_domain_config_api():
    """?„ë©”???¤ì •???…ë°?´íŠ¸?œë‹¤."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON ë³¸ë¬¸???„ìš”?©ë‹ˆ??"}), 400
    _domain_config.load_dict(data)
    validation = _domain_config.validate()
    if not validation["valid"]:
        return jsonify({"error": "?¤ì • ê²€ì¦??¤íŒ¨", "details": validation}), 400
    return jsonify({"message": "?„ë©”???¤ì •???…ë°?´íŠ¸?˜ì—ˆ?µë‹ˆ??", "config": _domain_config.to_dict()})


@app.route("/api/admin/domain/validate", methods=["POST"])
@jwt_auth.require_auth()
def validate_domain_config_api():
    """?„ë©”???¤ì •??ê²€ì¦í•œ??"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON ë³¸ë¬¸???„ìš”?©ë‹ˆ??"}), 400
    temp = DomainConfig()
    temp.load_dict(data)
    result = temp.validate()
    return jsonify(result)


@app.route("/api/admin/domain/template", methods=["GET"])
@jwt_auth.require_auth()
def get_domain_template_api():
    """ë¹??„ë©”???œí”Œë¦¿ì„ ë°˜í™˜?œë‹¤."""
    return jsonify(DomainConfig.export_template())


# --- Chart Data API ---
from src.chart_data import ChartDataGenerator
chart_data_gen = ChartDataGenerator(
    logger_db=chat_logger,
    feedback_db=feedback_manager,
    sentiment_analyzer=globals().get("sentiment_analyzer"),
    user_segmenter=globals().get("user_segmenter"),
)


@app.route("/api/admin/charts/categories", methods=["GET"])
@jwt_auth.require_auth()
def chart_categories():
    return jsonify(chart_data_gen.category_distribution())


@app.route("/api/admin/charts/trends", methods=["GET"])
@jwt_auth.require_auth()
def chart_trends():
    metric = request.args.get("metric", "queries")
    days = int(request.args.get("days", 30))
    return jsonify(chart_data_gen.daily_query_trend(days=days))


@app.route("/api/admin/charts/heatmap", methods=["GET"])
@jwt_auth.require_auth()
def chart_heatmap():
    days = int(request.args.get("days", 7))
    return jsonify(chart_data_gen.hourly_heatmap(days=days))


@app.route("/api/admin/charts/dashboard", methods=["GET"])
@jwt_auth.require_auth()
def chart_dashboard():
    charts = {
        "categories": chart_data_gen.category_distribution(),
        "trends": chart_data_gen.daily_query_trend(days=30),
        "heatmap": chart_data_gen.hourly_heatmap(days=7),
        "top_queries": chart_data_gen.top_queries(limit=10),
    }
    return jsonify({"charts": charts})


# ?€?€ Quality Scoring Routes ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€


@app.route("/api/admin/quality/scores", methods=["GET"])
@jwt_auth.require_auth()
def quality_scores_overview():
    """Return comprehensive quality report."""
    try:
        days = int(request.args.get("days", 30))
        report = quality_report.generate(days=days)
        return jsonify(report)
    except Exception as e:
        logger.error(f"Quality scores overview failed: {e}")
        return jsonify({"error": "Failed to generate quality scores."}), 500


@app.route("/api/admin/quality/low", methods=["GET"])
@jwt_auth.require_auth()
def quality_low_responses():
    """Return responses below quality threshold."""
    try:
        threshold = int(request.args.get("threshold", 60))
        low = quality_scorer.get_low_quality_responses(threshold=threshold)
        return jsonify({"threshold": threshold, "count": len(low), "responses": low})
    except Exception as e:
        logger.error(f"Low quality query failed: {e}")
        return jsonify({"error": "Failed to retrieve low quality responses."}), 500


@app.route("/api/admin/quality/trend", methods=["GET"])
@jwt_auth.require_auth()
def quality_trend():
    """Return quality score trend over time."""
    try:
        days = int(request.args.get("days", 30))
        trend = quality_scorer.get_quality_trend(days=days)
        return jsonify({"days": days, "trend": trend})
    except Exception as e:
        logger.error(f"Quality trend query failed: {e}")
        return jsonify({"error": "Failed to retrieve quality trend."}), 500


@app.route("/api/admin/quality/score", methods=["POST"])
@jwt_auth.require_auth()
def quality_score_single():
    """Score a specific Q&A pair."""
    try:
        data = request.get_json(force=True)
        query = data.get("query", "")
        answer = data.get("answer", "")
        category = data.get("category", "")

        if not query or not answer:
            return jsonify({"error": "Both 'query' and 'answer' are required."}), 400

        result = quality_scorer.score_response(query, answer, category)
        suggestions = quality_scorer.suggest_improvements(
            query, answer, result["breakdown"]
        )
        result["suggestions"] = suggestions
        return jsonify(result)
    except Exception as e:
        logger.error(f"Quality scoring failed: {e}")
        return jsonify({"error": "Failed to score response."}), 500


# ?€?€ API v2 Routes ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€


@app.route("/api/versions", methods=["GET"])
def api_versions():
    """List available API versions with their status."""
    versions = api_gateway.get_active_versions()
    return jsonify({"versions": versions})


@app.route("/api/v2/faq", methods=["GET"])
def v2_faq_list():
    """Paginated and sortable FAQ list (v2)."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    sort_by = request.args.get("sort", "id")
    order = request.args.get("order", "asc")

    items = []
    for item in chatbot.faq_items:
        items.append({
            "id": item.get("id", ""),
            "category": item.get("category", ""),
            "question": item.get("question", ""),
        })

    sorted_items = sort_helper.sort_items(items, sort_by, order)
    result = pagination_helper.paginate(sorted_items, page=page, per_page=per_page)

    resp = jsonify(result)
    resp.headers["X-API-Version"] = "v2"
    return api_gateway.add_deprecation_headers(resp, "v2")


@app.route("/api/v2/chat", methods=["POST"])
def v2_chat():
    """Chat endpoint (v2) - same as v1 but response includes API version."""
    client_ip = request.remote_addr or "unknown"
    if not app.config.get("TESTING") and not os.environ.get("TESTING"):
        if not rate_limiter.is_allowed(client_ip):
            return jsonify({"error": "?”ì²­???ˆë¬´ ë§ìŠµ?ˆë‹¤. ? ì‹œ ???¤ì‹œ ?œë„??ì£¼ì„¸??"}), 429

    tenant_id = request.headers.get("X-Tenant-Id", "default")
    tenant = tenant_manager.get_tenant(tenant_id)
    if tenant is None:
        return jsonify({"error": f"?Œë„Œ??'{tenant_id}'ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤."}), 404
    if not tenant.get("active", True):
        return jsonify({"error": f"?Œë„Œ??'{tenant_id}'ê°€ ë¹„í™œ???íƒœ?…ë‹ˆ??"}), 403

    data = request.get_json(silent=True)
    if not data or "query" not in data:
        return jsonify({"error": "query ?„ë“œê°€ ?„ìš”?©ë‹ˆ??"}), 400

    raw_query = data["query"]
    if not isinstance(raw_query, str):
        return jsonify({"error": "query??ë¬¸ì?´ì´?´ì•¼ ?©ë‹ˆ??"}), 400

    query = sanitize_input(raw_query, max_length=MAX_QUERY_LENGTH)
    if not query:
        return jsonify({"error": "ì§ˆë¬¸???…ë ¥??ì£¼ì„¸??"}), 400

    if len(query) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"ì§ˆë¬¸?€ {MAX_QUERY_LENGTH}???´ë‚´ë¡??…ë ¥??ì£¼ì„¸??"}), 400

    categories = classify_query(query)
    escalation = check_escalation(query)
    session_id = data.get("session_id")
    answer = chatbot.process_query(query, session_id=session_id)

    primary_category = categories[0] if categories else "GENERAL"
    is_escalation = escalation is not None

    response_data = {
        "answer": answer,
        "category": primary_category,
        "categories": categories,
        "is_escalation": is_escalation,
        "escalation_target": escalation.get("target") if escalation else None,
        "tenant_id": tenant_id,
        "api_version": "v2",
    }
    if session_id:
        response_data["session_id"] = session_id

    resp = jsonify(response_data)
    resp.headers["X-API-Version"] = "v2"
    return api_gateway.add_deprecation_headers(resp, "v2")


# ?€?€ Conversation Analytics Routes ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€


@app.route("/api/admin/analytics/patterns", methods=["GET"])
@jwt_auth.require_auth()
def admin_analytics_patterns():
    """?ì????€???¨í„´??ë°˜í™˜?œë‹¤."""
    try:
        days = request.args.get("days", 30, type=int)
        patterns = conversation_analytics.detect_patterns(days=days)
        sequences = conversation_analytics.pattern_detector.find_common_sequences()
        pairs = conversation_analytics.pattern_detector.find_question_pairs()
        seasonality = conversation_analytics.pattern_detector.detect_seasonality()
        return jsonify({
            "patterns": patterns,
            "sequences": sequences,
            "pairs": pairs,
            "seasonality": seasonality,
        })
    except Exception as e:
        logger.error(f"?¨í„´ ë¶„ì„ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¨í„´ ë¶„ì„ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/analytics/insights", methods=["GET"])
@jwt_auth.require_auth()
def admin_analytics_insights():
    """?ë™ ?ì„±???¸ì‚¬?´íŠ¸ë¥?ë°˜í™˜?œë‹¤."""
    try:
        days = request.args.get("days", 30, type=int)
        insights = conversation_analytics.generate_insights(days=days)
        return jsonify(insights)
    except Exception as e:
        logger.error(f"?¸ì‚¬?´íŠ¸ ?ì„± ?¤íŒ¨: {e}")
        return jsonify({"error": "?¸ì‚¬?´íŠ¸ ?ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/analytics/metrics", methods=["GET"])
@jwt_auth.require_auth()
def admin_analytics_metrics():
    """ëª¨ë“  ?€??ë¶„ì„ ì§€?œë? ë°˜í™˜?œë‹¤."""
    try:
        metrics = conversation_analytics.get_all_metrics()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"ë¶„ì„ ì§€??ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "ë¶„ì„ ì§€??ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


# --- ?ëŸ¬ ë³µêµ¬ API ?”ë“œ?¬ì¸??---


@app.route("/api/admin/errors", methods=["GET"])
@jwt_auth.require_auth()
def admin_errors():
    """ìµœê·¼ ?ëŸ¬ ëª©ë¡??ë°˜í™˜?œë‹¤."""
    try:
        limit = request.args.get("limit", 50, type=int)
        errors = error_recovery.error_logger.get_recent_errors(limit=limit)
        return jsonify({"errors": errors, "count": len(errors)})
    except Exception as e:
        logger.error(f"?ëŸ¬ ë¡œê·¸ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?ëŸ¬ ë¡œê·¸ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/errors/stats", methods=["GET"])
@jwt_auth.require_auth()
def admin_error_stats():
    """?ëŸ¬ ?µê³„ë¥?ë°˜í™˜?œë‹¤."""
    try:
        stats = error_recovery.get_error_stats()
        rate = error_recovery.error_logger.get_error_rate(minutes=60)
        stats["error_rate"] = rate
        return jsonify(stats)
    except Exception as e:
        logger.error(f"?ëŸ¬ ?µê³„ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?ëŸ¬ ?µê³„ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/admin/circuits", methods=["GET"])
@jwt_auth.require_auth()
def admin_circuits():
    """?œí‚· ë¸Œë ˆ?´ì»¤ ?íƒœë¥?ë°˜í™˜?œë‹¤."""
    try:
        status = error_recovery.get_circuit_status()
        return jsonify({"circuits": status})
    except Exception as e:
        logger.error(f"?œí‚· ë¸Œë ˆ?´ì»¤ ?íƒœ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?œí‚· ë¸Œë ˆ?´ì»¤ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/suggestions", methods=["GET"])
def api_suggestions():
    """?¸ì…˜ ê¸°ë°˜ ë§¥ë½ ?œì•ˆ??ë°˜í™˜?œë‹¤."""
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??"}), 400

    try:
        session_history: list = []
        ctx = chatbot.session_manager.get_context(session_id) if hasattr(chatbot.session_manager, "get_context") else {}
        if isinstance(ctx, dict):
            session_history = ctx.get("queries", [])

        if not session_history:
            suggestions = smart_suggestion_engine.get_onboarding_suggestions()
            return jsonify({"session_id": session_id, "suggestions": suggestions, "type": "onboarding"})

        last_query = session_history[-1]
        category = classify_query(last_query)[0] if last_query else "GENERAL"
        suggestions = smart_suggestion_engine.get_follow_up_suggestions(
            last_query, "", category, session_history=session_history,
        )
        tips = smart_suggestion_engine.get_contextual_tips(category)
        return jsonify({
            "session_id": session_id,
            "suggestions": suggestions,
            "tips": tips,
            "type": "contextual",
        })
    except Exception as e:
        logger.error(f"?œì•ˆ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?œì•ˆ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


@app.route("/api/onboarding", methods=["GET"])
def api_onboarding():
    """???¬ìš©?ë? ?„í•œ ?¨ë³´???œì•ˆ??ë°˜í™˜?œë‹¤."""
    try:
        suggestions = smart_suggestion_engine.get_onboarding_suggestions()
        tips = smart_suggestion_engine.get_contextual_tips("GENERAL")
        return jsonify({"suggestions": suggestions, "tips": tips})
    except Exception as e:
        logger.error(f"?¨ë³´???œì•ˆ ì¡°íšŒ ?¤íŒ¨: {e}")
        return jsonify({"error": "?¨ë³´???œì•ˆ ì¡°íšŒ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤."}), 500


def main():
    parser = argparse.ArgumentParser(description="ë³´ì„¸?„ì‹œ??ì±—ë´‡ ???œë²„")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = pa
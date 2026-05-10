"""Phase 1: Repository 단위 테스트."""

import asyncio
import pytest
from app.repositories.base import AsyncDBPool
from app.repositories.chat_log_repo import ChatLogRepository
from app.repositories.feedback_repo import FeedbackRepository
from app.repositories.faq_repo import FAQRepository


@pytest.fixture
async def chat_pool():
    pool = AsyncDBPool(":memory:")
    await pool.connect()
    repo = ChatLogRepository(pool)
    await repo.init_table()
    yield repo, pool
    await pool.close()


@pytest.fixture
async def feedback_pool():
    pool = AsyncDBPool(":memory:")
    await pool.connect()
    repo = FeedbackRepository(pool)
    await repo.init_table()
    yield repo, pool
    await pool.close()


@pytest.mark.asyncio
async def test_chat_log_insert_and_stats(chat_pool):
    repo, _ = chat_pool
    rid = await repo.log_query("테스트 질문", category="GENERAL", faq_id="A")
    assert rid > 0
    stats = await repo.get_stats()
    assert stats["total_queries"] == 1
    assert stats["escalation_rate"] == 0.0


@pytest.mark.asyncio
async def test_chat_log_escalation(chat_pool):
    repo, _ = chat_pool
    await repo.log_query("긴급 질문", is_escalation=True)
    stats = await repo.get_stats()
    assert stats["escalation_rate"] == 1.0


@pytest.mark.asyncio
async def test_feedback_save(feedback_pool):
    repo, _ = feedback_pool
    fid = await repo.save_feedback("qid-001", "helpful", "좋아요")
    assert fid > 0
    stats = await repo.get_stats()
    assert stats["satisfaction_rate"] == 1.0


@pytest.mark.asyncio
async def test_feedback_invalid_rating(feedback_pool):
    repo, _ = feedback_pool
    with pytest.raises(ValueError, match="rating"):
        await repo.save_feedback("qid-002", "meh")


@pytest.mark.asyncio
async def test_faq_repo_load():
    repo = FAQRepository("data/faq.json")
    await repo.load()
    items = repo.list_all()
    assert len(items) >= 50
    assert repo.count >= 50
    assert repo.version != ""
    assert repo.corpus_hash != ""
    first = items[0]
    assert "id" in first and "question" in first and "answer" in first


@pytest.mark.asyncio
async def test_faq_repo_get_by_id():
    repo = FAQRepository("data/faq.json")
    await repo.load()
    item = repo.get_by_id("A")
    assert item is not None
    assert item["category"] == "GENERAL"

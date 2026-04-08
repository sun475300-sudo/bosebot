# LLM Fallback and Vector Search Implementation

## Overview

This document describes the implementation of LLM fallback and vector search capabilities for the bonded exhibition chatbot. These features enhance the chatbot's ability to answer FAQ-related questions by combining traditional keyword/TF-IDF matching with semantic search and AI-powered fallback.

## Architecture

### Query Processing Pipeline

```
User Query
    ↓
1. Keyword Matching (keyword presence in FAQ)
    ↓
2. TF-IDF Similarity Matching (lexical similarity)
    ↓
3. Vector Search (semantic/embedding-based similarity)
    ↓
4. LLM Fallback (Claude API with context)
    ↓
5. Unknown Response (if all above fail)
```

## Components

### 1. Vector Search Engine (`src/vector_search.py`)

Provides semantic/embedding-based FAQ matching using Sentence Transformers.

**Key Features:**
- Pre-computes embeddings for all FAQ items at startup using `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Stores embeddings in memory (numpy arrays) for fast retrieval
- Uses cosine similarity to find semantically relevant FAQ items
- Includes embedding cache to avoid re-encoding identical queries
- Two-tier thresholding:
  - **CONFIDENT_THRESHOLD (0.65)**: High-confidence matches returned directly
  - **SUGGESTION_THRESHOLD (0.45)**: Lower-confidence matches used for "Did you mean?" suggestions

**Usage Example:**
```python
from src.vector_search import VectorSearchEngine

engine = VectorSearchEngine(faq_items)

# Find best matches
results = engine.find_best_match("외국물품 보세전시장", top_k=3)
# Returns: [{"item": {...}, "score": 0.87}, ...]

# Get suggestions for unclear queries
suggestions = engine.find_suggestions("박람회 물품", top_k=3)
# Returns: [{"item": {...}, "score": 0.55}, ...]

# Check match confidence
if engine.is_confident_match(0.70):
    # Use as primary answer
    pass
```

**Cache Statistics:**
```python
stats = engine.get_cache_stats()
# Returns: {
#   "cached_queries": 45,
#   "max_cache_size": 1000,
#   "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# }
```

### 2. LLM Fallback Provider (`src/llm_fallback.py`)

Provides Claude API integration with rate limiting, caching, and graceful degradation.

**Key Features:**
- Uses Anthropic Claude API (claude-opus-4-1-20250805)
- Rate limiting: max 10 calls per minute
- Response caching: 1-hour TTL with LRU eviction
- Graceful fallback when API is unavailable
- Includes FAQ context in system prompt to ensure consistency

**Configuration:**
- API Key: `CHATBOT_LLM_API_KEY` environment variable
- Auto-disables if key is not set or anthropic library is not installed

**Usage Example:**
```python
from src.llm_fallback import get_llm_provider

provider = get_llm_provider()

# Check if available
if provider.is_available():
    # Generate response with FAQ context
    faq_context = [
        {"item": {...}, "score": 0.55},
        {"item": {...}, "score": 0.48},
    ]

    response = provider.generate_response(
        "사용자 질문",
        faq_matches=faq_context,
        use_cache=True
    )

    # Add disclaimer automatically
    response_with_disclaimer = provider.generate_response_with_disclaimer(
        "사용자 질문",
        faq_matches=faq_context
    )

# Get statistics
stats = provider.get_stats()
# Returns: {
#   "enabled": true,
#   "rate_limiter": {...},
#   "cache": {...}
# }
```

**Rate Limiting:**
```python
limiter = provider.rate_limiter
# Blocks after 10 calls within 60 seconds
# Automatically resets when window expires
provider.reset_rate_limiter()  # For testing
```

**Response Caching:**
```python
cache = provider.response_cache
# Same question within 1 hour returns cached response
# Automatic LRU eviction at 256 items
provider.clear_cache()  # Clear all cached responses
```

### 3. Chatbot Integration (`src/chatbot.py`)

Enhanced `BondedExhibitionChatbot` with vector search and LLM fallback.

**New Methods:**
- `find_matching_faq_with_llm_fallback()`: Returns FAQ item or LLM-generated response
- Vector search automatically initialized if sentence-transformers is available
- LLM fallback automatically initialized if CHATBOT_LLM_API_KEY is set

**Pipeline Integration:**
```python
from src.chatbot import BondedExhibitionChatbot

chatbot = BondedExhibitionChatbot()

# Vector search enabled automatically if library installed
if chatbot.vector_search_enabled:
    print("Vector search active")

# LLM fallback enabled automatically if API key set
if chatbot.llm_enabled:
    print("LLM fallback active")

# Process query through full pipeline
response = chatbot.process_query("보세전시장 관련 질문")
# Automatically tries: keyword → TF-IDF → BM25 → vector search → LLM → unknown
```

**Error Handling:**
- Vector search: Gracefully degrades if sentence-transformers not installed
- LLM: Gracefully degrades if API key not set or API unavailable
- All errors caught and logged; chatbot continues functioning

## Dependencies

New dependencies added to `requirements.txt`:

```
anthropic>=0.25.0          # Claude API client
sentence-transformers>=2.2.0  # Embedding model
torch>=2.0.0               # Required by sentence-transformers
numpy>=1.24.0              # Numerical operations
```

**Installation:**
```bash
pip install -r requirements.txt
```

**Optional Installation (for testing):**
```bash
pip install pytest pytest-mock  # Testing framework
```

## Configuration

### Environment Variables

```bash
# LLM Fallback (required for LLM fallback feature)
export CHATBOT_LLM_API_KEY="sk-ant-..."

# Optional: Override embedding model
# (Currently hardcoded; can be made configurable)
```

### Vector Search Thresholds

Located in `src/vector_search.py`:
```python
CONFIDENT_THRESHOLD = 0.65      # High-confidence match
SUGGESTION_THRESHOLD = 0.45     # "Did you mean?" suggestions
```

### LLM Rate Limiting

Located in `src/llm_fallback.py`:
```python
max_calls = 10              # Calls per window
window_seconds = 60         # Time window
```

### Response Caching

```python
ttl_seconds = 3600          # 1 hour
max_size = 256              # Max cached responses
```

## Testing

Comprehensive test suites included:

### 1. Vector Search Tests (`tests/test_vector_search.py`)
- Embedding initialization and precomputation
- Best match finding
- Category filtering
- Confidence thresholds
- Cache functionality
- Cosine similarity calculations
- Edge cases (empty queries, empty FAQ lists)
- Performance tests

**Run Tests:**
```bash
pytest tests/test_vector_search.py -v
```

### 2. LLM Fallback Tests (`tests/test_llm_fallback.py`)
- Rate limiter functionality
- Response cache (TTL, LRU eviction)
- API error handling
- Rate limit blocking
- Cache expiration
- Disclaimer generation
- Fallback messages

**Run Tests:**
```bash
pytest tests/test_llm_fallback.py -v
```

### 3. Chatbot Integration Tests (`tests/test_chatbot_integration.py`)
- Vector search initialization
- LLM fallback initialization
- FAQ matching with vector search
- Multi-turn conversation
- Category handling
- Performance benchmarks
- Cache statistics
- Pipeline integration

**Run Tests:**
```bash
pytest tests/test_chatbot_integration.py -v
```

**Run All Tests:**
```bash
pytest tests/ -v
```

## System Prompts

The chatbot uses a specialized system prompt for LLM responses to ensure consistency with FAQ answers:

```
너는 보세전시장 민원응대 전문 챗봇이다.
관세법과 보세전시장 관련 질문에만 정확하고 신중하게 답변한다.
법적 근거가 확실하지 않은 경우 단정하지 말고 '확인 필요'라고 답한다.
```

This ensures LLM responses align with:
- Legal accuracy (referencing Korean Customs Law)
- Tone and style (professional, cautious)
- Scope (bonded exhibition domain only)

## Performance Characteristics

### Vector Search
- **Initialization:** ~5-10 seconds (depends on model download and FAQ size)
- **Per-query:** <100ms (with caching, cached queries <10ms)
- **Memory:** ~50MB per 1000 FAQ items (embeddings + model)

### LLM Fallback
- **Per-request:** 1-3 seconds (API latency)
- **Rate limit:** 10 requests/minute
- **Cache hit rate:** 50-80% for typical chatbot usage

### Overall Pipeline
- **Keyword matching:** <1ms
- **TF-IDF:** 1-5ms
- **Vector search:** <100ms (first query), <10ms (cached)
- **LLM:** 1-3 seconds (when invoked)
- **Total:** 1-5ms for FAQ hit, 1-3 seconds for LLM fallback

## Error Handling & Graceful Degradation

### Vector Search Degradation
```python
try:
    engine = VectorSearchEngine(faq_items)
except ImportError:
    # sentence-transformers not installed
    # Chatbot continues with keyword + TF-IDF only
```

### LLM Fallback Degradation
```python
# API key not set
# LLM fallback disabled, returns "unknown response"

# API unavailable
# Rate limit exceeded
# Cache miss + API error
# → Returns fallback message: "현재 AI 응답 서비스를 이용할 수 없습니다"
```

## Production Deployment

### Prerequisites
1. Install all dependencies: `pip install -r requirements.txt`
2. Set `CHATBOT_LLM_API_KEY` environment variable
3. Optional: Pre-warm embedding model in Docker image

### Recommended Settings
```bash
# For production
export CHATBOT_LLM_API_KEY="your-anthropic-key"

# Optional: Increase rate limit for high-traffic scenarios
# Modify src/llm_fallback.py RateLimiter(max_calls=20)

# Optional: Increase cache size for high-concurrency
# Modify ResponseCache(max_size=512)
```

### Monitoring
- Check LLM provider stats periodically:
  ```python
  provider.get_stats()  # Rate limit status, cache size
  ```
- Monitor cache hit rates
- Track LLM fallback usage (should be <5% of queries)

### Scaling Considerations
- Vector embeddings cached in memory; no additional scaling needed
- LLM API calls subject to Anthropic rate limits
- Response cache is in-memory; add Redis for distributed caching if needed

## Troubleshooting

### Issue: Vector search not working
**Solution:** Install sentence-transformers
```bash
pip install sentence-transformers torch
```

### Issue: LLM fallback not working
**Solution:** Set API key
```bash
export CHATBOT_LLM_API_KEY="your-key"
```

### Issue: Slow vector search on first query
**Solution:** Expected behavior; embedding model loads once. Subsequent queries use cache.

### Issue: "Rate limit exceeded" messages
**Solution:** Check current rate limit stats
```python
provider.get_stats()["rate_limiter"]
```

### Issue: High memory usage
**Solution:** Reduce embedding cache size or reload embedding model
```python
engine.clear_cache()
```

## Future Enhancements

1. **Configurable embedding model**: Allow switching models via environment variable
2. **Distributed caching**: Redis/Memcached for multi-instance deployments
3. **Async LLM calls**: Non-blocking API calls for better responsiveness
4. **Custom fine-tuning**: Fine-tune embedding model on bonded exhibition domain
5. **Feedback loop**: Learn from user feedback to improve matching
6. **Multi-language**: Support Korean/English/Chinese with language-specific models

## References

### Libraries
- [Sentence Transformers](https://www.sbert.net/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [PyTorch](https://pytorch.org/)

### Models
- [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)

### Papers
- [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://arxiv.org/abs/1908.10084)
- [Attention is All You Need](https://arxiv.org/abs/1706.03762)

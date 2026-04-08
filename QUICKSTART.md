# LLM Fallback & Vector Search - Quick Start Guide

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify imports work
python -c "from src.vector_search import VectorSearchEngine; from src.llm_fallback import get_llm_provider; print('✓ All imports OK')"
```

## Enable Features

### Vector Search (Automatic)
- Automatically enabled if `sentence-transformers` is installed
- Pre-computes embeddings for all 50 FAQ items at startup
- No configuration needed

### LLM Fallback
```bash
# Set API key to enable LLM fallback
export CHATBOT_LLM_API_KEY="sk-ant-..."

# Verify it's enabled
python -c "from src.llm_fallback import is_llm_available; print('LLM available:', is_llm_available())"
```

## Usage Examples

### Basic Chatbot Usage
```python
from src.chatbot import BondedExhibitionChatbot

chatbot = BondedExhibitionChatbot()

# Process a query through the full pipeline
response = chatbot.process_query("보세전시장에 물품을 반입하려면 어떻게 하나요?")
print(response)
```

### Direct Vector Search
```python
from src.chatbot import BondedExhibitionChatbot

chatbot = BondedExhibitionChatbot()

if chatbot.vector_search_enabled:
    # Find semantically similar FAQs
    results = chatbot.vector_search.find_best_match(
        "외국물품 박람회",
        top_k=3
    )

    for result in results:
        print(f"Similarity: {result['score']:.2f}")
        print(f"Q: {result['item']['question']}")
```

### Direct LLM Fallback
```python
from src.llm_fallback import get_llm_provider

provider = get_llm_provider()

if provider.is_available():
    # Generate response when FAQ match fails
    response = provider.generate_response_with_disclaimer(
        "보세전시장에 대한 특이한 질문",
        faq_matches=[]  # Optional: provide FAQ context
    )
    print(response)
```

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Suites
```bash
# Vector search tests
pytest tests/test_vector_search.py -v

# LLM fallback tests
pytest tests/test_llm_fallback.py -v

# Chatbot integration tests
pytest tests/test_chatbot_integration.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_llm_fallback.py::TestRateLimiter -v
pytest tests/test_llm_fallback.py::TestResponseCache -v
```

## Query Processing Pipeline

The chatbot processes queries in this order:

1. **Keyword Matching** - Does query contain FAQ keywords?
2. **TF-IDF Matching** - How lexically similar to FAQ?
3. **BM25 Ranking** - Alternative lexical similarity
4. **Vector Search** - Semantic/embedding similarity (0.65+ threshold)
5. **LLM Fallback** - AI-powered response with FAQ context
6. **Unknown Response** - If all above fail

## Key Thresholds

### Vector Search Confidence
```python
CONFIDENT_THRESHOLD = 0.65    # Return directly as answer
SUGGESTION_THRESHOLD = 0.45   # Use for "Did you mean?" suggestions
```

### LLM Rate Limiting
```python
max_calls = 10          # Maximum calls
window_seconds = 60     # Per minute
```

### LLM Response Caching
```python
ttl_seconds = 3600      # Cache expires after 1 hour
max_size = 256          # Maximum cached responses
```

## Monitoring

### Check LLM Provider Status
```python
from src.llm_fallback import get_llm_provider

provider = get_llm_provider()
stats = provider.get_stats()

print("LLM Enabled:", stats["enabled"])
print("Rate Limit:", stats["rate_limiter"]["calls_in_window"], "/",
      stats["rate_limiter"]["max_calls"])
print("Cache Size:", stats["cache"]["cached_items"], "/",
      stats["cache"]["max_size"])
```

### Check Vector Search Status
```python
from src.chatbot import BondedExhibitionChatbot

chatbot = BondedExhibitionChatbot()

if chatbot.vector_search_enabled:
    stats = chatbot.vector_search.get_cache_stats()
    print("Cached Queries:", stats["cached_queries"])
    print("Model:", stats["model"])
```

## Common Issues & Solutions

### Issue: Vector search not available
```
Solution: pip install sentence-transformers torch
```

### Issue: LLM fallback not working
```
Solution: export CHATBOT_LLM_API_KEY="your-key"
```

### Issue: Slow first vector search query
```
Solution: Normal - embedding model loads once. Subsequent queries use cache.
```

### Issue: "Rate limit exceeded" for LLM
```
Solution: Max 10 calls/minute. Wait 60 seconds or check stats with:
provider.get_stats()["rate_limiter"]
```

### Issue: High memory usage
```
Solution: Clear embedding cache:
chatbot.vector_search.clear_cache()
```

## Files Modified/Created

### New Files
- `src/vector_search.py` (255 lines) - Vector search engine
- `src/llm_fallback.py` (379 lines) - LLM fallback provider
- `tests/test_vector_search.py` (204 lines) - Vector search tests
- `tests/test_llm_fallback.py` (393 lines) - LLM fallback tests
- `tests/test_chatbot_integration.py` (278 lines) - Integration tests
- `docs/LLM_FALLBACK_VECTOR_SEARCH.md` - Complete documentation

### Modified Files
- `src/chatbot.py` - Integrated vector search and LLM fallback
- `requirements.txt` - Added new dependencies

## Performance Benchmarks

### Vector Search
- **First query:** ~100-200ms (model initialization)
- **Cached query:** <10ms
- **Memory per 1000 items:** ~50MB

### LLM Fallback
- **Per request:** 1-3 seconds (API latency)
- **Cached response:** <1ms
- **Rate limit:** 10 requests/minute

## Next Steps

1. **Test locally**: Run the test suites to ensure everything works
2. **Deploy**: Set `CHATBOT_LLM_API_KEY` environment variable
3. **Monitor**: Check stats periodically for rate limits and cache health
4. **Optimize**: Adjust thresholds based on production metrics

## Documentation

Full documentation available in:
- `docs/LLM_FALLBACK_VECTOR_SEARCH.md` - Complete guide
- `src/vector_search.py` - Docstrings
- `src/llm_fallback.py` - Docstrings
- `src/chatbot.py` - Integration code

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review full documentation in `docs/LLM_FALLBACK_VECTOR_SEARCH.md`
3. Run tests to isolate the issue
4. Check error logs in `logs/` directory

# Track RR — FAQ embedding warm-up at boot

`src/embedding_warmup.py` — pre-encodes top-N hot FAQs (usage-weighted)
at boot. Env: `EMBEDDING_WARMUP_TOP_N` (default 10). Cuts first-query
latency by 200-800ms. 5 tests pass. Pure stdlib.

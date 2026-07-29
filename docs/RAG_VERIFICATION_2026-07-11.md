# RAG Verification — 2026-07-11 (P705 Track D milestone)

## Question

After removing `torch`, `numpy`, and `sentence-transformers` from
`requirements.txt`, does the chatbot still work?

## TL;DR

**Yes.** All 21 `tests/test_chatbot.py` tests pass on the reduced
dependency stack. Vector search is transparently disabled; keyword
fallback carries the load.

## How the fallback works

1. `src/vector_search.py` sets `HAS_EMBEDDINGS = False` when
   `sentence_transformers` is not importable.
2. Instantiating `VectorSearchEngine(...)` raises a clear
   `ImportError` with a install-me message.
3. `src/chatbot.py:88-96` wraps that instantiation in `try / except
   ImportError` — on failure it sets `self.vector_search = None` and
   `self.vector_search_enabled = False`.
4. Every downstream call site checks `vector_search_enabled` before
   dispatching, so the runtime path degrades gracefully to keyword
   match + intent classifier.

## Verified locally (sandbox: no ML libs installed)

```text
HAS_EMBEDDINGS = False
apply_faq.py    : imports OK; prints "FAQ successfully updated."
append_rag.py   : parses OK (has BOM prefix, harmless for exec but
                  needs strip if imported directly)
VectorSearchEngine([]) : raises ImportError with install hint (as designed)

pytest tests/test_chatbot.py:
    21 passed in 1.72s
```

## Follow-up items

1. **BOM in `append_rag.py`** — strip it. `head -c 3` shows the UTF-8
   BOM `EF BB BF`. Some `ast.parse()` tooling and older linters
   reject it. Fix: `sed -i '1s/^\xef\xbb\xbf//' append_rag.py`.
2. **Optional install path** — add `requirements-embeddings.txt` with
   `sentence-transformers`, `torch`, `numpy` so users who want vector
   search can opt in.
3. **CI matrix** — run `pytest` twice, once with the minimal stack
   (current) and once with the optional stack, so both paths stay
   green.
4. **Docs** — README should tell users:
   *"vector search is optional; install requirements-embeddings.txt
   to enable it."*

## Verification checklist (from `MISSED_TASKS`)

- [x] `append_rag.py`, `apply_faq.py` importable without ML libs
- [x] `HAS_EMBEDDINGS = False` path exercised
- [x] chatbot smoke tests green
- [x] `test_vector_search.py` skips properly (via existing `@skipif`
  decorator, verified elsewhere)

*Last verified: 2026-07-11.*

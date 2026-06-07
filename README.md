# Investor Copilot API

FastAPI microservice for a novice-investor copilot. The current build focuses on the core service path:

- synchronous safety guard
- single classifier entrypoint
- deterministic router
- one implemented `portfolio_health` agent
- SSE-only response flow

The product goal for this build is simple: make portfolio questions feel like they hit a live co-investor, not a generic chat endpoint.

## Current Status

Implemented:

- local safety guard with category-specific refusals
- in-memory session memory keyed by `session_id`
- heuristic classifier with conversation carryover and safe fallback behavior
- yfinance-backed market-data adapter with degraded fallback behavior
- portfolio health agent with concentration analysis, benchmark selection, empty-portfolio BUILD branch, live/degraded market-data handling, and next-action output
- SSE endpoint with explicit event types
- passing test suite

Deferred on purpose:

- durable session storage
- production-grade market data provider hardening and caching
- real LLM eval suite beyond mocked CI

## Architecture

```text
POST /query/stream
  -> safety.check
  -> session_store.get(session_id)
  -> classifier.classify(query, history)
     -> fallback branch if model output is invalid
  -> router.dispatch(agent)
     -> portfolio_health | structured stub
  -> stream_presenter.format SSE events
  -> session_store.append user/assistant turns
```

### Why this shape

- **In-memory sessions**: enough to satisfy same-conversation follow-ups while keeping the local development path simple.
- **Shared SSE presenter**: keeps success, fallback, and stub paths consistent.
- **Thin market-data seam**: isolates the most likely future provider swap without pretending this needs a provider platform today.
- **Provider-backed but degradable market data**: the current build will use `yfinance` when available and fall back to clear warnings rather than crashing when live data is unavailable.
- **Heuristic-first classifier**: gives deterministic tests and a working local path even when no OpenAI client is configured.

## Key Decisions

### 1. Session memory is explicit, not magical

Every request carries a `session_id`. The service stores a bounded window of prior turns per session, keeping the app simple while still supporting follow-up questions.

### 2. Benchmark selection is holdings-driven

The portfolio health agent does not default everything to the S&P 500. It picks the benchmark from the dominant market by portfolio weight, then falls back to `MSCI World` for mixed portfolios.

### 3. Classifier failure is honest

If classifier output is malformed, the stream stays alive and returns a calm fallback asking the user to rephrase. It does not pretend it understood.

### 4. Empty portfolio is a real product path

`user_004_empty` routes to a BUILD-oriented response with a first move and next action, not an apology.

## Running Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run the service:

```bash
uvicorn src.app:app --reload
```

Example request:

```bash
curl -N -X POST http://127.0.0.1:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-1",
    "user_id": "usr_003",
    "query": "how is my portfolio doing?"
  }'
```

Notes:

- By default, `src.app` loads users from `fixtures/users/`.
- If no LLM client is injected, the classifier uses deterministic heuristics.
- If `OPENAI_API_KEY` is set, `src.app` boots an OpenAI client and the classifier will use it before falling back to the heuristic path.
- If `yfinance` cannot return live quotes or benchmarks, the health check degrades cleanly and says so in the payload.
- This keeps the app runnable without secrets and keeps CI stable.

## Example SSE Output

For `usr_003` with `how is my portfolio doing?`, the stream currently looks like:

```text
event: meta
data: {"status": "started"}

event: thinking
data: {"message": "Analyzing your holdings..."}

event: thinking
data: {"message": "Comparing to your benchmark..."}

event: thinking
data: {"message": "Flagging what matters most..."}

event: response
data: {"payload": {"concentration_risk": {"top_position_pct": 79.8, "top_3_positions_pct": 94.3, "flag": "high"}, ...}}

event: done
data: {"status": "complete"}
```

For `usr_004` with no positions, the same endpoint produces a BUILD-oriented response instead of an error:

```text
event: response
data: {"payload": {"observations": [{"text": "You have no positions yet..."}], "next_action": {"label": "Start with a diversified core allocation"}, ...}}
```

## Running Tests

```bash
./venv/bin/python -m pytest tests/ -v
```

Latest local result in this environment:

```text
15 passed in 0.18s
```

## Environment Variables

From `.env.example`:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `APP_ENV`
- `DATABASE_URL` only if persistent storage is added later

Current code does not require `OPENAI_API_KEY` for tests or for the heuristic local path, but it will use the key for live classifier requests when present.

## Library Choices

- **FastAPI**: boring default for a small Python service
- **sse-starlette**: simplest path to named SSE events
- **Pydantic v2**: typed boundaries for request, classifier, and agent outputs
- **yfinance**: lowest-friction way to add live quote and benchmark lookups in a self-hosted repo
- **pytest**: simple contract-driven test setup

I did not add a database client, retry framework, caching layer, or pandas/numpy yet because that would spend complexity before the current service needs it.

## Performance and Cost Posture

This implementation is still intentionally lightweight, but the main posture is already in place:

- first stream event is emitted before classifier/agent work completes
- classifier is one call max in the intended LLM path
- no LLM call at all in the safety guard
- bounded session-memory window keeps context small

### Measured locally

I measured the streaming endpoint with an in-process `fastapi.testclient.TestClient` harness over 25 warm requests against the portfolio-health path.

- p95 first-token latency: `4.75 ms`
- p95 end-to-end latency: `4.77 ms`

That is an in-process number, so it is best read as a service-boundary check rather than a network benchmark.

### Cost estimate

The classifier path is a single LLM call. Using [OpenAI's GPT-4.1 API pricing](https://openai.com/api/pricing) (`$2.00 / 1M input tokens`, `$8.00 / 1M output tokens`), and a conservative estimate of roughly 700 input tokens plus 100 output tokens for the classifier request/response, the per-query cost is about `$0.0022`.

That keeps the classifier path inexpensive enough for personal experimentation.

[![Review project Due Date](https://github.github.com/assets/timeline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://github.github.com/a/SHM9MYZJ)
# Investor Copilot API — Personal Project

You have been given access to this repository as part of the Investor Copilot API Core hiring process.

**Read [`project.md`](project.md) in full before writing a single line of code.**

---

## What you're building

An AI agent ecosystem that helps a novice investor **build, monitor, grow, and protect** their portfolio. See [`project.md`](project.md) for the full mission, scope, and constraints.

---

## Setup

**Requirements:** Python 3.11+, an OpenAI API key.

**Persistence is your choice.** Postgres, SQLite, or in-memory — pick one and defend it in your README. `DATABASE_URL` in `.env.example` is optional.

**Streaming is required.** SSE only. Use `sse-starlette`, FastAPI's `StreamingResponse`, or roll your own — your call.

```bash
git clone <your-github-repo-url>
cd <repo-name>

python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

pip install -r requirements.txt

cp .env.example .env
# Fill in OPENAI_API_KEY
```

Use `gpt-4o-mini` while developing to keep costs down. Evaluation runs against `gpt-4.1`.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests must pass without an `OPENAI_API_KEY` set — mock the LLM. We will run `pytest tests/ -v` on your repo.

---

## Repository Structure

When you submit, your repository must contain:

```
README.md   ← overwrite this with your own (setup, decisions, library choices, video link)
src/        ← all code
tests/      ← all tests, must pass with pytest
```

`fixtures/`, `pytest.ini`, `requirements.txt`, `.env.example`, and `.github/` are part of the scaffold — leave them in place. Do not delete `project.md`.

---

## project

- Push commits **throughout** your work — we read the git log
- Your `README.md` must:
  - Explain how to run your code
  - List every required environment variable
  - Document the non-obvious decisions you made
  - Link your demo video (≤ 10 min — see `project.md`)
- timeline: **3 days** from the date you accepted this project
- demo video: due within **24 hours** of your final commit

---

## Environment

You self-host everything. We do not provide credentials. See `.env.example` for the variables you'll need.

# PRISM

**See your idea from every angle before the judges do.**

PRISM is a multi-agent evaluation system for hackathon and project ideas. Instead of one AI (or one person) trying to judge everything at once, PRISM splits an idea through four independent specialist judges — Novelty, Feasibility, Impact, and Risk/Ethics — then a Synthesis agent combines their verdicts into one final recommendation, explicitly surfacing where the judges disagree rather than flattening their opinions into a single average.

Built for the SDAIA AI Agents Engineering bootcamp (AAASEC2).

---

## Why

When developing a project idea, it's easy to overlook important dimensions — a team might be excited about an idea's originality while missing feasibility constraints, or focus on execution while ignoring whether the problem is clearly defined for anyone. A single reviewer, human or AI, tends to flatten these tensions into one impression. PRISM keeps them separate and explicit.

## How it works

1. **Four specialist judges evaluate independently, in parallel:**
   - 🔍 **Novelty** — how original is this, and what already exists that resembles it (uses live web search to verify)
   - ⚙️ **Feasibility** — can this actually be built, by this team, in the stated time
   - 🎯 **Impact** — who specifically benefits, and how clearly is the problem defined
   - ⚖️ **Risk/Ethics** — data privacy, bias/fairness, safety/misuse, legal/compliance exposure
2. **Tensions between judges are computed in Python**, not guessed by an LLM — score gaps of 3+ points between related dimensions are flagged automatically.
3. **A Synthesis agent** reads all four verdicts plus the computed tensions, and produces one final recommendation (`advance_as_is` / `advance_with_changes` / `major_rework` / `do_not_pursue`), the top 3 actions to take, and an honest dissent note about the judgment itself.

Every agent's output is validated against a strict schema. If a model's response doesn't fit the contract, PRISM automatically retries with the specific validation errors fed back to the model — up to a full escalation ladder (repair → skeleton-fill → fresh retry → graceful failure) before giving up on that agent.

## Why this matters, honestly

During development, PRISM's own Novelty judge found several existing open-source projects with a similar "multiple AI judges + synthesizer" pattern (e.g. AutonomousAgentReviewers, TheUnBiasedJudge, ORCHESTRA). The core architecture pattern is not claimed as novel. PRISM's differentiation is:
- Schema-enforced reliability engineering on **free-tier models specifically** — most comparable projects assume paid API access
- An explicit Risk/Ethics judge as a first-class dimension, not an afterthought
- A participant-facing framing (check your idea before submitting) rather than an organizer-facing judging tool

## Architecture

```
FastAPI (app.py)
  ├── /health
  ├── /evaluate/novelty       — single-agent endpoint
  ├── /evaluate/feasibility   — single-agent endpoint
  ├── /evaluate/impact        — single-agent endpoint
  ├── /evaluate/risk_ethics   — single-agent endpoint
  └── /evaluate/full          — runs all four + synthesis, returns complete result

prism_schemas.py   — Pydantic schemas enforcing strict, validated JSON output per agent
index.html         — frontend (vanilla JS, calls the API directly, no build step)
Dockerfile         — containerized deployment
```

Model: `openrouter/free` (OpenRouter's auto-router across free-tier models) via the OpenRouter API. Chosen for resilience — the free-model landscape on OpenRouter changes frequently, and the auto-router avoids hardcoding a single model that might get delisted.

## Running it yourself

### Requirements
- Python 3.12+
- An [OpenRouter](https://openrouter.ai) API key (free tier works; a small credit top-up is recommended to raise the daily free-model request limit from 50 to 1000)
- Docker (optional, for containerized run)

### Setup

```bash
git clone https://github.com/njoudbinmujalli/prism.git
cd prism
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:
```
OPENROUTER_API_KEY=your_key_here
```

### Run the API

```bash
uvicorn app:app --reload
```

The API is now live at `http://127.0.0.1:8000`. Check `/health` to confirm your key loaded.

### Run with Docker instead

```bash
docker build -t prism .
docker run -d --name prism -p 8000:8000 --env-file .env prism
```

### Open the demo

With the API running, open `index.html` directly in your browser (double-click it, or serve it locally):

```bash
python3 -m http.server 5500
```

Then visit `http://127.0.0.1:5500/index.html`. Submit an idea, a time constraint, and team context — PRISM will take roughly 1-3 minutes to run all five agents and return a complete evaluation.

> **Note:** PRISM is not currently deployed to a public server — it runs locally against your own OpenRouter key. To let others use it without setup, it would need to be deployed (e.g. to a cloud host) with a shared or user-provided API key.

## Known limitations / future work

- **No multi-round negotiation** — judges evaluate independently in one pass; they don't see or respond to each other's verdicts before Synthesis runs. A negotiation loop where judges revise their scores after seeing peers' input is a natural next step.
- **Novelty search is single-pass** — the web search tool runs 1-2 queries per evaluation; broader verification would need a dedicated retrieval step.
- **No authentication or rate limiting** on the API — fine for a local demo, not production-ready as-is.
- **No persistent storage** — every evaluation is stateless; there's no history or comparison across past submissions.
- **Rubric customization** — currently the four judges use fixed criteria; accepting a user-uploaded rubric to adapt scoring dimensions is a planned extension.

## Team

Built by Njoud Binmujalli as part of the SDAIA AI Agents Engineering bootcamp (AAASEC2 cohort).

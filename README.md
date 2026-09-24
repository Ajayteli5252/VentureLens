# Multi-Agent Startup Idea Validator

A 7-agent CrewAI system that validates a business idea through parallel
research, a debate/cross-verification step, and a final investor-style verdict.

## Setup

1. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # Mac/Linux
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your real keys:
   ```
   cp .env.example .env
   ```
   - `OPENAI_API_KEY` (or your provider's key — update `MODEL_NAME` in `agents.py` accordingly)
   - `SERPER_API_KEY` from https://serper.dev (free tier)

## Run

**Quick command-line test:**
```
python crew.py
```

**Full Streamlit demo:**
```
streamlit run app.py
```

## Project Structure

```
startup-idea-validator/
├── agents.py         # All 7 agent definitions
├── tasks.py          # Task descriptions + expected outputs
├── crew.py           # Assembles the crew, hierarchical process
├── app.py            # Streamlit UI
├── tools/
│   └── search_tool.py
├── requirements.txt
└── .env.example
```

## Notes on the Free Tier

- `max_rpm=4` is set in `crew.py` to stay under Gemini's free-tier limit of 5 requests/minute.
  This makes a full run slower (roughly 2-3 minutes) since CrewAI paces its calls — this
  is expected, not a bug.
- If you see a `429 RESOURCE_EXHAUSTED` error anyway, wait ~60 seconds before retrying
  (the free tier's per-minute counter resets every minute).

## Architecture

```
User Idea → Coordinator Agent (manager)
    → Market / Competitor / Financial / Risk agents (parallel research)
    → Comparator/Debate Agent (resolves conflicting findings)
    → Investor-Verdict Agent (final score + Go/No-Go)
    → Report shown to user
```

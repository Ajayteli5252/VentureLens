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

**1. FastAPI Backend:**
```bash
uvicorn api:app --reload --port 8000
```

**2. React Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Quick command-line test:**
```bash
python crew.py
```

## Project Structure

```
startup-idea-validator/
├── agents.py         # All 7 agent definitions
├── tasks.py          # Task descriptions + expected outputs
├── crew.py           # Assembles the full 7-agent hierarchical crew
├── followup.py       # Fast follow-up question router & single-agent executor
├── api.py            # FastAPI REST API (initial validation + fast follow-ups)
├── frontend/         # React + Vite web UI
├── tools/
│   └── search_tool.py
├── requirements.txt
└── .env.example
```

## Architecture

**1. Initial Idea Validation (Full 7-Agent Pipeline):**
```
User Idea → Coordinator Agent (manager)
    → Market / Competitor / Financial / Risk agents (parallel research)
    → Comparator/Debate Agent (resolves conflicting findings)
    → Investor-Verdict Agent (final score + Go/No-Go)
    → Report & Score displayed to user
```

**2. Follow-Up Question Flow (Fast Single-Agent Execution):**
```
User Follow-up Question
    → Question Router / Classifier
    → Selected Specialist Agent ONLY (Market, Competitor, Financial, or Risk)
    → Direct focused answer with clickable sources (No debate, no verdict re-scoring)
```

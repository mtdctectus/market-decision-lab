# market-decision-lab

Market Decision Lab is a research-oriented decision-support tool for evaluating whether market conditions look reasonable for a strategy-based investment hypothesis.

> This tool is for research and education only.
> It does **not** execute live trades and is **not** financial advice.

## Core output
The application answers one question:

**"Is it reasonable to invest in this market under the selected conditions?"**

It produces a final label:
- **INVEST**: at least one scenario is robust under thresholds.
- **CAUTION**: mixed results; risk controls are required.
- **NO**: all tested scenarios are weak or too risky.

### Color coding
- 🟢 **GREEN**: strong metrics and acceptable risk.
- 🟡 **YELLOW**: mixed quality / moderate risk.
- 🔴 **RED**: fails key return, drawdown, or sample-size thresholds.

## Monorepo layout
- `app/` Streamlit UI
- `core/` reusable strategy, metrics, decision, scenarios, and storage logic
- `data/` SQLite database and cache directory

## Deploy on Streamlit Cloud
1. Push this repository to GitHub.
2. In Streamlit Cloud, create a new app from this repo.
3. Set main file path to:
   - `app/streamlit_app.py`
4. Deploy.

Dependencies are provided in the root `requirements.txt`, which Streamlit Cloud installs automatically.

## Local run
```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Project context (RU)
If you collaborate with ChatGPT/Codex across multiple chats, drop these into your workflow:
- `PROJECT_CONTEXT_RU.md` — copy-paste project context for a new chat
- `CODEX_PROMPT_RU.md` — strict instructions for Codex/ChatGPT to audit and patch the repo

# Codex / ChatGPT — strict instructions for Market Decision Lab

You are working inside the **market-decision-lab** repository (Streamlit monorepo).

## Goal
Maintain a **stable Streamlit Cloud deployment** and evolve the app without unnecessary complexity.

## Checklist before any change
1) Inspect repository structure and entry point: `app/streamlit_app.py`.
2) Verify `requirements.txt` (root) for import coverage.
3) Verify that data/SQLite paths are stable and correct.
4) Ensure code does not depend on local-only files missing from the repo.

## Implementation rules
- Fix issues **in code**, not with advice only.
- If an error is reproducible from logic/static checks, fix it immediately.
- Keep the project simple: minimize new files and dependencies.
- Streamlit Cloud first: everything should work after `git push`.

## Definition of Done
- App starts without errors.
- Quick/Compare/History tabs work.
- SQLite database is created at `data/app.db`.
- No hardcoded secrets.
- Any optimization must preserve existing functionality.

## Response format
1) What you checked
2) What is wrong (exact files and lines)
3) Fix (diff or full file)
4) Final result: how to run and what to verify

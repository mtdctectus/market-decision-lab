# ARCHITECTURE

## Purpose
Market Decision Lab is a **research-only decision support** project. It does **not** execute live trades and does **not** provide financial advice.

## Repository Layout
- `app/` = Streamlit UI only (presentation and user interaction).
- `src/mdl/` = reusable engine package (`mdl`) for decision logic, strategies, data, and backtesting.
- `tools/` = CLI and development utilities.

## Layering Rules
- `app/` may import from `mdl.*`.
- `mdl/` must not import `streamlit` or anything from `app/*`.
- Do not use `sys.path` modifications or import hacks; use standard package imports only.

## Public API Contract
Treat the following as stable public surface:
- `mdl.__version__`
- `mdl.decision`, `mdl.scenarios`
- `mdl.strategies` registry surface: `STRATEGIES`, `generate_candidates`

## Extension Guidelines
### Add a New Strategy
1. Implement strategy logic in `src/mdl/strategies/` (new module or existing family module).
2. Keep it reusable and UI-agnostic.
3. Register it in `src/mdl/strategies/__init__.py` by adding a `StrategySpec` entry to `STRATEGIES`.
4. Ensure candidate generation works through `generate_candidates`.

### Add a New Data Source
1. Add loader code under `src/mdl/data/`.
2. Keep source-specific details in `mdl.data` and expose clean function interfaces.
3. Keep `app/` clean: UI should call engine APIs, not own data-fetch business logic.

### Backtest and Lab Modules
- Keep `mdl.backtest` and `mdl.lab` reusable, deterministic where practical, and independent from Streamlit/UI concerns.
- Prefer pure functions and explicit inputs/outputs so logic is testable outside the app.

## Versioning (SemVer)
- **MAJOR**: incompatible API or behavior changes in public `mdl` contracts.
- **MINOR**: backward-compatible feature additions (new strategy, new optional API).
- **PATCH**: backward-compatible fixes, docs, and internal improvements.

When in doubt, bump conservatively and document user-visible implications.

## Quality Bar
- Repository code/docs/comments must remain English-only.
- Keep changes minimal and focused; avoid broad refactors unless requested.
- Do not add dependencies unless clearly justified.
- Always run compile checks (at minimum `python -m compileall src/mdl`).

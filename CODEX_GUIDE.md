# CODEX_GUIDE

## Non-Negotiable Rules for Codex
- Use English-only code, docs, comments, and commit/PR text.
- Preserve existing behavior unless explicitly asked to change it.
- Do not introduce `sys.path` hacks or non-standard imports.
- Do not move files or refactor architecture unless explicitly requested.
- `app/` is UI-only; new domain/business logic belongs in `src/mdl/`.
- Avoid adding runtime dependencies unless explicitly justified and requested.

## Guard Prompt (Paste at the Top of Every Codex Task)
```text
Guard rails for this task:
- English-only changes.
- No behavior/UI/business-logic changes unless explicitly requested.
- No new runtime dependencies.
- No sys.path hacks; use package imports.
- Do not move files or refactor architecture unless asked.
- app/ remains UI-only; new logic goes in src/mdl/.
- Run: python -m compileall src/mdl
```

## Common Task Templates

### Add a New Strategy
- Add implementation under `src/mdl/strategies/`.
- Register strategy in `src/mdl/strategies/__init__.py` (`STRATEGIES`, candidate compatibility).
- Keep UI unchanged unless explicitly requested.
- Constraints: no behavior changes outside scope, no new deps, run `python -m compileall src/mdl`.

### Add a New Data Loader
- Add loader under `src/mdl/data/` with clean function boundaries.
- Wire usage through `mdl` package interfaces, not direct UI-side data logic.
- Keep `app/` presentation-only.
- Constraints: no unrelated behavior changes, no new deps, run `python -m compileall src/mdl`.

### Small Refactor / Typing Cleanup
- Keep refactor narrow and behavior-preserving.
- Prefer clarity, typing improvements, and dead-code cleanup within current architecture.
- Do not move modules unless asked.
- Constraints: no behavior change, no new deps, run `python -m compileall src/mdl`.

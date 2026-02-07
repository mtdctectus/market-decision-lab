# CONTRIBUTING

Thanks for contributing to Market Decision Lab.

## Local setup
```bash
pip install -e .
```

## Run the app
```bash
streamlit run app/streamlit_app.py
```

## Smoke and compile checks
```bash
python -m compileall src/mdl
python tools/smoke_check.py
```

If `tools/smoke_check.py` is unavailable in your branch, run at least the compile check.

## Contribution rules
- Respect layering: `app/` is UI-only; reusable logic belongs in `src/mdl/`.
- Use English-only code, docs, comments, and PR text.
- Do not add runtime dependencies unless clearly justified.
- Do not introduce `sys.path` hacks; use package imports.
- Keep PRs small, focused, and behavior-preserving unless a behavior change is explicitly requested.

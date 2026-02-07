# PR_CHECKLIST

- [ ] Layering respected (`app/` UI vs `src/mdl/` engine).
- [ ] No `sys.path` hacks introduced.
- [ ] No new runtime dependencies.
- [ ] English-only changes.
- [ ] `python -m compileall src/mdl` passes.
- [ ] Streamlit app starts (`streamlit run app/streamlit_app.py`).
- [ ] Imports use the `mdl` package (standard package imports).

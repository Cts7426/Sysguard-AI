# Contributing

Use Python 3.12 and uv. Read README.md and docs/architecture.md before changing
module boundaries. Run `uv sync --dev`; never commit `.venv`.

Keep pull requests focused. Explain observable behavior, rationale, and
verification. Add deterministic tests for behavior changes and reproduce bugs
before fixing them. Unit tests must not depend on current host processes or
wall-clock sleeps. Use temporary SQLite databases. Real-host tests belong in
integration tests with the `live` marker.

Before submitting:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv build
```

Use `uv run ruff format .` to format and `uv add` / `uv add --dev` for dependency
changes, reviewing and committing `uv.lock`. Keep full type hints in production
code. Preserve domain/adapter boundaries and nullable metrics. Add a documented,
versioned migration before changing the schema; never silently reshape an
existing database.

Do not commit credentials, captures, databases, datasets, models, compiled files,
or large binaries. Inspect `git status` and staged diffs before committing.
Sanitize bug reports and include OS, Python version, commands, expected behavior,
and actual errors. The current milestone is Phase 0–1; ML, APIs, dashboards, and
background services are outside its scope.

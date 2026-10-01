# Phase 0–1 verification report

Verified on 2026-09-19, Windows, CPython 3.12.10, uv 0.12.7, Git 2.51.2.
Initial repository contained only .git, no commits, code, README, or AGENTS.md.
The default Python was 3.14; uv selected the existing Python 3.12 installation.

## Commands and results

| Command | Observed result |
| --- | --- |
| `uv sync --dev` | 17 packages resolved/checked successfully |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 23 Python files already formatted |
| `uv run mypy` | No issues in 12 source files |
| `uv run pytest` | 38 passed, 96% total statement coverage |
| `uv run sysguard snapshot` | Valid JSON, 375 process rows in the final capture |
| `uv run sysguard collect --duration 10 --interval 2` | Completed, 2 snapshots in the final run |
| `uv run sysguard status` | 3 system samples, 1128 process rows, 2 completed sessions across smoke runs |
| `uv run sysguard samples --limit 5` | Returned all 3 stored samples, newest first |
| `uv build` | Built source distribution and wheel |

Snapshot stdout was redirected to ignored `data/snapshot.json`. The first
redirection attempt failed because data/ did not yet exist; after collect
created it, the complete snapshot command succeeded. The initial unoptimized
collection had only one snapshot; grouping reads with psutil.oneshot improved
the final run to two. Profiling before that optimization measured 10.85 seconds
per snapshot for 374 processes, dominated by Windows psutil calls.

Additional checks: SQLite integrity_check returned `ok`; foreign_key_check was
empty; 375 stored process observations have measured CPU percentages. The built
wheel contains `sysguard/storage/migrations/001_initial.sql`. Git ignore checks
cover database, snapshot capture, virtual environment, coverage, and wheel.
No commits or pushes were made. Git status shows only source/config/docs/tests
and the lockfile as new content. This sandbox reports a warning when Git tries
to read the user's global ignore file; local ignore rules were verified directly.

Actual final collect output:

```json
{
  "session_id": "e91aa49a-fe07-43a0-a67e-905c3e212aed",
  "sample_count": 2,
  "status": "completed"
}
```

## Tests and review

Tests cover collector conversion, nullable denied/unsupported values, disappearing
and zombie processes, PID reuse, first CPU baselines, CLI validation and JSON,
SQLite round trips, FK enforcement, duplicate rollback, rollback during
KeyboardInterrupt, schema rejection, deadlines, slow readers, stop events,
interrupt/failure session finalization, long waits, and tiny finite intervals.
One marked live test uses the host; unit tests do not depend on its process list.

Independent review identified two scheduler defects, reproduced as failing tests:
unbounded Event.wait on Windows/Python 3.12 and overflow from tiny positive
intervals. Fixes use <=200 ms waits and remainder-based scheduling. The final
suite passed after these fixes and the oneshot optimization.

GitHub Actions has Windows/Ubuntu jobs but was not executed remotely in this
session. Linux and manual keyboard Ctrl+C were not directly verified; injected
KeyboardInterrupt, bounded waits, stop events, and transaction rollback were tested.

## Created file inventory

```text
.github/workflows/ci.yml
.gitignore
.python-version
CONTRIBUTING.md
LICENSE
README.md
pyproject.toml
uv.lock
docs/architecture.md
docs/implementation-plan.md
docs/verification.md
docs/decisions/0001-sqlite.md
src/sysguard/__init__.py
src/sysguard/cli.py
src/sysguard/config.py
src/sysguard/domain/__init__.py
src/sysguard/domain/models.py
src/sysguard/domain/ports.py
src/sysguard/collectors/__init__.py
src/sysguard/collectors/psutil_collector.py
src/sysguard/storage/__init__.py
src/sysguard/storage/sqlite.py
src/sysguard/storage/migrations/001_initial.sql
src/sysguard/services/__init__.py
src/sysguard/services/collection.py
tests/conftest.py
tests/unit/test_cli.py
tests/unit/test_collector.py
tests/unit/test_service.py
tests/integration/test_live_collector.py
tests/integration/test_storage.py
```

Ignored generated artifacts: .venv/, caches, .coverage, data/ captures/database,
and dist/ packages. No pre-existing user files were overwritten.

## Remaining limits and Phase 2

The 2-second interval is not achievable on this host with a full process scan.
Missed ticks are skipped, and in-flight reads can exceed the requested duration.
First CPU observations are null. Unknown identities cannot form histories.
No retention/encryption, hard real-time guarantee, or force-kill session cleanup.

For Phase 2, start with bounded CPU, memory-growth, and I/O scenarios; save
scenario metadata and expected windows outside Git. Derive counter rates and
rolling-window features with explicit missingness and reset handling. Establish
interpretable thresholds, persistence windows, and false-positive measurements
before training any model. Keep train/evaluation sessions separate to avoid leakage.

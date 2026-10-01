# Phase 0–1 implementation plan

Goal: a readable Python 3.12 repository and Windows-compatible metrics CLI;
no ML, dashboard, service, or network endpoint in this phase.

## Design summary

Use immutable domain dataclasses, a psutil collector, a SQLite repository,
and an orchestration service connected by structural Protocol interfaces.
The CLI uses argparse and emits JSON for reproducible inspection.
SQLite stores sessions, system samples, and process samples in one transaction
per snapshot. No ORM is needed for three tables; JSON-only storage would make
identity and time queries harder. SQLite is the selected middle ground.

Process identity is (pid, create_time). Unavailable metrics are null; unknown
identities must not be merged. CPU is a delta measurement; first observations
are null. Collection starts immediately, uses monotonic deadlines, skips missed
ticks, and finishes sessions on interruption. Each snapshot is best-effort,
not an atomic operating-system view.

## Implementation and acceptance

- [x] Foundation: pyproject, Python pin, uv lock, src layout, ignore rules.
- [x] Collector: write deterministic fake-psutil tests, observe failures,
  implement mapping, nullable fields, disappearing processes and PID reuse.
  Files: domain/models.py, collectors/psutil_collector.py, tests/unit/test_collector.py.
- [x] Storage: write temporary SQLite tests for round trips, FK enforcement,
  rollback and schema version. Implement storage/sqlite.py and migrations/001_initial.sql.
- [x] Service and CLI: tests for finite positive options, deadlines, stop events,
  interrupt and session failure; implement config.py, domain/ports.py,
  services/collection.py and cli.py.
- [x] Documentation and CI: architecture, schema ADR, README, contribution guide,
  MIT license; Windows and Linux jobs with locked uv sync, Ruff, mypy and pytest.
- [x] Verify all user acceptance commands, actual SQLite contents, git ignore
  rules, package build and full test suite. Record actual results.

Test contracts: snapshot() -> Snapshot; start_session(duration, interval) -> str;
save_snapshot(session_id, snapshot) -> int; finish_session(session_id, status) -> None;
collect(collector, store, options, stop, clock) -> CollectionResult.

Review focus: non-finite input, PID reuse during reads, missing CPU baselines,
transaction interruption, collector slower than interval. Tests belong to the
collector, storage, or service responsible for each behavior.

Ruling: the user's explicit instruction to continue without a real blocker
supersedes skill approval handoffs. Work directly in the empty requested folder;
no existing changes or commits can be overwritten. No automatic commit/push.

Execution notes: initial test run failed on missing domain implementation.
The first implemented suite had 30 passes and one incorrect deadline expectation:
an in-flight synchronous snapshot can finish after the deadline. The assertion
was corrected to bound that overrun by snapshot cost, preserving sample counts.
Independent review found long Windows waits and subnormal-interval arithmetic;
both were reproduced as failing tests and fixed. Profiling showed slow Windows
process queries; oneshot reduced duplicate OS reads. See verification.md for
final commands, measured results, and remaining performance limits.

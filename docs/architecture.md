# Architecture: Phase 0–1

## Purpose and boundaries

Collect measurements for future OS/ML experiments, without detecting anomalies
or labeling processes as malicious. Windows 11 is the development target;
portable psutil calls isolate OS differences.

| Layer | Responsibility | Dependencies |
| --- | --- | --- |
| domain/models.py | Immutable measurements, identities, query results | Standard library |
| domain/ports.py | Collector and SampleStore contracts | Domain |
| collectors/psutil_collector.py | Translate observations into nullable models | psutil, domain |
| storage/sqlite.py | Schema, transactions, queries | sqlite3, domain |
| services/collection.py | Lifecycle and monotonic scheduling | Protocols, config |
| cli.py | Parse inputs, construct adapters, serialize output | Adapters, service |

Replace storage by implementing SampleStore or the OS adapter by implementing
Collector; neither changes the loop. No placeholder ML or dashboard modules.

## Snapshot semantics

A snapshot has a UTC start timestamp and observed processes. Unknown, denied,
or unsupported fields are null. AccessDenied is handled per field; NoSuchProcess
and ZombieProcess discard that process. Unexpected bugs propagate visibly.

Fresh psutil objects avoid cached identities across iterations. An is_running
check after reads rejects detected disappearance or PID reuse. This is a
best-effort defense, not an atomic guarantee. Missing creation time means unknown
identity, even when PID is known.

System CPU uses psutil's nonblocking interval calculation and discards the first
reading. Process CPU tracks cumulative user+system seconds against monotonic
elapsed time by (pid, create_time). First observations, missing identities, or
counter resets yield null; absent identities are evicted each snapshot. Process
CPU can exceed 100%. I/O preserves cumulative counter semantics; sizes are bytes.
See psutil's [API documentation](https://psutil.readthedocs.io/stable/) for CPU
initialization, process_iter caching, and process identity checks.

## Collection lifecycle

1. Validate finite positive duration/interval and persist a running session.
2. Sample immediately, committing the complete snapshot as one transaction.
3. Use monotonic deadlines and skip missed ticks; avoid catch-up bursts.
4. Wait via Event.wait in at most 200 ms slices, allowing Windows/Python 3.12
   to process KeyboardInterrupt even with very long requested intervals.
5. Finalize as completed, interrupted, or failed; propagate unexpected errors.

No snapshot starts at/after the deadline, but an in-flight read/write can finish
later. Python KeyboardInterrupt rolls back unfinished transactions; prior
commits survive. Force-kill cannot finalize metadata reliably, so a persisted
running status is not proof of a live collector.

## Storage and testing

See [ADR 0001](decisions/0001-sqlite.md). One connection per command, WAL, foreign
keys, and a five-second lock timeout. Install schema 1 atomically; reject unknown
versions. CLI context managers own connections. Data paths are local and ignored.

Fake psutil objects test field conversion, permissions, and races. Fake clocks
test schedules without sleeping. Temporary real SQLite tests cover persistence,
constraints, rollback, and identity. One live test checks stable host invariants.
Future features should derive rates/windows separately, record missingness and
scenario metadata, and compare a rule baseline before adding ML.

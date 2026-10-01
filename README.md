# SysGuard AI

A local system and process metrics collector built to learn operating systems
and the foundations of a complete machine learning system. **There is no ML
model or anomaly detection in the current release.**

## Problem and current scope

CPU spikes, memory growth, and unusual I/O are difficult to understand without
a history of measurements. SysGuard records that history before attempting to
classify it. Phase 0–1 provides a Python repository, CLI, psutil collector,
SQLite persistence, tests, and CI. It targets Windows 11 and keeps OS-specific
behavior behind a replaceable adapter for future Linux use.

## Architecture

```text
CLI (argparse)
    -> Collection service -> Collector protocol <- PsutilCollector
                          -> SampleStore protocol <- SQLiteStore
                 immutable domain models
```

The domain does not import psutil; the service does not import SQLite. See
[architecture](docs/architecture.md), [schema decision](docs/decisions/0001-sqlite.md),
and [implementation plan](docs/implementation-plan.md).

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
From the cloned repository directory, run:

```powershell
uv python install 3.12
uv sync --dev
uv run sysguard snapshot
uv run sysguard collect --duration 30 --interval 2
uv run sysguard status
uv run sysguard samples --limit 10
```

The same commands work in a Linux shell. `.python-version` selects Python 3.12;
the project currently requires Python 3.12.x. Activation is unnecessary with
`uv run`. Commit `uv.lock` for reproducible dependencies; CI uses
`uv sync --locked --dev`. Ordinary user permissions suffice: inaccessible
fields become JSON `null` / SQL `NULL`.

## CLI examples

| Command | Behavior |
| --- | --- |
| `snapshot` | Print system and process metrics as JSON; do not save. |
| `collect --duration 30 --interval 2` | Start immediately, save periodically, print session summary. |
| `status` | Print path, counts, latest UTC time, average CPU and peak memory %. |
| `samples --limit 10` | Print recent system samples, newest first. |

Persistent commands accept `--db PATH` **after the command**:

```powershell
uv run sysguard collect --duration 10 --interval 2 --db data/demo.sqlite3
uv run sysguard status --db data/demo.sqlite3
uv run sysguard samples --limit 5 --db data/demo.sqlite3
uv run sysguard --help
```

The default is `data/sysguard.sqlite3`, relative to the working directory.
Use an explicit path when running from different directories. `status` and
`samples` initialize an empty database if the file does not exist.
Duration and interval must be finite positive seconds; limits must be positive
integers. Ctrl+C finalizes collection and returns exit code 130. Other expected
CLI errors return 1; invalid arguments return 2.

Illustrative output (IDs and counts depend on the run):

```json
{
  "session_id": "0e2db722-2276-4600-880c-01a9462d93bb",
  "sample_count": 5,
  "status": "completed"
}
```

Read process rows through the repository API or SQL:

```python
from pathlib import Path
from sysguard.storage.sqlite import SQLiteStore

with SQLiteStore(Path("data/sysguard.sqlite3")) as store:
    for sample in store.samples(1):
        for process in store.process_samples(sample.id):
            print(process.identity, process.name, process.rss)
```

## Metrics and interpretation

- System: UTC timestamp, CPU %, total/available memory bytes, memory %, cumulative
  disk read/write bytes, network sent/received bytes, and observed process count.
- Process: PID, creation time (Unix seconds), name, executable path, parent PID,
  status, CPU %, RSS/VMS bytes, thread count, cumulative disk read/write bytes,
  and username. Missing fields are null, never replaced with zero.
- Identity is `(pid, create_time)`. Without creation time, identity is unknown;
  those observations cannot safely be joined into a process history.
- CPU needs two observations. The first system reading and every new process's
  first CPU reading are null. Standalone `snapshot` therefore has null CPU
  percentages. Subsequent `collect` samples contain measured deltas.
- Process CPU is user + system CPU time divided by monotonic elapsed time;
  multithreaded processes can exceed 100%. It is not normalized by core count.
- I/O values are cumulative counters, **not bytes per second**. Future features
  must compute deltas and handle resets/restarts before deriving rates.

## Testing

```powershell
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run pytest -m "not live"
uv run pytest --cov-report=html
uv build
```

Unit tests use fake process data and clocks. SQLite tests use temporary files;
one marked `live` test checks stable invariants on the real host. GitHub Actions
runs lint, format, strict type checking, tests, and packaging on Windows and
Ubuntu. Generated databases, reports, builds, datasets, and models are Git-ignored.

## Roadmap

1. **Phase 0–1 (current):** repository foundations and collector MVP.
2. **Phase 2:** bounded workload scenarios, dataset metadata/labels, time-window
   features, and an interpretable CPU/memory/I/O rule baseline.
3. **Later:** evaluate ML detectors against the baseline, explain findings,
   and consider API/dashboard work after measurement quality is established.

## Current limitations

Snapshots are sequential best-effort reads, not atomic system views. Short-lived
processes may be missed; disappeared/reused processes are discarded. Process
count and collected row count may differ. Metrics vary by OS and permission;
Windows VMS should not be assumed equivalent to Linux VMS. Missed schedule ticks
are skipped; no new snapshot starts after the deadline, but an in-flight read or
transaction can finish later. Ctrl+C is cooperative at Python interruption
points; scheduler waits are bounded to 200 ms, but OS calls may take longer.
Force-kill/power loss can leave a session marked `running`; SQLite protects
committed data. Multiple collectors are not a supported workflow. No retention,
compression, encryption, or background service is included; long runs grow the
local database. CPU averages exclude nulls and are not time-weighted.
Linux CI is configured; local verification was performed on Windows.
On the development host with about 375 processes, the 10-second/2-second smoke
run produced two snapshots because complete process reads exceeded the requested
interval. Treat the interval as a scheduling target, not a throughput guarantee.

## Privacy note

**Process names, executable paths, and usernames may contain sensitive data.**
Data stays local; this application has no telemetry or upload feature. Inspect
databases and terminal output before sharing, including in issues and portfolio
examples. Never commit raw captures, datasets, or environment files.

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [MIT](LICENSE).

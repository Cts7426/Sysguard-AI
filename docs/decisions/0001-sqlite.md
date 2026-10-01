# ADR 0001: SQLite snapshots and process identities

Status: accepted for Phase 0–1.

Use stdlib SQLite and package resource `001_initial.sql`, with user_version 1.
Create new schemas transactionally, reuse version 1, reject unknown versions,
and require explicit upgrade migrations for future schema changes.

- collection_sessions: UUID key, UTC start/end, duration, interval, status.
- system_samples: integer key, session FK, UTC ISO 8601 time, nullable metrics.
- process_samples: integer key, sample FK, PID, nullable Unix creation time,
  nullable metadata/metrics. UNIQUE(sample_id, pid) prevents duplicate PID rows
  in one snapshot, without making PID a global identity.

Foreign keys cascade on parent deletion. Indexes cover timestamp,
session+timestamp, PID+create_time, and process parent sample. Process timestamps
and sessions come from joins. Unknown creation times must never be grouped into
process histories; known identity always uses both PID and creation time.

Commit the system row and all process rows together. Reuse one connection and
executemany. WAL supports concurrent readers; one collection writer is the
supported workflow. No global process table is necessary: metadata changes and
unknown identities cannot safely be upserted.

CSV/JSON simplify export but weaken relational queries and partial-write
recovery. An ORM/external database adds unnecessary setup for three tables.
SQLite supports offline operation, with limited write concurrency and future
migration/retention work. Byte counters use signed 64-bit integers; counters
exceeding that range would need a schema change.

Stored names, paths, and usernames are sensitive. Ignore databases and journals,
review/sanitize exports, and keep captures outside Git.

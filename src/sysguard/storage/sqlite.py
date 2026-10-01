"""One connection per repository; one atomic transaction per snapshot."""

import sqlite3
from dataclasses import astuple
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from sysguard.domain.models import ProcessSample, Snapshot, StoredSample, StoreStatus, SystemSample


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=5)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                migration = (
                    files("sysguard.storage").joinpath("migrations/001_initial.sql").read_text()
                )
                self._conn.executescript(
                    "BEGIN IMMEDIATE;\n" + migration + "\nPRAGMA user_version = 1;\nCOMMIT;"
                )
            elif version != 1:
                raise ValueError(f"Unsupported database schema version: {version}")
        except BaseException:
            self._conn.close()
            raise

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._conn.close()

    def start_session(self, duration: float, interval: float) -> str:
        session_id = str(uuid4())
        with self._conn:
            self._conn.execute(
                "INSERT INTO collection_sessions VALUES (?, ?, NULL, ?, ?, 'running')",
                (session_id, datetime.now(UTC).isoformat(), duration, interval),
            )
        return session_id

    def finish_session(self, session_id: str, status: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE collection_sessions SET ended_at = ?, status = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), status, session_id),
            )

    def save_snapshot(self, session_id: str, snapshot: Snapshot) -> int:
        with self._conn:
            values = astuple(snapshot.system)
            cursor = self._conn.execute(
                "INSERT INTO system_samples (session_id, timestamp, cpu_percent, memory_total, "
                "memory_available, memory_percent, disk_read_bytes, disk_write_bytes, "
                "network_bytes_sent, network_bytes_recv, process_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, snapshot.system.timestamp.isoformat(), *values[1:]),
            )
            sample_id = cursor.lastrowid
            assert sample_id is not None
            self._conn.executemany(
                "INSERT INTO process_samples (sample_id, pid, create_time, name, exe, ppid, "
                "status, cpu_percent, rss, vms, num_threads, disk_read_bytes, disk_write_bytes, "
                "username) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ((sample_id, *astuple(p)) for p in snapshot.processes),
            )
        return sample_id

    def status(self) -> StoreStatus:
        row = self._conn.execute(
            "SELECT COUNT(*), MAX(timestamp), AVG(cpu_percent), MAX(memory_percent) "
            "FROM system_samples"
        ).fetchone()
        return StoreStatus(
            str(self.path),
            row[0],
            self._conn.execute("SELECT COUNT(*) FROM process_samples").fetchone()[0],
            self._conn.execute("SELECT COUNT(*) FROM collection_sessions").fetchone()[0],
            row[1],
            row[2],
            row[3],
        )

    def samples(self, limit: int) -> list[StoredSample]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        rows = self._conn.execute(
            "SELECT * FROM system_samples ORDER BY timestamp DESC, id DESC LIMIT ?", (limit,)
        )
        result = []
        for row in rows:
            values = dict(row)
            sample_id, session_id = values.pop("id"), values.pop("session_id")
            values["timestamp"] = datetime.fromisoformat(values["timestamp"])
            result.append(StoredSample(sample_id, session_id, SystemSample(**values)))
        return result

    def process_samples(self, sample_id: int) -> list[ProcessSample]:
        rows = self._conn.execute(
            "SELECT * FROM process_samples WHERE sample_id = ? ORDER BY pid", (sample_id,)
        )
        result = []
        for row in rows:
            values = dict(row)
            values.pop("id")
            values.pop("sample_id")
            result.append(ProcessSample(**values))
        return result

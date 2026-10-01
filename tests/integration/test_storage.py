import sqlite3
from dataclasses import replace

import pytest

from sysguard.storage.sqlite import SQLiteStore


def test_round_trip_reopen_and_identity(tmp_path, snapshot):
    path = tmp_path / "nested" / "metrics.db"
    with SQLiteStore(path) as store:
        session = store.start_session(10, 2)
        sample_id = store.save_snapshot(session, snapshot)
        other = replace(snapshot.processes[0], create_time=200.0)
        store.save_snapshot(session, replace(snapshot, processes=(other,)))
        assert store.process_samples(sample_id) == list(snapshot.processes)
        store.finish_session(session, "completed")
    with SQLiteStore(path) as store:
        assert store.status().sample_count == 2
        assert store.samples(1)[0].system == snapshot.system
        assert store.samples(1)[0].session_id == session
        assert store.process_samples(store.samples(1)[0].id)[0].identity == (42, 200.0)


def test_foreign_keys_and_atomic_snapshot(tmp_path, snapshot):
    with SQLiteStore(tmp_path / "metrics.db") as store:
        with pytest.raises(sqlite3.IntegrityError):
            store.save_snapshot("missing", snapshot)
        session = store.start_session(10, 2)
        duplicate = replace(snapshot, processes=snapshot.processes * 2)
        with pytest.raises(sqlite3.IntegrityError):
            store.save_snapshot(session, duplicate)
        assert store.status().sample_count == 0
        store.save_snapshot(session, snapshot)
        assert store.status().sample_count == 1


def test_future_schema_is_rejected(tmp_path):
    path = tmp_path / "new.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 999")
    with pytest.raises(ValueError, match="schema"):
        SQLiteStore(path)


def test_interrupt_during_process_insert_rolls_back_entire_snapshot(tmp_path, snapshot):
    class InterruptedProcesses(tuple):
        def __iter__(self):
            yield self[0]
            raise KeyboardInterrupt

    interrupted = replace(snapshot, processes=InterruptedProcesses(snapshot.processes))
    path = tmp_path / "interrupted.db"
    with SQLiteStore(path) as store:
        session = store.start_session(10, 2)
        with pytest.raises(KeyboardInterrupt):
            store.save_snapshot(session, interrupted)
        assert store.status().sample_count == 0
        assert store.status().process_sample_count == 0
        store.save_snapshot(session, snapshot)
    with SQLiteStore(path) as store:
        assert store.status().sample_count == 1
        assert store.status().process_sample_count == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

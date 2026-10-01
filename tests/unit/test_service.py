from threading import Event

import pytest

from sysguard.config import CollectionOptions
from sysguard.services.collection import collect
from sysguard.storage.sqlite import SQLiteStore


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds
        return False


class Collector:
    def __init__(self, snapshot, clock, stop, cost=0.0, error=None):
        self.value, self.clock, self.stop = snapshot, clock, stop
        self.cost, self.error = cost, error

    def snapshot(self):
        if self.error:
            raise self.error
        self.clock.now += self.cost
        return self.value


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("field", ["duration", "interval"])
def test_invalid_options(field, value):
    with pytest.raises(ValueError):
        CollectionOptions(**{field: value})


@pytest.mark.parametrize(
    ("duration", "interval", "cost", "expected"), [(10, 2, 0, 5), (1, 5, 0, 1), (5, 1, 1.5, 3)]
)
def test_deadline_and_slow_collector(tmp_path, snapshot, duration, interval, cost, expected):
    clock, stop = Clock(), Event()
    with SQLiteStore(tmp_path / "test.db") as store:
        result = collect(
            Collector(snapshot, clock, stop, cost),
            store,
            CollectionOptions(duration, interval),
            stop=stop,
            clock=clock,
            wait=clock.wait,
        )
        assert result.sample_count == expected
        assert store.status().sample_count == expected
        assert duration <= clock.now <= duration + cost
        assert result.status == "completed"


def test_stop_event_ends_session_without_samples(tmp_path, snapshot):
    clock, stop = Clock(), Event()
    stop.set()
    with SQLiteStore(tmp_path / "test.db") as store:
        result = collect(
            Collector(snapshot, clock, stop),
            store,
            CollectionOptions(),
            stop=stop,
            clock=clock,
            wait=clock.wait,
        )
        assert result.sample_count == 0
        assert result.status == "interrupted"


@pytest.mark.parametrize("error", [KeyboardInterrupt, RuntimeError])
def test_interrupt_and_failure_close_session(tmp_path, snapshot, error):
    import sqlite3

    path = tmp_path / "test.db"
    clock, stop = Clock(), Event()
    with SQLiteStore(path) as store:
        if error is RuntimeError:
            with pytest.raises(RuntimeError):
                collect(Collector(snapshot, clock, stop, error=error), store, CollectionOptions())
        else:
            assert (
                collect(
                    Collector(snapshot, clock, stop, error=error), store, CollectionOptions()
                ).status
                == "interrupted"
            )
    with sqlite3.connect(path) as conn:
        status, ended = conn.execute("SELECT status, ended_at FROM collection_sessions").fetchone()
        assert status == ("interrupted" if error is KeyboardInterrupt else "failed")
        assert ended is not None


def test_stop_during_wait_keeps_committed_sample(tmp_path, snapshot):
    clock, stop = Clock(), Event()

    def stop_wait(seconds):
        stop.set()
        return True

    with SQLiteStore(tmp_path / "test.db") as store:
        result = collect(
            Collector(snapshot, clock, stop),
            store,
            CollectionOptions(),
            stop=stop,
            clock=clock,
            wait=stop_wait,
        )
        assert result.status == "interrupted"
        assert store.status().sample_count == 1


def test_long_intervals_use_short_interruptible_waits(tmp_path, snapshot):
    clock, stop = Clock(), Event()

    def interruptible_wait(seconds):
        assert seconds <= 0.2
        stop.set()
        return True

    with SQLiteStore(tmp_path / "test.db") as store:
        result = collect(
            Collector(snapshot, clock, stop),
            store,
            CollectionOptions(3600, 3600),
            stop=stop,
            clock=clock,
            wait=interruptible_wait,
        )
        assert result.status == "interrupted"


def test_tiny_finite_interval_does_not_overflow(tmp_path, snapshot):
    clock, stop = Clock(), Event()
    with SQLiteStore(tmp_path / "test.db") as store:
        result = collect(
            Collector(snapshot, clock, stop, cost=0.01),
            store,
            CollectionOptions(0.025, 1e-320),
            stop=stop,
            clock=clock,
            wait=clock.wait,
        )
        assert result.sample_count == 3
        assert result.status == "completed"

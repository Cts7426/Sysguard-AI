from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from sysguard.collectors.psutil_collector import PsutilCollector


def process(pid=42, created=100.0):
    proc = Mock(spec=psutil.Process)
    proc.oneshot.side_effect = nullcontext
    proc.pid = pid
    values = dict(
        create_time=created,
        name="worker",
        exe="C:/worker.exe",
        ppid=1,
        status="running",
        username="student",
        num_threads=3,
        memory_info=SimpleNamespace(rss=123, vms=456),
        io_counters=SimpleNamespace(read_bytes=7, write_bytes=8),
        cpu_times=SimpleNamespace(user=2.0, system=1.0),
        is_running=True,
    )
    for name, value in values.items():
        getattr(proc, name).return_value = value
    return proc


def backend(procs):
    api = Mock(spec=psutil)
    api.process_iter.return_value = procs
    api.cpu_percent.return_value = 12.5
    api.virtual_memory.return_value = SimpleNamespace(total=1000, available=600, percent=40.0)
    api.disk_io_counters.return_value = SimpleNamespace(read_bytes=11, write_bytes=22)
    api.net_io_counters.return_value = SimpleNamespace(bytes_sent=33, bytes_recv=44)
    api.pids.return_value = [42, 43]
    return api


def test_maps_metrics_and_computes_cpu_only_after_baseline():
    proc = process()
    collector = PsutilCollector(api=backend([proc]), clock=iter([0.0, 2.0]).__next__)
    first = collector.snapshot()
    assert first.system.cpu_percent is None
    assert first.system.memory_total == 1000
    assert first.system.network_bytes_recv == 44
    assert first.system.timestamp.utcoffset().total_seconds() == 0
    assert first.processes[0].cpu_percent is None
    assert first.processes[0].rss == 123
    proc.cpu_times.return_value = SimpleNamespace(user=3.0, system=1.0)
    second = collector.snapshot()
    assert second.system.cpu_percent == 12.5
    assert second.processes[0].cpu_percent == 50.0


@pytest.mark.parametrize("error", [psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess])
def test_process_errors_do_not_break_snapshot(error):
    bad, good = process(), process(43)
    bad.exe.side_effect = error(42)
    result = PsutilCollector(api=backend([bad, good])).snapshot()
    assert any(p.pid == 43 for p in result.processes)
    if error is psutil.AccessDenied:
        assert result.processes[0].exe is None
        assert result.processes[0].rss == 123
    else:
        assert len(result.processes) == 1


def test_missing_metrics_are_null_and_unknown_identity_is_not_invented():
    proc = process()
    proc.create_time.side_effect = psutil.AccessDenied(42)
    proc.io_counters.side_effect = NotImplementedError
    api = backend([proc])
    api.disk_io_counters.return_value = None
    api.net_io_counters.side_effect = NotImplementedError
    result = PsutilCollector(api=api).snapshot()
    assert result.system.disk_read_bytes is None
    assert result.system.network_bytes_sent is None
    assert result.processes[0].create_time is None
    assert result.processes[0].identity is None
    assert result.processes[0].disk_read_bytes is None


def test_reused_pid_has_new_identity_and_cpu_baseline():
    proc = process()
    collector = PsutilCollector(api=backend([proc]), clock=iter([0.0, 2.0]).__next__)
    first = collector.snapshot().processes[0]
    proc.create_time.return_value = 200.0
    second = collector.snapshot().processes[0]
    assert first.identity != second.identity
    assert second.cpu_percent is None


def test_process_reused_during_read_is_discarded():
    proc = process()
    proc.is_running.return_value = False
    assert PsutilCollector(api=backend([proc])).snapshot().processes == ()

"""Best-effort psutil adapter; no platform-specific imports outside this layer."""

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from types import ModuleType

import psutil

from sysguard.domain.models import ProcessSample, Snapshot, SystemSample


def optional[T](read: Callable[[], T]) -> T | None:
    """Only expected permission/unsupported errors become missing metrics."""
    try:
        return read()
    except (psutil.AccessDenied, NotImplementedError, AttributeError):
        return None


class PsutilCollector:
    def __init__(self, api: ModuleType = psutil, clock: Callable[[], float] = monotonic) -> None:
        self._api = api
        self._clock = clock
        self._cpu_primed = False
        self._previous: dict[tuple[int, float], tuple[float, float]] = {}

    def snapshot(self) -> Snapshot:
        timestamp = datetime.now(UTC)
        cpu = optional(lambda: self._api.cpu_percent(interval=None))
        if not self._cpu_primed:
            self._cpu_primed = True
            cpu = None
        memory = optional(self._api.virtual_memory)
        disk = optional(self._api.disk_io_counters)
        network = optional(self._api.net_io_counters)
        pids = optional(self._api.pids)
        system = SystemSample(
            timestamp,
            cpu,
            memory.total if memory else None,
            memory.available if memory else None,
            memory.percent if memory else None,
            disk.read_bytes if disk else None,
            disk.write_bytes if disk else None,
            network.bytes_sent if network else None,
            network.bytes_recv if network else None,
            len(pids) if pids is not None else None,
        )
        # Fresh objects prevent process_iter's cached creation time hiding PID reuse.
        self._api.process_iter.cache_clear()
        processes: list[ProcessSample] = []
        current: dict[tuple[int, float], tuple[float, float]] = {}
        for proc in self._api.process_iter():
            try:
                sample = self._process(proc, current)
                if sample is not None:
                    processes.append(sample)
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
        self._previous = current
        return Snapshot(system, tuple(processes))

    def _process(
        self, proc: psutil.Process, current: dict[tuple[int, float], tuple[float, float]]
    ) -> ProcessSample | None:
        # Share psutil's expensive OS reads within this one observation only.
        with proc.oneshot():
            created = optional(proc.create_time)
            name = optional(proc.name)
            exe = optional(proc.exe)
            ppid = optional(proc.ppid)
            status = optional(proc.status)
            memory = optional(proc.memory_info)
            threads = optional(proc.num_threads)
            io = optional(proc.io_counters)
            username = optional(proc.username)
            cpu_times = optional(proc.cpu_times)
        now = self._clock()
        cpu = None
        # Re-check after reads to avoid assigning a successor's metrics to an old PID.
        if optional(proc.is_running) is False:
            return None
        if created is not None and cpu_times is not None:
            key = (proc.pid, created)
            total = cpu_times.user + cpu_times.system
            previous = self._previous.get(key)
            if previous is not None:
                elapsed, delta = now - previous[0], total - previous[1]
                if elapsed > 0 and delta >= 0:
                    cpu = 100.0 * delta / elapsed
            current[key] = (now, total)
        return ProcessSample(
            proc.pid,
            created,
            name,
            exe,
            ppid,
            status,
            cpu,
            memory.rss if memory else None,
            memory.vms if memory else None,
            threads,
            io.read_bytes if io else None,
            io.write_bytes if io else None,
            username,
        )

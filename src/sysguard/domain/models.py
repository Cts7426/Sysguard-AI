"""Values use bytes, seconds, percentages, and timezone-aware UTC timestamps."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SystemSample:
    timestamp: datetime
    cpu_percent: float | None
    memory_total: int | None
    memory_available: int | None
    memory_percent: float | None
    disk_read_bytes: int | None
    disk_write_bytes: int | None
    network_bytes_sent: int | None
    network_bytes_recv: int | None
    process_count: int | None


@dataclass(frozen=True)
class ProcessSample:
    pid: int
    create_time: float | None
    name: str | None
    exe: str | None
    ppid: int | None
    status: str | None
    cpu_percent: float | None
    rss: int | None
    vms: int | None
    num_threads: int | None
    disk_read_bytes: int | None
    disk_write_bytes: int | None
    username: str | None

    @property
    def identity(self) -> tuple[int, float] | None:
        return None if self.create_time is None else (self.pid, self.create_time)


@dataclass(frozen=True)
class Snapshot:
    system: SystemSample
    processes: tuple[ProcessSample, ...]


@dataclass(frozen=True)
class StoredSample:
    id: int
    session_id: str
    system: SystemSample


@dataclass(frozen=True)
class StoreStatus:
    database: str
    sample_count: int
    process_sample_count: int
    session_count: int
    latest_timestamp: str | None
    average_cpu_percent: float | None
    peak_memory_percent: float | None


@dataclass(frozen=True)
class CollectionResult:
    session_id: str
    sample_count: int
    status: str

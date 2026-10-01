from datetime import UTC, datetime

import pytest

from sysguard.collectors.psutil_collector import PsutilCollector


@pytest.mark.live
def test_real_snapshot_has_utc_time_and_consistent_values():
    before = datetime.now(UTC)
    snapshot = PsutilCollector().snapshot()
    assert before <= snapshot.system.timestamp <= datetime.now(UTC)
    assert snapshot.system.memory_total is None or snapshot.system.memory_total > 0
    assert all(p.pid >= 0 for p in snapshot.processes)
    assert snapshot.system.cpu_percent is None

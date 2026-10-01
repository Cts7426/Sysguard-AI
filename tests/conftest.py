from datetime import UTC, datetime

import pytest

from sysguard.domain.models import ProcessSample, Snapshot, SystemSample


@pytest.fixture
def snapshot() -> Snapshot:
    return Snapshot(
        SystemSample(datetime(2026, 1, 1, tzinfo=UTC), 25.0, 1000, 600, 40.0, 10, 20, 30, 40, 2),
        (ProcessSample(42, 100.0, "worker", None, 1, "running", None, 100, 200, 2, 3, 4, None),),
    )

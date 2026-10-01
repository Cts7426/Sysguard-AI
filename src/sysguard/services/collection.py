from collections.abc import Callable
from math import fmod
from threading import Event
from time import monotonic

from sysguard.config import CollectionOptions
from sysguard.domain.models import CollectionResult
from sysguard.domain.ports import Collector, SampleStore


def collect(
    collector: Collector,
    store: SampleStore,
    options: CollectionOptions,
    *,
    stop: Event | None = None,
    clock: Callable[[], float] = monotonic,
    wait: Callable[[float], bool] | None = None,
) -> CollectionResult:
    stop = stop if stop is not None else Event()
    wait = wait if wait is not None else stop.wait
    session_id = store.start_session(options.duration, options.interval)
    count, status = 0, "completed"
    try:
        start = clock()
        deadline = start + options.duration
        while not stop.is_set() and clock() < deadline:
            store.save_snapshot(session_id, collector.snapshot())
            count += 1
            now = clock()
            # Skip missed ticks instead of generating a burst of catch-up samples.
            remainder = fmod(now - start, options.interval)
            target = min(deadline, now + (options.interval - remainder))
            # Windows Python 3.12 lock waits defer SIGINT until timeout. Return
            # to Python frequently, even when the requested interval is hours.
            while not stop.is_set() and (delay := target - clock()) > 0:
                if wait(min(delay, 0.2)):
                    status = "interrupted"
                    break
            if status == "interrupted":
                break
        if stop.is_set():
            status = "interrupted"
    except KeyboardInterrupt:
        status = "interrupted"
    except BaseException:
        status = "failed"
        raise
    finally:
        store.finish_session(session_id, status)
    return CollectionResult(session_id, count, status)

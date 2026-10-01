from dataclasses import dataclass
from math import isfinite
from pathlib import Path

DEFAULT_DATABASE = Path("data/sysguard.sqlite3")


@dataclass(frozen=True)
class CollectionOptions:
    duration: float = 30.0
    interval: float = 2.0

    def __post_init__(self) -> None:
        for name in ("duration", "interval"):
            value = getattr(self, name)
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and greater than zero")

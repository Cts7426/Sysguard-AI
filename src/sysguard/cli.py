"""Small CLI composition root; output is JSON with explicit null metrics."""

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sysguard.collectors.psutil_collector import PsutilCollector
from sysguard.config import DEFAULT_DATABASE, CollectionOptions
from sysguard.services.collection import collect
from sysguard.storage.sqlite import SQLiteStore


def positive_float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return result


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SysGuard local metrics collector")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("snapshot", help="Print a current snapshot without saving")
    collecting = commands.add_parser("collect", help="Collect and persist periodic snapshots")
    collecting.add_argument("--duration", type=positive_float, default=30.0)
    collecting.add_argument("--interval", type=positive_float, default=2.0)
    status = commands.add_parser("status", help="Print database counts and basic statistics")
    samples = commands.add_parser("samples", help="Print recent system samples")
    samples.add_argument("--limit", type=positive_int, default=10)
    for subparser in (collecting, status, samples):
        subparser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args(argv)
    try:
        output: object
        if args.command == "snapshot":
            output = asdict(PsutilCollector().snapshot())
        else:
            with SQLiteStore(args.db) as store:
                if args.command == "collect":
                    result = collect(
                        PsutilCollector(), store, CollectionOptions(args.duration, args.interval)
                    )
                    print(json.dumps(asdict(result), indent=2))
                    return 130 if result.status == "interrupted" else 0
                if args.command == "status":
                    output = asdict(store.status())
                else:
                    output = [asdict(sample) for sample in store.samples(args.limit)]
        print(json.dumps(output, default=json_default, indent=2))
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"sysguard: {exc}", file=sys.stderr)
        return 1

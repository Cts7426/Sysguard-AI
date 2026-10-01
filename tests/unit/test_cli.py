import json

import pytest

from sysguard.cli import main


@pytest.mark.parametrize(
    "args",
    [
        ["collect", "--duration", "0"],
        ["collect", "--interval", "nan"],
        ["collect", "--duration", "inf"],
        ["samples", "--limit", "0"],
    ],
)
def test_cli_rejects_invalid_inputs(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_status_and_samples_empty_database(tmp_path, capsys):
    db = str(tmp_path / "empty.db")
    assert main(["status", "--db", db]) == 0
    assert json.loads(capsys.readouterr().out)["sample_count"] == 0
    assert main(["samples", "--db", db, "--limit", "5"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_snapshot_uses_domain_data(monkeypatch, snapshot, capsys):
    import sysguard.cli as cli

    class FixedCollector:
        def snapshot(self):
            return snapshot

    monkeypatch.setattr(cli, "PsutilCollector", FixedCollector)
    assert main(["snapshot"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["system"]["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert output["processes"][0]["pid"] == 42
    assert output["processes"][0]["exe"] is None


def test_collect_command_persists_before_interrupt(monkeypatch, snapshot, tmp_path, capsys):
    import sysguard.cli as cli
    from sysguard.storage.sqlite import SQLiteStore

    class InterruptingCollector:
        def __init__(self):
            self.count = 0

        def snapshot(self):
            self.count += 1
            if self.count > 1:
                raise KeyboardInterrupt
            return snapshot

    monkeypatch.setattr(cli, "PsutilCollector", InterruptingCollector)
    path = tmp_path / "interrupted.db"
    assert main(["collect", "--duration", "10", "--interval", "1e-320", "--db", str(path)]) == 130
    output = json.loads(capsys.readouterr().out)
    assert output["sample_count"] == 1
    assert output["status"] == "interrupted"
    with SQLiteStore(path) as store:
        assert store.status().sample_count == 1

"""Pure checks for the one operator-only timing diagnostic; no native imports."""

import importlib.util
from pathlib import Path

import pytest


def probe():
    path = Path(__file__).with_name("lance_phase_cost_probe.py")
    assert path.is_file(), "fixed phase diagnostic is missing"
    spec = importlib.util.spec_from_file_location("phase_probe_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase_wrapper_preserves_objects_exceptions_and_fixed_keys():
    p = probe()
    phases = p.Phases()
    value = object()
    assert phases.wrap("proof", lambda: value)() is value
    error = ValueError("unchanged")

    def fail():
        raise error

    with pytest.raises(ValueError) as caught:
        phases.wrap("proof", fail)()
    assert caught.value is error
    assert phases.report()["proof"][0] == 2
    with pytest.raises(ValueError):
        phases.wrap("arbitrary", lambda: None)


def test_phase_slot_retains_unpaired_start_and_refusal_without_growth(tmp_path):
    p = probe()
    slot = tmp_path / "slot"
    slot.write_bytes(b" " * 32768)
    slot.chmod(0o600)
    evidence = p.Evidence(slot)
    evidence.append({"phase": "start", "stage": 1081}, 1536)
    evidence.refuse(1081, "measured refusal")
    assert slot.stat().st_size == 32768
    assert evidence.starts() == 1
    assert len(evidence.rows()) == 1  # No invented end on failure.
    assert evidence.refusal()["stage"] == 1081
    with pytest.raises(ValueError):
        evidence.append({"unbounded": "x" * 2048}, 1536)
    assert len(evidence.rows()) == 1


def test_phase_script_pin_rejects_changed_bytes(tmp_path, monkeypatch):
    import hashlib

    p = probe()
    source = tmp_path / "diagnostic.py"
    source.write_bytes(b"fixed operator code")
    source.chmod(0o600)
    monkeypatch.setattr(p, "SCRIPT", source)
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    p.script_pin(expected)
    source.write_bytes(b"changed operator code")
    with pytest.raises(ValueError):
        p.script_pin(expected)


def test_phase_worker_loader_never_executes_pytest_tail(tmp_path):
    p = probe()
    source = tmp_path / "frozen_worker.py"
    source.write_text(
        "def _fixture_main(): return 'original function'\n"
        "if __name__ == '__main__':\n _fixture_main()\n raise SystemExit(0)\n"
        "raise AssertionError('pytest tail executed')\n"
    )
    module = p.load_worker(source)
    assert module._fixture_main() == "original function"


def test_phase_event_line_limit_includes_original_newline(tmp_path):
    p = probe()
    path = tmp_path / "slot"
    path.write_bytes(b" " * 32768)
    with pytest.raises(ValueError):
        p.Evidence(path).append({"x": "x" * 1528}, 1536)

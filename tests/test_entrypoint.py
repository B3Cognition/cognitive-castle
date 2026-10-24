"""Cold hook dispatch must avoid unrelated imports and preserve CLI semantics."""

import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
ENTRY = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]["castle"]
COLD_CALL = """
import importlib, importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name in ('cognitive_castle.cli', 'cognitive_castle.llm_client',
                    'cognitive_castle.corpus_origin'):
            raise AssertionError('cold hook imported unrelated module: ' + name)
sys.meta_path.insert(0, Guard())
module, function = sys.argv.pop(1).split(':')
sys.argv[0] = 'castle'
getattr(importlib.import_module(module), function)()
"""


def invoke(tmp_path, args, *, stdin="{}", env=None):
    home = tmp_path / "home"
    (home / ".castle").mkdir(parents=True, exist_ok=True)
    (home / ".castle/codex-capture.disabled").touch()
    environment = {
        **os.environ,
        "HOME": str(home),
        "PYTHONPATH": str(ROOT),
        "CASTLE_PALACE_PATH": str(tmp_path / "palace"),
        "CASTLE_BRAIN_HOST": "codex",
        **(env or {}),
    }
    return subprocess.run(
        [sys.executable, "-c", COLD_CALL, ENTRY, *args],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=environment,
        timeout=8,
    )


@pytest.mark.parametrize("event", ["session-start", "stop", "precompact"])
def test_paused_codex_hook_does_not_import_unrelated_cli(tmp_path, event):
    result = invoke(tmp_path, ["hook", "run", "--hook", event, "--harness", "codex"])
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    if event == "session-start":
        assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    else:
        assert output == {}


@pytest.mark.skipif(sys.platform != "darwin", reason="bounded hook supervision requires macOS")
def test_enabled_bounded_startup_restores_exact_source_in_cold_process(tmp_path):
    from cognitive_castle.fast_memory import MemoryStore
    from cognitive_castle.memory_capture import capture_one, queue_source

    palace = tmp_path / "palace"
    palace.mkdir(mode=0o700)
    store = MemoryStore(palace / ".memory")
    source = tmp_path / "source.jsonl"
    exact = 'Sixth Sense: preserve "quotes", backslashes \\ and původní text.'
    source.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": exact}],
                },
            }
        )
        + "\n"
    )
    queued = queue_source(
        store, source, allowed_root=tmp_path, format="codex", workspace=str(tmp_path)
    )
    captured = capture_one(store, queued["source_key"])
    assert captured["status"] == "ok" and captured["pending_bytes"] == 0
    capture_config = palace / ".memory/capture.json"
    capture_config.write_text('{"version":1,"enabled":true}')
    capture_config.chmod(0o600)
    policy = palace / ".brain/hosts/codex/policy.json"
    policy.parent.mkdir(parents=True, mode=0o700)
    policy.write_text('{"allow_local_sources":true}')
    policy.chmod(0o600)

    result = invoke(
        tmp_path,
        ["hook", "run", "--hook", "session-start", "--harness", "codex"],
        stdin=json.dumps({"cwd": str(tmp_path), "source": "compact"}),
    )
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.encode()) <= 8192
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    packet = json.loads(context.split("\n", 1)[1])
    assert packet["status"] == "ok", packet
    assert [item["text"] for item in packet["sources"]] == [exact]
    assert packet["authority"] == "historical_evidence_not_current_instructions"


def entrypoint():
    assert importlib.util.find_spec("cognitive_castle.entrypoint") is not None, "fast route missing"
    return importlib.import_module("cognitive_castle.entrypoint")


@pytest.mark.parametrize("explicit", [True, False])
def test_hook_palace_precedence_and_normalization(tmp_path, monkeypatch, explicit):
    module = entrypoint()
    from cognitive_castle import hooks_cli

    seen = []
    monkeypatch.setattr(hooks_cli, "run_hook", lambda *a, **kw: seen.append((a, kw)))
    monkeypatch.setenv("CASTLE_PALACE_PATH", str(tmp_path / "parent/../configured"))
    arguments = ["hook", "run", "--hook", "session-start", "--harness", "codex"]
    if explicit:
        arguments[:0] = ["--palace", str(tmp_path / "explicit")]
    monkeypatch.setattr(sys, "argv", ["castle", *arguments])
    module.main()
    expected = tmp_path / ("explicit" if explicit else "configured")
    assert len(seen) == 1
    assert Path(seen[0][1]["palace"]) == expected


@pytest.mark.parametrize(
    "arguments",
    [
        ["--version"],
        ["memory", "status"],
        ["hook", "run", "--hook", "session-start", "--harness", "claude-code"],
        ["hook", "run", "--hook", "invalid", "--harness", "codex"],
        ["hook", "run", "--hook", "stop", "--harness", "codex", "--unknown"],
        ["hook", "run", "--hook", "stop", "--harness", "codex", "--palace", "/wrong-position"],
        ["hook", "run", "--hook", "stop"],
        ["hook", "run", "--help"],
    ],
)
def test_other_commands_and_invalid_forms_keep_full_cli_handling(monkeypatch, arguments):
    module = entrypoint()
    called = []
    monkeypatch.setattr(sys, "argv", ["castle", *arguments])

    def fallback():
        called.append(list(sys.argv))
        return 37

    monkeypatch.setitem(sys.modules, "cognitive_castle.cli", SimpleNamespace(main=fallback))
    assert module.main() == 37
    assert called == [["castle", *arguments]]


def test_fast_hook_keeps_bounded_stdin(tmp_path):
    result = invoke(
        tmp_path,
        ["hook", "run", "--hook", "session-start", "--harness", "codex"],
        stdin="x" * 65537,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}
    assert "input limit" in result.stderr.lower()

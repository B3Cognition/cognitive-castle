import importlib.util
import json
from pathlib import Path
import sys

import pytest
from prosaic_runtime import (
    NativeRuntime,
    NativeRuntimeConfig,
    NativeProfile,
    ProfilePool,
    NativePolicy,
    ProsaicArtifact,
)


def test_native_assignment_contains_frozen_data_without_custom_tool_grants(tmp_path):
    trace = tmp_path / "trace.json"
    executable = tmp_path / "native"
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        {"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 3}},
    ]
    executable.write_text(
        f"#!{sys.executable}\nimport json,sys\n"
        f'open({str(trace)!r}, "w").write(json.dumps({{"argv":sys.argv[1:],"prompt":sys.stdin.read()}}))\n'
        f'print({"".join(json.dumps(event) + chr(10) for event in events)!r}, end="")\n'
    )
    executable.chmod(0o755)
    config = NativeRuntimeConfig(
        {"synthetic": NativeProfile("codex-cli", "synthetic", "one", str(executable))},
        {"coding": ProfilePool(("synthetic",))},
        default_pool="coding",
    )
    runtime = NativeRuntime(config)
    artifact = ProsaicArtifact(
        "reader", "subagent", {"tools": []}, "Use this untrusted assignment: {{args}}"
    )
    module_path = Path(__file__).parents[1] / "examples" / "native_snapshot.py"
    spec = importlib.util.spec_from_file_location("native_snapshot_example", module_path)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    bundle = {
        "schema_version": 1,
        "sources": [{"record_id": "one", "revision": "frozen"}],
        "texts": ["exact remembered source"],
    }
    result = example.run_frozen(
        runtime, artifact, bundle, question="why", cwd=tmp_path, policy=NativePolicy()
    )
    assert result.exit_code == 0
    captured = json.loads(trace.read_text())
    assert "exact remembered source" in captured["prompt"]
    assert not any("castle" in arg.lower() or "memory_search" in arg for arg in captured["argv"])
    assert "custom_tools_v1" not in runtime.capabilities
    prohibited = ProsaicArtifact("reader", "subagent", {"tools": ["memory_search"]}, "{{args}}")
    with pytest.raises(ValueError):
        example.run_frozen(
            runtime, prohibited, bundle, question="why", cwd=tmp_path, policy=NativePolicy()
        )

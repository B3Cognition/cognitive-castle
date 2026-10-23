"""Run with clean installed wheels: python -I scripts/wheel_smoke.py."""

from importlib import metadata
import builtins
import json
from pathlib import Path
import sys
import tempfile
import time


def main():
    assert sys.flags.isolated == 1
    actual_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"cognitive_castle", "torch", "spacy", "prosaic_harness"}:
            raise AssertionError("optional dependency imported")
        return actual_import(name, *args, **kwargs)

    builtins.__import__ = guarded
    from prosaic_memory_castle import CastleMemoryProvider, WorkerCommand, memory_tools
    import prosaic_memory_castle
    from prosaic_runtime import InvocationScope
    from prosaic_runtime.tools import execute_custom_tool

    owner = metadata.distribution("b3-prosaic-memory-castle")
    assert owner.version == prosaic_memory_castle.__version__
    assert "site-packages" in str(Path(prosaic_memory_castle.__file__).resolve())
    assert metadata.packages_distributions()["prosaic_memory_castle"] == [
        "b3-prosaic-memory-castle"
    ]
    installed = {d.metadata["Name"].lower().replace("_", "-") for d in metadata.distributions()}
    assert (
        not {"b3-cognitive-castle", "cognitive-castle", "torch", "spacy", "b3-prosaic-harness"}
        & installed
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        worker = root / "worker.py"
        worker.write_text("""import json,sys
for line in sys.stdin:
    request=json.loads(line)
    result={'schema_version':1,'profile':'memory-v1','fingerprint':'a'*64,
        'capabilities':['health','search','fetch','snapshot']}
    if request['op']=='search': result={'hits':[],'degraded_signals':[]}
    print(json.dumps({'version':1,'id':request['id'],'ok':True,'result':result}),flush=True)
""")
        with CastleMemoryProvider(
            WorkerCommand((sys.executable, str(worker))),
            palace_path=root,
            namespace="synthetic",
            config_path=root / "config.json",
            allowed_wings=("project",),
        ) as provider:
            assert provider.health()["profile"] == "memory-v1"
            tools = memory_tools(provider, authorize=lambda context: context.scope.run_id is None)
            result = execute_custom_tool(
                tools["memory_search"],
                '{"query":"synthetic"}',
                check_boundary=lambda: None,
                scope=InvocationScope("smoke"),
                deadline=time.monotonic() + 5,
            )
            assert result == {"status": "ok", "result": {"hits": [], "degraded_signals": []}}
    print(
        json.dumps(
            {
                "version": owner.version,
                "checks": [
                    "installed-ownership",
                    "runtime-only",
                    "no-castle-import",
                    "private-worker",
                    "safe-tools",
                    "no-conversation-run-id",
                ],
            }
        )
    )


if __name__ == "__main__":
    main()

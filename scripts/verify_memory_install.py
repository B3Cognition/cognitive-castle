"""Qualify separately installed worker/adapter wheels using local synthetic data.

Run outside the source checkout. The worker environment must contain provisioned
CPU models; neither environment needs an editable installation of the other.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


PREPARE = r"""
import json, sys
from pathlib import Path
from cognitive_castle.config import CognitiveCastleConfig
from cognitive_castle.context import PalacePaths
from cognitive_castle.backends.lancedb_backend import LanceDBBackend
from cognitive_castle.provider_setup import prepare_provider
root = Path(sys.argv[1])
config_dir = root / "config"
config_dir.mkdir(parents=True)
(config_dir / "config.json").write_text(json.dumps({"embedder_model":"BAAI/bge-m3", "embedder_dim":1024, "embedding_device":"cpu"}))
config = CognitiveCastleConfig(config_dir=config_dir)
backend = LanceDBBackend(cfg=config)
collection = backend.get_collection(str(root / "palace"), collection_name="castle_drawers", create=True)
text = "Atlas chose SQLite for local persistence because deployment must work offline. 🙂\r\n  Exact evidence.\r\n"
collection.upsert(ids=["atlas", "foreign"], documents=[text, "Private foreign project decision."], metadatas=[{"wing":"approved", "source_revision":"first", "representation":"project", "source_file":"/synthetic/atlas.md"}, {"wing":"foreign"}])
backend.close()
prepare_provider(PalacePaths.resolve(root / "palace"), namespace="qualification", config=config)
print(json.dumps({"fixture_ready":True}))
"""

CONSUME = r"""
import hashlib, json, os, sys, time
from pathlib import Path
from prosaic_memory_castle import CastleMemoryProvider, WorkerCommand, MemoryProviderError
root, worker, guard = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def state():
    return {str(p.relative_to(root / "palace")): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns, p.stat().st_mode) for p in (root / "palace").rglob("*") if p.is_file()}
before, started = state(), time.monotonic()
argv = (worker, guard) if not os.environ.get("CASTLE_SMOKE_COVERAGE") else (worker, "-m", "coverage", "run", "--parallel-mode", "--source=cognitive_castle", guard)
provider = CastleMemoryProvider(WorkerCommand(argv), palace_path=root / "palace", namespace="qualification", config_path=root / "config/config.json", allowed_wings=("approved",))
try:
    health = provider.health()
    assert health["profile"] == "memory-v1"
    child = provider._transport._process.pid
    found = provider.search("Why did Atlas choose SQLite for offline persistence?")
    assert [hit["record_id"] for hit in found["hits"]] == ["atlas"]
    source = provider.fetch("atlas")
    text = "Atlas chose SQLite for local persistence because deployment must work offline. 🙂\r\n  Exact evidence.\r\n"
    assert source["text"] == text and source["text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    try:
        provider.fetch("foreign")
        raise AssertionError("foreign source exposed")
    except MemoryProviderError as error:
        assert error.code == "not_found"
    bundle = provider.snapshot(["atlas"], expected={"atlas":{"text_sha256":source["text_sha256"], "revision":"first"}})
    assert bundle["texts"] == [text]
finally:
    provider.close()
assert state() == before
assert not any(name.split(".")[0] in {"cognitive_castle","torch","spacy"} for name in sys.modules)
try:
    os.kill(child, 0)
    raise AssertionError("worker not reaped")
except ProcessLookupError:
    pass
print(json.dumps({"installed_worker_and_adapter":True, "exact_text":True, "scope_isolation":True, "read_only":True, "no_optional_engines_or_network":True, "separate_dependencies":True, "worker_reaped":True, "seconds":round(time.monotonic()-started,3)}))
"""

GUARD = """
import importlib.abc, runpy, socket, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("cognitive_castle.soar", "cognitive_castle.sue", "cognitive_castle.quality", "cognitive_castle.understanding", "cognitive_castle.llm", "cognitive_castle.judge", "spacy")):
            raise AssertionError("optional engine imported")
sys.meta_path.insert(0, Guard())
def no_network(*args, **kwargs):
    raise AssertionError("network forbidden")
socket.socket.connect = no_network
runpy.run_module("cognitive_castle.provider_worker", run_name="__main__")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-python", required=True)
    parser.add_argument("--adapter-python", required=True)
    args = parser.parse_args()
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    with tempfile.TemporaryDirectory(prefix="castle-wheel-smoke-") as directory:
        root = Path(directory)
        child_env = {**env, "HOME": str(root / "home")}
        guard = root / "worker_guard.py"
        guard.write_text(GUARD)
        prepared = subprocess.run(
            [args.worker_python, "-c", PREPARE, directory],
            cwd=directory,
            env=child_env,
            check=False,
            timeout=120,
            capture_output=True,
        )
        if prepared.returncode:
            sys.stderr.write(prepared.stderr.decode(errors="replace"))
            prepared.check_returncode()
        result = subprocess.run(
            [args.adapter_python, "-c", CONSUME, directory, args.worker_python, str(guard)],
            cwd=directory,
            env=child_env,
            check=False,
            timeout=150,
            capture_output=True,
        )
        if result.returncode:
            sys.stderr.write(result.stderr.decode(errors="replace"))
            result.check_returncode()
        print(result.stdout.decode().strip())


if __name__ == "__main__":
    main()

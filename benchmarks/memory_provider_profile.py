"""Profile local FTS provider overhead on the frozen synthetic corpus.

Zero vectors avoid neural ingestion; this is a diagnostic, not the actual-model
qualification benchmark. No user palace or external service is accessed.
"""

import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from memory_provider_bench import _forbid_network_and_optional_engines, _metadata  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    attempts = _forbid_network_and_optional_engines(forbid_neural=True)
    from cognitive_castle.backends.lancedb_backend import LanceDBBackend
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.context import CastleContext, PalacePaths
    from cognitive_castle.memory import MemoryService

    fixture_path = ROOT / "tests/fixtures/memory_eval/coding_decisions_v1.json"
    fixture = json.loads(fixture_path.read_text())
    result = {
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "methods": {},
    }
    with tempfile.TemporaryDirectory(prefix="castle-fts-profile-") as directory:
        root = Path(directory) / "palace"
        cfg = CognitiveCastleConfig(config_dir=Path(directory) / "config")
        cfg._file_config = {"embedder_model": "synthetic", "embedder_dim": 4}
        backend = LanceDBBackend(cfg=cfg)
        col = backend.get_collection(str(root), collection_name="castle_drawers", create=True)
        docs = fixture["documents"]
        col.upsert(
            ids=[d["id"] for d in docs],
            documents=[d["text"] for d in docs],
            metadatas=[_metadata(d) for d in docs],
            embeddings=[[0.0] * 4 for _ in docs],
        )
        backend.close()
        paths = PalacePaths.resolve(root)
        paths.provider.mkdir()
        (paths.provider / "identity.json").write_text(
            json.dumps({"schema_version": 1, "namespace": "profile"})
        )
        with CastleContext.open(paths, config=cfg, read_only=True) as context:
            service = MemoryService(context, namespace="profile", allowed_wings={"atlas"})
            service.health()
            for method in ("fts", "provider"):
                profile, latencies = cProfile.Profile(), []
                profile.enable()
                for question in fixture["questions"] * 2:
                    start = time.perf_counter()
                    if method == "fts":
                        context.get_collection().fts_search(
                            question["query"], n_results=5, where="wing = 'atlas'"
                        )
                    else:
                        service.search(question["query"], limit=5)
                    latencies.append((time.perf_counter() - start) * 1000)
                profile.disable()
                stats = pstats.Stats(profile)
                rows = [
                    {
                        "file": str(Path(key[0]).name),
                        "line": key[1],
                        "function": key[2],
                        "calls": value[1],
                        "self_seconds": value[2],
                        "cumulative_seconds": value[3],
                    }
                    for key, value in stats.stats.items()
                ]
                result["methods"][method] = {
                    "queries": len(latencies),
                    "median_ms": statistics.median(latencies),
                    "top_cumulative": sorted(rows, key=lambda r: -r["cumulative_seconds"])[:35],
                    "castle_calls": [
                        r
                        for r in rows
                        if r["file"]
                        in {
                            "memory.py",
                            "searcher.py",
                            "lancedb_backend.py",
                            "context.py",
                            "revisions.py",
                        }
                    ],
                }
    result["forbidden_attempts"] = attempts
    assert not any(attempts.values()), attempts
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({name: data["median_ms"] for name, data in result["methods"].items()}))


if __name__ == "__main__":
    main()

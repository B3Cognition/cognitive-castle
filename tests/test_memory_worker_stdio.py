import hashlib
import json
import os
import subprocess
import sys

from cognitive_castle.context import PalacePaths
from cognitive_castle.provider_setup import prepare_provider


def test_real_worker_real_lance_no_engines_network_or_store_writes(synthetic_palace, tmp_path):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    config_path = cfg_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "embedder_dim": 4,
                "embedder_model": "synthetic",
                "embedding_device": "cpu",
                "reranker_device": "cpu",
            }
        )
    )
    from cognitive_castle.config import CognitiveCastleConfig

    config = CognitiveCastleConfig(config_dir=cfg_dir)
    synthetic_palace.drawers.upsert(
        ids=["own", "foreign"],
        documents=[
            "The Atlas decision preserves exact Unicode 🙂.\r\n",
            "private foreign decision",
        ],
        embeddings=[[1.0, 0.0, 0.0, 0.0]] * 2,
        metadatas=[{"wing": "project"}, {"wing": "other"}],
    )
    prepare_provider(PalacePaths.resolve(synthetic_palace.root), namespace="test", config=config)

    def state():
        return {
            str(p.relative_to(synthetic_palace.root)): (
                hashlib.sha256(p.read_bytes()).hexdigest(),
                p.stat().st_mtime_ns,
                p.stat().st_mode,
            )
            for p in synthetic_palace.root.rglob("*")
            if p.is_file()
        }

    before = state()
    bootstrap = """
import importlib.abc, os, socket, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(part in fullname for part in ("soar", "sue", "understanding", "spacy", "quality_rerank", "llm_client", "judge")):
            raise AssertionError("forbidden optional engine: " + fullname)
sys.meta_path.insert(0, Guard())
def network(*args, **kwargs):
    raise AssertionError("network forbidden")
socket.socket.connect = network
from cognitive_castle import embedding, reranker
embedding._get_model = lambda *args, **kwargs: None
embedding.embed_texts = lambda texts, **kwargs: [[1.,0.,0.,0.] for _ in texts]
def score(query, candidates, **kwargs):
    os.write(1, b"dependency diagnostic on native stdout\\n")
    return [float(len(candidates) - i) for i in range(len(candidates))]
reranker.rerank = score
from cognitive_castle.provider_worker import main
main()
"""
    operations = [
        ("hello", {}),
        ("search", {"query": "Atlas decision"}),
        ("fetch", {"record_id": "foreign"}),
        ("fetch", {"record_id": "own"}),
        ("snapshot", {"record_ids": ["own"]}),
        ("close", {}),
    ]
    request = b"".join(
        json.dumps({"version": 1, "id": str(i), "op": op, "args": args}).encode() + b"\n"
        for i, (op, args) in enumerate(operations)
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            bootstrap,
            "--palace",
            str(synthetic_palace.root),
            "--namespace",
            "test",
            "--config",
            str(config_path),
            "--wing",
            "project",
            "--profile",
            "memory-v1",
        ],
        input=request,
        capture_output=True,
        timeout=30,
        env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
    )
    assert result.returncode == 0, result.stderr.decode()
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(replies) == 6
    assert replies[0]["ok"] is True
    assert replies[1]["result"]["hits"][0]["record_id"] == "own"
    assert replies[2]["error"] == {"code": "not_found"}
    assert replies[3]["result"]["text"].endswith("🙂.\r\n")
    assert replies[4]["result"]["texts"] == [replies[3]["result"]["text"]]
    assert b"dependency diagnostic" in result.stderr
    assert state() == before

#!/usr/bin/env python3
"""Offline actual-model retrieval pilot over frozen, invented project history.

Run from the repository root with provisioned BAAI/bge-m3 and
BAAI/bge-reranker-base snapshots in HF_HOME. The script creates only a disposable
palace, never opens an existing user palace, and forbids network connections,
SOAR, quality analysis, SUE and generative transports in every child process.
Retrieval metrics are not answer accuracy or a claim of production qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEFAULT_FIXTURE = ROOT / "tests/fixtures/memory_eval/coding_decisions_v1.json"
MODEL_IDS = ("BAAI/bge-m3", "BAAI/bge-reranker-base")


def retrieval_metrics(retrieved, relevant, k=5):
    ranked = list(dict.fromkeys(retrieved))[:k]
    relevant = set(relevant)
    found = set(ranked) & relevant
    first = next((i for i, rid in enumerate(ranked, 1) if rid in relevant), None)
    dcg = sum(1 / math.log2(i + 1) for i, rid in enumerate(ranked, 1) if rid in relevant)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return {
        "recall_at_5": len(found) / len(relevant) if relevant else None,
        "mrr_at_5": (1 / first if first else 0.0) if relevant else None,
        "recall_any": float(bool(found)) if relevant else None,
        "recall_all": float(found == relevant) if relevant else None,
        "precision_at_5": len(found) / k,
        "ndcg_at_5": dcg / ideal if ideal else None,
        "empty_for_unanswerable": float(not ranked) if not relevant else None,
    }


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _rss_mib():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024 * 1024 if sys.platform == "darwin" else 1024)


def _percentiles(values):
    if not values:
        return {"samples": 0, "p50_ms": None, "p95_ms": None}
    ordered = sorted(values)
    return {
        "samples": len(values),
        "p50_ms": statistics.median(ordered),
        "p95_ms": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
    }


def _forbid_network_and_optional_engines(*, forbid_neural=False):
    import builtins
    import importlib.abc
    import importlib.machinery
    import importlib.util
    import socket

    attempts = {"network": [], "optional_import": []}
    original_import = builtins.__import__
    forbidden = (
        "spacy",
        "cognitive_castle.soar_bridge",
        "cognitive_castle.quality_rerank",
        "cognitive_castle.understanding",
        "cognitive_castle.sue",
        "cognitive_castle.sue_worker",
        "cognitive_castle.judge",
        "cognitive_castle.llm_client",
    )
    if forbid_neural:
        forbidden += (
            "torch",
            "sentence_transformers",
            "cognitive_castle.embedding",
            "cognitive_castle.reranker",
        )

    def forbidden_name(name):
        return any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)

    class ForbiddenLoader(importlib.abc.Loader):
        def create_module(self, spec):
            return None

        def exec_module(self, module):
            attempts["optional_import"].append(module.__name__)
            raise ImportError("optional engine forbidden by benchmark")

    class ForbiddenFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if forbidden_name(fullname):
                # Availability probes can inspect a spec without loading engines.
                return importlib.machinery.ModuleSpec(fullname, ForbiddenLoader())
            return None

    def checked_import(name, globals=None, locals=None, fromlist=(), level=0):
        package = (globals or {}).get("__package__")
        absolute = importlib.util.resolve_name("." * level + name, package) if level else name
        names = [absolute] + [absolute + "." + part for part in fromlist or () if part != "*"]
        if any(forbidden_name(item) for item in names):
            attempts["optional_import"].append(absolute)
            raise ImportError("optional engine forbidden by benchmark")
        return original_import(name, globals, locals, fromlist, level)

    def no_network(*args, **kwargs):
        attempts["network"].append("connection")
        raise OSError("network forbidden by benchmark")

    builtins.__import__ = checked_import
    sys.meta_path.insert(0, ForbiddenFinder())
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    socket.getaddrinfo = no_network
    socket.gethostbyname = no_network
    socket.gethostbyname_ex = no_network
    socket.gethostbyaddr = no_network
    return attempts


def _configuration(root):
    from cognitive_castle.config import CognitiveCastleConfig

    cfg = CognitiveCastleConfig(config_dir=root / ".benchmark-config")
    cfg._file_config = {
        "embedder_model": MODEL_IDS[0],
        "embedder_dim": 1024,
        "embedding_device": "cpu",
        "reranker_model_cpu": MODEL_IDS[1],
    }
    return cfg


def _metadata(doc):
    return {
        "wing": doc.get("wing", "atlas"),
        "room": "decisions",
        "source_file": "fixture://coding-decisions-v1/" + doc["source"],
        "source_revision": hashlib.sha256(doc["text"].encode("utf-8")).hexdigest(),
        "representation": "project",
        "filed_at": f"2026-10-{doc['day']:02d}T12:00:00+00:00",
        "ingest_complete": True,
        "chunk_index": 0,
    }


def _configuration_values(config):
    names = (
        "embedder_model",
        "embedder_identity",
        "embedder_dim",
        "embedding_device",
        "reranker_model_cpu",
        "reranker_model_gpu",
        "reranker_k_interactive",
        "weight_dense",
        "weight_sparse",
        "weight_kg",
        "k_rrf",
        "recency_tau_days",
        "recency_max_boost",
        "info_weight_enabled",
    )
    return {name: getattr(config, name) for name in names}


def _prepare(root, fixture):
    from cognitive_castle.backends.lancedb_backend import LanceDBBackend
    from cognitive_castle.embedding import embed_texts

    cfg = _configuration(root)
    docs = fixture["documents"]
    start = time.perf_counter()
    vectors = embed_texts([doc["text"] for doc in docs], cfg=cfg)
    backend = LanceDBBackend(cfg=cfg)
    try:
        col = backend.get_collection(str(root), collection_name="castle_drawers", create=True)
        col.add(
            ids=[doc["id"] for doc in docs],
            documents=[doc["text"] for doc in docs],
            metadatas=[_metadata(doc) for doc in docs],
            embeddings=vectors,
        )
        col._ensure_fts_index(replace=True)
        backend.get_collection(
            str(root.parent / "empty-palace"), collection_name="castle_drawers", create=True
        )
    finally:
        backend.close()
    for palace in (root, root.parent / "empty-palace"):
        provider = palace / ".provider"
        provider.mkdir()
        (provider / "identity.json").write_bytes(
            _json_bytes({"schema_version": 1, "namespace": "synthetic-memory-pilot"})
        )
    return {
        "ingest_ms": (time.perf_counter() - start) * 1000,
        "peak_rss_mib": _rss_mib(),
        "documents": len(docs),
        "configuration": _configuration_values(cfg),
    }


def _evaluate(root, fixture, method, warm_repeats):
    from cognitive_castle.context import CastleContext, PalacePaths
    from cognitive_castle.memory import MemoryService

    cfg = _configuration(root)
    context = CastleContext.open(PalacePaths.resolve(root), config=cfg, read_only=True)
    service = MemoryService(
        context,
        namespace="synthetic-memory-pilot",
        allowed_wings=frozenset(fixture["allowed_wings"]),
        profile=method if method != "fts" else "memory-fts-v1",
    )
    expected = {doc["id"]: doc for doc in fixture["documents"]}
    allowed = frozenset(fixture["allowed_wings"])
    failures = []

    def query(question):
        start = time.perf_counter()
        if method != "fts":
            response = service.search(question["query"], limit=5)
            elapsed = (time.perf_counter() - start) * 1000
            hits = [hit.as_dict() for hit in response.hits]
            payload_bytes = len(_json_bytes(response.as_dict()))
            degraded = list(response.degraded_signals)
        else:
            rows = context.get_collection().fts_search(
                question["query"], n_results=5, where="wing = 'atlas'"
            )
            elapsed = (time.perf_counter() - start) * 1000
            hits = [
                {
                    "record_id": row["id"],
                    "excerpt": row["text"],
                    "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                    "wing": row["wing"],
                    "revision": json.loads(row["metadata_json"])["source_revision"],
                }
                for row in rows
            ]
            payload_bytes = len(_json_bytes(hits))
            degraded = []
        # Fetch verification is intentionally outside measured search latency.
        for hit in hits:
            rid = hit["record_id"]
            doc = expected.get(rid)
            if doc is None or doc.get("wing", "atlas") not in allowed:
                failures.append({"gate": "scope", "question": question["id"], "record": rid})
                continue
            exact = service.fetch(rid)
            digest = hashlib.sha256(doc["text"].encode()).hexdigest()
            if (
                exact.text != doc["text"]
                or exact.text_sha256 != digest
                or hit["text_sha256"] != digest
                or hit["excerpt"] != doc["text"][:512]
                or hit["revision"] != _metadata(doc)["source_revision"]
                or exact.provenance.source_id
                != hashlib.sha256(_metadata(doc)["source_file"].encode()).hexdigest()
                or exact.provenance.representation != "project"
                or exact.provenance.captured_at != _metadata(doc)["filed_at"]
                or exact.provenance.wing != doc.get("wing", "atlas")
            ):
                failures.append(
                    {"gate": "source_integrity", "question": question["id"], "record": rid}
                )
        return {
            "id": question["id"],
            "split": question["split"],
            "kind": question["kind"],
            "returned_ids": [hit["record_id"] for hit in hits],
            "latency_ms": elapsed,
            "payload_bytes": payload_bytes,
            "context_text_bytes": sum(len(hit["excerpt"].encode()) for hit in hits),
            "degraded_signals": degraded,
            "metrics": retrieval_metrics([hit["record_id"] for hit in hits], question["relevant"]),
        }

    try:
        cold = query(fixture["questions"][0])
        warm = [query(question) for _ in range(warm_repeats) for question in fixture["questions"]]
        # Exact fetch must have the same scope boundary as both recall paths.
        from cognitive_castle.memory_types import MemoryError

        for doc in fixture["documents"]:
            if doc.get("wing", "atlas") in allowed:
                continue
            try:
                service.fetch(doc["id"])
            except MemoryError as exc:
                if exc.code != "not_found":
                    failures.append({"gate": "scope_fetch_error", "record": doc["id"]})
            else:
                failures.append({"gate": "scope_fetch_disclosure", "record": doc["id"]})
        devices = []
        if method == "memory-v1":
            from cognitive_castle import reranker

            devices = sorted({device for _, device in reranker._model_cache})
        if method == "memory-v1" and devices != ["cpu"]:
            failures.append({"gate": "cpu_device", "observed": devices})
        empty_context = CastleContext.open(
            PalacePaths.resolve(root.parent / "empty-palace"), config=cfg, read_only=True
        )
        try:
            if method != "fts":
                empty_service = MemoryService(
                    empty_context,
                    namespace="synthetic-memory-pilot",
                    allowed_wings=allowed,
                    profile=method,
                )
                empty_result = empty_service.search("history that has never been stored")
                successful_empty = not empty_result.hits and not empty_result.degraded_signals
            else:
                successful_empty = not empty_context.get_collection().fts_search(
                    "history that has never been stored", where="wing = 'atlas'"
                )
            if not successful_empty:
                failures.append({"gate": "successful_empty_store"})
        except Exception as exc:
            successful_empty = False
            failures.append({"gate": "successful_empty_store", "error_class": type(exc).__name__})
        finally:
            empty_context.close()
        return {
            "method": method,
            "cold_query": cold,
            "warm_queries": warm,
            "peak_rss_mib": _rss_mib(),
            "functional_failures": failures,
            "actual_reranker_devices": devices,
            "successful_empty_store": successful_empty,
        }
    finally:
        context.close()


def _child(args):
    forbid_neural = args.phase == "evaluate" and args.method != "memory-v1"
    attempts = _forbid_network_and_optional_engines(forbid_neural=forbid_neural)
    fixture = json.loads(args.fixture.read_text())
    result = (
        _prepare(args.palace, fixture)
        if args.phase == "prepare"
        else _evaluate(args.palace, fixture, args.method, args.warm_repeats)
    )
    result["forbidden_attempts"] = attempts
    result["initialized_forbidden_modules"] = [
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in (
                "spacy",
                "cognitive_castle.soar_bridge",
                "cognitive_castle.quality_rerank",
                "cognitive_castle.understanding",
                "cognitive_castle.sue",
                "cognitive_castle.judge",
                "cognitive_castle.llm_client",
            )
            + (
                (
                    "torch",
                    "sentence_transformers",
                    "cognitive_castle.embedding",
                    "cognitive_castle.reranker",
                )
                if forbid_neural
                else ()
            )
        )
    ]
    args.child_output.write_bytes(_json_bytes(result))


def _model_evidence(cache):
    evidence = {}
    for model in MODEL_IDS:
        directory = cache / "hub" / ("models--" + model.replace("/", "--"))
        revision = (directory / "refs/main").read_text().strip()
        snapshot = directory / "snapshots" / revision
        files = {
            str(path.relative_to(snapshot)): {
                "sha256": _file_hash(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(snapshot.rglob("*"))
            if path.is_file()
        }
        if not any(name.endswith((".safetensors", ".bin")) for name in files):
            raise RuntimeError("mandatory model weights not provisioned")
        evidence[model] = {
            "revision": revision,
            "files": files,
            "manifest_sha256": hashlib.sha256(_json_bytes(files)).hexdigest(),
        }
    return evidence


def _summarize(runs):
    warm = runs[0]["warm_queries"]
    result = {
        "cold_model_search_latency": _percentiles(
            [run["cold_query"]["latency_ms"] for run in runs]
        ),
        "warm_search_latency": _percentiles([q["latency_ms"] for q in warm]),
        "peak_rss_mib": max(run["peak_rss_mib"] for run in runs),
        "splits": {},
    }
    for split in ("dev", "heldout"):
        rows = [q for q in warm if q["split"] == split]
        metrics = {}
        for key in retrieval_metrics([], set()):
            values = [q["metrics"][key] for q in rows if q["metrics"][key] is not None]
            metrics[key] = statistics.mean(values) if values else None
        result["splits"][split] = {
            "observations": len(rows),
            "metrics": metrics,
            "warm_latency": _percentiles([q["latency_ms"] for q in rows]),
            "mean_payload_bytes": statistics.mean(q["payload_bytes"] for q in rows),
            "mean_context_text_bytes": statistics.mean(q["context_text_bytes"] for q in rows),
        }
    return result


def _source_hashes():
    paths = [Path(__file__)] + [
        ROOT / "cognitive_castle" / name
        for name in (
            "searcher.py",
            "embedding.py",
            "reranker.py",
            "fusion.py",
            "memory.py",
            "memory_types.py",
            "context.py",
            "config.py",
            "revisions.py",
            "backends/lancedb_backend.py",
        )
    ]
    return {str(path.relative_to(ROOT)): _file_hash(path) for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/verification/memory-pilot-fts-v1.json"
    )
    parser.add_argument("--warm-repeats", type=int, default=2)
    parser.add_argument("--cold-runs", type=int, default=3)
    parser.add_argument("--phase", choices=("prepare", "evaluate"), help=argparse.SUPPRESS)
    parser.add_argument("--palace", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--method", choices=("memory-v1", "memory-fts-v1", "fts"), help=argparse.SUPPRESS
    )
    parser.add_argument("--child-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.phase:
        _child(args)
        return
    if not 1 <= args.warm_repeats <= 10 or not 1 <= args.cold_runs <= 10:
        parser.error("warm-repeats and cold-runs must be between 1 and 10")
    cache = Path(os.environ.get("HF_HOME", ""))
    if not str(cache) or not (cache / "hub").is_dir():
        parser.error("HF_HOME must point to explicitly provisioned model weights")
    fixture = json.loads(args.fixture.read_text())
    if (
        len(fixture["questions"]) != 40
        or sum(q["split"] == "dev" for q in fixture["questions"]) != 10
    ):
        parser.error("version 1 pilot requires a frozen 10-dev/30-heldout fixture")
    source_start = _source_hashes()
    env = dict(
        os.environ,
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_DATASETS_OFFLINE="1",
        CASTLE_EMBEDDER_MODEL=MODEL_IDS[0],
        CASTLE_EMBEDDER_DIM="1024",
        CASTLE_EMBEDDER_IDENTITY="bge-m3",
        CASTLE_EMBEDDING_DEVICE="cpu",
        CASTLE_RERANKER_MODEL_CPU=MODEL_IDS[1],
        CUDA_VISIBLE_DEVICES="",
        TOKENIZERS_PARALLELISM="false",
    )
    models = _model_evidence(cache)
    started = time.perf_counter()
    raw = {}
    with tempfile.TemporaryDirectory(prefix="castle-memory-pilot-") as temporary:
        workspace = Path(temporary)
        root = workspace / "palace"

        def launch(phase, output, method=None, repeats=0):
            command = [
                sys.executable,
                str(Path(__file__)),
                "--phase",
                phase,
                "--fixture",
                str(args.fixture.resolve()),
                "--palace",
                str(root),
                "--child-output",
                str(output),
                "--warm-repeats",
                str(repeats),
            ]
            if method:
                command += ["--method", method]
            run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=900)
            if run.returncode:
                raise RuntimeError(
                    f"benchmark child {phase}/{method} failed:\n{run.stderr[-8000:]}"
                )
            return json.loads(output.read_text())

        preparation = launch("prepare", workspace / "prepare.json")
        for method in ("fts", "memory-fts-v1", "memory-v1"):
            print(
                f"Evaluating {method}: {args.cold_runs} cold processes, {args.warm_repeats} warm passes",
                flush=True,
            )
            raw[method] = [
                launch(
                    "evaluate",
                    workspace / f"{method}-{i}.json",
                    method,
                    args.warm_repeats if i == 0 else 0,
                )
                for i in range(args.cold_runs)
            ]
    versions = {
        name: importlib.metadata.version(name)
        for name in ("torch", "sentence-transformers", "transformers", "lancedb", "pyarrow")
    }
    failures = [
        failure for runs in raw.values() for run in runs for failure in run["functional_failures"]
    ]
    forbidden = [run["forbidden_attempts"] for runs in raw.values() for run in runs] + [
        preparation["forbidden_attempts"]
    ]
    initialized = [
        name
        for runs in raw.values()
        for run in runs
        for name in run["initialized_forbidden_modules"]
    ] + preparation["initialized_forbidden_modules"]
    if any(any(attempt.values()) for attempt in forbidden) or initialized:
        failures.append({"gate": "forbidden_engine_or_network_attempt"})
    result = {
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fixture": {
            "name": fixture["name"],
            "sha256": _file_hash(args.fixture),
            "documents": len(fixture["documents"]),
            "dev_questions": 10,
            "heldout_questions": 30,
            "labels_frozen_before_execution": True,
            "post_result_tuning": False,
        },
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "device": "cpu",
            "cpu_model": "not exposed by sandbox (sysctl denied); architecture and logical count recorded",
        },
        "python": platform.python_version(),
        "versions": versions,
        "models": models,
        "configuration": {
            "profiles": ["memory-fts-v1", "memory-v1"],
            "candidate_budget": preparation["configuration"]["reranker_k_interactive"],
            "top_k": 5,
            "kg": "not provisioned; optional signal excluded",
            "baseline": "actual LanceDB Tantivy FTS with identical wing filter",
        },
        "preparation": preparation,
        "summary": {name: _summarize(runs) for name, runs in raw.items()},
        "functional_gates": {
            "passed": not failures,
            "failures": failures,
            "network_and_optional_import_attempts": forbidden,
            "initialized_forbidden_modules": initialized,
        },
        "source_hashes_start": source_start,
        "source_hashes_end": _source_hashes(),
        "source_changed_during_run": source_start != _source_hashes(),
        "elapsed_seconds": time.perf_counter() - started,
        "limits": [
            "Synthetic single-project fixture; no production recall or latency guarantee.",
            "No generated answers: retrieval metrics do not measure answer accuracy or factual truth.",
            "Unanswerable empty-result rate is measured separately; no score threshold or answer-abstention policy is introduced.",
            "Cold means fresh Python/model process with OS filesystem cache potentially warm; three observations by default.",
            "Cold samples all use frozen dev01; they are process-start samples, not a distribution across questions.",
            "Warm latency includes production search and serialization, excludes subsequent integrity-check fetches.",
            "Raw FTS, memory-fts-v1 and relevance-only memory-v1 use identical records and scope; KG is absent from this fixture.",
            "Host hardware and other concurrent workloads affect latency; pilot does not enable rollout.",
        ],
        "raw_runs": raw,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
    if failures:
        raise SystemExit("functional qualification failed; evidence retained")


if __name__ == "__main__":
    main()

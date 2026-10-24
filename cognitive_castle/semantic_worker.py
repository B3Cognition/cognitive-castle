"""One fixed isolated tokenize/infer executable; never a permanent model process."""

from __future__ import annotations

import argparse
import importlib.abc
import json
import os
from pathlib import Path
import sys

MAX_FRAME = 512 * 1024
TASK_RSS = 512 * 1024**2
TOTAL_RSS = 640 * 1024**2


class _ForbiddenImports(importlib.abc.MetaPathFinder):
    def __init__(self, operation):
        self.operation = operation

    def find_spec(self, fullname, path=None, target=None):
        root = fullname.partition(".")[0]
        blocked = {
            "torch",
            "transformers",
            "sentence_transformers",
            "tensorflow",
            "keras",
            "mlx",
            "ollama",
            "openai",
            "anthropic",
            "requests",
            "httpx",
            "onnx",
            "onnxruntime_extensions",
            "optimum",
            "pandas",
            "lancedb",
            "lance",
            "pyarrow",
        }
        blocked |= {"numpy", "onnxruntime"} if self.operation == "tokenize" else {"tokenizers"}
        if root in blocked or fullname.startswith(
            (
                "cognitive_castle.embedding",
                "cognitive_castle.backends",
                "cognitive_castle.searcher",
                "cognitive_castle.reranker",
                "cognitive_castle.llm",
            )
        ):
            raise ModuleNotFoundError("semantic worker forbids optional runtime: " + fullname)
        return None


def _install_guards(operation):
    sys.meta_path.insert(0, _ForbiddenImports(operation))

    def audit(event, args):
        if event.startswith("socket.") or event in {
            "subprocess.Popen",
            "os.system",
            "os.exec",
            "os.fork",
            "os.forkpty",
            "os.posix_spawn",
        }:
            raise PermissionError("semantic worker forbids network and children")

    sys.addaudithook(audit)


def _admit(request):
    """Require the existing supervisor's exact live guardian/session chain."""
    import psutil
    from cognitive_castle.brain_reader_guardian import _group_rss

    if sys.platform != "darwin" or type(request.get("_host_pid")) is not int:
        return "semantic_unsupervised"
    try:
        guardian = psutil.Process(os.getppid())
        host = psutil.Process(request["_host_pid"])
        expected = Path(__file__).with_name("brain_reader_guardian.py").resolve()
        command = guardian.cmdline()
        if (
            guardian.ppid() != host.pid
            or os.getpgrp() != guardian.pid
            or os.getsid(0) != guardian.pid
            or os.getsid(guardian.pid) != guardian.pid
            or len(command) != 3
            or command[1] != "-I"
            or Path(command[2]).resolve() != expected
            or guardian.uids().effective != os.getuid()
            or host.uids().effective != os.getuid()
        ):
            return "semantic_unsupervised"
        task = _group_rss(guardian.pid)
        if task > TASK_RSS:
            return "worker_memory_limit"
        if task + host.memory_info().rss > TOTAL_RSS:
            return "total_memory_limit"
    except (OSError, psutil.Error):
        return "semantic_unsupervised"
    return None


def _infer(paths, page):
    from cognitive_castle.semantic_profile import DIMENSION, validate_sequence, validate_vector

    import numpy as np
    import onnxruntime as ort

    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    session = ort.InferenceSession(
        str(paths["model_qint8_arm64.onnx"]),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    if session.get_providers() != ["CPUExecutionProvider"]:
        raise ValueError("non-CPU execution provider")
    inputs = {item.name: item for item in session.get_inputs()}
    if not {"input_ids", "attention_mask"} <= inputs.keys() or inputs.keys() - {
        "input_ids",
        "attention_mask",
        "token_type_ids",
    }:
        raise ValueError("ONNX input signature")
    vectors = []
    for unit in page["units"]:
        row = unit["tokens"]
        validate_sequence(row)
        feed = {}
        for name, item in inputs.items():
            dtype = {"tensor(int64)": np.int64, "tensor(int32)": np.int32}.get(item.type)
            if dtype is None:
                raise ValueError("ONNX input type")
            feed[name] = np.asarray([row[name]], dtype=dtype)
        outputs = session.run(None, feed)
        rank3 = [value for value in outputs if getattr(value, "ndim", None) == 3]
        if len(rank3) != 1 or rank3[0].shape != (1, len(row["input_ids"]), DIMENSION):
            raise ValueError("ONNX output shape")
        token_vectors = rank3[0][0]
        if not np.isfinite(token_vectors).all():
            raise ValueError("nonfinite token embeddings")
        weights = np.asarray(row["attention_mask"], dtype=np.float32)[:, None]
        pooled = (token_vectors.astype(np.float32) * weights).sum(axis=0) / weights.sum()
        norm = float(np.linalg.norm(pooled))
        if not np.isfinite(norm) or norm <= 0:
            raise ValueError("invalid pooling norm")
        vector = (pooled / norm).tolist()
        validate_vector(vector)
        vectors.append({"unit_id": unit["unit_id"], "vector": vector})
    return {
        "status": "ok",
        "profile": page["profile"],
        "handoff_hash": page["handoff_hash"],
        "input_binding": page["input_binding"],
        "start_window": page["start_window"],
        "total_units": page["total_units"],
        "next_continuation": page["next_continuation"],
        "complete": page["complete"],
        "vectors": vectors,
        "runtime": {
            "onnxruntime": ort.__version__,
            "providers": session.get_providers(),
            "tokenizer_loaded": "tokenizers" in sys.modules,
        },
    }


def _execute(request, profile):
    from cognitive_castle.semantic_profile import load_profile, validate_runtime_versions
    from cognitive_castle.semantic_windows import tokenize_page, validate_page, validate_sources

    if (
        set(request) != {"operation", "arguments", "_host_pid"}
        or request["operation"] not in {"tokenize", "infer"}
        or not isinstance(request["arguments"], dict)
    ):
        raise ValueError("semantic operation signature")
    operation, arguments = request["operation"], request["arguments"]
    if operation == "tokenize":
        if set(arguments) != {"sources", "continuation"}:
            raise ValueError("tokenize arguments")
        validate_sources(arguments["sources"])
    else:
        if set(arguments) != {"page", "expected_handoff"}:
            raise ValueError("infer arguments")
        validate_page(arguments["page"])
        if arguments["expected_handoff"] != arguments["page"]["handoff_hash"]:
            raise ValueError("infer handoff mismatch")
    _install_guards(operation)
    validate_runtime_versions()
    paths = load_profile(profile)
    if operation == "tokenize":
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(paths["tokenizer.json"]))
        return tokenize_page(tokenizer, arguments["sources"], arguments["continuation"])
    return _infer(paths, arguments["page"])


def main():
    os.umask(0o077)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    # Only the executable's own trusted checkout supplies imports; -I ignores cwd.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cognitive_castle.semantic_profile import decode_frame

    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args()
    try:
        request = decode_frame(sys.stdin.buffer.read(MAX_FRAME + 1))
        refusal = _admit(request)
        if refusal:
            result = {"status": "unavailable", "reason": refusal}
        else:
            result = _execute(request, args.profile)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OSError):
        result = {"status": "unavailable", "reason": "semantic_invalid_request"}
    except Exception as exc:
        result = {"status": "unavailable", "reason": "semantic_" + type(exc).__name__}
    output = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(output) > MAX_FRAME:
        output = b'{"status":"unavailable","reason":"worker_output_limit"}'
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()

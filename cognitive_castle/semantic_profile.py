"""Immutable offline semantic contract. This module imports no native runtime.

Artifact paths are supplied by trusted host preparation, never tool arguments.
The manifest supplies locations/receipts only; it cannot override this contract.
"""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import stat

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MAX_FRAME = 512 * 1024
MAX_TOKENS = 128
DIMENSION = 384
VOCAB_SIZE = 250037
PINNED_FILES = {
    "model_qint8_arm64.onnx": (
        118412398,
        "783fea82d71a58179b830a4dbd2d58447e640609e98eedf9ffa12622d375a672",
    ),
    "tokenizer.json": (9081518, "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8"),
    "tokenizer_config.json": (
        526,
        "5036ea374ffedd706e3bef33e2e0d6953cb868ef8a490e76e32ba0faa37a6b9b",
    ),
    "sentence_bert_config.json": (
        53,
        "70f4448f31320443fe3557cacea5abf2dcc4915dda8c80646bec9f3bb0aa5a1f",
    ),
    "1_Pooling/config.json": (
        190,
        "4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23",
    ),
    "config.json": (645, "6300193cb75e01cf80c96decef7187dfb33094d97cc1490b7ead6ff134476e4e"),
}
RUNTIME_VERSIONS = {"tokenizers": "0.22.2", "onnxruntime": "1.25.1"}
CONTRACT = {
    "runtime_versions": RUNTIME_VERSIONS,
    "model": MODEL,
    "revision": REVISION,
    "files": PINNED_FILES,
    "windowing": "exact-overflow-v1",
    "max_tokens": MAX_TOKENS,
    "content_overlap": 32,
    "dimension": DIMENSION,
    "lowercase": False,
    "pooling": "attention_mask_mean_then_l2_normalize",
    "inference": {
        "artifact": "qint8_arm64",
        "provider": "CPUExecutionProvider",
        "intra_threads": 1,
        "inter_threads": 1,
        "execution": "sequential",
        "cpu_arena": False,
        "memory_pattern": False,
        "graph_optimizations": "default",
        "telemetry": False,
    },
}


def canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


PROFILE_ID = digest(CONTRACT)


def decode_frame(frame):
    if not isinstance(frame, bytes) or len(frame) > MAX_FRAME:
        raise ValueError("frame limit")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate frame key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("nonfinite JSON")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON number")
        return parsed

    try:
        result = json.loads(
            frame,
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
        if not isinstance(result, dict):
            raise ValueError("object frame required")
        return result
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid frame") from exc


def _owned_file(path, *, symlink=False):
    path = Path(path)
    if not path.is_absolute() or (path.is_symlink() and not symlink):
        raise ValueError("unsafe artifact path")
    path = path.resolve(strict=True)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError("unsafe artifact ownership or permissions")
    return path


def load_profile(manifest):
    """Verify all six pinned artifacts before importing Tokenizers or ORT."""
    manifest = _owned_file(manifest)
    if manifest.stat().st_size > MAX_FRAME:
        raise ValueError("manifest limit")
    profile = decode_frame(manifest.read_bytes())
    if profile.get("model") != MODEL or profile.get("revision") != REVISION:
        raise ValueError("unpinned model or revision")
    files = profile.get("files")
    if not isinstance(files, dict) or set(files) != set(PINNED_FILES) - {"model_qint8_arm64.onnx"}:
        raise ValueError("artifact file set")
    paths = {"model_qint8_arm64.onnx": profile.get("artifact_path")}
    for name, receipt in files.items():
        if not isinstance(receipt, dict):
            raise ValueError("invalid artifact receipt")
        size, sha = PINNED_FILES[name]
        if receipt.get("bytes") != size or receipt.get("sha256") != sha:
            raise ValueError("unpinned receipt")
        paths[name] = receipt.get("path")
    size, sha = PINNED_FILES["model_qint8_arm64.onnx"]
    if profile.get("artifact_bytes") != size or profile.get("artifact_sha256") != sha:
        raise ValueError("unpinned model receipt")
    for name, location in paths.items():
        if not isinstance(location, str):
            raise ValueError("missing artifact location")
        path = _owned_file(location, symlink=True)
        size, expected = PINNED_FILES[name]
        if path.stat().st_size != size:
            raise ValueError("artifact size mismatch")
        hashed = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                hashed.update(block)
        if hashed.hexdigest() != expected:
            raise ValueError("artifact hash mismatch")
        paths[name] = path
    return paths


def validate_sequence(row):
    if not isinstance(row, dict) or set(row) != {"input_ids", "attention_mask", "token_type_ids"}:
        raise ValueError("token signature")
    ids, mask, types = (row[key] for key in ("input_ids", "attention_mask", "token_type_ids"))
    if not all(isinstance(values, list) for values in (ids, mask, types)):
        raise ValueError("token array type")
    if not 0 < len(ids) <= MAX_TOKENS or len(mask) != len(ids) or len(types) != len(ids):
        raise ValueError("token shape")
    if any(type(value) is not int or not 0 <= value < VOCAB_SIZE for value in ids):
        raise ValueError("token vocabulary")
    if any(type(value) is not int or value not in (0, 1) for value in mask + types) or not any(
        mask
    ):
        raise ValueError("token masks")


def validate_vector(vector):
    if not isinstance(vector, list) or len(vector) != DIMENSION:
        raise ValueError("vector dimension")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
        raise ValueError("nonfinite vector")
    if abs(math.sqrt(sum(value * value for value in vector)) - 1.0) > 1e-5:
        raise ValueError("vector normalization")


def validate_runtime_versions():
    """Distribution metadata is safe in the host/worker before native imports."""
    try:
        observed = {name: metadata.version(name) for name in RUNTIME_VERSIONS}
    except metadata.PackageNotFoundError as exc:
        raise ValueError("qualified runtime version unavailable") from exc
    if observed != RUNTIME_VERSIONS:
        raise ValueError("unqualified runtime version")
    return observed

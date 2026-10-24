"""Guarded offline qualification; never reads a palace or imports native packages here.

Set CASTLE_TEST_SEMANTIC_PROFILE to an operator-prepared pinned manifest to run
native qualification. Missing/pressure/refusal outcomes remain explicit evidence.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from cognitive_castle.canonical_records import prepare_remember


DOCUMENTS = [
    "The project review was moved to Thursday afternoon.",
    "The train to Prague leaves at 18:30.",
    "Mira prefers black coffee without sugar.",
    "The roses should be watered every morning.",
    "The flight to Vienna was delayed by two hours.",
    "The novel was written by Karel Čapek.",
    "The server backup runs every Sunday night.",
    "The project review will take place in the small conference room.",
]
QUERIES = [
    "Na kdy byla schůzka k projektu přesunuta?",
    "Um wie viel Uhr fährt der Zug nach Prag ab?",
    "¿Con qué frecuencia hay que regar las rosas?",
]


def envelope(texts):
    result = []
    for index, text in enumerate(texts):
        record = prepare_remember(str(index), text).records[0].source()
        result.append({"source": record, "expected_hash": record["provenance"]["text_hash"]})
    return result


def test_unsupervised_invocation_refuses_before_missing_profile_read(tmp_path):
    from cognitive_castle import semantic_runtime

    worker = Path(semantic_runtime.__file__).with_name("semantic_worker.py")
    result = subprocess.run(
        [sys.executable, "-I", str(worker), "--profile", str(tmp_path / "missing")],
        input=b'{"operation":"tokenize","arguments":{},"_host_pid":1}',
        capture_output=True,
        timeout=3,
    )
    assert json.loads(result.stdout) == {"status": "unavailable", "reason": "semantic_unsupervised"}


@pytest.fixture
def profile():
    location = os.environ.get("CASTLE_TEST_SEMANTIC_PROFILE")
    if not location:
        pytest.skip("operator-prepared pinned offline profile not selected")
    return Path(location)


def run(texts, profile, continuation=None, infer=True):
    from cognitive_castle.semantic_runtime import SemanticSession

    # Existing test-only retries allow capture/admission/pressure to clear; each
    # attempt is a fresh fixed budget, and no production retry is added.
    refusals = []
    import psutil

    parent = psutil.Process()
    for _ in range(5):
        before = {(child.pid, child.create_time()) for child in parent.children(recursive=True)}
        started = time.monotonic()
        with SemanticSession(profile) as session:
            page = session.tokenize(envelope(texts), continuation)
            result = session.infer(page) if infer and page.get("status") == "ok" else page
            evidence = {
                "result_status": result.get("status"),
                "reason": result.get("reason"),
                "resources": session.resources,
                "elapsed_end_to_end_seconds": round(time.monotonic() - started, 4),
                "page_bytes": len(
                    json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode()
                ),
                "response_bytes": len(
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
                ),
                "total_units": page.get("total_units"),
                "start_window": page.get("start_window"),
                "returned_units": len(page.get("units", [])),
                "runtime": result.get("runtime"),
            }
            print(json.dumps(evidence))
        after = {(child.pid, child.create_time()) for child in parent.children(recursive=True)}
        assert after <= before, "semantic descendants survived session cleanup"
        if result.get("status") == "ok":
            return page, result
        refusals.append(evidence)
        if result.get("reason") not in {
            "memory_busy",
            "system_pressure_unavailable",
            "parent_memory_limit",
            "total_memory_limit",
        }:
            break
        time.sleep(0.2)
    pytest.fail("guarded semantic refusal: " + json.dumps(refusals))


def test_pinned_offline_multilingual_rankings(profile):
    _, docs = run(DOCUMENTS, profile)
    _, queries = run(QUERIES, profile)
    vectors = [row["vector"] for row in docs["vectors"]]
    for query, expected in zip(queries["vectors"], [0, 1, 3]):
        scores = [sum(a * b for a, b in zip(query["vector"], vector)) for vector in vectors]
        assert max(range(8), key=scores.__getitem__) == expected
    assert not {"tokenizers", "numpy", "onnxruntime"} & sys.modules.keys()


def test_unicode_long_tail_paging_and_nonsemantic_complete(profile):
    texts = ["  Česky\x00 Německy 尾 🇨🇿 " * 200] * 2 + [" \t\n   "]
    first, inferred = run(texts, profile)
    assert len(inferred["vectors"]) == 32
    assert first["total_units"] > 32
    pages = [first]
    while pages[-1]["next_continuation"]:
        page, _ = run(texts, profile, pages[-1]["next_continuation"], infer=False)
        pages.append(page)
    units = [unit for page in pages for unit in page["units"]]
    for index, text in enumerate(texts):
        canonical_id = envelope(texts)[index]["source"]["id"]
        selected = [unit for unit in units if unit["canonical_id"] == canonical_id]
        assert selected[0]["char_start"] == 0
        assert selected[-1]["char_end"] == len(text)
        assert selected[0]["token_start"] == 0
        for left, right in zip(selected, selected[1:]):
            assert right["token_start"] == left["token_end"] - 32
        if index == 2:
            assert len(selected) == 1 and selected[0]["nonsemantic"]
    assert pages[-1]["complete"]


def test_invalid_profile_refuses_and_admission_cleanup(tmp_path, profile):
    from cognitive_castle import memory_runtime
    from cognitive_castle.semantic_runtime import SemanticSession

    manifest = tmp_path / "invalid.json"
    manifest.write_text('{"model":"untrusted"}')
    manifest.chmod(0o600)
    with SemanticSession(manifest) as session:
        result = session.tokenize(envelope(["synthetic"]))
    print(json.dumps({"invalid_profile": result, "resources": session.resources}))
    assert result["reason"] == "semantic_invalid_request"
    fd = memory_runtime._admission()
    os.close(fd)


@pytest.mark.parametrize(
    "operation,blocked", [("tokenize", ["numpy", "onnxruntime"]), ("infer", ["tokenizers"])]
)
def test_worker_guard_denies_phase_cross_imports_network_and_children(operation, blocked):
    from cognitive_castle import semantic_runtime

    checkout = str(Path(semantic_runtime.__file__).parents[1])
    program = """
import importlib,json,socket,subprocess,sys
sys.path.insert(0,sys.argv[1])
from cognitive_castle.semantic_worker import _install_guards
_install_guards(sys.argv[2])
results=[]
for name in json.loads(sys.argv[3])+['torch','sentence_transformers','pandas','lance','lancedb','openai']:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        results.append(name)
    else:
        raise AssertionError('forbidden import: '+name)
for call in (lambda: socket.socket(),lambda: subprocess.run([sys.executable,'-c','pass'])):
    try:
        call()
    except PermissionError:
        results.append('denied')
    else:
        raise AssertionError('forbidden operation')
print(json.dumps(results))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", program, checkout, operation, json.dumps(blocked)],
        capture_output=True,
        timeout=3,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout)[-2:] == ["denied", "denied"]

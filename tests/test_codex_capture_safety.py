"""Capture safety regressions; no models or personal archive are used."""

import builtins
from pathlib import Path

import pytest

from cognitive_castle.codex_hooks import handle_hook
from cognitive_castle.config import CognitiveCastleConfig
from cognitive_castle.convo_miner import mine_convos
from cognitive_castle.palace import mine_palace_lock


@pytest.mark.parametrize("event", ["stop", "precompact"])
def test_paused_capture_does_not_import_storage(tmp_path, monkeypatch, event):
    marker = Path.home() / ".castle" / "codex-capture.disabled"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    transcript = tmp_path / "current.txt"
    transcript.write_text("> Exact words.\nAnswer.\n")
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"config", "palace", "convo_miner"}:
            pytest.fail(f"Paused capture imported {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    try:
        assert handle_hook(event, {"transcript_path": str(transcript)}) == {}
    finally:
        marker.unlink()


def test_capture_skips_busy_palace_then_can_retry(tmp_path, monkeypatch):
    transcript = tmp_path / "current.txt"
    transcript.write_text("> Exact words.\nAnswer.\n")
    data = {"transcript_path": str(transcript)}
    calls = []
    monkeypatch.setattr("cognitive_castle.convo_miner.mine_convos", lambda **kw: calls.append(kw))
    with mine_palace_lock(CognitiveCastleConfig().palace_path):
        assert handle_hook("stop", data) == {}
        assert handle_hook("precompact", data) == {}
    assert calls == []
    handle_hook("stop", data)
    assert len(calls) == 1
    assert calls[0]["skip_kg"] is True


def test_capture_holds_lock_during_mining_and_releases_after_failure(tmp_path, monkeypatch):
    transcript = tmp_path / "current.txt"
    transcript.write_text("> Exact words.\nAnswer.\n")
    data = {"transcript_path": str(transcript)}
    calls = []

    def failing_mine(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            handle_hook("precompact", data)
            raise OSError("test storage failure")

    monkeypatch.setattr("cognitive_castle.convo_miner.mine_convos", failing_mine)
    with pytest.raises(OSError, match="test storage failure"):
        handle_hook("stop", data)
    assert len(calls) == 1
    handle_hook("stop", data)
    assert len(calls) == 2


def test_dry_run_does_not_enrich_archive(tmp_path, monkeypatch, capsys):
    transcript = tmp_path / "current.txt"
    transcript.write_text("> Preserve these exact words.\nAnswer.\n")
    touched = []
    monkeypatch.setattr("cognitive_castle.kg_enricher.enrich_palace", lambda *a: touched.append(a))
    mine_convos(str(transcript), str(tmp_path / "palace"), dry_run=True)
    assert "current.txt" in capsys.readouterr().out
    assert touched == []


def test_capture_stores_verbatim_and_retries_without_kg_or_models(tmp_path, monkeypatch):
    """Exercise real normalization, storage and dedup with synthetic embeddings."""
    from cognitive_castle.palace import get_collection

    transcript = tmp_path / "current.txt"
    original = "> Preserve these exact words.\n  Answer with spacing.\n"
    transcript.write_text(original)
    touched = []
    monkeypatch.setattr("cognitive_castle.kg_enricher.enrich_palace", lambda *a: touched.append(a))
    dimension = CognitiveCastleConfig().embedder_dim
    monkeypatch.setattr(
        "cognitive_castle.embedding.embed_texts",
        lambda texts, *a, **kw: [[1.0] + [0.0] * (dimension - 1) for _ in texts],
    )
    original_import = builtins.__import__

    def no_model_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.split(".")[0] in {"torch", "sentence_transformers", "transformers"}:
            pytest.fail(f"Safety test attempted model import: {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", no_model_import)
    data = {"transcript_path": str(transcript), "cwd": "/work/safety"}
    handle_hook("stop", data)
    handle_hook("precompact", data)
    collection = get_collection(CognitiveCastleConfig().palace_path)
    result = collection.get(where={"source_file": str(transcript.resolve())})
    assert result["documents"] == [original]
    assert touched == []

from argparse import Namespace
import json

import pytest

from cognitive_castle.config import CognitiveCastleConfig
from cognitive_castle.context import PalacePaths
from cognitive_castle.memory_types import MemoryError
from cognitive_castle.provider_setup import prepare_provider
from cognitive_castle.provider_worker import _open_service, _UnavailableService


@pytest.fixture
def prepared(synthetic_palace, tmp_path):
    import lancedb

    directory = tmp_path / "config"
    directory.mkdir()
    config_path = directory / "config.json"
    config_path.write_text(
        json.dumps({"embedder_model": "synthetic", "embedder_dim": 4, "embedding_device": "cpu"})
    )
    db = lancedb.connect(str(synthetic_palace.root / "lancedb"))
    db.create_table("castle_metadata", [{"key": "embedder_identity", "value": "synthetic"}])
    prepare_provider(
        PalacePaths.resolve(synthetic_palace.root),
        namespace="test",
        config=CognitiveCastleConfig(config_dir=directory),
    )
    return Namespace(
        palace=str(synthetic_palace.root),
        config=str(config_path),
        namespace="test",
        wing=["approved"],
    )


def test_worker_prewarms_only_bound_offline_cpu_models(prepared, monkeypatch):
    calls = []

    def encoder(device, *, cfg):
        import os

        assert os.environ["HF_HUB_OFFLINE"] == os.environ["TRANSFORMERS_OFFLINE"] == "1"
        calls.append((device, cfg.embedder_model))

    def reranker(query, candidates, *, device, cfg):
        calls.append((device, cfg.reranker_model_cpu))
        assert query == "local preflight" and candidates == ["local preflight"]
        return [1.0]

    monkeypatch.setattr("cognitive_castle.embedding._get_model", encoder)
    monkeypatch.setattr("cognitive_castle.reranker.rerank", reranker)
    context, service = _open_service(prepared)
    try:
        assert service.health().status == "ready"
        assert calls == [("cpu", "synthetic"), ("cpu", "BAAI/bge-reranker-base")]
    finally:
        context.close()


def test_missing_model_is_safe_unavailable_and_context_is_closed(prepared, monkeypatch):
    closed = []
    from cognitive_castle.context import CastleContext

    original = CastleContext.close

    def close(self):
        closed.append(True)
        original(self)

    def missing(*args, **kwargs):
        raise OSError("private local path model failure")

    monkeypatch.setattr(CastleContext, "close", close)
    monkeypatch.setattr("cognitive_castle.embedding._get_model", missing)
    with pytest.raises(MemoryError, match="^unavailable$"):
        _open_service(prepared)
    assert closed == [True]


@pytest.mark.parametrize(
    "change", [{"palace": "relative"}, {"config": "relative"}, {"namespace": "wrong"}]
)
def test_bad_worker_binding_fails_before_loading_models(prepared, monkeypatch, change):
    for name, value in change.items():
        setattr(prepared, name, value)
    monkeypatch.setattr(
        "cognitive_castle.embedding._get_model",
        lambda *a, **kw: pytest.fail("model loaded for invalid grant"),
    )
    with pytest.raises(MemoryError, match="incompatible_store"):
        _open_service(prepared)


def test_unavailable_service_never_exposes_internal_details():
    service = _UnavailableService("unavailable")
    for method in ("health", "search", "fetch", "snapshot"):
        with pytest.raises(MemoryError, match="^unavailable$"):
            getattr(service, method)()

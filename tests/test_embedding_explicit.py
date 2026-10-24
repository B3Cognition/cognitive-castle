"""Explicit embedding config reaches model loading and same-model CPU retry."""

import sys
from types import SimpleNamespace

import numpy as np

from cognitive_castle import embedding


def test_explicit_config_selects_model_cpu_and_keeps_contexts_separate(monkeypatch):
    class Encoder:
        def __init__(self, name, device):
            self.name, self.device = name, device

        def encode(self, texts, **kwargs):
            assert self.device == "cpu"
            return np.array(
                [[1.0, 0.0] if self.name == "first/model" else [0.0, 1.0] for _ in texts]
            )

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder)
    )
    monkeypatch.setattr(embedding, "_model_cache", {})
    monkeypatch.setenv("CASTLE_EMBEDDER_MODEL", "ambient/model")
    first = SimpleNamespace(embedder_model="first/model", embedding_device="cpu")
    second = SimpleNamespace(embedder_model="second/model", embedding_device="cpu")
    assert embedding.embed_texts(["source"], cfg=first) == [[1.0, 0.0]]
    assert embedding.embed_texts(["source"], cfg=second) == [[0.0, 1.0]]
    function = embedding.get_embedding_function(cfg=first)
    assert function(["source"]) == [[1.0, 0.0]]


def test_explicit_config_cpu_fallback_keeps_configured_model(monkeypatch):
    class Encoder:
        def __init__(self, name, device):
            self.name, self.device = name, device

        def encode(self, texts, **kwargs):
            assert self.name == "explicit/model"
            if self.device == "cuda":
                raise RuntimeError("CUDA out of memory")
            return np.array([[0.0, 1.0] for _ in texts])

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder)
    )
    monkeypatch.setattr(embedding, "_model_cache", {})
    monkeypatch.setenv("CASTLE_EMBEDDER_MODEL", "ambient/model")
    config = SimpleNamespace(embedder_model="explicit/model", embedding_device="cuda")
    assert embedding.embed_texts(["original words"], cfg=config) == [[0.0, 1.0]]

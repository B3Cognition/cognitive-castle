"""The optional NLP boundary may never load a real model in these tests."""

import builtins
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace


def test_parser_and_consumers_import_without_optional_model(monkeypatch):
    real_import = builtins.__import__

    def no_model(name, *args, **kwargs):
        if name.split(".")[0] in {"spacy", "torch", "transformers", "sentence_transformers"}:
            raise AssertionError("model package imported")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_model)
    for name in ("markdown_parser", "semantic_metrics", "entity_metrics"):
        module = importlib.import_module("cognitive_castle.understanding." + name)
        importlib.reload(module)


def test_explicit_opt_out_reaches_parser_semantics_and_entities(monkeypatch):
    from cognitive_castle.understanding import nlp_runtime
    from cognitive_castle.understanding.enhanced_metrics import analyze_with_enhanced_metrics
    from cognitive_castle.understanding.entity_metrics import EntityExtractor
    from cognitive_castle.understanding.markdown_parser import extract_requirements
    from cognitive_castle.understanding.semantic_metrics import SemanticAnalyzer

    def forbidden():
        raise AssertionError("opt-out consulted the shared NLP loader")

    monkeypatch.setattr(nlp_runtime, "get_nlp", forbidden)
    text = "The system must store a complete audit record."
    assert extract_requirements(text, use_spacy=False)
    assert EntityExtractor(use_spacy=False).nlp is None
    assert SemanticAnalyzer(use_spacy=False).nlp is None
    result = analyze_with_enhanced_metrics(text, use_spacy=False)
    assert isinstance(result["enhanced_metrics"]["overall_weighted_average"], float)


def test_concurrent_consumers_share_one_complete_pipeline(monkeypatch):
    from cognitive_castle.understanding import nlp_runtime
    from cognitive_castle.understanding.entity_metrics import EntityExtractor
    from cognitive_castle.understanding.markdown_parser import extract_requirements
    from cognitive_castle.understanding.semantic_metrics import SemanticAnalyzer

    calls = []

    def pipeline(text):
        return SimpleNamespace(sents=[SimpleNamespace(text="Shared sentence from fake pipeline.")])

    def load(name):
        calls.append(name)
        return pipeline

    monkeypatch.setitem(sys.modules, "spacy", SimpleNamespace(load=load))
    nlp_runtime.reset_nlp()
    try:
        jobs = [lambda: SemanticAnalyzer().nlp, lambda: EntityExtractor().nlp] * 8
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert all(item is pipeline for item in pool.map(lambda job: job(), jobs))
        assert extract_requirements("A sufficiently long prose sentence.") == [
            "Shared sentence from fake pipeline."
        ]
        assert calls == ["en_core_web_sm"]
    finally:
        nlp_runtime.reset_nlp()


def test_missing_model_cached_until_explicit_reset(monkeypatch):
    from cognitive_castle.understanding import nlp_runtime

    calls = []

    def missing(name):
        calls.append(name)
        raise OSError("model missing")

    fake_spacy = SimpleNamespace(load=missing)
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)
    nlp_runtime.reset_nlp()
    try:
        assert nlp_runtime.get_nlp() is None
        pipeline = object()
        fake_spacy.load = lambda name: pipeline
        assert nlp_runtime.get_nlp() is None
        assert calls == ["en_core_web_sm"]
        nlp_runtime.reset_nlp()
        assert nlp_runtime.get_nlp() is pipeline
    finally:
        nlp_runtime.reset_nlp()

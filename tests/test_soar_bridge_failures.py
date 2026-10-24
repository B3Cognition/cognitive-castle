"""Migration diagnostics and native/model-free execution of symbolic ranking."""

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from cognitive_castle import soar_bridge as bridge
from cognitive_castle.config import CognitiveCastleConfig


@pytest.mark.parametrize("exists", [False, True])
def test_custom_rules_explicitly_disable_boosts_and_reset_audits(tmp_path, capsys, exists):
    path = tmp_path / "custom.soar"
    if exists:
        path.write_text("arbitrary custom production contents")
    hits = [
        {
            "score": 0.7,
            "entity_match": True,
            "soar_tags": ["stale"],
            "soar_boost": 5.0,
            "score_pre_soar": 0.1,
            "symbolic_status": "applied",
        }
    ]
    original = deepcopy(hits)
    result = bridge.apply_soar_boosts(hits, SimpleNamespace(soar_rules_path=str(path)))
    assert result[0]["score"] == 0.7
    assert result[0]["score_pre_soar"] == 0.7
    assert result[0]["soar_boost"] == 1.0
    assert result[0]["soar_tags"] == []
    assert result[0]["symbolic_status"] == "unsupported_custom_rules"
    assert hits == original
    warning = capsys.readouterr().err
    assert "unsupported" in warning and "CASTLE_SOAR_RULES_PATH" in warning


@pytest.mark.parametrize("source", ["environment", "config_file"])
def test_custom_configuration_reaches_the_migration_diagnostic(source, monkeypatch, capsys):
    monkeypatch.delenv("CASTLE_SOAR_RULES_PATH", raising=False)
    cfg = CognitiveCastleConfig.__new__(CognitiveCastleConfig)
    cfg._file_config = {}
    if source == "environment":
        monkeypatch.setenv("CASTLE_SOAR_RULES_PATH", "/custom.soar")
    else:
        cfg._file_config["soar_rules_path"] = "/custom.soar"
    result = bridge._apply_soar_to_reranked([(1.0, {"entity_match": True})], cfg)
    assert result[0][0] == 1.0
    assert result[0][1]["symbolic_status"] == "unsupported_custom_rules"
    assert "unsupported" in capsys.readouterr().err


def test_symbolic_stage_runs_with_native_and_model_imports_forbidden():
    # Fresh process prevents already-imported modules from concealing a dependency.
    script = r"""
import importlib.abc, sys
from types import SimpleNamespace
class NoNativeOrModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'Python_sml_ClientInterface', '_Python_sml_ClientInterface',
                                     'torch', 'transformers', 'sentence_transformers', 'spacy'}:
            raise AssertionError('forbidden import: ' + fullname)
sys.meta_path.insert(0, NoNativeOrModels())
from cognitive_castle.searcher import _stage_5_symbolic
from cognitive_castle.soar_bridge import apply_soar_boosts
cfg = SimpleNamespace(soar_rules_path=None)
assert apply_soar_boosts([{'score': 1.0, 'entity_match': True}], cfg)[0]['score'] == 1.3
assert _stage_5_symbolic([(1.0, {'entity_match': True})], cfg)[0][0] == 1.3
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=10
    )
    assert proc.returncode == 0, proc.stderr

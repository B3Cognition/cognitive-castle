import json

from cognitive_castle.config import CognitiveCastleConfig


def test_selected_llm_settings_survive_new_config_without_project_secrets(tmp_path):
    cfg = CognitiveCastleConfig(config_dir=tmp_path)
    cfg.set_llm_settings(
        provider="openai-compat", model="selected-model", endpoint="http://localhost:9000/v1"
    )
    fresh = CognitiveCastleConfig(config_dir=tmp_path)
    assert fresh.llm_provider == "openai-compat"
    assert fresh.llm_model == "selected-model"
    assert fresh.llm_endpoint == "http://localhost:9000/v1"
    assert set(json.loads((tmp_path / "config.json").read_text())) == {
        "llm_provider",
        "llm_model",
        "llm_endpoint",
    }


def test_environment_retains_documented_precedence(tmp_path, monkeypatch):
    cfg = CognitiveCastleConfig(config_dir=tmp_path)
    cfg.set_llm_settings(provider="ollama", model="selected-model")
    monkeypatch.setenv("CASTLE_LLM_MODEL", "environment-model")
    assert CognitiveCastleConfig(config_dir=tmp_path).llm_model == "environment-model"

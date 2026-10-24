import builtins
import subprocess


def test_import_and_construction_never_load_castle_models_or_spawn(monkeypatch, tmp_path):
    actual_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name.split(".")[0] not in {"cognitive_castle", "torch", "spacy"}
        return actual_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("construction spawned a process")

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    from prosaic_memory_castle import CastleMemoryProvider, WorkerCommand, memory_tools

    provider = CastleMemoryProvider(
        WorkerCommand(("/usr/bin/python3", "-m", "cognitive_castle.provider_worker")),
        palace_path=tmp_path,
        namespace="tenant",
        config_path=tmp_path / "cfg",
        allowed_wings=("project",),
    )
    memory_tools(provider, authorize=lambda ctx: True)
    provider.close()


def test_older_runtime_imports_cleanly_and_is_rejected_at_registration(monkeypatch):
    import importlib
    import prosaic_runtime
    import prosaic_memory_castle.tools as tools

    monkeypatch.delattr(prosaic_runtime, "ToolExecutionError")
    monkeypatch.setattr(
        prosaic_runtime.ProsaicRuntime, "capabilities", frozenset({"custom_tools_v1"})
    )
    importlib.reload(tools)
    import pytest

    with pytest.raises(ValueError, match="custom_tool_errors_v1"):
        tools.memory_tools(object(), authorize=lambda ctx: True)

import json
from types import SimpleNamespace

import pytest

from cognitive_castle.context import PalacePaths
from cognitive_castle.memory_types import MemoryError
from cognitive_castle.provider_setup import prepare_provider


def test_prepare_is_explicit_idempotent_and_refuses_rebinding(synthetic_palace):
    paths = PalacePaths.resolve(synthetic_palace.root)
    cfg = SimpleNamespace(embedder_dim=4, embedder_model="test")
    prepare_provider(paths, namespace="test", config=cfg)
    identity = paths.provider / "identity.json"
    before = identity.stat().st_mtime_ns
    prepare_provider(paths, namespace="test", config=cfg)
    assert identity.stat().st_mtime_ns == before
    with pytest.raises(MemoryError, match="incompatible_store"):
        prepare_provider(paths, namespace="other", config=cfg)
    assert json.loads(identity.read_text())["namespace"] == "test"


def test_boolean_identity_version_is_rejected(synthetic_palace):
    paths = PalacePaths.resolve(synthetic_palace.root)
    paths.provider.mkdir()
    (paths.provider / "identity.json").write_text(
        json.dumps({"schema_version": True, "namespace": "test"})
    )
    with pytest.raises(MemoryError, match="incompatible_store"):
        prepare_provider(
            paths, namespace="test", config=SimpleNamespace(embedder_dim=4, embedder_model="test")
        )

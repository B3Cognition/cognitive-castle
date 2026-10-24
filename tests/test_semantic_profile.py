"""Pinned profile, strict frames, and vector/token handoff trust boundaries."""

import json
import math

import pytest


def test_profile_identity_and_mutable_manifest_refusal(tmp_path):
    from cognitive_castle.semantic_profile import PROFILE_ID, load_profile

    assert len(PROFILE_ID) == 64
    manifest = tmp_path / "profile.json"
    manifest.write_text(json.dumps({"model": "other", "revision": "mutable"}))
    manifest.chmod(0o600)
    with pytest.raises(ValueError):
        load_profile(manifest)


def test_duplicate_nonfinite_and_oversized_frames_refuse():
    from cognitive_castle.semantic_profile import decode_frame

    for frame in (
        b'{"operation":"infer","operation":"tokenize"}',
        b'{"a":NaN}',
        b'{"a":1e999}',
        b" " * 524289,
    ):
        with pytest.raises(ValueError):
            decode_frame(frame)
    assert decode_frame(b'{"a":1}') == {"a": 1}


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_ids", [True]),
        ("input_ids", [250037]),
        ("attention_mask", [0]),
        ("token_type_ids", [2]),
    ],
)
def test_invalid_token_sequence_refuses(field, value):
    from cognitive_castle.semantic_profile import validate_sequence

    row = {"input_ids": [42], "attention_mask": [1], "token_type_ids": [0]}
    row[field] = value
    with pytest.raises(ValueError):
        validate_sequence(row)


def test_nonfinite_wrong_dimension_and_unnormalized_vectors_refuse():
    from cognitive_castle.semantic_profile import validate_vector

    validate_vector([1.0] + [0.0] * 383)
    for vector in ([0.0] * 384, [1.0] * 383, [math.nan] * 384, [math.inf] * 384):
        with pytest.raises(ValueError):
            validate_vector(vector)


def test_artifact_symlink_resolves_only_to_owned_unwritable_regular_file(tmp_path):
    from cognitive_castle.semantic_profile import _owned_file

    target = tmp_path / "blob"
    target.write_bytes(b"synthetic")
    target.chmod(0o600)
    link = tmp_path / "snapshot"
    link.symlink_to(target)
    assert _owned_file(link, symlink=True) == target.resolve()
    with pytest.raises(ValueError):
        _owned_file(link)
    target.chmod(0o622)
    with pytest.raises(ValueError):
        _owned_file(link, symlink=True)
    with pytest.raises(ValueError):
        _owned_file(tmp_path)


def test_unqualified_runtime_versions_refuse_without_native_imports(monkeypatch):
    from cognitive_castle import semantic_profile

    monkeypatch.setattr(
        semantic_profile.metadata,
        "version",
        lambda name: {"tokenizers": "0.22.2", "onnxruntime": "1.25.1"}[name],
    )
    assert semantic_profile.validate_runtime_versions() == {
        "tokenizers": "0.22.2",
        "onnxruntime": "1.25.1",
    }
    monkeypatch.setattr(semantic_profile.metadata, "version", lambda name: "unqualified")
    with pytest.raises(ValueError, match="runtime version"):
        semantic_profile.validate_runtime_versions()

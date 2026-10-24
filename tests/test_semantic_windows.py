"""Pure semantic binding tests, requiring no tokenizer or native imports."""

import copy

import pytest

from cognitive_castle.canonical_records import prepare_remember


def sources(text="  Česky\x00尾  "):
    record = prepare_remember("fixture", text).records[0]
    return [
        {"source": record.source(), "expected_hash": record.source()["provenance"]["text_hash"]}
    ]


def test_exact_source_hash_and_input_limit_checked_before_tokenization():
    from cognitive_castle.semantic_windows import validate_sources

    value = sources()
    assert validate_sources(value)[0].text == "  Česky\x00尾  "
    value[0]["expected_hash"] = "0" * 64
    with pytest.raises(ValueError):
        validate_sources(value)
    with pytest.raises(ValueError):
        validate_sources(sources() * 9)


def test_stale_continuation_and_handoff_tampering_refuse():
    from cognitive_castle.semantic_windows import make_unit, page_units, validate_page

    records = sources("x" * 40)
    units = [
        make_unit(
            records[0]["source"],
            i,
            i + 1,
            i,
            i + 1,
            {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]},
            [[0, 0], [i, i + 1], [0, 0]],
        )
        for i in range(40)
    ]
    first = page_units(records, units)
    assert len(first["units"]) == 32
    assert first["total_units"] == 40
    assert first["complete"] is False
    second = page_units(records, units, first["next_continuation"])
    assert len(second["units"]) == 8 and second["complete"] is True
    with pytest.raises(ValueError):
        page_units(sources("changed"), units, first["next_continuation"])
    validate_page(first)
    changed = copy.deepcopy(first)
    changed["units"][0]["tokens"]["input_ids"][1] = 43
    with pytest.raises(ValueError):
        validate_page(changed)


def test_nonsemantic_unit_and_chunk_absolute_offsets():
    from cognitive_castle.semantic_windows import make_unit

    source = sources(" \t\x00")[0]["source"]
    source["provenance"]["chunk_start"] = 100
    source["provenance"]["chunk_end"] = 103
    unit = make_unit(
        source,
        0,
        0,
        0,
        3,
        {"input_ids": [0, 2], "attention_mask": [1, 1], "token_type_ids": [0, 0]},
        [[0, 0], [0, 0]],
    )
    assert unit["absolute_start"] == 100 and unit["absolute_end"] == 103
    assert unit["nonsemantic"] is True


def test_page_refuses_units_from_another_source_set():
    from cognitive_castle.semantic_windows import make_unit, page_units

    original = sources("original")
    unit = make_unit(
        original[0]["source"],
        0,
        1,
        0,
        8,
        {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]},
        [[0, 0], [0, 8], [0, 0]],
    )
    with pytest.raises(ValueError, match="source set"):
        page_units(sources("replacement"), [unit])

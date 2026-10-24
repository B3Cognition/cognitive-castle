"""Exact semantic windows and deterministic source-bound paging; no storage."""

from __future__ import annotations

import json
import re

from .canonical_records import CanonicalRecord
from .semantic_profile import PROFILE_ID, digest, validate_sequence

MAX_SOURCES = 8
PAGE_SIZE = 32
OVERLAP = 32
_HASH = re.compile(r"[a-f0-9]{64}")


def validate_sources(sources):
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise ValueError("source count")
    records = []
    for item in sources:
        if not isinstance(item, dict) or set(item) != {"source", "expected_hash"}:
            raise ValueError("source envelope")
        record = CanonicalRecord.from_source(item["source"])
        if item["expected_hash"] != json.loads(record.provenance_json)["text_hash"]:
            raise ValueError("expected source hash mismatch")
        records.append(record)
    return records


def input_binding(sources):
    records = validate_sources(sources)
    return digest({"profile": PROFILE_ID, "sources": [record.source() for record in records]})


def make_unit(source, token_start, token_end, char_start, char_end, tokens, offsets):
    record = CanonicalRecord.from_source(source)
    provenance = json.loads(record.provenance_json)
    validate_sequence(tokens)
    if (
        any(type(value) is not int for value in (token_start, token_end, char_start, char_end))
        or not 0 <= token_start <= token_end
        or not 0 <= char_start <= char_end <= len(record.text)
    ):
        raise ValueError("window bounds")
    _validate_offsets(offsets, len(tokens["input_ids"]), len(record.text))
    unit = {
        "canonical_id": record.id,
        "source_hash": provenance["text_hash"],
        "profile": PROFILE_ID,
        "token_start": token_start,
        "token_end": token_end,
        "char_start": char_start,
        "char_end": char_end,
        "source_length": len(record.text),
        "chunk_start": provenance["chunk_start"],
        "absolute_start": provenance["chunk_start"] + char_start,
        "absolute_end": provenance["chunk_start"] + char_end,
        "nonsemantic": token_start == token_end,
        "tokens": tokens,
        "token_offsets": offsets,
        "input_token_hash": digest(tokens),
    }
    unit["unit_id"] = digest(unit)
    return unit


def _validate_offsets(offsets, length, source_length):
    if not isinstance(offsets, list) or len(offsets) != length:
        raise ValueError("token offset shape")
    for pair in offsets:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or any(type(value) is not int for value in pair)
            or not 0 <= pair[0] <= pair[1] <= source_length
        ):
            raise ValueError("token offset bounds")


def validate_unit(unit):
    fields = {
        "canonical_id",
        "source_hash",
        "profile",
        "token_start",
        "token_end",
        "char_start",
        "char_end",
        "source_length",
        "chunk_start",
        "absolute_start",
        "absolute_end",
        "nonsemantic",
        "tokens",
        "token_offsets",
        "input_token_hash",
        "unit_id",
    }
    if not isinstance(unit, dict) or set(unit) != fields or unit["profile"] != PROFILE_ID:
        raise ValueError("unit signature")
    if not isinstance(unit["canonical_id"], str) or not re.fullmatch(
        r"memory:[a-f0-9]{64}", unit["canonical_id"]
    ):
        raise ValueError("canonical identity")
    if not isinstance(unit["source_hash"], str) or not _HASH.fullmatch(unit["source_hash"]):
        raise ValueError("source hash")
    numeric = (
        "token_start",
        "token_end",
        "char_start",
        "char_end",
        "source_length",
        "chunk_start",
        "absolute_start",
        "absolute_end",
    )
    if any(type(unit[key]) is not int or unit[key] < 0 for key in numeric):
        raise ValueError("unit offsets")
    if (
        not unit["token_start"] <= unit["token_end"]
        or not unit["char_start"] <= unit["char_end"] <= unit["source_length"] <= 8192
        or unit["absolute_start"] != unit["chunk_start"] + unit["char_start"]
        or unit["absolute_end"] != unit["chunk_start"] + unit["char_end"]
        or type(unit["nonsemantic"]) is not bool
        or unit["nonsemantic"] != (unit["token_start"] == unit["token_end"])
    ):
        raise ValueError("unit offset identity")
    validate_sequence(unit["tokens"])
    _validate_offsets(
        unit["token_offsets"], len(unit["tokens"]["input_ids"]), unit["source_length"]
    )
    if unit["input_token_hash"] != digest(unit["tokens"]) or unit["unit_id"] != digest(
        {key: value for key, value in unit.items() if key != "unit_id"}
    ):
        raise ValueError("unit handoff identity")


def page_units(sources, units, continuation=None):
    binding = input_binding(sources)
    allowed = {
        (
            record.id,
            json.loads(record.provenance_json)["text_hash"],
            json.loads(record.provenance_json)["chunk_start"],
            len(record.text),
        )
        for record in validate_sources(sources)
    }
    start = 0
    if continuation is not None:
        if (
            not isinstance(continuation, dict)
            or set(continuation) != {"binding", "next_window"}
            or continuation["binding"] != binding
            or type(continuation["next_window"]) is not int
            or not 0 < continuation["next_window"] < len(units)
            or continuation["next_window"] % PAGE_SIZE
        ):
            raise ValueError("stale or invalid continuation")
        start = continuation["next_window"]
    selected = units[start : start + PAGE_SIZE]
    for unit in selected:
        validate_unit(unit)
        if (
            unit["canonical_id"],
            unit["source_hash"],
            unit["chunk_start"],
            unit["source_length"],
        ) not in allowed:
            raise ValueError("unit does not belong to source set")
    end = start + len(selected)
    result = {
        "status": "ok",
        "profile": PROFILE_ID,
        "input_binding": binding,
        "start_window": start,
        "total_units": len(units),
        "units": selected,
        "next_continuation": {"binding": binding, "next_window": end} if end < len(units) else None,
        "complete": end == len(units),
    }
    result["handoff_hash"] = digest(result)
    return result


def validate_page(page):
    fields = {
        "status",
        "profile",
        "input_binding",
        "start_window",
        "total_units",
        "units",
        "next_continuation",
        "complete",
        "handoff_hash",
    }
    if (
        not isinstance(page, dict)
        or set(page) != fields
        or page["status"] != "ok"
        or page["profile"] != PROFILE_ID
    ):
        raise ValueError("page signature")
    if not isinstance(page["input_binding"], str) or not _HASH.fullmatch(page["input_binding"]):
        raise ValueError("input binding")
    start, total, units = page["start_window"], page["total_units"], page["units"]
    if (
        type(start) is not int
        or type(total) is not int
        or not 0 <= start < total
        or start % PAGE_SIZE
        or not isinstance(units, list)
        or len(units) != min(PAGE_SIZE, total - start)
    ):
        raise ValueError("page bounds")
    end = start + len(units)
    expected = {"binding": page["input_binding"], "next_window": end} if end < total else None
    if (
        page["next_continuation"] != expected
        or type(page["complete"]) is not bool
        or page["complete"] != (end == total)
    ):
        raise ValueError("page coverage")
    for unit in units:
        validate_unit(unit)
    if page["handoff_hash"] != digest(
        {key: value for key, value in page.items() if key != "handoff_hash"}
    ):
        raise ValueError("page handoff identity")


def tokenize_page(tokenizer, sources, continuation=None):
    """Use native overflow encodings, verifying every content token against full encoding.

    IDs/special tokens come from the pinned postprocessor, never guessed IDs or
    decoded/re-encoded text. Native offsets always refer to the unchanged source.
    """
    records = validate_sources(sources)
    units = []
    tokenizer.no_padding()
    for record in records:
        tokenizer.no_truncation()
        full = tokenizer.encode(record.text, add_special_tokens=False)
        expected = list(zip(full.ids, full.offsets))
        tokenizer.enable_truncation(max_length=128, stride=OVERLAP, strategy="longest_first")
        first = tokenizer.encode(record.text, add_special_tokens=True)
        encodings = [first, *first.overflowing]
        start = 0
        for index, encoded in enumerate(encodings):
            content = [
                (token, offset)
                for token, offset, special in zip(
                    encoded.ids, encoded.offsets, encoded.special_tokens_mask
                )
                if not special
            ]
            end = start + len(content)
            if content != expected[start:end] or (expected and not content):
                raise ValueError("native overflow coverage differs from exact token sequence")
            char_start = 0 if index == 0 else min(offset[0] for _, offset in content)
            char_end = (
                len(record.text)
                if index == len(encodings) - 1
                else max(offset[1] for _, offset in content)
            )
            tokens = {
                "input_ids": encoded.ids,
                "attention_mask": encoded.attention_mask,
                "token_type_ids": encoded.type_ids,
            }
            units.append(
                make_unit(
                    record.source(),
                    start,
                    end,
                    char_start,
                    char_end,
                    tokens,
                    [list(pair) for pair in encoded.offsets],
                )
            )
            if index < len(encodings) - 1:
                if len(content) <= OVERLAP:
                    raise ValueError("nonadvancing overflow")
                start = end - OVERLAP
        if end != len(expected):
            raise ValueError("incomplete token coverage")
    return page_units(sources, units, continuation)

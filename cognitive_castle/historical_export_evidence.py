"""Shared pure exact historical evidence packing; no storage capabilities."""

from . import bulk_exact_codec as bulk
from .canonical_records import _hash, _json


def quoted_pieces(pieces):
    yield '"'
    for piece in pieces:
        for offset in range(0, len(piece), 8192):
            yield _json(piece[offset : offset + 8192])[1:-1]
    yield '"'


def historical_scope_header(columns, metadata, kinds):
    yield (
        '{"format":"sqlite-source-scopes-v1","precedence":["columns","metadata","caller"],"origin":"history"'
    )
    for name, pieces in (("columns", columns), ("metadata", metadata)):
        yield "," + _json(name) + ":"
        yield from pieces
    yield ',"selection":{'
    for ordinal, scope in enumerate(("workspace", "wing", "room")):
        if ordinal:
            yield ","
        origin = None
        yield _json(scope) + ":{"
        for index, (name, kind) in enumerate(zip(("columns", "metadata"), kinds[scope])):
            if index:
                yield ","
            yield _json(name) + ":" + _json(kind)
            if origin is None and kind not in (None, "null"):
                origin = name
        yield ',"selected_origin":' + _json(origin or "caller") + "}"
    yield '},"chunks":['


def pages(pieces):
    """Stable packing independent of database read/chunk boundaries."""
    pending, size = [], 0
    for piece in pieces:
        for character in piece:
            width = len(character.encode())
            if size + width > bulk.PAGE_BYTES:
                yield "".join(pending)
                pending, size = [], 0
            pending.append(character)
            size += width
    if pending:
        yield "".join(pending)


def member_text(owner, ordinal, record, scopes):
    source = record.source()
    p = source["provenance"]
    return _json(
        dict(
            id=record.id,
            ordinal=ordinal,
            start=p["chunk_start"],
            end=p["chunk_end"],
            bytes=len(record.text.encode()),
            hash=p["text_hash"],
            exposure=_hash(_json(source)),
            scopes=dict(
                first_page=bulk.page_id(owner, "scopes", 0) if scopes["pages"] else None, **scopes
            ),
        )
    )

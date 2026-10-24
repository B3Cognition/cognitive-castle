import pytest

from cognitive_castle.backends import (
    GetResult,
    QueryResult,
    get_backend,
)


def test_query_result_empty_preserves_outer_dimension():
    empty = QueryResult.empty(num_queries=2)
    assert empty.ids == [[], []]
    assert empty.documents == [[], []]
    assert empty.distances == [[], []]
    assert empty.embeddings is None


def test_typed_results_support_dict_compat_access():
    """Transitional compat shim per base.py — retained until callers migrate to attrs."""
    result = GetResult(ids=["a"], documents=["da"], metadatas=[{"w": 1}])
    assert result["ids"] == ["a"]
    assert result.get("documents") == ["da"]
    assert result.get("missing", "default") == "default"
    assert "ids" in result
    assert "missing" not in result


def test_registry_unknown_backend_raises():
    with pytest.raises(KeyError):
        get_backend("no-such-backend-exists")


def test_resolve_backend_priority_order(tmp_path):
    from cognitive_castle.backends import resolve_backend_for_palace

    # explicit kwarg wins over everything
    assert resolve_backend_for_palace(explicit="pg", config_value="lance") == "pg"
    # config value wins over env / default
    assert resolve_backend_for_palace(config_value="lance", env_value="qdrant") == "lance"
    # env wins over default
    assert resolve_backend_for_palace(env_value="qdrant", default="lancedb") == "qdrant"


def test_lancedb_schema_uses_config_dim(tmp_path):
    """Schema dim is sourced from config.embedder_dim, not a hardcoded constant."""
    from unittest.mock import MagicMock
    from cognitive_castle.backends.lancedb_backend import _build_schema

    cfg_384 = MagicMock()
    cfg_384.embedder_dim = 384
    schema_384 = _build_schema(cfg_384)
    vector_field_384 = next(f for f in schema_384 if f.name == "vector")
    # pyarrow's list_ field has list_size accessible via .type.list_size
    assert vector_field_384.type.list_size == 384

    cfg_1024 = MagicMock()
    cfg_1024.embedder_dim = 1024
    schema_1024 = _build_schema(cfg_1024)
    vector_field_1024 = next(f for f in schema_1024 if f.name == "vector")
    assert vector_field_1024.type.list_size == 1024


def test_fts_index_is_created_alongside_vector(tmp_path):
    """When a backend creates a new collection, an FTS index on the text column is built."""
    from cognitive_castle.backends.lancedb_backend import LanceDBBackend, PalaceRef

    backend = LanceDBBackend()
    palace = PalaceRef(id="test", local_path=str(tmp_path / "palace"))
    col = backend.get_collection(
        palace=palace,
        collection_name="drawers",
        create=True,
    )
    # Add a row so we have something to search.
    col.add(
        documents=["the quick brown fox jumps over the lazy dog"],
        ids=["d1"],
        metadatas=[{"wing": "test", "room": "test", "ts": "2026-05-10"}],
    )
    # Refresh FTS index after adding data (create_fts_index with replace=True).
    col._ensure_fts_index(replace=True)
    # FTS should find the row by a keyword in the document.
    results = col.fts_search("brown fox", n_results=5)
    assert len(results) >= 1
    # Result row format: at minimum should have an id and the query terms in the text.
    first = results[0]
    # Be liberal in what we accept — the row may have keys "id", "ids", or be a (id, doc) tuple.
    if isinstance(first, dict):
        assert any(v == "d1" for v in first.values())
    else:
        assert "d1" in str(first)


def test_list_drawer_ids_empty_palace(collection):
    """list_drawer_ids returns [] for an empty collection."""
    assert collection.list_drawer_ids() == []


def test_list_drawer_ids_returns_all_ids(collection):
    """list_drawer_ids returns all stored drawer ids."""
    collection.add(
        documents=["alpha text", "beta text", "gamma text"],
        ids=["id-a", "id-b", "id-c"],
        metadatas=[{"wing": "w", "room": "r"} for _ in range(3)],
    )
    ids = collection.list_drawer_ids()
    assert sorted(ids) == ["id-a", "id-b", "id-c"]


def test_iter_id_text_yields_every_drawer_once(collection):
    """iter_id_text streams (id, text) for the whole collection in one pass."""
    collection.add(
        documents=["alpha text", "beta text", "gamma text"],
        ids=["id-a", "id-b", "id-c"],
        metadatas=[{"wing": "w", "room": "r"} for _ in range(3)],
    )
    assert sorted(collection.iter_id_text(batch_size=2)) == [
        ("id-a", "alpha text"),
        ("id-b", "beta text"),
        ("id-c", "gamma text"),
    ]


def test_iter_id_text_empty_palace(collection):
    assert list(collection.iter_id_text()) == []


def test_list_drawer_ids_reads_more_than_the_default_query_limit(collection):
    """A plain LanceDB query is limited to 10 rows unless told otherwise."""
    n = 25
    collection.add(
        documents=[f"text {i}" for i in range(n)],
        ids=[f"id-{i:02d}" for i in range(n)],
        metadatas=[{"wing": "w", "room": "r"} for _ in range(n)],
    )
    assert len(collection.list_drawer_ids()) == n
    assert len(list(collection.iter_id_text(batch_size=7))) == n


class _SelectSpy:
    """Wrap a LanceDB query and record every ``select`` projection."""

    def __init__(self, query, selected):
        self._query = query
        self._selected = selected

    def select(self, columns):
        self._selected.append(list(columns) if not isinstance(columns, dict) else dict(columns))
        return _SelectSpy(self._query.select(columns), self._selected)

    def __getattr__(self, name):
        attr = getattr(self._query, name)
        if not callable(attr):
            return attr

        def wrapped(*args, **kwargs):
            result = attr(*args, **kwargs)
            if hasattr(result, "to_list") and hasattr(result, "select"):
                return _SelectSpy(result, self._selected)
            return result

        return wrapped


class _TableSpy:
    def __init__(self, table, selected):
        self._table = table
        self._selected = selected

    def search(self, *args, **kwargs):
        return _SelectSpy(self._table.search(*args, **kwargs), self._selected)

    def __getattr__(self, name):
        return getattr(self._table, name)


def _spy_on_select(collection):
    selected: list = []
    collection._table = _TableSpy(collection._table, selected)
    return selected


def test_get_metadata_only_never_reads_text_or_vector(collection):
    """``get(include=["metadatas"])`` must project away text and vector.

    Without the projection every metadata-only fetch materialised full rows
    — 800-char text plus the embedding — for every match: a status call on
    an 875K-drawer palace was gigabytes, and ``file_already_mined`` on a
    361K-row source file the same.
    """
    collection.add(
        documents=["alpha text", "beta text"],
        ids=["id-a", "id-b"],
        metadatas=[
            {"wing": "w", "room": "r", "filed_at": "2026-01-01", "chunk_index": 0},
            {"wing": "w", "room": "s", "filed_at": "2026-01-02", "chunk_index": 1},
        ],
    )
    selected = _spy_on_select(collection)
    result = collection.get(include=["metadatas"], where={"wing": "w"})
    assert sorted(result["ids"]) == ["id-a", "id-b"]
    metas = sorted(result["metadatas"], key=lambda m: m["chunk_index"])
    assert metas[0]["room"] == "r" and metas[0]["filed_at"] == "2026-01-01"
    assert metas[1]["room"] == "s" and metas[1]["chunk_index"] == 1
    assert result["documents"] == []
    assert selected, "get() did not project columns"
    for cols in selected:
        assert "text" not in cols and "vector" not in cols


def test_get_documents_only_skips_vector_and_metadata(collection):
    collection.add(documents=["alpha text"], ids=["id-a"], metadatas=[{"wing": "w", "room": "r"}])
    selected = _spy_on_select(collection)
    result = collection.get(include=["documents"], ids=["id-a"])
    assert result["documents"] == ["alpha text"]
    assert result["metadatas"] == []
    for cols in selected:
        assert "vector" not in cols and "metadata_json" not in cols


def test_get_default_include_still_returns_documents_and_metadata(collection):
    collection.add(documents=["alpha text"], ids=["id-a"], metadatas=[{"wing": "w", "room": "r"}])
    result = collection.get(ids=["id-a"])
    assert result["documents"] == ["alpha text"]
    assert result["metadatas"][0]["wing"] == "w"
    assert result["embeddings"] is None
    with_vec = collection.get(ids=["id-a"], include=["embeddings"])
    assert len(with_vec["embeddings"][0]) > 0

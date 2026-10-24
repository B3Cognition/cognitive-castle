from contextlib import closing
import json
import sqlite3
from types import SimpleNamespace

import pytest

from cognitive_castle.context import CastleContext, PalacePaths
from cognitive_castle.memory import recall_health
from cognitive_castle.memory_types import MemoryError


class NoVectorOrFTS:
    dense_available = False

    def fts_search(self, *args, **kwargs):
        raise OSError("index unavailable")


@pytest.mark.parametrize("bad", ["graph", "registry", "pointer_schema"])
def test_invalid_auxiliary_files_never_certify_kg_only_recall(tmp_path, bad):
    root = tmp_path / "palace"
    paths = PalacePaths.resolve(root)
    paths.state_dir.mkdir(parents=True)
    from cognitive_castle.knowledge_graph import KnowledgeGraph

    graph = KnowledgeGraph(str(paths.knowledge_graph))
    graph.close()
    with closing(sqlite3.connect(paths.knowledge_graph)) as connection, connection:
        connection.execute("PRAGMA journal_mode=DELETE")
    paths.entity_registry.write_text(json.dumps({"people": {}, "projects": []}))
    if bad == "graph":
        paths.knowledge_graph.unlink()
        sqlite3.connect(paths.knowledge_graph).close()
    elif bad == "registry":
        paths.entity_registry.write_text("{malformed")
    else:
        with closing(sqlite3.connect(paths.knowledge_graph)) as connection, connection:
            connection.execute("DROP TABLE triple_sources")
            connection.execute("ALTER TABLE triples DROP COLUMN source_drawer_id")
    with CastleContext.open(paths, config=SimpleNamespace()) as context:
        with pytest.raises(MemoryError, match="incompatible_store"):
            recall_health(context, NoVectorOrFTS())


def test_valid_empty_graph_is_a_usable_empty_kg_signal(tmp_path):
    paths = PalacePaths.resolve(tmp_path)
    from cognitive_castle.knowledge_graph import KnowledgeGraph

    graph = KnowledgeGraph(str(paths.knowledge_graph))
    graph.close()
    with closing(sqlite3.connect(paths.knowledge_graph)) as connection, connection:
        connection.execute("PRAGMA journal_mode=DELETE")
    paths.entity_registry.write_text(json.dumps({"people": {}, "projects": []}))
    with CastleContext.open(paths, config=SimpleNamespace()) as context:
        assert recall_health(context, NoVectorOrFTS()) == ("dense", "sparse")

"""
knowledge_graph.py — Temporal Entity-Relationship Graph for Cognitive Castle
=====================================================================

Real knowledge graph with:
  - Entity nodes (people, projects, tools, concepts)
  - Typed relationship edges (daughter_of, does, loves, works_on, etc.)
  - Temporal validity (valid_from → valid_to — knows WHEN facts are true)
  - Closet references (links back to the verbatim memory)

Storage: SQLite (local, no dependencies, no subscriptions)
Query: entity-first traversal with time filtering

This is what competes with Zep's temporal knowledge graph.
Zep uses Neo4j in the cloud ($25/mo+). We use SQLite locally (free).

Usage:
    from cognitive_castle.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.add_triple("Max", "child_of", "Alice", valid_from="2015-04-01")
    kg.add_triple("Max", "does", "swimming", valid_from="2025-01-01")
    kg.add_triple("Max", "loves", "chess", valid_from="2025-10-01")

    # Query: everything about Max
    kg.query_entity("Max")

    # Query: what was true about Max in January 2026?
    kg.query_entity("Max", as_of="2026-01-15")

    # Query: who is connected to Alice?
    kg.query_entity("Alice", direction="both")

    # Invalidate: Max's sports injury resolved
    kg.invalidate("Max", "has_issue", "sports_injury", ended="2026-02-15")
"""

import hashlib
import json
import os
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path


DEFAULT_KG_PATH = os.path.expanduser("~/.castle/knowledge_graph.sqlite3")


class KnowledgeGraph:
    def __init__(self, db_path: str = None, *, read_only: bool = False):
        self.db_path = db_path or DEFAULT_KG_PATH
        self.read_only = read_only
        if not read_only:
            db_parent = Path(self.db_path).parent
            db_parent.mkdir(parents=True, exist_ok=True)
            try:
                db_parent.chmod(0o700)
            except (OSError, NotImplementedError):
                pass
        self._connection = None
        self._lock = threading.Lock()
        if not read_only:
            self._init_db()
        conn = self._conn()
        self._triple_columns = {row["name"] for row in conn.execute("PRAGMA table_info(triples)")}
        self._has_triple_sources = (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='triple_sources'"
            ).fetchone()
            is not None
        )

    def _init_db(self):
        conn = self._conn()
        conn.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'unknown',
                properties TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS triples (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                confidence REAL DEFAULT 1.0,
                source_closet TEXT,
                source_file TEXT,
                source_drawer_id TEXT,
                adapter_name TEXT,
                extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject) REFERENCES entities(id),
                FOREIGN KEY (object) REFERENCES entities(id)
            );

            CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject);
            CREATE INDEX IF NOT EXISTS idx_triples_object ON triples(object);
            CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate);
            CREATE INDEX IF NOT EXISTS idx_triples_valid ON triples(valid_from, valid_to);
        """)
        self._migrate_schema(conn)
        conn.commit()

    def _migrate_schema(self, conn):
        """Backwards-compatible schema migration for older triples tables.

        Fresh palaces get ``source_drawer_id`` / ``adapter_name`` (RFC 002 §5.5)
        directly from the canonical ``CREATE TABLE`` above, so this path is a
        no-op on new installs. It exists for palaces that were created before
        those columns were added: SQLite has no ``ADD COLUMN IF NOT EXISTS``,
        so we introspect the schema and only issue the ALTER when the column
        is missing.
        """
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(triples)")}
        if "source_drawer_id" not in existing:
            conn.execute("ALTER TABLE triples ADD COLUMN source_drawer_id TEXT")
        if "adapter_name" not in existing:
            conn.execute("ALTER TABLE triples ADD COLUMN adapter_name TEXT")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS triple_sources (
                triple_id TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                source_closet TEXT,
                source_file TEXT,
                source_drawer_id TEXT,
                adapter_name TEXT,
                extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (triple_id, source_identity),
                FOREIGN KEY (triple_id) REFERENCES triples(id)
            );
            CREATE INDEX IF NOT EXISTS idx_triple_sources_drawer
                ON triple_sources(source_drawer_id);
        """)
        # Preserve the original row and ID. Reopening writable graphs is
        # idempotent; evidence is never moved out of the compatibility columns.
        for row in conn.execute(
            "SELECT id, source_closet, source_file, source_drawer_id, adapter_name, "
            "extracted_at FROM triples"
        ):
            self._record_source(
                conn,
                row["id"],
                row["source_closet"],
                row["source_file"],
                row["source_drawer_id"],
                row["adapter_name"],
                row["extracted_at"],
            )

    @staticmethod
    def _record_source(
        conn,
        triple_id,
        source_closet,
        source_file,
        source_drawer_id,
        adapter_name,
        extracted_at=None,
    ):
        fields = (source_closet, source_file, source_drawer_id, adapter_name)
        if all(value is None for value in fields):
            return
        identity = hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode()).hexdigest()
        conn.execute(
            """INSERT OR IGNORE INTO triple_sources (
                triple_id, source_identity, source_closet, source_file,
                source_drawer_id, adapter_name, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))""",
            (triple_id, identity, *fields, extracted_at),
        )

    def _conn(self):
        if self._connection is None:
            target = self.db_path
            if self.read_only:
                self._check_read_only_layout()
                target = Path(self.db_path).absolute().as_uri() + "?mode=ro"
            self._connection = sqlite3.connect(
                target, timeout=10, check_same_thread=False, uri=self.read_only
            )
            if not self.read_only:
                self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _check_read_only_layout(self):
        """Refuse WAL housekeeping instead of hiding committed WAL evidence.

        SQLite ``mode=ro`` can still create missing WAL/SHM sidecars. A closed
        WAL graph therefore requires explicit writable operator preparation
        (for example, checkpointing and selecting DELETE journal mode). An
        active WAL graph with existing sidecars remains readable, including its
        committed WAL contents. Never use ``immutable=1`` on these live files.
        """
        path = Path(self.db_path)
        if not path.is_file():
            return  # SQLite reports the normal missing/unopenable DB error.
        with path.open("rb") as stream:
            header = stream.read(20)
        if header[:16] == b"SQLite format 3\x00" and header[18:20] == b"\x02\x02":
            if not all(Path(str(path) + suffix).is_file() for suffix in ("-wal", "-shm")):
                raise sqlite3.OperationalError(
                    "read-only WAL graph requires existing -wal and -shm sidecars; "
                    "explicit writable preparation is required"
                )

    def _require_writable(self):
        if self.read_only:
            raise sqlite3.OperationalError("attempt to write a readonly database")

    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _entity_id(self, name: str) -> str:
        return name.lower().replace(" ", "_").replace("'", "")

    # ── Write operations ──────────────────────────────────────────────────

    def add_entity(self, name: str, entity_type: str = "unknown", properties: dict = None):
        """Add or update an entity node."""
        self._require_writable()
        eid = self._entity_id(name)
        props = json.dumps(properties or {})
        with self._lock:
            conn = self._conn()
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO entities (id, name, type, properties) VALUES (?, ?, ?, ?)",
                    (eid, name, entity_type, props),
                )
        return eid

    def add_triple(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: str = None,
        valid_to: str = None,
        confidence: float = 1.0,
        source_closet: str = None,
        source_file: str = None,
        source_drawer_id: str = None,
        adapter_name: str = None,
    ):
        """
        Add a relationship triple: subject → predicate → object.

        ``source_drawer_id`` and ``adapter_name`` are RFC 002 §5.5 provenance
        fields populated by adapters that advertise ``supports_kg_triples``;
        they default to ``None`` so every existing caller stays source-compatible.

        Examples:
            add_triple("Max", "child_of", "Alice", valid_from="2015-04-01")
            add_triple("Max", "does", "swimming", valid_from="2025-01-01")
            add_triple("Alice", "worried_about", "Max injury", valid_from="2026-01", valid_to="2026-02")
        """
        self._require_writable()
        sub_id = self._entity_id(subject)
        obj_id = self._entity_id(obj)
        pred = predicate.lower().replace(" ", "_")

        # Auto-create entities if they don't exist
        with self._lock:
            conn = self._conn()
            with conn:
                conn.execute(
                    "INSERT OR IGNORE INTO entities (id, name) VALUES (?, ?)", (sub_id, subject)
                )
                conn.execute(
                    "INSERT OR IGNORE INTO entities (id, name) VALUES (?, ?)", (obj_id, obj)
                )

                # Repeated evidence shares a claim only when its full temporal
                # interval agrees. A different interval is a distinct claim.
                existing = conn.execute(
                    "SELECT id FROM triples WHERE subject=? AND predicate=? AND object=? "
                    "AND valid_from IS ? AND valid_to IS ? ORDER BY rowid LIMIT 1",
                    (sub_id, pred, obj_id, valid_from, valid_to),
                ).fetchone()

                if existing:
                    self._record_source(
                        conn,
                        existing["id"],
                        source_closet,
                        source_file,
                        source_drawer_id,
                        adapter_name,
                    )
                    return existing["id"]

                triple_id = f"t_{sub_id}_{pred}_{obj_id}_{hashlib.sha256(f'{valid_from}{datetime.now().isoformat()}'.encode()).hexdigest()[:12]}"

                conn.execute(
                    """INSERT INTO triples (
                        id, subject, predicate, object,
                        valid_from, valid_to, confidence,
                        source_closet, source_file,
                        source_drawer_id, adapter_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        triple_id,
                        sub_id,
                        pred,
                        obj_id,
                        valid_from,
                        valid_to,
                        confidence,
                        source_closet,
                        source_file,
                        source_drawer_id,
                        adapter_name,
                    ),
                )
                self._record_source(
                    conn, triple_id, source_closet, source_file, source_drawer_id, adapter_name
                )
        return triple_id

    def invalidate(self, subject: str, predicate: str, obj: str, ended: str = None):
        """Mark a relationship as no longer valid (set valid_to date)."""
        self._require_writable()
        sub_id = self._entity_id(subject)
        obj_id = self._entity_id(obj)
        pred = predicate.lower().replace(" ", "_")
        ended = ended or date.today().isoformat()

        with self._lock:
            conn = self._conn()
            with conn:
                conn.execute(
                    "UPDATE triples SET valid_to=? WHERE subject=? AND predicate=? AND object=? AND valid_to IS NULL",
                    (ended, sub_id, pred, obj_id),
                )

    # ── Query operations ──────────────────────────────────────────────────

    def query_entity(self, name: str, as_of: str = None, direction: str = "outgoing"):
        """
        Get all relationships for an entity.

        direction: "outgoing" (entity → ?), "incoming" (? → entity), "both"
        as_of: date string — only return facts valid at that time
        """
        eid = self._entity_id(name)

        results = []
        with self._lock:
            conn = self._conn()

            if direction in ("outgoing", "both"):
                query = "SELECT t.*, e.name as obj_name FROM triples t JOIN entities e ON t.object = e.id WHERE t.subject = ?"
                params = [eid]
                if as_of:
                    query += " AND (t.valid_from IS NULL OR t.valid_from <= ?) AND (t.valid_to IS NULL OR t.valid_to >= ?)"
                    params.extend([as_of, as_of])
                for row in conn.execute(query, params).fetchall():
                    results.append(
                        {
                            "direction": "outgoing",
                            "subject": name,
                            "predicate": row["predicate"],
                            "object": row["obj_name"],
                            "valid_from": row["valid_from"],
                            "valid_to": row["valid_to"],
                            "confidence": row["confidence"],
                            "source_closet": row["source_closet"],
                            "current": row["valid_to"] is None,
                        }
                    )

            if direction in ("incoming", "both"):
                query = "SELECT t.*, e.name as sub_name FROM triples t JOIN entities e ON t.subject = e.id WHERE t.object = ?"
                params = [eid]
                if as_of:
                    query += " AND (t.valid_from IS NULL OR t.valid_from <= ?) AND (t.valid_to IS NULL OR t.valid_to >= ?)"
                    params.extend([as_of, as_of])
                for row in conn.execute(query, params).fetchall():
                    results.append(
                        {
                            "direction": "incoming",
                            "subject": row["sub_name"],
                            "predicate": row["predicate"],
                            "object": name,
                            "valid_from": row["valid_from"],
                            "valid_to": row["valid_to"],
                            "confidence": row["confidence"],
                            "source_closet": row["source_closet"],
                            "current": row["valid_to"] is None,
                        }
                    )

        return results

    def query_relationship(self, predicate: str, as_of: str = None):
        """Get all triples with a given relationship type."""
        pred = predicate.lower().replace(" ", "_")
        query = """
            SELECT t.*, s.name as sub_name, o.name as obj_name
            FROM triples t
            JOIN entities s ON t.subject = s.id
            JOIN entities o ON t.object = o.id
            WHERE t.predicate = ?
        """
        params = [pred]
        if as_of:
            query += " AND (t.valid_from IS NULL OR t.valid_from <= ?) AND (t.valid_to IS NULL OR t.valid_to >= ?)"
            params.extend([as_of, as_of])

        results = []
        with self._lock:
            conn = self._conn()
            for row in conn.execute(query, params).fetchall():
                results.append(
                    {
                        "subject": row["sub_name"],
                        "predicate": pred,
                        "object": row["obj_name"],
                        "valid_from": row["valid_from"],
                        "valid_to": row["valid_to"],
                        "current": row["valid_to"] is None,
                    }
                )
        return results

    def timeline(self, entity_name: str = None):
        """Get all facts in chronological order, optionally filtered by entity."""
        with self._lock:
            conn = self._conn()
            if entity_name:
                eid = self._entity_id(entity_name)
                rows = conn.execute(
                    """
                    SELECT t.*, s.name as sub_name, o.name as obj_name
                    FROM triples t
                    JOIN entities s ON t.subject = s.id
                    JOIN entities o ON t.object = o.id
                    WHERE (t.subject = ? OR t.object = ?)
                    ORDER BY t.valid_from ASC NULLS LAST
                    LIMIT 100
                """,
                    (eid, eid),
                ).fetchall()
            else:
                rows = conn.execute("""
                    SELECT t.*, s.name as sub_name, o.name as obj_name
                    FROM triples t
                    JOIN entities s ON t.subject = s.id
                    JOIN entities o ON t.object = o.id
                    ORDER BY t.valid_from ASC NULLS LAST
                    LIMIT 100
                """).fetchall()

        return [
            {
                "subject": r["sub_name"],
                "predicate": r["predicate"],
                "object": r["obj_name"],
                "valid_from": r["valid_from"],
                "valid_to": r["valid_to"],
                "current": r["valid_to"] is None,
            }
            for r in rows
        ]

    # ── Stats ─────────────────────────────────────────────────────────────

    def validate_recall(self):
        """Verify usable source-pointer schema through a real read-only query."""
        if not {"id", "subject", "object", "extracted_at"} <= self._triple_columns:
            raise ValueError("incompatible graph recall schema")
        if not self._has_triple_sources and "source_drawer_id" not in self._triple_columns:
            raise ValueError("graph lacks recall source pointers")
        self.find_drawers_by_entities(["castle_provider_health_probe"], limit=1)

    def stats(self):
        with self._lock:
            conn = self._conn()
            entities = conn.execute("SELECT COUNT(*) as cnt FROM entities").fetchone()["cnt"]
            triples = conn.execute("SELECT COUNT(*) as cnt FROM triples").fetchone()["cnt"]
            current = conn.execute(
                "SELECT COUNT(*) as cnt FROM triples WHERE valid_to IS NULL"
            ).fetchone()["cnt"]
            expired = triples - current
            predicates = [
                r["predicate"]
                for r in conn.execute(
                    "SELECT DISTINCT predicate FROM triples ORDER BY predicate"
                ).fetchall()
            ]
        return {
            "entities": entities,
            "triples": triples,
            "current_facts": current,
            "expired_facts": expired,
            "relationship_types": predicates,
        }

    # ── KG-hop drawer lookup ──────────────────────────────────────────────

    def sources_for_triple(self, triple_id: str) -> list[dict]:
        """Return all recorded source identities, including legacy evidence.

        Older read-only graphs use their original columns without a migration.
        Missing optional provenance fields are represented by ``None``.
        """
        with self._lock:
            conn = self._conn()
            if self._has_triple_sources:
                return [
                    dict(row)
                    for row in conn.execute(
                        "SELECT triple_id, source_closet, source_file, source_drawer_id, "
                        "adapter_name, extracted_at FROM triple_sources WHERE triple_id=? "
                        "ORDER BY extracted_at, source_identity",
                        (triple_id,),
                    )
                ]
            fields = ("source_closet", "source_file", "source_drawer_id", "adapter_name")
            projection = ", ".join(
                name if name in self._triple_columns else f"NULL AS {name}"
                for name in (*fields, "extracted_at")
            )
            row = conn.execute(
                f"SELECT id AS triple_id, {projection} FROM triples WHERE id=?", (triple_id,)
            ).fetchone()
            if row is None or all(row[name] is None for name in fields):
                return []
            return [dict(row)]

    def find_drawers_by_entities(
        self,
        entity_names: list,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        """Return drawer IDs tagged with any of the supplied entities.

        Drawers are ranked by the count of distinct queried entities they touch
        (descending), then by recency of triple insertion (descending via
        MAX(extracted_at)), then by drawer_id ascending for determinism.

        Parameters
        ----------
        entity_names:
            Canonical entity names. Internally resolved to entity IDs via
            ``_entity_id``.
        limit:
            Maximum number of drawer IDs to return.
        """
        if not entity_names:
            return []
        entity_ids = sorted({self._entity_id(name) for name in entity_names})
        placeholders = ",".join("?" * len(entity_ids))
        sources = []
        if "source_drawer_id" in self._triple_columns:
            sources.append(
                "SELECT id AS triple_id, source_drawer_id, extracted_at FROM triples "
                "WHERE source_drawer_id IS NOT NULL"
            )
        if self._has_triple_sources:
            sources.append(
                "SELECT triple_id, source_drawer_id, extracted_at FROM triple_sources "
                "WHERE source_drawer_id IS NOT NULL"
            )
        if not sources:
            return []
        source_sql = " UNION ALL ".join(sources)
        sql = f"""
            WITH sources AS ({source_sql}),
            matches AS (
                SELECT s.source_drawer_id, t.subject AS entity_id, s.extracted_at
                FROM triples t JOIN sources s ON s.triple_id=t.id
                WHERE t.subject IN ({placeholders})
                UNION ALL
                SELECT s.source_drawer_id, t.object AS entity_id, s.extracted_at
                FROM triples t JOIN sources s ON s.triple_id=t.id
                WHERE t.object IN ({placeholders})
            )
            SELECT source_drawer_id,
                   COUNT(DISTINCT entity_id) AS match_count,
                   MAX(extracted_at) AS latest_extracted_at
            FROM matches
            GROUP BY source_drawer_id
            ORDER BY match_count DESC, latest_extracted_at DESC, source_drawer_id ASC
            LIMIT ? OFFSET ?
        """
        with self._lock:
            conn = self._conn()
            rows = conn.execute(sql, entity_ids + entity_ids + [limit, offset]).fetchall()
        return [r[0] for r in rows]

    # ── Seed from known facts ─────────────────────────────────────────────

    def seed_from_entity_facts(self, entity_facts: dict):
        """
        Seed the knowledge graph from fact_checker.py ENTITY_FACTS.
        This bootstraps the graph with known ground truth.
        """
        for key, facts in entity_facts.items():
            name = facts.get("full_name", key.capitalize())
            etype = facts.get("type", "person")
            self.add_entity(
                name,
                etype,
                {
                    "gender": facts.get("gender", ""),
                    "birthday": facts.get("birthday", ""),
                },
            )

            # Relationships
            parent = facts.get("parent")
            if parent:
                self.add_triple(
                    name, "child_of", parent.capitalize(), valid_from=facts.get("birthday")
                )

            partner = facts.get("partner")
            if partner:
                self.add_triple(name, "married_to", partner.capitalize())

            relationship = facts.get("relationship", "")
            if relationship == "daughter":
                self.add_triple(
                    name,
                    "is_child_of",
                    facts.get("parent", "").capitalize() or name,
                    valid_from=facts.get("birthday"),
                )
            elif relationship == "husband":
                self.add_triple(name, "is_partner_of", facts.get("partner", name).capitalize())
            elif relationship == "brother":
                self.add_triple(name, "is_sibling_of", facts.get("sibling", name).capitalize())
            elif relationship == "dog":
                self.add_triple(name, "is_pet_of", facts.get("owner", name).capitalize())
                self.add_entity(name, "animal")

            # Interests
            for interest in facts.get("interests", []):
                self.add_triple(name, "loves", interest.capitalize(), valid_from="2025-01-01")

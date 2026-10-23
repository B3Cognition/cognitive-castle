"""Read-only memory operations. Authorization is a trusted host responsibility."""

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import math
import re

from .memory_types import (
    MemoryError,
    MemorySlice,
    MemorySource,
    ProviderHealth,
    SearchHit,
    SearchResult,
    SourceBundle,
    SourceExpectation,
)
from .revisions import revision_completed, source_representation


def encoded(value) -> bytes:
    return json.dumps(
        value.as_dict() if hasattr(value, "as_dict") else value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(text):
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeError:
        raise MemoryError("incompatible_store") from None


def _input_text(value, maximum):
    if not isinstance(value, str) or not value:
        raise MemoryError("invalid_request")
    try:
        if len(value.encode("utf-8")) > maximum:
            raise MemoryError("invalid_request")
    except UnicodeError:
        raise MemoryError("invalid_request") from None
    return value


def bounded(value, maximum=49152):
    if len(encoded(value)) > maximum:
        raise MemoryError("result_limit")
    return value


def config_fingerprint(config, profile="memory-v1"):
    keys = (
        "embedder_model",
        "embedder_dim",
        "embedding_device",
        "reranker_model_cpu",
        "reranker_model_gpu",
        "reranker_device",
    )
    if profile == "memory-fts-v1":
        keys = ("weight_sparse",)
    else:
        keys += ("weight_sparse", "weight_kg", "weight_dense", "reranker_k_interactive")
    keys += ("k_rrf", "recency_tau_days", "recency_max_boost")
    return hashlib.sha256(
        encoded({"profile": profile, **{key: getattr(config, key, None) for key in keys}})
    ).hexdigest()


def recall_health(context, collection, *, profile="memory-v1"):
    """Probe read availability without model downloads or corpus disclosure."""
    fts_only = profile == "memory-fts-v1"
    failures = [] if fts_only or getattr(collection, "dense_available", True) else ["dense"]
    try:
        collection.fts_search("castle_provider_health_probe", n_results=1)
    except Exception:
        if fts_only:
            raise MemoryError("incompatible_store") from None
        failures.append("sparse")
    if len(failures) == 2:
        graph = getattr(context.paths, "knowledge_graph", None)
        registry = getattr(context.paths, "entity_registry", None)
        try:
            if graph is None or registry is None or not graph.is_file() or not registry.is_file():
                raise ValueError()
            context.graph.validate_recall()
            context.registry
        except Exception:
            raise MemoryError("incompatible_store") from None
    return tuple(failures)


def _grouped_search_hits(groups, limit):
    from .searcher import _capture_sort_key

    ordered = []
    for group in groups.values():
        sources = sorted(
            group["sources"].values(),
            key=lambda source: _capture_sort_key(source.captured_at, source.record_id),
        )
        primary, alternates = sources[0], sources[1:]
        ordered.append((group, primary, alternates))
    ordered.sort(key=lambda item: (-item[0]["score"], item[1].record_id))
    return [
        SearchHit(
            **asdict(primary),
            score=group["score"],
            rank=rank,
            excerpt=group["text"][:512],
            excerpt_is_complete=len(group["text"]) <= 512,
            alternate_sources=tuple(alternates[:8]),
            alternate_sources_complete=group["complete"] and len(alternates) <= 8,
        )
        for rank, (group, primary, alternates) in enumerate(ordered[:limit], 1)
    ]


class MemoryService:
    def __init__(self, context, *, namespace, allowed_wings, profile="memory-fts-v1"):
        if profile not in ("memory-fts-v1", "memory-v1"):
            raise MemoryError("invalid_request")
        self.profile = profile
        _input_text(namespace, 256)
        if (
            not isinstance(allowed_wings, (set, frozenset))
            or not allowed_wings
            or len(allowed_wings) > 128
        ):
            raise MemoryError("invalid_request")
        for wing in allowed_wings:
            _input_text(wing, 256)
        self.context = context
        self.allowed_wings = frozenset(allowed_wings)
        try:
            identity = json.loads(
                (context.paths.provider / "identity.json").read_text(encoding="utf-8")
            )
            if (
                identity != {"schema_version": 1, "namespace": namespace}
                or type(identity.get("schema_version")) is not int
            ):
                raise ValueError("identity differs")
        except (OSError, ValueError, TypeError):
            raise MemoryError("incompatible_store") from None

    def _record(self, record_id):
        _input_text(record_id, 512)
        try:
            data = self.context.get_collection().get(
                ids=[record_id], include=["documents", "metadatas"]
            )
        except Exception:
            raise MemoryError("unavailable") from None
        ids, docs, metas = (
            data.get("ids") or [],
            data.get("documents") or [],
            data.get("metadatas") or [],
        )
        if len(ids) != 1 or ids[0] != record_id or len(docs) != 1 or len(metas) != 1:
            raise MemoryError("not_found")
        metadata = metas[0] or {}
        if not isinstance(metadata, dict) or not isinstance(metadata.get("wing"), str):
            raise MemoryError("not_found")
        if metadata.get("room") == "_registry" or metadata.get("ingest_mode") == "registry":
            raise MemoryError("not_found")
        if metadata.get("wing") not in self.allowed_wings or not revision_completed(
            self.context.paths.root, metadata, record_id=record_id
        ):
            raise MemoryError("not_found")
        if not isinstance(docs[0], str):
            raise MemoryError("incompatible_store")
        return docs[0], metadata

    def _source(self, record_id, text, meta):
        def field(name, maximum=256):
            value = meta.get(name)
            if value is None:
                return None
            if not isinstance(value, str):
                raise MemoryError("incompatible_store")
            try:
                size = len(value.encode())
            except UnicodeError:
                raise MemoryError("incompatible_store") from None
            if size > maximum:
                raise MemoryError("result_limit")
            return value

        source_file = meta.get("source_file")
        # Filesystem paths are never sent across the model-facing boundary.
        source_id = digest(source_file) if isinstance(source_file, str) else None
        revision = field("source_revision") or field("revision")
        captured_at = field("filed_at")
        if revision is not None and re.fullmatch(r"[A-Za-z0-9_.-]+", revision) is None:
            raise MemoryError("incompatible_store")
        if captured_at is not None:
            try:
                datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            except ValueError:
                raise MemoryError("incompatible_store") from None
        return MemorySource(
            record_id,
            digest(text),
            revision,
            source_representation(meta),
            field("wing"),
            captured_at,
            source_id,
        )

    def fetch(self, record_id, *, start_char=0, max_chars=8000):
        if (
            type(start_char) is not int
            or start_char < 0
            or type(max_chars) is not int
            or not 1 <= max_chars <= 8000
        ):
            raise MemoryError("invalid_request")
        text, meta = self._record(record_id)
        if start_char > len(text):
            raise MemoryError("invalid_request")
        piece = text[start_char : start_char + max_chars]
        end = start_char + len(piece)
        return bounded(
            MemorySlice(
                record_id,
                digest(text),
                digest(piece),
                piece,
                start_char,
                None if end == len(text) else end,
                end == len(text),
                self._source(record_id, text, meta),
            )
        )

    def search(self, query, *, limit=5):
        _input_text(query, 4096)
        if not query.strip() or type(limit) is not int or not 1 <= limit <= 20:
            raise MemoryError("invalid_request")
        from .searcher import search_memories

        try:
            result = search_memories(
                query=query,
                palace_path=str(self.context.paths.root),
                context=self.context,
                profile=self.profile,
                allowed_wings=self.allowed_wings,
                n_results=20,
            )
        except Exception:
            raise MemoryError("unavailable") from None
        groups = {}
        for row in result.get("results", [])[:20]:
            rid = row.get("id") or row.get("record_id") or row.get("drawer_id")
            try:
                text, metadata = self._record(rid)
            except MemoryError as exc:
                if exc.code == "not_found":
                    continue
                raise
            score = row.get("score")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            ):
                raise MemoryError("unavailable")
            source = self._source(rid, text, metadata)
            sources, complete = self._alternate_sources(row, source)
            group = groups.setdefault(
                source.text_sha256,
                {"text": text, "sources": {}, "score": float(score), "complete": True},
            )
            group["sources"].update({item.record_id: item for item in sources})
            group["score"] = max(group["score"], float(score))
            group["complete"] = group["complete"] and complete
        hits = _grouped_search_hits(groups, limit)
        diagnostics = result.get("diagnostics") or {}
        failures = tuple(
            s
            for s in diagnostics.get("failed_signals", [])
            if s in {"dense", "sparse", "kg", "reranker"}
        )
        return bounded(SearchResult(tuple(hits), failures))

    def _alternate_sources(self, row, primary):
        """Resolve only bounded authorized IDs, never trust stored provenance blobs."""
        alternate_ids = row.get("alternate_record_ids", ())
        complete = row.get("alternate_sources_complete", True)
        if not isinstance(alternate_ids, (list, tuple)) or type(complete) is not bool:
            raise MemoryError("unavailable")
        complete = complete and len(alternate_ids) <= 8
        sources = [primary]
        seen = {primary.record_id}
        for record_id in alternate_ids[:8]:
            try:
                text, metadata = self._record(record_id)
            except MemoryError as exc:
                if exc.code in {"not_found", "invalid_request"}:
                    complete = False
                    continue
                raise
            source = self._source(record_id, text, metadata)
            if source.text_sha256 != primary.text_sha256:
                complete = False
            elif source.record_id not in seen:
                seen.add(source.record_id)
                sources.append(source)
        return sources, complete

    def snapshot(self, record_ids, *, expected=None, maximum_bytes=262144):
        if not isinstance(record_ids, tuple) or not record_ids or len(record_ids) > 128:
            raise MemoryError("invalid_request")
        for record_id in record_ids:
            _input_text(record_id, 512)
        if len(set(record_ids)) != len(record_ids):
            raise MemoryError("invalid_request")
        if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 1048576:
            raise MemoryError("invalid_request")
        if expected is not None and (
            not isinstance(expected, dict) or set(expected) != set(record_ids)
        ):
            raise MemoryError("invalid_request")
        sources, texts = [], []
        for rid in record_ids:
            text, meta = self._record(rid)
            source = self._source(rid, text, meta)
            if expected is not None:
                expectation = expected[rid]
                if not isinstance(expectation, SourceExpectation):
                    raise MemoryError("invalid_request")
                if (expectation.text_sha256, expectation.revision) != (
                    source.text_sha256,
                    source.revision,
                ):
                    raise MemoryError("incompatible_store")
            sources.append(source)
            texts.append(text)
            bounded({"sources": [s.as_dict() for s in sources], "texts": texts}, maximum_bytes)
        payload = {"schema_version": 1, "sources": [s.as_dict() for s in sources], "texts": texts}
        return bounded(
            SourceBundle(
                tuple(sources), tuple(texts), hashlib.sha256(encoded(payload)).hexdigest()
            ),
            maximum_bytes,
        )

    def health(self):
        try:
            col = self.context.get_collection()
            disabled = recall_health(self.context, col, profile=self.profile)
        except Exception:
            raise MemoryError("incompatible_store") from None
        return ProviderHealth(
            "degraded" if disabled else "ready",
            profile=self.profile,
            fingerprint=config_fingerprint(self.context.config, self.profile),
            degraded_signals=disabled,
        )

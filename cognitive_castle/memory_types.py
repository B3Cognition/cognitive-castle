"""Versioned, source-preserving values for the optional memory boundary."""

from dataclasses import asdict, dataclass


class MemoryError(Exception):
    CODES = frozenset(
        {
            "invalid_request",
            "not_found",
            "unavailable",
            "deadline_exceeded",
            "cancelled",
            "result_limit",
            "incompatible_store",
        }
    )

    def __init__(self, code):
        if code not in self.CODES:
            raise ValueError("unknown memory error code")
        self.code = code
        super().__init__(code)


class WireValue:
    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class MemorySource(WireValue):
    record_id: str
    text_sha256: str
    revision: str | None
    representation: str | None
    wing: str
    captured_at: str | None
    source_id: str | None


@dataclass(frozen=True)
class SearchHit(MemorySource):
    score: float
    rank: int
    excerpt: str
    excerpt_is_complete: bool
    alternate_sources: tuple[MemorySource, ...] = ()
    # Completeness is relative to the known scoped recall pool, not a full scan.
    alternate_sources_complete: bool = True


@dataclass(frozen=True)
class SearchResult(WireValue):
    hits: tuple[SearchHit, ...]
    degraded_signals: tuple[str, ...] = ()
    schema_version: int = 1


@dataclass(frozen=True)
class MemorySlice(WireValue):
    record_id: str
    text_sha256: str
    slice_sha256: str
    text: str
    start_char: int
    next_start_char: int | None
    complete: bool
    provenance: MemorySource
    schema_version: int = 1


@dataclass(frozen=True)
class SourceExpectation(WireValue):
    text_sha256: str
    revision: str | None


@dataclass(frozen=True)
class SourceBundle(WireValue):
    sources: tuple[MemorySource, ...]
    texts: tuple[str, ...]
    digest: str
    schema_version: int = 1


@dataclass(frozen=True)
class ProviderHealth(WireValue):
    status: str
    profile: str = "memory-fts-v1"
    capabilities: tuple[str, ...] = ("search", "fetch", "snapshot", "health")
    fingerprint: str = ""
    degraded_signals: tuple[str, ...] = ()
    schema_version: int = 1
    recency_boost: bool = False

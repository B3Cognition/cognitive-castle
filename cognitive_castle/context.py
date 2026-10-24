"""Explicit palace paths and handles for read-only memory consumers.

Resolution is read-only. New custom palaces keep auxiliary state under their
own root; ambiguous historical shared state requires explicit migration.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True)
class PalacePaths:
    root: Path
    config_dir: Path
    state_dir: Path
    knowledge_graph: Path
    entity_registry: Path
    revisions: Path
    provider: Path
    locks: Path
    logs: Path
    manifest: Path

    @classmethod
    def resolve(cls, palace_path, *, config_dir=None) -> "PalacePaths":
        root = Path(palace_path).expanduser().resolve()
        state = (root / ".castle").resolve()
        provider = (root / ".provider").resolve()
        if not state.is_relative_to(root) or not provider.is_relative_to(root):
            raise ValueError("palace state escapes root; explicit migration required")
        manifest = state / "paths.json"
        if not manifest.resolve().is_relative_to(root):
            raise ValueError("invalid palace path manifest; explicit migration required")
        config = Path(config_dir).expanduser().resolve() if config_dir else state
        graph = state / "knowledge_graph.sqlite3"
        registry = state / "entity_registry.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if (
                    not isinstance(data, dict)
                    or type(data.get("version")) is not int
                    or data["version"] != 1
                ):
                    raise ValueError("unsupported version")
                resolved = {}
                for name, default in (("knowledge_graph", graph), ("entity_registry", registry)):
                    value = data.get(name)
                    candidate = default if value is None else root / value
                    if value is not None and (
                        not isinstance(value, str) or Path(value).is_absolute()
                    ):
                        raise ValueError("paths must be relative")
                    candidate = candidate.resolve()
                    if not candidate.is_relative_to(root):
                        raise ValueError("path escapes palace")
                    resolved[name] = candidate
                graph, registry = resolved["knowledge_graph"], resolved["entity_registry"]
            except (OSError, TypeError, ValueError) as exc:
                raise ValueError(
                    "invalid palace path manifest; explicit migration required"
                ) from exc
        else:
            default_legacy = (Path.home() / ".castle" / "palace").resolve()
            chosen = []
            for name, private in (
                ("knowledge_graph.sqlite3", graph),
                ("entity_registry.json", registry),
            ):
                direct, sibling = root / name, root.parent / name
                candidates = [path for path in (private, direct) if path.exists()]
                if sibling.exists():
                    if root == default_legacy:
                        candidates.append(sibling)
                    else:
                        raise ValueError(
                            "ambiguous shared palace state; explicit migration required"
                        )
                if len(candidates) > 1:
                    raise ValueError("ambiguous palace state; explicit migration required")
                chosen.append(candidates[0] if candidates else private)
            graph, registry = chosen
            allowed = root.parent if root == default_legacy else root
            graph, registry = graph.resolve(), registry.resolve()
            if not graph.is_relative_to(allowed) or not registry.is_relative_to(allowed):
                raise ValueError("palace state escapes root; explicit migration required")
            if root == default_legacy and config_dir is None:
                config = root.parent
        return cls(
            root=root,
            config_dir=config,
            state_dir=state,
            knowledge_graph=graph,
            entity_registry=registry,
            revisions=state / "revisions",
            provider=provider,
            locks=state / "locks",
            logs=state / "logs",
            manifest=manifest,
        )

    @property
    def palace_path(self) -> Path:
        return self.root


@dataclass(frozen=True)
class _ConfigSnapshot:
    _values: object

    def __getattr__(self, name):
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name) from None


def _snapshot_config(config):
    values = deepcopy(vars(config))
    for owner in reversed(type(config).__mro__):
        for name, descriptor in vars(owner).items():
            if isinstance(descriptor, property):
                values[name] = deepcopy(getattr(config, name))
    return _ConfigSnapshot(MappingProxyType(values))


class CastleContext:
    """A single explicit config/root binding with lazy local read handles."""

    def __init__(self, paths, config, *, create, read_only):
        self.paths = paths
        self.config = _snapshot_config(config)
        self.read_only = read_only
        self._create = create
        self._backend = None
        self._graph = None
        self._registry = None
        self._closed = False

    @classmethod
    def open(cls, paths, *, config, create=False, read_only=True) -> "CastleContext":
        if not isinstance(paths, PalacePaths):
            raise TypeError("paths must be PalacePaths")
        if create and read_only:
            raise ValueError("read-only contexts cannot create a palace")
        if create:
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.state_dir.mkdir(parents=True, exist_ok=True)
        elif not paths.root.is_dir():
            raise FileNotFoundError("palace does not exist")
        return cls(paths, config, create=create, read_only=read_only)

    def _require_open(self):
        if self._closed:
            raise RuntimeError("palace context is closed")

    def get_collection(self, name="castle_drawers"):
        self._require_open()
        if self._backend is None:
            from .backends.lancedb_backend import LanceDBBackend

            self._backend = LanceDBBackend(cfg=self.config, read_only=self.read_only)
        from .backends.base import PalaceRef

        return self._backend.get_collection(
            palace=PalaceRef(id=str(self.paths.root), local_path=str(self.paths.root)),
            collection_name=name,
            create=self._create,
        )

    @property
    def registry(self):
        self._require_open()
        if self._registry is None:
            from .entity_registry import EntityRegistry

            self._registry = EntityRegistry.load(
                path=self.paths.entity_registry, read_only=self.read_only
            )
        return self._registry

    @property
    def entity_registry(self):
        return self.registry

    @property
    def graph(self):
        self._require_open()
        if self._graph is None:
            from .knowledge_graph import KnowledgeGraph

            self._graph = KnowledgeGraph(
                db_path=str(self.paths.knowledge_graph), read_only=self.read_only
            )
        return self._graph

    @property
    def knowledge_graph(self):
        return self.graph

    def close(self):
        if self._graph is not None:
            self._graph.close()
        if self._backend is not None:
            self._backend.close()
        self._closed = True

    def __enter__(self):
        self._require_open()
        return self

    def __exit__(self, *_exc):
        self.close()

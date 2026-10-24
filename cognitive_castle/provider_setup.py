"""Explicit operator preparation; never called by provider reads."""

import json

from .context import CastleContext
from .memory import MemoryService, recall_health
from .memory_types import MemoryError
from .palace import mutation_session
from .revisions import atomic_json


def prepare_provider(paths, *, namespace, config):
    if not isinstance(namespace, str) or not namespace or len(namespace.encode()) > 256:
        raise MemoryError("invalid_request")
    if not paths.root.is_dir() or not (paths.root / "lancedb").is_dir():
        raise MemoryError("incompatible_store")
    identity = {"schema_version": 1, "namespace": namespace}
    with mutation_session(paths.root):
        identity_path = paths.provider / "identity.json"
        if identity_path.exists():
            try:
                stored = json.loads(identity_path.read_text())
                if stored != identity or type(stored.get("schema_version")) is not int:
                    raise ValueError()
            except (ValueError, OSError):
                raise MemoryError("incompatible_store") from None
        # Explicit maintenance may build an absent FTS index. It must not
        # invent an embedder identity or migrate historical rows on open.
        with CastleContext.open(paths, config=config, read_only=True) as context:
            col = context.get_collection()
            if col is None:
                raise MemoryError("incompatible_store")
            try:
                col.fts_search("castle_provider_health_probe", n_results=1)
            except Exception:
                try:
                    col._table.create_fts_index("text", replace=True)
                except Exception:
                    pass  # Another verified recall signal may remain usable.
            recall_health(context, col, profile="memory-fts-v1")
        if not identity_path.exists():
            atomic_json(identity_path, identity)
        with CastleContext.open(paths, config=config, read_only=True) as context:
            return MemoryService(
                context, namespace=namespace, allowed_wings={"_preflight"}
            ).health()

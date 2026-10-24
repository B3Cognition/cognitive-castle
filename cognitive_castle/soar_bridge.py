"""Compatibility imports for the former native SOAR bridge.

Ranking now uses deterministic Python rules. These aliases preserve legacy
callers and audit keys without loading a native engine or parsing rule files.
"""

from .symbolic_rules import (
    apply_symbolic_boosts as apply_soar_boosts,
    apply_to_reranked as _apply_soar_to_reranked,
)

__all__ = ["apply_soar_boosts", "_apply_soar_to_reranked"]

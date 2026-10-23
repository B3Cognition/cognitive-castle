"""Optional read-only Castle provider. Imports never load or start Castle."""

__version__ = "0.1.0"

from .client import CastleMemoryProvider
from .transport import MemoryProviderError, WorkerCommand
from .tools import memory_tools

__all__ = ["CastleMemoryProvider", "MemoryProviderError", "WorkerCommand", "memory_tools"]

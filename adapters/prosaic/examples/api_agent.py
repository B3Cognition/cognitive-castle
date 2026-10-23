"""Host-owned API registration; endpoint/auth configuration comes from the host."""

from prosaic_runtime import ProsaicRuntime, RunPolicy
from prosaic_memory_castle import memory_tools


def bind(config, provider, *, authorize):
    tools = memory_tools(provider, authorize=authorize)
    return ProsaicRuntime(config, custom_tools=tools), RunPolicy(allowed_tools=frozenset(tools))

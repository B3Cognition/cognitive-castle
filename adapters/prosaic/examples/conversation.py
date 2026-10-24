"""Bind one trusted owner per provider; no run ID is required for a chat turn."""

from prosaic_harness import ConversationBindings, ConversationPolicy
from prosaic_runtime import RunPolicy
from prosaic_memory_castle import memory_tools


def bindings(agent, config, provider, *, authorize_owner):
    # Conversation instructions must omit {{args}}; messages are user inputs.
    # authorize_owner captures the authenticated host owner/provider association.
    # It receives trusted context and must not derive ownership from model text.
    tools = memory_tools(provider, authorize=authorize_owner)
    return ConversationBindings(
        agent,
        version="memory-reader-v1",
        config=config,
        policy=ConversationPolicy(),
        run_policy=RunPolicy(
            allowed_tools=frozenset(tools), max_provider_requests=3, max_tool_calls=2
        ),
        custom_tools=tools,
    )

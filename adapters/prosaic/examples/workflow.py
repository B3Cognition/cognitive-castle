"""Harness owns workflow state; memory is only a registered Runtime tool."""

from prosaic_harness import WorkflowBindings
from prosaic_memory_castle import memory_tools


def bindings(config, provider, *, authorize):
    return WorkflowBindings(config=config, custom_tools=memory_tools(provider, authorize=authorize))


def freeze(provider, selected_hits):
    """Call before Harness.run; persist this bundle as ordinary workflow inputs."""
    ids = [hit["record_id"] for hit in selected_hits]
    expected = {
        hit["record_id"]: {"text_sha256": hit["text_sha256"], "revision": hit["revision"]}
        for hit in selected_hits
    }
    return provider.snapshot(ids, expected=expected)

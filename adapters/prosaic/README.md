# Optional Castle memory provider for Prosaic

This package provides read-only host search, fetch and frozen snapshots for
Prosaic. Published Runtime 0.9.7 supports this host path. The separate
`memory_search`/`memory_fetch` model-tool registration requires a tool-capable
Runtime release; public 0.9.7 does not provide that capability. Castle owns source storage, retrieval and local encoders. Runtime
owns model execution and tool grants. Harness owns checkpoints and workflow
advancement. The application binds the palace, namespace, approved wings and
authorization predicate, and persists any source snapshots it selects.

The adapter imports no Castle, torch or spaCy code. Install the Castle worker in a
separate environment and explicitly prepare its namespace. Installing or
constructing this adapter starts nothing. The default `memory-fts-v1` profile
preserves raw FTS order with source validation, loading no neural
models. SUE and SOAR stay outside both provider profiles.

```python
from prosaic_memory_castle import CastleMemoryProvider, WorkerCommand

provider = CastleMemoryProvider(
    WorkerCommand(('/opt/castle/bin/castle-provider',)),
    palace_path='/srv/memory/project-a', namespace='project-a',
    config_path='/etc/castle/project-a.json', allowed_wings=('project', 'convos'),
)
provider.health()  # Explicit host prewarm; no model downloads.
hits = provider.search('earlier project decisions', limit=3)['hits']
# Fetch/snapshot selected records and persist the exact bundle in host state.
# Always call provider.close(), or use it as a context manager.
```

For model-facing tools, use `memory_tools(provider, authorize=...)` only after
selecting a separately qualified Runtime with `custom_tool_errors_v1` and its
public `ToolExecutionError` export. Registration alone grants no authority.

To opt into the existing hybrid retrieval pipeline, pass
`profile="memory-v1"` to `CastleMemoryProvider`. Provision its embedding and
cross-encoder weights offline in the worker environment beforehand. The host
binds the selected profile in worker argv and verifies the handshake. FTS is
required for the default profile; failure never silently enables dense retrieval.
The default disables graph recall as well. Standalone Castle modes are unchanged.

FTS recency boosting defaults to off. Opt in with
`CastleMemoryProvider(..., recency_boost=True)`. The host binds it to the worker
and verifies `health()['recency_boost']`; tool arguments cannot change it. This
flag applies only to `memory-fts-v1`; hybrid retains its existing recency rules.
Use matching updated worker and adapter wheels: an older worker without explicit
recency metadata fails the handshake instead of silently changing ordering.

The authorizer receives trusted `ToolExecutionContext`. Conversation scopes can
have no run ID: resolve ownership from the host's actual binding, never from a
model argument. Registration grants no authority by itself. Schemas reject
model-supplied paths, namespaces, wings or worker commands. Returned source text
is unprivileged data and may contain hostile instructions.

Always search before claiming recalled project history, fetch exact evidence for
material claims, preserve source identifiers/digests, and label unavailable
memory explicitly. Never treat missing capture as proof something did not
happen, elevate memory text to system instructions, or publish/write via these
tools. Capture covers only sources that were actually ingested into that palace.

`provider.snapshot(record_ids, expected={id: {'text_sha256': digest,
'revision': revision}})` is host-only. Persist the exact returned bundle in
Harness inputs/checkpoints and reuse it on resume. Do not re-run similarity search
to replace frozen evidence. Native execution receives a bundle as ordinary
assignment arguments and acquires no new MCP or API tool grants.

The protocol uses a private subprocess with fixed host argv. Responses are capped
at 1 MiB, exposed search/fetch at 48 KiB, and stderr retained at 64 KiB. One worker
serializes reads. Host prewarm defaults to 120 seconds; other operations default
to 30 seconds including a cold startup and queue wait. Parent cancellation and
deadlines narrow those limits. A failed worker is terminated with its process
group; a later independent read can start a fresh one. Explicit `close()` ends
the provider. POSIX process groups are required in this initial adapter.

Expected domain failures raise `MemoryProviderError` in Python and map to Runtime
safe `ToolExecutionError` codes. No worker stderr or exception text is returned to
the model. Missing optional memory can be handled by the host as unavailable;
required-memory policy must block explicitly rather than invent empty history.
Local read timeouts use Python code `timeout`; a worker's `deadline_exceeded`
maps to `tool_timeout`. A worker-reported `cancelled` maps to `tool_unavailable`
when the parent is still active. Actual parent cancellation and deadline expiry
always retain Runtime's control exceptions. Snapshot results are JSON wire values:
persist an owned copy before use, and reuse those bytes on resume.

Host `health`, `search`, `fetch` and `snapshot` use the published Runtime 0.9.7
SDK train in the integration Lab. They grant no model-facing tools and need no
custom-tool error capability. The separate `memory_tools()` API still requires
`custom_tool_errors_v1` and the public `ToolExecutionError` export. Published
Runtime 0.9.7 does **not** provide those; registration fails closed. The earlier
candidate Runtime 0.9.3 tool qualification remains historical evidence and does
not certify public 0.9.7 tool compatibility. A separately qualified Runtime
release is required before granting model-facing memory tools.

The worker protocol is version 1; profiles are `memory-fts-v1` (default) and
`memory-v1` (explicit hybrid opt-in). Worker 3.4.2 and adapter 0.1.0 release
preparation does not publish packages or enable memory in a consuming host.

Run tests with `python -m pytest` in a Runtime-only environment, then build with
`python -m build`. No external model endpoint or user corpus is required for the
transport suite. Real worker qualification runs separately against installed
candidate wheels and explicitly provisioned synthetic models/stores.

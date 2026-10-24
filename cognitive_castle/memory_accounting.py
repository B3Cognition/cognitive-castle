"""Describe the indexed subset without concealing omitted source material."""

from pathlib import Path

COUNTERS = (
    "processed_records",
    "indexed_records",
    "text_blocks",
    "text_bytes",
    "metadata_records",
    "duplicate_records",
    "internal_records",
    "internal_blocks",
    "tool_records",
    "tool_blocks",
    "attachment_blocks",
    "unsupported_records",
    "unsupported_blocks",
    "malformed_records",
    "oversized_records",
    "oversized_bytes",
)


def empty_accounting():
    return dict.fromkeys(COUNTERS, 0)


def classify_record(record, format, messages):
    counts = empty_accounting()
    counts["processed_records"] = 1
    counts["indexed_records"] = int(bool(messages))
    counts["text_blocks"] = len(messages)
    counts["text_bytes"] = sum(len(m["text"].encode("utf-8")) for m in messages)
    if not isinstance(record, dict):
        counts["unsupported_records"] = 1
        return counts
    kind = record.get("type")
    payload = record.get("payload") if format == "codex" else record.get("message")
    payload = payload if isinstance(payload, dict) else {}
    if format == "codex" and kind == "response_item":
        payload_kind = payload.get("type")
        if payload_kind in ("reasoning", "compaction_reasoning") or (
            payload_kind == "message"
            and payload.get("role") == "assistant"
            and payload.get("channel") not in (None, "final", "commentary")
        ):
            counts["internal_records"] = 1
            return counts
        if payload_kind in (
            "function_call",
            "function_call_output",
            "custom_tool_call",
            "custom_tool_call_output",
            "tool_call",
            "tool_result",
        ):
            counts["tool_records"] = 1
            return counts
    elif format == "codex" and kind == "event_msg":
        if payload.get("type") in ("user_message", "agent_message"):
            counts["duplicate_records"] = 1
        elif payload.get("type") in ("agent_reasoning", "reasoning"):
            counts["internal_records"] = 1
        elif payload.get("type") in (
            "token_count",
            "task_started",
            "task_complete",
            "turn_aborted",
            "context_compacted",
            "thread_rolled_back",
            "rate_limits",
        ):
            counts["metadata_records"] = 1
        else:
            counts["unsupported_records"] = 1
        return counts
    elif kind in (
        "session_meta",
        "turn_context",
        "summary",
        "progress",
        "file-history-snapshot",
        "queue-operation",
        "system",
    ):
        counts["metadata_records"] = 1
        return counts
    elif (
        format == "claude"
        and kind == "assistant"
        and payload.get("channel", record.get("channel")) not in (None, "final", "commentary")
    ):
        counts["internal_records"] = 1
        return counts
    content = payload.get("content")
    if isinstance(content, list):
        accepted = {m["block"] for m in messages}
        for index, block in enumerate(content):
            if index in accepted:
                continue
            block_kind = block.get("type") if isinstance(block, dict) else None
            if block_kind in ("tool_use", "tool_result", "tool_call", "function_call_output"):
                counts["tool_blocks"] += 1
            elif block_kind in (
                "image",
                "input_image",
                "document",
                "input_file",
                "audio",
                "input_audio",
                "video",
            ):
                counts["attachment_blocks"] += 1
            elif block_kind in ("thinking", "redacted_thinking", "reasoning"):
                counts["internal_blocks"] += 1
            elif block_kind in ("input_text", "output_text", "text") and block.get("text") == "":
                continue
            else:
                counts["unsupported_blocks"] += 1
    elif not messages:
        counts["unsupported_records"] = 1
    if not messages and isinstance(content, list) and not content:
        counts["metadata_records"] = 1
    return counts


def add_counts(checkpoint, delta):
    counts = checkpoint["accounting"]
    for name, count in delta.items():
        counts[name] = counts.get(name, 0) + count


def observe_workspace(record, checkpoint):
    if not isinstance(record, dict):
        return
    payload = record.get("payload")
    cwd = record.get("cwd")
    if record.get("type") == "session_meta" and isinstance(payload, dict):
        cwd = payload.get("cwd")
    if (
        isinstance(cwd, str)
        and len(cwd.encode("utf-8")) <= 2048
        and Path(cwd).is_absolute()
        and ".." not in Path(cwd).parts
    ):
        # Association claimed by the original transcript; never a permission grant.
        checkpoint.setdefault("workspace", cwd)


def coverage_summary(checkpoint):
    counts = checkpoint["accounting"]
    pending = max(0, checkpoint["observed_size"] - checkpoint["offset"])
    missing = sum(
        counts.get(k, 0)
        for k in (
            "tool_records",
            "tool_blocks",
            "attachment_blocks",
            "unsupported_records",
            "unsupported_blocks",
            "malformed_records",
            "oversized_records",
        )
    )
    coverage = (
        "accounting_incomplete"
        if checkpoint["accounting_start"]
        else "pending"
        if pending or checkpoint.get("pending") or checkpoint.get("skipping")
        else "gaps"
        if missing
        else "complete_supported_text"
    )
    return {
        "accounting": dict(counts),
        "accounting_start": checkpoint["accounting_start"],
        "observed_size": checkpoint["observed_size"],
        "observed_mtime_ns": checkpoint["observed_mtime_ns"],
        "pending_bytes": pending,
        "text_coverage": coverage,
        "workspace": checkpoint.get("workspace"),
    }

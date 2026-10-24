"""Strict host-assisted brain boundary. No implicit model, provider, or archive access."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .bounded_json import MAX_FRAME_BYTES, strict_loads


def obj(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


TEXT = {"type": "string"}
ID = {"type": "string", "maxLength": 128}
VERSION = {"type": "integer", "enum": [1]}
REVISION = {"type": "integer", "minimum": 1}
JSON_OBJECT = {"type": "object"}
SOURCE = obj({"id": ID, "text": TEXT, "provenance": JSON_OBJECT}, ("id", "text", "provenance"))
OBLIGATION = obj(
    {
        "id": ID,
        "text": TEXT,
        "source_id": ID,
        "start": {"type": "integer", "minimum": 0},
        "end": {"type": "integer", "minimum": 1},
    },
    ("id", "text", "source_id", "start", "end"),
)
COMMON = {"protocol_version": VERSION, "session_id": ID}
MUTATION = COMMON | {"request_id": ID, "expected_revision": REVISION}
SPECS = {
    "castle_brain_capabilities": (
        "Inspect model-free capabilities without opening the palace.",
        obj({}),
    ),
    "castle_article_assess": (
        "Bounded article observations, not a truth or aggregate quality score.",
        obj({"text": TEXT, "language": TEXT, "scope": TEXT, "provenance": JSON_OBJECT}, ("text",)),
    ),
    "castle_brain_recall": (
        "Read-only native recall under trusted exposure policy; returns previews and hashes. Unprovable reads are unavailable.",
        obj(
            {
                "query": TEXT,
                "limit": {"type": "integer", "minimum": 1, "maximum": 8},
                "session_id": ID,
                "protocol_version": VERSION,
            },
            ("query",),
        ),
    ),
    "castle_problem_begin": (
        "Start or supersede a bounded SUE examination of your interpretation. Supply original obligations as exact spans; no model is called.",
        obj(
            {
                "protocol_version": VERSION,
                "request_id": ID,
                "problem": TEXT,
                "interpretation": TEXT,
                "sources": {"type": "array", "items": SOURCE, "maxItems": 8},
                "archive_ids": {"type": "array", "items": ID, "maxItems": 8},
                "obligations": {"type": "array", "items": OBLIGATION, "maxItems": 64},
                "parent_id": ID,
                "expected_revision": REVISION,
                "revision_reason": TEXT,
            },
            (
                "protocol_version",
                "request_id",
                "problem",
                "interpretation",
                "sources",
                "obligations",
            ),
        ),
    ),
    "castle_problem_respond": (
        "Submit the active assistant response against the paged SUE schema. Issue dispositions and commitments remain attributed judgments.",
        obj(
            MUTATION
            | {
                "response": JSON_OBJECT,
                "dispositions": {"type": "array", "items": JSON_OBJECT, "maxItems": 128},
                "commitment_map": {"type": "array", "items": JSON_OBJECT, "maxItems": 64},
            },
            (*MUTATION, "response"),
        ),
    ),
    "castle_problem_status": (
        "Resume from current bounded state; consumes the root request budget.",
        obj(COMMON, COMMON),
    ),
    "castle_problem_page": (
        "Read one revision/policy-bound page. Nonzero offset requires the previous cursor.",
        obj(
            COMMON
            | {
                "kind": {
                    "type": "string",
                    "enum": [
                        "sources",
                        "problem",
                        "interpretation",
                        "obligations",
                        "issues",
                        "events",
                        "question",
                        "schema",
                        "source_map",
                        "corrections",
                        "dispositions",
                        "commitments",
                    ],
                },
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 2048},
                "cursor": JSON_OBJECT,
            },
            (*COMMON, "kind"),
        ),
    ),
    "castle_problem_cancel": (
        "Cancel a session; cancellation remains available after the request budget.",
        obj(MUTATION | {"reason": TEXT}, MUTATION),
    ),
    "castle_problem_correct": (
        "Record a correction and invalidate current advice; begin a successor if a slot remains.",
        obj(MUTATION | {"correction": TEXT}, (*MUTATION, "correction")),
    ),
}


def validate(value, schema):
    kind = schema.get("type")
    expected = {"object": dict, "array": list, "string": str, "integer": int}
    if kind in expected and type(value) is not expected[kind]:
        raise ValueError("Invalid parameter type")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Unsupported parameter value")
    if kind == "object":
        if any(key not in value for key in schema.get("required", [])):
            raise ValueError("Missing required parameter")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError("Unknown parameter")
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key])
    elif kind == "array":
        if len(value) > schema.get("maxItems", 2048):
            raise ValueError("Collection limit exceeded")
        for item in value:
            validate(item, schema.get("items", {}))
    elif kind == "string" and len(value) > schema.get("maxLength", MAX_FRAME_BYTES):
        raise ValueError("Text limit exceeded")
    elif kind == "integer" and not schema.get("minimum", -(2**63)) <= value <= schema.get(
        "maximum", 2**63 - 1
    ):
        raise ValueError("Integer outside range")


class BrainAPI:
    def __init__(self, palace):
        self.palace = Path(palace).expanduser()
        self.policy_path = self.palace / ".brain" / "policy.json"

    def policy(self):
        """Operator-owned, private, bounded file; fail closed and re-read each call."""
        from .brain_loop import controller_capabilities

        denied = {"allow_local_sources": False, "policy_epoch": "missing-or-invalid-v1"}
        if controller_capabilities()["status"] != "available":
            return denied
        try:
            # Reject symlink components, not just the final file.
            if any(p.is_symlink() for p in (self.policy_path, *self.policy_path.parents)):
                return denied
            fd = os.open(self.policy_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o077
                    or info.st_size > 8192
                ):
                    return denied
                raw = stream.read(8193)
            policy = strict_loads(raw, max_bytes=8192)
            if not isinstance(policy, dict) or set(policy) - {
                "allow_local_sources",
                "allowed_source_hashes",
            }:
                return denied
            allow = policy.get("allow_local_sources", False)
            hashes = policy.get("allowed_source_hashes", [])
            if (
                type(allow) is not bool
                or not isinstance(hashes, list)
                or len(hashes) > 16
                or any(
                    not isinstance(h, str) or not re.fullmatch("[a-f0-9]{64}", h) for h in hashes
                )
            ):
                return denied
            return {
                "allow_local_sources": allow,
                "allowed_source_hashes": hashes,
                "policy_epoch": hashlib.sha256(raw).hexdigest(),
            }
        except (OSError, ValueError):
            return denied

    @staticmethod
    def _allowed(source, policy):
        from .brain_loop import source_exposure_hash

        return policy["allow_local_sources"] or source_exposure_hash(source) in policy.get(
            "allowed_source_hashes", []
        )

    def _sources(self, operation, *args, **kwargs):
        from .brain_loop import controller_capabilities

        support = controller_capabilities()
        if support["status"] != "available":
            return support
        policy = self.policy()
        if not policy["allow_local_sources"] and not policy.get("allowed_source_hashes"):
            return {
                "status": "exposure_blocked",
                "reason": "Trusted local source exposure policy is required.",
            }
        from . import brain_sources

        result = getattr(brain_sources, operation)(str(self.palace), *args, **kwargs)
        if result.get("status") != "ok":
            return result
        # Re-evaluate after potentially slow native work. No stale authorization.
        current = self.policy()
        if current["policy_epoch"] != policy["policy_epoch"]:
            return {"status": "exposure_blocked", "reason": "Exposure policy changed during read."}
        authorized = [s for s in result["sources"] if self._allowed(s, current)]
        if operation == "read_sources" and len(authorized) != len(result["sources"]):
            return {"status": "exposure_blocked", "reason": "Source snapshot is not authorized."}
        return {"status": "ok", "sources": authorized}

    @staticmethod
    def _failed_read(loop, parent_id, result):
        # An admitted read that never reaches begin still consumed an automatic
        # attempt. Use the controller's durable counter, without advancing SUE.
        if parent_id is not None:
            current = loop.status(parent_id)
            if current.get("status") != "ok":
                return current
        return result

    def _bind_archive(self, loop, args, arguments, ids):
        fingerprint = hashlib.sha256(
            json.dumps(
                {"operation": "archive_begin", "arguments": arguments},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        replay = loop.replay(args["request_id"], fingerprint)
        if replay is not None:
            return replay
        parent_id = args.get("parent_id")
        preflight = loop.preflight_begin(
            args["problem"], parent_id=parent_id, expected_revision=args.get("expected_revision")
        )
        if preflight is not None:
            return preflight
        try:
            loaded = self._sources("read_sources", ids)
        except (ValueError, OSError):
            self._failed_read(loop, parent_id, {"status": "invalid_request"})
            raise
        if loaded["status"] != "ok":
            return self._failed_read(loop, parent_id, loaded)
        if {s["id"] for s in loaded["sources"]} != set(ids):
            return self._failed_read(
                loop,
                parent_id,
                {"status": "unavailable", "reason": "Not all requested source snapshots exist."},
            )
        args["sources"] = args["sources"] + loaded["sources"]
        args["request_fingerprint"] = fingerprint
        return None

    def call(self, name, arguments):
        if name not in SPECS:
            raise ValueError("Unknown brain operation")
        # Also bound direct Python calls before dispatch, independent of wire framing.
        from .brain_loop import _bounded

        _bounded(arguments, MAX_FRAME_BYTES)
        validate(arguments, SPECS[name][1])
        args = dict(arguments)
        if name == "castle_brain_capabilities":
            from .brain_sources import capabilities
            from .brain_loop import controller_capabilities

            return {
                "status": "ok",
                "protocol_version": 1,
                "model_required": False,
                "article_profile": "article-v1",
                "interpretation_mode": "host_assisted",
                "problem_controller": controller_capabilities(),
                "source_reader": capabilities(),
                "exposure_policy": "trusted_local_file",
                "limits": {
                    "examinations": 2,
                    "turns_per_examination": 14,
                    "requests_per_root": 64,
                    "wire_input_bytes": MAX_FRAME_BYTES,
                    "wire_output_bytes": 32768,
                },
                "trusted_operator_controls": ["inspect", "resume", "purge_source"],
                "independent_checks": "not_performed",
            }
        if name == "castle_article_assess":
            from .understanding.article_metrics import analyze_article_quality

            return analyze_article_quality(**args)
        if name == "castle_brain_recall":
            from .brain_loop import source_exposure_hash

            if ("session_id" in args) != ("protocol_version" in args):
                raise ValueError("Scoped recall requires session_id and protocol_version")
            session_id = args.pop("session_id", None)
            args.pop("protocol_version", None)
            if session_id is not None:
                from .brain_loop import BrainLoop

                state = BrainLoop(self.palace / ".brain", exposure_policy=self.policy).status(
                    session_id
                )
                if state["status"] != "ok" or state["execution_state"] != "awaiting_response":
                    return state
            result = self._sources("recall", **args)
            if result["status"] != "ok":
                return result
            return {
                "status": "ok",
                "sources": [
                    {
                        "id": s["id"],
                        "hash": hashlib.sha256(s["text"].encode("utf-8")).hexdigest(),
                        "exposure_hash": source_exposure_hash(s),
                        "text_bytes": len(s["text"].encode("utf-8")),
                        "preview": s["text"][:512],
                        "preview_truncated": len(s["text"]) > 512,
                        "attribution": "archive_snapshot",
                        "truth_verified": False,
                    }
                    for s in result["sources"]
                ],
                "next_action": "Use archive_ids in problem_begin to bind full snapshots.",
            }
        from .brain_loop import BrainLoop

        operation = name.removeprefix("castle_problem_")
        loop = BrainLoop(self.palace / ".brain", exposure_policy=self.policy)
        if operation == "begin":
            ids = args.pop("archive_ids", [])
            if len(ids) + len(args["sources"]) > 8:
                raise ValueError("Source bundle count limit")
            if ids:
                # Bind idempotency to the exact host request, not mutable native
                # table provenance. Lookup is content-free and rechecks current
                # policy/lifecycle before an archive can be reopened.
                failure = self._bind_archive(loop, args, arguments, ids)
                if failure is not None:
                    return failure
        if operation in ("status", "page"):
            args.pop("protocol_version")
        try:
            result = getattr(loop, operation)(**args)
        except (ValueError, OSError):
            if args.get("request_fingerprint"):
                self._failed_read(loop, args.get("parent_id"), {"status": "invalid_request"})
            raise
        if (
            args.get("request_fingerprint")
            and result.get("status") != "ok"
            and "budgets" not in result
        ):
            return self._failed_read(loop, args.get("parent_id"), result)
        return result


def tool_registry(api_factory):
    """Lazy factory keeps discovery free of storage and native initialization."""

    def handler(name):
        return lambda **arguments: api_factory().call(name, arguments)

    return {
        name: {
            "description": description,
            "input_schema": schema,
            "handler": handler(name),
            "strict_arguments": True,
        }
        for name, (description, schema) in SPECS.items()
    }


ACTIONS = {
    "capabilities": "castle_brain_capabilities",
    "article": "castle_article_assess",
    "recall": "castle_brain_recall",
} | {
    action: f"castle_problem_{action}"
    for action in ("begin", "respond", "status", "page", "cancel", "correct")
}


def configure_parser(sub):
    parser = sub.add_parser("brain", help="Bounded model-free article and problem examination")
    parser.add_argument("brain_action", choices=ACTIONS)
    parser.add_argument("--input", default="-", help="Bounded JSON file, or - for stdin")


def cmd_brain(args):
    import sys
    from .config import CognitiveCastleConfig
    from .bounded_json import FrameReader

    try:
        if args.brain_action == "capabilities" and args.input == "-":
            request = {}
        elif args.input == "-":
            # Interactive/native stdin uses the same first-byte deadline as MCP.
            stream = getattr(sys.stdin, "buffer", sys.stdin)
            if hasattr(stream, "getvalue"):
                raw = stream.read(MAX_FRAME_BYTES + 1)
            else:
                raw = FrameReader(stream).read()
            request = strict_loads(raw or b"{}")
        else:
            from .brain_loop import controller_capabilities

            if controller_capabilities()["status"] != "available":
                raise ValueError("Private file access unavailable; use standard input")
            fd = os.open(args.input, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FRAME_BYTES:
                    raise ValueError("Input must be a bounded regular file")
                request = strict_loads(stream.read(MAX_FRAME_BYTES + 1))
        result = BrainAPI(args.palace or CognitiveCastleConfig().palace_path).call(
            ACTIONS[args.brain_action], request
        )
        raw = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > 32768:
            raise ValueError("Response exceeds limit; request a bounded page")
        print(raw)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "invalid_request", "reason": str(exc)}))
        raise SystemExit(2) from None

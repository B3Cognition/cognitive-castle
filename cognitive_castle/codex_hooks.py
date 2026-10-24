"""Codex hook adapter: bounded startup context and background verbatim capture.

Codex runs Stop/PreCompact asynchronously according to hooks/hooks.json. Unlike
Claude's diary hook, this adapter imports only the supplied transcript and does
not request another model turn or generate a summary.
"""

import contextlib
import re
import sys
from pathlib import Path


def session_wing(cwd: str) -> str:
    """Use a readable, valid wing for the Codex workspace."""
    name = Path(cwd).name if cwd else "sessions"
    slug = re.sub(r"[^\w]+", "_", name.lower()).strip("_") or "sessions"
    return "codex_" + slug[:100]


def handle_hook(event: str, data: dict) -> dict:
    """Return Codex-compatible JSON; never block or continue a model turn."""
    if event == "session-start":
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "Cognitive Castle provides local memory through castle_* MCP tools. "
                    "For earlier decisions or conversations, use the castle skill and search "
                    "before inferring history. Preserve exact user text when asked to remember it."
                ),
            }
        }
    if event not in {"stop", "precompact"}:
        raise ValueError(f"Unsupported Codex hook: {event}")

    # A running harness may retain hooks after its config has been edited.
    # This live switch stops even those invocations before storage/model imports.
    if (Path.home() / ".castle" / "codex-capture.disabled").exists():
        return {}

    transcript = data.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return {}
    path = Path(transcript).expanduser()
    if not path.is_file() or path.is_symlink():
        return {}

    # Heavy imports happen only in background capture, never SessionStart.
    from .config import CognitiveCastleConfig
    from .palace import MineAlreadyRunning, mine_palace_lock

    cwd = data.get("cwd")
    wing = session_wing(cwd if isinstance(cwd, str) else "")
    palace_path = CognitiveCastleConfig().palace_path
    try:
        # Share the CLI mine lock and acquire it before loading the miner.
        # Competing captures must exit, not wait with their own models loaded.
        with mine_palace_lock(palace_path):
            from .convo_miner import mine_convos

            with contextlib.redirect_stdout(sys.stderr):
                mine_convos(
                    convo_dir=str(path.resolve()),
                    palace_path=palace_path,
                    wing=wing,
                    agent="codex",
                    skip_kg=True,
                )
    except MineAlreadyRunning:
        print(
            "[castle] Capture skipped: palace mine already running; retry on next hook.",
            file=sys.stderr,
        )
    return {}

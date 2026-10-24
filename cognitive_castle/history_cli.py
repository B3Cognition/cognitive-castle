"""Explicit operator controls for bounded historical conversion; no daemon."""

from pathlib import Path


def configure_history_parser(actions):
    parser = actions.add_parser("history", help="Convert legacy history into common exact memory")
    operations = parser.add_subparsers(dest="history_action", required=True)
    prepare = operations.add_parser(
        "prepare", help="Create/resume a verified private archive snapshot"
    )
    prepare.add_argument("--source", required=True, help="Original local .lance drawer archive")
    operations.add_parser("index", help="Convert one supervised slice of the pinned archive")
    operations.add_parser("status", help="Report historical conversion progress and gaps")


def cmd_history(palace, args):
    from .memory_runtime import run_history

    arguments = {}
    if args.history_action == "prepare":
        arguments["source"] = str(Path(args.source).expanduser().absolute())
    return run_history(Path(palace), args.history_action, arguments)

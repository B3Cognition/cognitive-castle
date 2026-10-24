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
    operations.add_parser(
        "index-scopes",
        help="Build one bounded workspace lookup index for existing memory stores",
    )
    operations.add_parser("status", help="Report historical conversion progress and gaps")
    repair = operations.add_parser(
        "repair", help="Repair one recorded row-size gap under unchanged history limits"
    )
    repair.add_argument("--store-id", required=True, help="Registered historical store SHA256")
    repair.add_argument("--fragment", required=True, type=int, help="Gap's immutable fragment")
    repair.add_argument("--offset", required=True, type=int, help="Cursor before the rejected row")
    repair.add_argument("--row-address", type=int, help="Previous physical row address, if present")


def cmd_history(palace, args):
    from .memory_runtime import run_history

    arguments = {}
    if args.history_action == "prepare":
        arguments["source"] = str(Path(args.source).expanduser().absolute())
    elif args.history_action == "repair":
        cursor = {"fragment": args.fragment, "offset": args.offset}
        if args.row_address is not None:
            cursor["row_address"] = args.row_address
        arguments = {"store_id": args.store_id, "cursor": cursor}
    return run_history(Path(palace), args.history_action, arguments)

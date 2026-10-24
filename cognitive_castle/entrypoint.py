"""Keep configured Codex hooks independent of unrelated CLI startup imports."""

import argparse
import sys


class _UseFullCLI(Exception):
    """The full parser owns diagnostics and all forms outside this fast route."""


class _HookParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, add_help=False, allow_abbrev=False, **kwargs)

    def error(self, message):
        raise _UseFullCLI


def _codex_hook(arguments):
    parser = _HookParser()
    parser.add_argument("--palace")
    commands = parser.add_subparsers(dest="command", required=True)
    hook = commands.add_parser("hook")
    actions = hook.add_subparsers(dest="hook_action", required=True)
    run = actions.add_parser("run")
    run.add_argument("--hook", required=True, choices=("session-start", "stop", "precompact"))
    run.add_argument("--harness", required=True, choices=("codex",))
    try:
        return parser.parse_args(arguments)
    except _UseFullCLI:
        return None


def main():
    args = _codex_hook(sys.argv[1:])
    if args is None:
        from .cli import main as full_main

        return full_main()

    from .config import CognitiveCastleConfig
    from .hooks_cli import run_hook

    palace = args.palace or CognitiveCastleConfig().palace_path
    run_hook(hook_name=args.hook, harness=args.harness, palace=palace)

"""Fixed article subprocess entry point; invoked with Python -I -S.

No site initialization, caller main module, pickle, optional packages or package
startup is required. Only this sibling measurement module and stdlib are loaded.
The parent enforces the process deadline; both IPC directions have byte bounds.
"""

import importlib.abc
import importlib.util
import json
from pathlib import Path
import sys


class _NoOptionalPackages(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {
            "spacy",
            "en_core_web_sm",
            "torch",
            "transformers",
            "sentence_transformers",
            "cognitive_castle",
            "openai",
            "anthropic",
            "lancedb",
            "pyarrow",
        }:
            raise ImportError("article worker permits only its fixed module and stdlib")
        return None


def _deny_network(event, arguments):
    if event.startswith("socket."):
        raise RuntimeError("article worker does not permit network operations")


def main():
    sys.meta_path.insert(0, _NoOptionalPackages())
    sys.addaudithook(_deny_network)
    raw = sys.stdin.buffer.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        return 2
    request = json.loads(raw)
    if not isinstance(request, dict) or set(request) != {"text", "language"}:
        return 2
    text, language = request["text"], request["language"]
    if type(text) is not str or len(text) > 65536 or len(text.encode("utf-8")) > 65536:
        return 2
    if type(language) is not str or len(language) > 64:
        return 2
    spec = importlib.util.spec_from_file_location(
        "_castle_article_measurements", Path(__file__).with_name("article_metrics.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = json.dumps(
        module._measure(text, language), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    if len(result) > 16384:
        return 2
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

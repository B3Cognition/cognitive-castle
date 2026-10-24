"""Disposable fault worker: commit a trusted intent acknowledgement, lose reply."""

import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cognitive_castle.semantic_store_worker import _install_guards, _admit, _execute  # noqa: E402

os.umask(0o077)
request = json.load(sys.stdin)
_install_guards("queue")
refusal = _admit(request, "queue")
if refusal:
    print(json.dumps(refusal))
else:
    assert request["operation"] == "queue_intent_complete"
    assert _execute(request)["status"] == "ok"
    # Exit after the FULL SQLite transaction; the host receives no frame.

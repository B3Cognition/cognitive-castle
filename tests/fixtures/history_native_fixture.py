"""Small native qualification fixture, launched only by the RSS guardian."""

import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cognitive_castle.memory_history_worker import _install_guards  # noqa: E402

_install_guards()
os.umask(0o077)
request = json.load(sys.stdin)
source = Path(request["source"])

import lance  # noqa: E402
import pyarrow as pa  # noqa: E402

texts = ["sharedneedle exact ž😀\r\n" + str(i) for i in range(6)]
metadata = ['{ "workspace": "/qualification", "revision": %d }' % i for i in range(6)]
if request.get("oversized"):
    metadata[3] = json.dumps({"oversized": "x" * (1024**2 + 1)})
if request.get("large_text"):
    # Near the unchanged native batch ceiling, including exact Unicode boundaries.
    texts[3] = "sharedneedle large exact ž😀\r\n" + ("sample ž😀\n" * 154000)
table = pa.table(
    {
        "id": ["duplicate", "deleted", "duplicate", "third", "fourth", "fifth"],
        "text": texts,
        "metadata_json": metadata,
        "wing": ["qualification"] * 6,
        "room": ["native"] * 6,
        "vector": pa.array([[1.0, 2.0, 3.0, 4.0]] * 6, type=pa.list_(pa.float32(), 4)),
    }
)
dataset = lance.write_dataset(table, source, max_rows_per_file=2, max_rows_per_group=2)
dataset.delete("id = 'deleted'")

# Probe the actual adapter's fragment/deletion resume in this disposable process.
from cognitive_castle.memory_history import _scan_rows  # noqa: E402

iterator = _scan_rows(source, dataset.version, {"fragment": 0, "offset": 0})
first = next(iterator)
iterator.close()
cursor = {key: first[key] for key in ("fragment", "offset", "row_address")}
remaining = list(_scan_rows(source, dataset.version, cursor))
assert len(remaining) == 4
assert len({first["row_address"], *(row["row_address"] for row in remaining)}) == 5
assert all("vector" not in row["values"] for row in [first, *remaining])
print(json.dumps({"status": "ok", "version": dataset.version, "rows": 5}))

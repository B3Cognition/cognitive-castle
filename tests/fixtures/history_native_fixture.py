"""Small native qualification fixture, launched only by the RSS guardian."""

import json
import hashlib
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
    texts[3] = "sharedneedle large exact ž😀\x00\r\n" + ("sample ž😀\n" * 154000)
if request.get("stream_text"):
    texts[3] = "sharedneedle streamed ž😀\x00\r\n" + ("sample ž😀\x00\n" * 300000)
table = pa.table(
    {
        "id": ["duplicate", "deleted", "duplicate", "third", "fourth", "fifth"],
        "text": texts,
        "metadata_json": metadata,
        "wing": ["qualification"] * 6,
        "room": ["native"] * 6,
        "select": ["keyword column value"] * 6,
        "field with spaces": ["spaced identifier value ž"] * 6,
        "vector": pa.array([[1.0, 2.0, 3.0, 4.0]] * 6, type=pa.list_(pa.float32(), 4)),
    }
)
dataset = lance.write_dataset(table, source, max_rows_per_file=2, max_rows_per_group=2)
dataset.delete("id = 'deleted'")

if request.get("projection_proof"):
    try:
        try:
            from cognitive_castle.history_projection import NativeProjectedRow
        except ModuleNotFoundError:
            print(json.dumps({"status": "projection_reader_missing"}))
            raise SystemExit(0)
        # Fragment IDs follow native file creation, not necessarily input order.
        seen, previous, target = {}, {}, None
        scan = dataset.scanner(
            columns=["id"],
            with_row_address=True,
            batch_size=1,
            strict_batch_size=True,
            batch_readahead=0,
            fragment_readahead=0,
            io_buffer_size=32 * 1024**2,
            scan_in_order=True,
            use_scalar_index=False,
        )
        for batch in scan.to_batches():
            address = batch.column(batch.schema.get_field_index("_rowaddr"))[0].as_py()
            fragment = address >> 32
            if batch.column(batch.schema.get_field_index("id"))[0].as_py() == "third":
                cursor = {"fragment": fragment, "offset": seen.get(fragment, 0)}
                if fragment in previous:
                    cursor["row_address"] = previous[fragment]
                target = address
                break
            seen[fragment] = seen.get(fragment, 0) + 1
            previous[fragment] = address
        assert target is not None
        reader = NativeProjectedRow(source, dataset.version, cursor)
        try:
            header = reader.header()
            assert header["row_address"] == target
            assert header["offset"] == cursor["offset"] + 1
            assert header["values"]["id"] == "third", {
                "actual": header["values"],
                "cursor": cursor,
                "target": target,
                "bytes": header["text_bytes"],
                "characters": header["text_characters"],
            }
            assert header["text_bytes"] == len(texts[3].encode())
            assert header["text_characters"] == len(texts[3])
            assert header["text_hash"] == hashlib.sha256(texts[3].encode()).hexdigest()
            assert header["values"]["select"] == "keyword column value"
            assert header["values"]["field with spaces"] == "spaced identifier value ž"
            assert "text" not in header["values"] and "vector" not in header["values"]
            for start in (
                0,
                3,
                8191,
                len(texts[3]) // 2 - 131072,
                len(texts[3]) // 2,
                len(texts[3]) - 19,
            ):
                assert reader.page(start) == texts[3][start : start + 131072]
            reader.close()
            reader = NativeProjectedRow(source, dataset.version, cursor)
            reader.bind_header(header)
            assert reader.page(8191) == texts[3][8191 : 8191 + 131072]
            for start, limit in ((-1, 4), (True, 4), (0, 0), (0, 131073)):
                try:
                    reader.page(start, limit)
                except ValueError:
                    pass
                else:
                    raise AssertionError("unbounded projection accepted")
        finally:
            reader.close()
        print(
            json.dumps(
                {"status": "ok", "projection_exact": True, "text_bytes": len(texts[3].encode())}
            )
        )
        raise SystemExit(0)
    except Exception as exc:
        import traceback

        print(
            json.dumps(
                {
                    "status": "projection_error",
                    "type": type(exc).__name__,
                    "detail": traceback.format_exc(limit=4)[-1500:],
                }
            )
        )
        raise SystemExit(0)

# Probe the actual adapter's fragment/deletion resume in this disposable process.
from cognitive_castle.memory_history import _scan_rows  # noqa: E402

if request.get("stream_text"):
    assert dataset.count_rows() == 5
    print(json.dumps({"status": "ok", "version": dataset.version, "rows": 5}))
    raise SystemExit(0)
iterator = _scan_rows(source, dataset.version, {"fragment": 0, "offset": 0})
first = next(iterator)
iterator.close()
cursor = {key: first[key] for key in ("fragment", "offset", "row_address")}
remaining = list(_scan_rows(source, dataset.version, cursor))
assert len(remaining) == 4
assert len({first["row_address"], *(row["row_address"] for row in remaining)}) == 5
assert all("vector" not in row["values"] for row in [first, *remaining])
print(json.dumps({"status": "ok", "version": dataset.version, "rows": 5}))

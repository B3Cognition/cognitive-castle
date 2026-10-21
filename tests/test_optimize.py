"""Tests for cognitive_castle.optimize — palace compaction and FTS rebuild."""

import argparse
import json
import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

import lancedb
import numpy as np
import pyarrow as pa
import pytest

from cognitive_castle import optimize as opt
from cognitive_castle.cli import cmd_optimize

ROWS = 6


def _row(i: int) -> pa.Table:
    return pa.table(
        {
            "id": [f"r{i}"],
            "text": [f"row {i} has some words"],
            "vector": [np.full(4, float(i), dtype="float32")],
        }
    )


def _seed(palace_path: str, table_name: str = "castle_drawers", rows: int = ROWS):
    """Build a table from ``rows`` single-row appends, FTS covering only row 0."""
    db = lancedb.connect(os.path.join(palace_path, "lancedb"))
    table = db.create_table(table_name, _row(0))
    table.create_fts_index("text")
    for i in range(1, rows):
        table.add(_row(i))
    return db.open_table(table_name)


# ── table_stats ──────────────────────────────────────────────────────────


def test_table_stats_reports_fragments_versions_and_fts_coverage(palace_path):
    table = _seed(palace_path)

    stats = opt.table_stats(table)

    assert stats["rows"] == ROWS
    assert stats["fragments"] == ROWS
    assert stats["versions"] >= ROWS
    assert stats["fts_indexed_rows"] == 1
    assert stats["fts_unindexed_rows"] == ROWS - 1
    assert stats["bytes"] > 0


def test_table_stats_without_fts_index_reports_none(palace_path):
    db = lancedb.connect(os.path.join(palace_path, "lancedb"))
    table = db.create_table("castle_drawers", _row(0))

    stats = opt.table_stats(table)

    assert stats["fts_indexed_rows"] is None
    assert stats["fts_unindexed_rows"] is None


# ── optimize_table ───────────────────────────────────────────────────────


def test_optimize_table_compacts_and_covers_every_row_with_fts(palace_path):
    table = _seed(palace_path)
    versions_before = opt.table_stats(table)["versions"]

    result = opt.optimize_table(table)

    after = result["after"]
    assert result["before"]["fragments"] == ROWS
    assert after["fragments"] == 1
    assert after["rows"] == ROWS, "compaction must never lose a drawer"
    assert after["fts_unindexed_rows"] == 0
    assert after["fts_indexed_rows"] == ROWS
    assert result["compaction"]["fragments_removed"] == ROWS
    assert result["compaction"]["fragments_added"] == 1
    # Old versions are kept: nothing is destroyed without an explicit prune.
    assert after["versions"] > versions_before
    assert result["pruned_versions"] is None


def test_optimize_table_keeps_text_verbatim(palace_path):
    table = _seed(palace_path)
    before = sorted(r["text"] for r in table.search(None).limit(ROWS).to_list())

    opt.optimize_table(table)

    after = sorted(r["text"] for r in table.search(None).limit(ROWS).to_list())
    assert after == before


def test_optimize_table_prunes_old_versions_only_when_asked(palace_path):
    table = _seed(palace_path)

    result = opt.optimize_table(table, prune_older_than_days=0)

    assert result["pruned_versions"] is not None
    assert result["after"]["versions"] < result["before"]["versions"]
    assert result["after"]["rows"] == ROWS


def test_optimize_table_incremental_fts_indexes_new_rows_without_rebuild(palace_path):
    """``fts_incremental`` adds the unindexed rows to the existing index (cheap,
    bounded memory) instead of rebuilding it over every row."""
    table = _seed(palace_path)

    result = opt.optimize_table(table, fts_incremental=True, skip_compact=True)

    after = result["after"]
    assert after["fts_unindexed_rows"] == 0
    assert after["fts_indexed_rows"] == ROWS
    assert after["fragments"] == ROWS, "no compaction was asked for"
    assert result["fts"] == "incremental"


def test_optimize_table_incremental_fts_falls_back_to_full_build_without_index(palace_path):
    db = lancedb.connect(os.path.join(palace_path, "lancedb"))
    table = db.create_table("castle_drawers", _row(0))
    table.add(_row(1))

    result = opt.optimize_table(table, fts_incremental=True, skip_compact=True)

    assert result["fts"] == "rebuilt"
    assert result["after"]["fts_unindexed_rows"] == 0


def test_optimize_table_reports_fts_mode():
    table = _mock_table()

    assert opt.optimize_table(table, skip_fts=True)["fts"] == "skipped"
    assert opt.optimize_table(table)["fts"] == "rebuilt"


# ── optimize_palace ──────────────────────────────────────────────────────


def test_optimize_palace_dry_run_reports_without_changing_anything(palace_path):
    table = _seed(palace_path)

    report = opt.optimize_palace(palace_path, dry_run=True)

    assert report["status"] == "dry-run"
    drawers = report["tables"]["castle_drawers"]
    assert drawers["before"]["fragments"] == ROWS
    assert "after" not in drawers
    assert opt.table_stats(table)["fragments"] == ROWS


def test_optimize_palace_optimizes_every_known_table_and_skips_missing(palace_path):
    _seed(palace_path)

    report = opt.optimize_palace(palace_path)

    assert report["status"] == "ok"
    assert report["tables"]["castle_drawers"]["after"]["fragments"] == 1
    assert report["tables"]["castle_closets"]["status"] == "missing"


def test_optimize_palace_without_palace_reports_unknown(tmp_dir):
    report = opt.optimize_palace(os.path.join(tmp_dir, "nope"))

    assert report["status"] == "unknown"
    assert report["tables"] == {}


# ── CLI ──────────────────────────────────────────────────────────────────


def test_optimize_table_passes_memory_knobs_to_lance():
    """``threads`` caps compaction workers; ``fts_heap_mb`` bounds the FTS writer heap."""
    table = MagicMock()
    table.count_rows.return_value = 1
    table.to_lance.return_value.get_fragments.return_value = [object()]
    table.list_versions.return_value = [object()]
    table.stats.return_value = {"total_bytes": 1}
    table.index_stats.return_value = None
    table.to_lance.return_value.optimize.compact_files.return_value = MagicMock(
        fragments_removed=1, fragments_added=1, files_removed=1, files_added=1
    )

    opt.optimize_table(table, threads=1, fts_heap_mb=256)

    table.create_fts_index.assert_called_once_with(
        "text", replace=True, writer_heap_size=256 * 1024 * 1024
    )
    table.to_lance.return_value.optimize.compact_files.assert_called_once_with(num_threads=1)


def _mock_table() -> MagicMock:
    table = MagicMock()
    table.count_rows.return_value = 1
    table.to_lance.return_value.get_fragments.return_value = [object()]
    table.list_versions.return_value = [object()]
    table.stats.return_value = {"total_bytes": 1}
    table.index_stats.return_value = None
    table.to_lance.return_value.optimize.compact_files.return_value = MagicMock(
        fragments_removed=1, fragments_added=1, files_removed=1, files_added=1
    )
    return table


def test_optimize_table_skip_fts_only_compacts():
    table = _mock_table()

    result = opt.optimize_table(table, skip_fts=True)

    table.create_fts_index.assert_not_called()
    table.to_lance.return_value.optimize.compact_files.assert_called_once()
    assert result["compaction"]["fragments_added"] == 1


def test_optimize_table_skip_compact_only_rebuilds_fts():
    table = _mock_table()

    result = opt.optimize_table(table, skip_compact=True)

    table.create_fts_index.assert_called_once_with("text", replace=True)
    table.to_lance.return_value.optimize.compact_files.assert_not_called()
    assert result["compaction"] is None


def test_optimize_table_prune_unverified_reaches_lance_cleanup():
    table = _mock_table()

    opt.optimize_table(table, prune_older_than_days=0, prune_unverified=True, skip_fts=True)

    table.to_lance.return_value.cleanup_old_versions.assert_called_once_with(
        older_than=timedelta(days=0), delete_unverified=True
    )


def test_optimize_table_prune_keeps_unverified_files_by_default():
    table = _mock_table()

    opt.optimize_table(table, prune_older_than_days=1, skip_fts=True)

    table.to_lance.return_value.cleanup_old_versions.assert_called_once_with(
        older_than=timedelta(days=1), delete_unverified=False
    )


def test_print_report_handles_skipped_compaction(capsys):
    stats = {
        "rows": 1,
        "fragments": 1,
        "versions": 1,
        "bytes": 1,
        "fts_indexed_rows": 1,
        "fts_unindexed_rows": 0,
    }
    report = {
        "palace": "/p",
        "status": "ok",
        "tables": {
            "castle_drawers": {
                "status": "ok",
                "before": stats,
                "after": stats,
                "compaction": None,
                "pruned_versions": None,
            }
        },
    }

    opt.print_report(report)

    assert "compact: skipped" in capsys.readouterr().out


def _cli_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        palace=None,
        dry_run=False,
        json=False,
        prune_older_than=None,
        threads=None,
        fts_heap_mb=None,
        skip_fts=False,
        skip_compact=False,
        prune_unverified=False,
        fts_incremental=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@patch("cognitive_castle.cli.CognitiveCastleConfig")
def test_cmd_optimize_uses_config_palace_and_passes_flags(mock_config_cls):
    mock_config_cls.return_value.palace_path = "/fake/palace"
    args = _cli_args(
        dry_run=True,
        prune_older_than=3,
        prune_unverified=True,
        threads=1,
        fts_heap_mb=256,
        skip_fts=True,
    )

    with patch("cognitive_castle.optimize.optimize_palace") as mock_opt:
        mock_opt.return_value = {"status": "dry-run", "palace": "/fake/palace", "tables": {}}
        cmd_optimize(args)

    mock_opt.assert_called_once_with(
        "/fake/palace",
        dry_run=True,
        prune_older_than_days=3,
        threads=1,
        fts_heap_mb=256,
        skip_fts=True,
        skip_compact=False,
        prune_unverified=True,
        fts_incremental=False,
    )


@patch("cognitive_castle.cli.CognitiveCastleConfig")
def test_cmd_optimize_json_output(mock_config_cls, capsys):
    args = _cli_args(palace="~/p", json=True)

    with patch("cognitive_castle.optimize.optimize_palace") as mock_opt:
        mock_opt.return_value = {"status": "ok", "palace": "x", "tables": {}}
        cmd_optimize(args)

    mock_opt.assert_called_once_with(
        os.path.expanduser("~/p"),
        dry_run=False,
        prune_older_than_days=None,
        threads=None,
        fts_heap_mb=None,
        skip_fts=False,
        skip_compact=False,
        prune_unverified=False,
        fts_incremental=False,
    )
    assert json.loads(capsys.readouterr().out) == {"status": "ok", "palace": "x", "tables": {}}


@patch("cognitive_castle.cli.CognitiveCastleConfig")
def test_cmd_optimize_exits_nonzero_on_error(mock_config_cls):
    mock_config_cls.return_value.palace_path = "/fake/palace"
    args = _cli_args()

    with patch("cognitive_castle.optimize.optimize_palace") as mock_opt:
        mock_opt.return_value = {"status": "error", "palace": "/fake/palace", "tables": {}}
        with pytest.raises(SystemExit) as exc:
            cmd_optimize(args)

    assert exc.value.code == 1

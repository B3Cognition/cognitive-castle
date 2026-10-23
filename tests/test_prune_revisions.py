"""`castle prune-revisions`: superseded source revisions are found and removed."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from cognitive_castle import prune_revisions as pr


def _dim(collection) -> int:
    return collection._table.schema.field("vector").type.list_size


def _file(collection, source_file, revision, n, *, filed_at, complete=True, wing="sessions"):
    """File ``n`` drawers of one revision of ``source_file`` with fixed vectors."""
    dim = _dim(collection)
    ids = [f"drawer_{wing}_r_{revision}_{i}" for i in range(n)]
    metas = []
    for i in range(n):
        meta = {
            "wing": wing,
            "room": "r",
            "source_file": source_file,
            "chunk_index": i,
            "filed_at": filed_at,
            "ingest_complete": complete and i == n - 1,
            "normalize_version": 3,
        }
        if revision is not None:
            meta["source_revision"] = revision
            meta["representation"] = "general"
        metas.append(meta)
    collection.add(
        documents=[f"{revision} chunk {i} " + "x" * 10 for i in range(n)],
        ids=ids,
        metadatas=metas,
        embeddings=[[0.1] * dim for _ in range(n)],
    )
    return ids


def _ids(collection) -> set:
    return set(collection.list_drawer_ids())


def test_keeps_only_the_newest_complete_revision(collection):
    _file(collection, "/t/session.jsonl", "rev1", 3, filed_at="2026-01-01T00:00:00")
    _file(collection, "/t/session.jsonl", "rev2", 4, filed_at="2026-01-02T00:00:00")
    _file(collection, "/t/session.jsonl", "rev3", 5, filed_at="2026-01-03T00:00:00")
    _file(collection, "/t/other.md", "o1", 2, filed_at="2026-01-01T00:00:00", wing="projects")

    plans, seen = pr.plan_table(collection, "castle_drawers")

    assert seen == 14
    assert [p.source_file for p in plans] == ["/t/session.jsonl"]
    plan = plans[0]
    assert plan.kept_revision == "rev3"
    assert plan.kept_rows == 5
    assert plan.superseded_rows == 7
    assert plan.revisions == 3
    assert plan.legacy_rows == 0


def test_file_without_a_complete_revision_keeps_everything(collection):
    _file(collection, "/t/s.jsonl", "rev1", 3, filed_at="2026-01-01T00:00:00", complete=False)
    _file(collection, "/t/s.jsonl", "rev2", 3, filed_at="2026-01-02T00:00:00", complete=False)

    plans, _ = pr.plan_table(collection, "castle_drawers")

    assert plans == []


def test_incomplete_revision_newer_than_the_kept_one_is_left_alone(collection):
    """A miner may be writing it right now."""
    _file(collection, "/t/s.jsonl", "old", 2, filed_at="2026-01-01T00:00:00")
    _file(collection, "/t/s.jsonl", "cur", 3, filed_at="2026-01-02T00:00:00")
    live = _file(
        collection, "/t/s.jsonl", "live", 4, filed_at="2026-01-03T00:00:00", complete=False
    )

    [plan], _ = pr.plan_table(collection, "castle_drawers")

    assert plan.kept_revision == "cur"
    assert plan.superseded_rows == 2
    assert not set(plan.delete_ids) & set(live)


def test_abandoned_incomplete_revision_older_than_the_kept_one_goes(collection):
    _file(collection, "/t/s.jsonl", "killed", 2, filed_at="2026-01-01T00:00:00", complete=False)
    _file(collection, "/t/s.jsonl", "cur", 3, filed_at="2026-01-02T00:00:00")

    [plan], _ = pr.plan_table(collection, "castle_drawers")

    assert plan.superseded_rows == 2


def test_legacy_drawers_of_a_re_mined_file_are_preserved(collection):
    """Drawers from before source revisions (the whole-file giants) go once
    the file has a complete current revision, and only then."""
    legacy = _file(collection, "/t/rollout.jsonl", None, 2, filed_at="2026-08-30T00:00:00")
    plans, _ = pr.plan_table(collection, "castle_drawers")
    assert plans == []

    _file(collection, "/t/rollout.jsonl", "cur", 3, filed_at="2026-10-01T00:00:00", wing="codex")
    plans, _ = pr.plan_table(collection, "castle_drawers")
    assert plans == []
    assert set(legacy) <= _ids(collection)


def test_wing_filter(collection):
    _file(collection, "/t/a.jsonl", "r1", 2, filed_at="2026-01-01T00:00:00", wing="sessions")
    _file(collection, "/t/a.jsonl", "r2", 2, filed_at="2026-01-02T00:00:00", wing="sessions")
    _file(collection, "/t/b.md", "p1", 2, filed_at="2026-01-01T00:00:00", wing="projects")
    _file(collection, "/t/b.md", "p2", 2, filed_at="2026-01-02T00:00:00", wing="projects")

    plans, _ = pr.plan_table(collection, "castle_drawers", wing="projects")

    assert [p.source_file for p in plans] == ["/t/b.md"]


def test_dry_run_deletes_nothing_and_apply_deletes_the_plan(collection, palace_path, monkeypatch):
    monkeypatch.setattr(pr, "_miner_alive", lambda: None)
    old = _file(collection, "/t/s.jsonl", "old", 3, filed_at="2026-01-01T00:00:00")
    cur = _file(collection, "/t/s.jsonl", "cur", 2, filed_at="2026-01-02T00:00:00")

    plan = pr.prune_revisions(palace_path)
    assert plan.superseded_rows == 3
    assert plan.applied is False
    assert _ids(collection) == set(old) | set(cur)

    plan = pr.prune_revisions(palace_path, apply=True)
    assert plan.applied is True
    assert plan.deleted_rows == 3
    assert _ids(collection) == set(cur)

    again = pr.prune_revisions(palace_path)
    assert again.superseded_rows == 0


def test_apply_refuses_while_a_miner_is_running(collection, palace_path, monkeypatch):
    monkeypatch.setattr(pr, "_miner_alive", lambda: "mine_transcript.pid (pid 1)")
    _file(collection, "/t/s.jsonl", "old", 1, filed_at="2026-01-01T00:00:00")
    _file(collection, "/t/s.jsonl", "cur", 1, filed_at="2026-01-02T00:00:00")

    with pytest.raises(pr.PruneRevisionsError, match="miner is running"):
        pr.prune_revisions(palace_path, apply=True)
    assert len(_ids(collection)) == 2

    pr.prune_revisions(palace_path, apply=True, force=True)
    assert len(_ids(collection)) == 1


def test_plan_as_dict_and_report(collection, palace_path, monkeypatch):
    monkeypatch.setattr(pr, "_miner_alive", lambda: None)
    _file(collection, "/t/s.jsonl", "old", 2, filed_at="2026-01-01T00:00:00")
    _file(collection, "/t/s.jsonl", "cur", 2, filed_at="2026-01-02T00:00:00")

    plan = pr.prune_revisions(palace_path)
    as_dict = json.loads(json.dumps(plan.as_dict()))

    assert as_dict["superseded_rows"] == 2
    assert as_dict["by_wing"] == {"sessions": 2}
    assert as_dict["sources"][0]["kept_revision"] == "cur"
    assert "delete_ids" not in as_dict["sources"][0]
    text = pr.format_plan(plan)
    assert "Dry run" in text and "/t/s.jsonl" in text


def test_cli_prune_revisions_passes_flags_through(capsys):
    from cognitive_castle import cli

    fake = pr.PrunePlan(
        palace="/p", sources=[], rows_total=0, superseded_rows=0, superseded_chars=0, by_wing={}
    )
    with patch("cognitive_castle.prune_revisions.prune_revisions", return_value=fake) as run:
        with patch("sys.argv", ["castle", "prune-revisions", "--apply", "--wing", "w", "--force"]):
            cli.main()

    run.assert_called_once_with(None, apply=True, wing="w", force=True)
    assert "Nothing to prune" in capsys.readouterr().out

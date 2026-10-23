"""Diary correction and growth must preserve source history and every pointer."""

import pytest
from cognitive_castle.diary_ingest import ingest_diaries


@pytest.mark.parametrize("change", ["correction", "append"])
def test_diary_changes_preserve_both_versions(synthetic_palace, tmp_path, change):
    directory = tmp_path / "diary"
    directory.mkdir()
    path = directory / "2026-10-23.md"
    original = "## Morning\r\nAlice decided to preserve this exact original sentence and its whitespace.  \r\n"
    path.write_bytes(original.encode())
    ingest_diaries(directory, synthetic_palace.root)
    old_ids = set(synthetic_palace.drawers.get().ids)
    updated = (
        original.replace("Alice", "Bobby")
        if change == "correction"
        else original
        + "\r\n## Evening\r\nThe evening decision must not erase the morning index.\r\n"
    )
    path.write_bytes(updated.encode())
    assert ingest_diaries(directory, synthetic_palace.root)["days_updated"] == 1
    records = synthetic_palace.drawers.get()
    assert original in records.documents
    assert updated in records.documents
    assert old_ids < set(records.ids)
    closet_text = "\n".join(synthetic_palace.closets.get().documents)
    assert "morning" in closet_text.lower()
    if change == "append":
        assert "evening" in closet_text.lower()


def test_same_day_in_different_diary_roots_does_not_collide(synthetic_palace, tmp_path):
    for name in ("work", "personal"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "2026-10-23.md").write_text(
            f"## {name}\nThe exact {name} content must retain its own source identity and history.\n"
        )
        ingest_diaries(directory, synthetic_palace.root)
    assert synthetic_palace.drawers.count() == 2

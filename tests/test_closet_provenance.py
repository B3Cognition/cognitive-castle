from cognitive_castle.palace import build_closet_lines


def test_topic_points_to_its_actual_span_beyond_first_three_drawers():
    text = "background " * 300 + "\n## Migration choice\nWe decided to keep exact source history.\n"
    cut = len(text) - 100
    spans = [(f"d{i}", i * cut // 4, (i + 1) * cut // 4) for i in range(4)] + [
        ("d4", cut, len(text))
    ]
    lines = build_closet_lines(
        "notes.md", [s[0] for s in spans], text, "project", "notes", drawer_spans=spans
    )
    migration = next(line for line in lines if "migration choice" in line)
    assert migration.endswith("→d4")

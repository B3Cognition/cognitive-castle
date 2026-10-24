"""Hand-checked article extraction, applicability, and standalone bounds."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


def assess(text, **kwargs):
    from cognitive_castle.understanding import analyze_article_quality

    return analyze_article_quality(text, **kwargs)


def test_article_keeps_surrounding_prose_and_reports_only_measurements():
    from cognitive_castle.understanding.article_metrics import _extract_prose

    text = "Before the list.\n\n- First item.\n- Second item.\n\nAfter the list."
    prose, counts, _ = _extract_prose(text)
    assert prose == "Before the list.\n\nFirst item.\nSecond item.\n\nAfter the list."
    assert counts["list_lines"] == 2
    result = assess(text, language="en")
    assert result["status"] == "assessed"
    assert result["profile"] == "article-v1"
    assert result["quality_score"] is None
    assert result["quality_boost"] == 1.0
    assert result["analyzed_prose"]["words"] == 10
    assert result["analyzed_prose"]["sentences"] == 4
    assert "text" not in result["source"]
    assert "text" not in result["analyzed_prose"]
    assert "requirements" not in result


def test_markdown_extraction_policy_distinguishes_excluded_content():
    from cognitive_castle.understanding.article_metrics import _extract_prose

    text = (
        "# Heading\n\nA [link label](https://example.org/path) stays.\n"
        "> A quotation stays.\nUse `hidden_code` carefully.\n"
        "```python\nhidden_code()\n```\n~~~sql\nSELECT hidden;\n~~~\n"
        "| Col | Value |\n| --- | --- |\n| hidden | data |\n"
        "<div>hidden html</div>\n\nClosing prose."
    )
    prose, counts, reasons = _extract_prose(text)
    assert prose == (
        "Heading\n\nA link label stays.\nA quotation stays.\nUse  carefully.\n\nClosing prose."
    )
    assert counts["headings"] == 1
    assert counts["blockquote_lines"] == 1
    assert counts["link_destinations"] == 1
    assert counts["inline_code"] == 1
    assert counts["code_fences"] == 2
    assert counts["table_lines"] == 3
    assert counts["html_lines"] == 1
    assert "tables_excluded" in reasons
    assert "html_excluded" in reasons


def test_decimal_abbreviation_url_and_unicode_boundaries():
    from cognitive_castle.understanding.article_metrics import _sentences, _words

    text = "Dr. Smith paid 2.5 dollars, e.g. today. Visit https://example.org/a?q=2. Done!"
    assert _sentences(text) == [
        "Dr. Smith paid 2.5 dollars, e.g. today.",
        "Visit https://example.org/a?q=2.",
        "Done!",
    ]
    assert _words("Café cafe\u0301 中文 2.5 don't stop") == [
        "Café",
        "cafe\u0301",
        "中文",
        "2.5",
        "don't",
        "stop",
    ]
    assert _sentences("“One.” Two！三。") == ["“One.”", "Two！", "三。"]
    assert _words("See https://example.org/a?q=2 now.") == [
        "See",
        "https://example.org/a?q=2",
        "now",
    ]


@pytest.mark.parametrize(
    "text", ["", " \n\t", "```py\nx = 1\n```", "~~~\nx\n~~~", "| a | b |\n| --- | --- |"]
)
def test_nonprose_is_not_an_invented_zero_quality_article(text):
    result = assess(text, language="en")
    assert result["status"] == "not_applicable"
    assert result["quality_score"] is None
    assert result["readability"]["flesch_reading_ease"]["value"] is None
    assert result["readability"]["flesch_reading_ease"]["reason"] == "no_analyzable_prose"


@pytest.mark.parametrize(
    "language,text",
    [
        ("cs", "Toto je český článek. Je krátký."),
        ("zh", "这是中文。第二句话。"),
        ("mixed", "English text. Česká věta."),
        ("unknown", "This language was not declared."),
    ],
)
def test_english_formulas_need_declared_applicable_language(language, text):
    result = assess(text, language=language)
    assert result["language"] == {"declared": language, "detected": "unknown"}
    assert result["analyzed_prose"]["words"] > 0
    for metric in result["readability"].values():
        assert metric == {"value": None, "reason": "requires_declared_english"}


@pytest.mark.parametrize("sentence_count, applicable", [(29, False), (30, True)])
def test_smog_minimum_analyzed_sentences(sentence_count, applicable):
    result = assess("The cat sat. " * sentence_count, language="en")
    assert result["analyzed_prose"]["sentences"] == sentence_count
    smog = result["readability"]["smog_index"]
    if applicable:
        assert smog == {"value": 3.1291, "reason": None}
    else:
        assert smog == {"value": None, "reason": "requires_30_sentences"}


def test_excerpt_identity_and_provenance_do_not_imply_whole_article():
    text = "Exact cafe\u0301 text.\r\nEmoji 😀."
    provenance = {"revision": "rev-4", "byte_range": [20, 49], "origin": "caller_attributed"}
    result = assess(text, scope="excerpt", provenance=provenance)
    assert result["scope"] == "excerpt"
    assert result["incomplete"] is True
    assert result["source"]["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert result["source"]["utf8_bytes"] == 31
    assert result["source"]["provenance"] == provenance
    assert result["independent_checks"] == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "😀" * 16385},
        {"text": "a", "provenance": {"data": "x" * 8192}},
        {"text": "\ud800"},
        {"text": "a", "language": "en" * 65},
        {"text": "a", "scope": "invented"},
        {"text": "a", "provenance": {"number": float("nan")}},
    ],
)
def test_standalone_input_rejected_before_worker_admission(kwargs, monkeypatch):
    from cognitive_castle.understanding import article_metrics

    def forbidden(*args, **kwargs):
        pytest.fail("invalid standalone input reached worker")

    monkeypatch.setattr(article_metrics, "_run_isolated", forbidden)
    with pytest.raises(ValueError):
        assess(**kwargs)


def test_standalone_provenance_rejects_cycles_and_excessive_depth():
    cycle = {}
    cycle["self"] = cycle
    with pytest.raises(ValueError):
        assess("Text.", provenance=cycle)
    nested = {}
    for _ in range(34):
        nested = {"child": nested}
    with pytest.raises(ValueError):
        assess("Text.", provenance=nested)


def test_maximum_unbroken_unicode_input_has_bounded_result():
    result = assess("é" * 32768)
    assert result["source"]["utf8_bytes"] == 65536
    assert result["analyzed_prose"]["words"] == 1
    assert len(result["findings"]) <= 128
    assert len(json.dumps(result, ensure_ascii=False).encode()) < 32768


def test_isolated_compute_deadline_reaps_its_worker(monkeypatch):
    from cognitive_castle.understanding import article_metrics

    popen = subprocess.Popen
    workers = []

    def stalled_worker(command, **kwargs):
        worker = popen([sys.executable, "-I", "-S", "-c", "import time; time.sleep(30)"], **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(article_metrics.subprocess, "Popen", stalled_worker)
    monkeypatch.setattr(article_metrics, "COMPUTE_SECONDS", 0.1)
    result = assess("Bounded article.")
    assert result["status"] == "unavailable"
    assert result["reason"] == "article_compute_deadline"
    assert workers and all(worker.poll() is not None for worker in workers)


def test_nested_list_prose_is_not_mistaken_for_indented_code():
    from cognitive_castle.understanding.article_metrics import _extract_prose

    prose, counts, _ = _extract_prose("Opening.\n- Parent item.\n    - Nested item.\n\nClosing.")
    assert prose == "Opening.\nParent item.\nNested item.\n\nClosing."
    assert counts["list_lines"] == 2
    assert counts["indented_code_lines"] == 0


def test_reference_links_keep_labels_and_exclude_destinations():
    from cognitive_castle.understanding.article_metrics import _extract_prose

    prose, counts, _ = _extract_prose("Read [this label][ref].\n\n[ref]: https://example.com")
    assert prose == "Read this label."
    assert counts["link_destinations"] == 1
    assert counts["reference_definitions"] == 1


def test_unknown_language_has_no_syllable_work_or_grade_estimate():
    result = assess("这是中文。Second sentence.")
    assert result["analyzed_prose"]["sentences"] == 2
    assert result["readability"]["flesch_kincaid_grade"]["value"] is None


def test_article_worker_never_reexecutes_host_top_level(tmp_path):
    marker = tmp_path / "host-starts.txt"
    host = tmp_path / "host.py"
    root = Path(__file__).resolve().parents[1]
    host.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(root)!r})\n"
        f"with Path({str(marker)!r}).open('a') as output:\n"
        "    output.write('host started\\n')\n"
        "from cognitive_castle.understanding import analyze_article_quality\n"
        "if __name__ == '__main__':\n"
        "    print(json.dumps(analyze_article_quality('A small article.', language='en')))\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", str(host)], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "assessed"
    assert marker.read_text().splitlines() == ["host started"]

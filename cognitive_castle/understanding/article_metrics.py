"""Bounded, model-free article measurements (article-v1).

This profile has no calibrated quality aggregate. Readability estimates describe
declared English prose; they do not verify truth, completeness or understanding.
The original UTF-8 bytes are hashed without normalization and never overwritten.
The public result contains counts, not a second copy of the source text.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from threading import Lock

PROFILE = "article-v1"
TEXT_BYTES = 64 * 1024
PROVENANCE_BYTES = 8 * 1024
COMPUTE_SECONDS = 2.0
_admission = Lock()
_METRICS = (
    "flesch_reading_ease",
    "flesch_kincaid_grade",
    "gunning_fog_index",
    "smog_index",
    "coleman_liau_index",
    "automated_readability_index",
)
_URL = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_ABBREVIATION = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|e\.g|i\.e)\.", re.IGNORECASE)
_INITIALS = re.compile(r"\b(?:[A-Za-z]\.){2,}")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HTML = re.compile(r"</?[A-Za-z][^>]*>|<!--|<![A-Z]", re.IGNORECASE)
_POLICY = {
    "version": "article-prose-v1",
    "included": ["paragraphs", "headings", "list_prose", "block_quotes", "link_labels"],
    "excluded": [
        "fenced_code",
        "indented_code",
        "inline_code",
        "link_destinations",
        "images",
        "html_lines",
        "pipe_table_lines",
        "reference_definitions",
    ],
    "limits": "Conservative Markdown subset; HTML-bearing and pipe-table lines are excluded whole.",
    "tokenizer": "unicode-category-v1; decimals, common English abbreviations and URLs guarded",
}


def _bounded_provenance(value):
    """Validate before encoding; never traverse an unbounded caller object."""
    if value is None:
        return {}
    if type(value) is not dict:
        raise ValueError("provenance must be a JSON object")
    active = set()
    budget = [0, 0]

    def visit(item, depth):
        budget[0] += 1
        if depth > 32 or budget[0] > PROVENANCE_BYTES:
            raise ValueError("provenance structure exceeds limit")
        kind = type(item)
        if kind is str:
            if len(item) > PROVENANCE_BYTES:
                raise ValueError("provenance exceeds byte limit")
            budget[1] += len(item.encode("utf-8"))
        elif kind in (dict, list):
            if id(item) in active or len(item) > PROVENANCE_BYTES:
                raise ValueError("provenance must be bounded acyclic JSON")
            active.add(id(item))
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise ValueError("provenance keys must be strings")
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
            active.remove(id(item))
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError("provenance numbers must be finite")
        elif kind is int:
            if item.bit_length() > 64:
                raise ValueError("provenance integer exceeds limit")
        elif item is not None and kind is not bool:
            raise ValueError("provenance must contain JSON values")
        if budget[1] > PROVENANCE_BYTES:
            raise ValueError("provenance exceeds byte limit")

    try:
        visit(value, 0)
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > PROVENANCE_BYTES:
            raise ValueError("provenance exceeds byte limit")
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("provenance is not valid bounded UTF-8 JSON") from exc
    return json.loads(encoded)


def _inline(line, counts):
    """Strip inline code and simple Markdown links in one bounded scan."""
    output = []
    cursor = 0
    while cursor < len(line):
        char = line[cursor]
        if char == "`":
            end = cursor + 1
            while end < len(line) and line[end] == "`":
                end += 1
            delimiter = line[cursor:end]
            close = line.find(delimiter, end)
            counts["inline_code"] += 1
            cursor = len(line) if close == -1 else close + len(delimiter)
            continue
        image = line.startswith("![", cursor)
        start = cursor + 1 if image else cursor
        if line[start : start + 1] == "[":
            label_end = line.find("]", start + 1)
            if label_end != -1 and line[label_end + 1 : label_end + 2] == "[":
                reference_end = line.find("]", label_end + 2)
                if reference_end != -1:
                    counts["link_destinations"] += 1
                    if image:
                        counts["images"] += 1
                    else:
                        output.append(line[start + 1 : label_end])
                    cursor = reference_end + 1
                    continue
            if label_end != -1 and line[label_end + 1 : label_end + 2] == "(":
                depth = 1
                end = label_end + 2
                while end < len(line) and depth:
                    if line[end] == "(":
                        depth += 1
                    elif line[end] == ")":
                        depth -= 1
                    end += 1
                if depth == 0:
                    counts["link_destinations"] += 1
                    if image:
                        counts["images"] += 1
                    else:
                        output.append(line[start + 1 : label_end])
                    cursor = end
                    continue
        output.append(char)
        cursor += 1
    return "".join(output)


def _extract_prose(text):
    """Return extracted prose, format counts and exclusion reasons, never mutate source."""
    counts = dict.fromkeys(
        (
            "headings",
            "list_lines",
            "blockquote_lines",
            "link_destinations",
            "inline_code",
            "code_fences",
            "code_lines",
            "table_lines",
            "html_lines",
            "images",
            "reference_definitions",
            "indented_code_lines",
        ),
        0,
    )
    prose = []
    fence = None
    html_block = None
    for raw_line in text.splitlines():
        line = raw_line
        marker = _FENCE.match(line)
        if fence:
            counts["code_lines"] += 1
            stripped = line.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= fence[1]:
                fence = None
            continue
        if marker:
            token = marker.group(1)
            fence = (token[0], len(token))
            counts["code_fences"] += 1
            counts["code_lines"] += 1
            continue
        if html_block:
            counts["html_lines"] += 1
            if html_block in line.lower():
                html_block = None
            continue
        if _HTML.search(line):
            counts["html_lines"] += 1
            lower = line.lower()
            if "<!--" in lower and "-->" not in lower:
                html_block = "-->"
            else:
                tag = re.search(r"<(script|style|pre|div|table)\b", lower)
                if tag and "</" + tag.group(1) + ">" not in lower:
                    html_block = "</" + tag.group(1) + ">"
            continue
        if line.count("|") >= 2:
            counts["table_lines"] += 1
            continue
        if re.match(r"^\s{0,3}\[[^\]]+\]:", line):
            counts["reference_definitions"] += 1
            continue
        if line.startswith(("    ", "\t")) and line.strip() and not _BULLET.match(line):
            counts["indented_code_lines"] += 1
            continue
        if _HEADING.match(line):
            counts["headings"] += 1
            line = _HEADING.sub("", line).rstrip(" #")
        if line.lstrip().startswith(">"):
            counts["blockquote_lines"] += 1
            line = re.sub(r"^\s*(?:>\s*)+", "", line)
        if _BULLET.match(line):
            counts["list_lines"] += 1
            line = _BULLET.sub("", line)
        if re.fullmatch(r"\s*(?:[-*_]\s*){3,}", line):
            continue
        prose.append(_inline(line, counts))
    reasons = []
    for count, reason in (
        ("code_lines", "fenced_code_excluded"),
        ("inline_code", "inline_code_excluded"),
        ("table_lines", "tables_excluded"),
        ("html_lines", "html_excluded"),
        ("link_destinations", "link_destinations_excluded"),
        ("images", "images_excluded"),
        ("reference_definitions", "reference_definitions_excluded"),
        ("indented_code_lines", "indented_code_excluded"),
    ):
        if counts[count]:
            reasons.append(reason)
    if fence:
        reasons.append("unclosed_code_fence_excluded_to_end")
    if html_block:
        reasons.append("unclosed_html_block_excluded_to_end")
    return "\n".join(prose).strip(), counts, reasons


def _sentences(text):
    protected = set()
    for pattern in (_URL, _ABBREVIATION, _INITIALS):
        for match in pattern.finditer(text):
            end = match.end()
            if pattern is _URL:
                end = match.start() + len(match.group().rstrip(".,;!?"))
            protected.update(range(match.start(), end))
    sentences = []
    start = cursor = 0
    while cursor < len(text):
        char = text[cursor]
        if cursor in protected or char not in ".!?。！？":
            cursor += 1
            continue
        if char == "." and cursor and cursor + 1 < len(text):
            if text[cursor - 1].isdigit() and text[cursor + 1].isdigit():
                cursor += 1
                continue
        end = cursor + 1
        while end < len(text) and text[end] in ".!?。！？\"'”’»)]}":
            end += 1
        if char in "。！？" or end == len(text) or text[end].isspace():
            part = text[start:end].strip()
            if any(c.isalnum() for c in part):
                sentences.append(part)
            start = end
        cursor = end
    remaining = text[start:].strip()
    if any(c.isalnum() for c in remaining):
        sentences.append(remaining)
    return sentences


def _words(text):
    """Unicode letters/numbers with combining marks, decimal points and inner apostrophes."""
    words = []
    start = None
    index = 0
    while index < len(text):
        char = text[index]
        if start is None and char.lower() == "h":
            url = _URL.match(text, index)
            if url:
                words.append(url.group().rstrip(".,;!?"))
                index = url.end()
                continue
        category = unicodedata.category(char)[0]
        inside = category in "LN" or (category == "M" and start is not None)
        if start is not None and index + 1 < len(text):
            if char in "'’" and text[index + 1].isalpha():
                inside = True
            if char == "." and text[index - 1].isdigit() and text[index + 1].isdigit():
                inside = True
        if inside:
            if start is None:
                start = index
        elif start is not None:
            words.append(text[start:index])
            start = None
        index += 1
    if start is not None:
        words.append(text[start:])
    return words


def _syllables(word):
    lowered = word.lower()
    groups = len(re.findall(r"[aeiouy]+", lowered))
    if lowered.endswith("e") and not lowered.endswith(("le", "ye")) and groups > 1:
        groups -= 1
    return max(1, groups)


def _measure(text, language):
    prose, counts, exclusions = _extract_prose(text)
    words = _words(prose)
    sentences = _sentences(prose)
    word_count, sentence_count = len(words), len(sentences)
    reason = None
    if not word_count:
        reason = "no_analyzable_prose"
    elif language.lower().replace("_", "-").split("-")[0] != "en":
        reason = "requires_declared_english"
    readability = {key: {"value": None, "reason": reason} for key in _METRICS}
    if reason is None:
        syllables = [_syllables(word) for word in words]
        mean_words = word_count / max(1, sentence_count)
        mean_syllables = sum(syllables) / word_count
        complex_words = sum(value >= 3 for value in syllables)
        letters = sum(sum(char.isalpha() for char in word) for word in words)
        values = {
            "flesch_reading_ease": 206.835 - 1.015 * mean_words - 84.6 * mean_syllables,
            "flesch_kincaid_grade": 0.39 * mean_words + 11.8 * mean_syllables - 15.59,
            "gunning_fog_index": 0.4 * (mean_words + 100 * complex_words / word_count),
            "coleman_liau_index": 0.0588 * (100 * letters / word_count)
            - 0.296 * (100 * sentence_count / word_count)
            - 15.8,
            "automated_readability_index": 4.71 * sum(map(len, words)) / word_count
            + 0.5 * mean_words
            - 21.43,
        }
        if sentence_count >= 30:
            values["smog_index"] = 1.043 * math.sqrt(complex_words * 30 / sentence_count) + 3.1291
        else:
            readability["smog_index"]["reason"] = "requires_30_sentences"
        for key, value in values.items():
            readability[key] = {"value": round(value, 4), "reason": None}
    findings = [{"code": item} for item in exclusions]
    if reason:
        findings.append({"code": reason})
    return {
        "status": "assessed" if word_count else "not_applicable",
        "analyzed_prose": {
            "utf8_bytes": len(prose.encode("utf-8")),
            "characters": len(prose),
            "words": word_count,
            "sentences": sentence_count,
        },
        "extraction": {"policy": _POLICY, "counts": counts, "excluded_reasons": exclusions},
        "readability": readability,
        "readability_method": "English formulas with heuristic syllables; declared language is not verified",
        "findings": findings,
        "findings_remaining": 0,
    }


def _run_isolated(text, language):
    """Run a fixed stdlib-only entry point, never the host's __main__ module."""
    if not _admission.acquire(blocking=False):
        return {"status": "unavailable", "reason": "article_worker_busy", "findings": []}
    process = None
    try:
        started = time.monotonic()
        request = json.dumps({"text": text, "language": language}, ensure_ascii=False).encode(
            "utf-8"
        )
        worker = Path(__file__).with_name("article_worker.py")
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", str(worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        output, _ = process.communicate(
            input=request,
            timeout=max(0.001, COMPUTE_SECONDS - (time.monotonic() - started)),
        )
        if process.returncode != 0 or len(output) > 16384:
            raise ValueError("invalid article worker result")
        result = json.loads(output)
        if not isinstance(result, dict) or result.get("status") not in {
            "assessed",
            "not_applicable",
        }:
            raise ValueError("invalid article worker result")
        return result
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "reason": "article_compute_deadline", "findings": []}
    except (OSError, RuntimeError, ValueError):
        return {"status": "unavailable", "reason": "article_worker_unavailable", "findings": []}
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=0.2)
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()
        _admission.release()


def analyze_article_quality(
    text: str, *, language: str = "unknown", scope: str = "article", provenance: dict | None = None
) -> dict:
    """Measure an explicitly selected article/excerpt with no model or retention.

    Reject invalid/oversized input before spawning. Computation failure is an
    explicit unavailable result; no content is silently truncated to fit a cap.
    """
    if type(text) is not str or len(text) > TEXT_BYTES:
        raise ValueError("article text must be a UTF-8 string within 64 KiB")
    try:
        raw = text.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("article text must be valid UTF-8") from exc
    if len(raw) > TEXT_BYTES:
        raise ValueError("article text exceeds 64 KiB")
    if (
        type(language) is not str
        or len(language) > 64
        or not re.fullmatch(r"[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{2,8})*", language)
    ):
        raise ValueError("language must be a bounded language tag, mixed, or unknown")
    if type(scope) is not str or scope not in {"article", "excerpt"}:
        raise ValueError("scope must be article or excerpt")
    provenance = _bounded_provenance(provenance)
    result = _run_isolated(text, language)
    result.update(
        {
            "profile": PROFILE,
            "quality_score": None,
            "quality_boost": 1.0,
            "quality_reason": "article_aggregate_uncalibrated",
            "language": {"declared": language, "detected": "unknown"},
            "scope": scope,
            "incomplete": scope == "excerpt",
            "source": {
                "utf8_bytes": len(raw),
                "characters": len(text),
                "lines": len(text.splitlines()),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "provenance": provenance,
                "provenance_confidence": "caller_attributed",
            },
            "independent_checks": [],
            "limitations": [
                "No factual verification",
                "No completeness or understanding certificate",
                "No calibrated article quality aggregate",
            ],
        }
    )
    return result

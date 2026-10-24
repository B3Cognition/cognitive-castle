#!/usr/bin/env python3
"""Reproducible model-free capture/context/recall evaluation on selected evidence.

Default data is public and synthetic. --fixture accepts a private hashed evidence
fixture; its exact excerpts are REPLAYED, never presented as historical capture.
Only fixture-listed ordinary source files are read. No transcript discovery,
provider, embedding, model, hook activation, or production palace is involved.
The unchanged first-token baseline is always reported. --query-plan adds a
separate bounded operator profile; freeze that plan from question text before
inspecting answers. --question-budget and --recall-limit permit declared
sensitivity runs with the same plan, not answer-guided query tuning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cognitive_castle.fast_memory import MemoryStore
from cognitive_castle.memory_capture import capture_one, coverage, queue_source
from cognitive_castle.memory_context import restore_context, update_context

BUDGET = 8192
QUESTION_BUDGET = 4 * BUDGET
MAX_FIXTURE_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
STOP_WORDS = frozenset(
    "a an and are as at be been by can could did do does for from given guide "
    "how if in into is it its may mean must now of on or our per say should "
    "some still than that the their them then there these this those through "
    "to treat use was were what when where which who why will with would you "
    "your based supplied already actually according report justified".split()
)


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _private_write(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _privacy_supported():
    if os.name != "posix" or not all(
        hasattr(os, name) for name in ("O_NOFOLLOW", "O_NONBLOCK", "getuid")
    ):
        raise ValueError("evaluation requires POSIX privacy primitives")


def _read_bounded(path, maximum):
    _privacy_supported()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("evaluation source must be a regular file")
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("source exceeds evaluation byte bound")
    return raw


def verify_fixture(fixture):
    """Verify current file hashes, exact UTF-8 slices and both offset conventions."""
    if fixture.get("schema_version") != 1:
        raise ValueError("fixture schema version")
    if len(_encoded(fixture)) > MAX_FIXTURE_BYTES:
        raise ValueError("fixture byte bound")
    sources, spans, questions = (
        fixture.get("sources", []),
        fixture.get("evidence_spans", []),
        fixture.get("questions", []),
    )
    if not 1 <= len(sources) <= 8 or not 1 <= len(spans) <= 64 or not 1 <= len(questions) <= 32:
        raise ValueError("fixture count bounds")
    originals = {}
    for source in sources:
        identity = source["source_id"]
        if identity in originals:
            raise ValueError("duplicate source identity")
        path = Path(source["path"])
        if not path.is_absolute() or path.suffix.lower() not in {
            ".md",
            ".txt",
            ".py",
            ".ts",
            ".tsx",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".mjs",
        }:
            raise ValueError("fixture requires explicit ordinary-text source paths")
        raw = _read_bounded(path, MAX_SOURCE_BYTES)
        raw.decode("utf-8")
        if _sha(raw) != source["sha256"]:
            raise ValueError("source hash changed")
        originals[identity] = (source, raw)
    identities = set()
    for span in spans:
        identity = span["evidence_id"]
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError("duplicate or invalid evidence identity")
        identities.add(identity)
        source, raw = originals[span["source_id"]]
        if span["source_path"] != source["path"] or span["source_sha256"] != source["sha256"]:
            raise ValueError("span source/hash mismatch")
        start, end = span["byte_start_0based"], span["byte_end_0based_exclusive"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
            raise ValueError("span byte bounds")
        selected = raw[start:end]
        if len(selected) > 65536 or selected.decode("utf-8") != span["quotation"]:
            raise ValueError("span quotation mismatch")
        if _sha(selected) != span["span_sha256"]:
            raise ValueError("span hash mismatch")
        lines = raw.splitlines(keepends=True)
        first, last = span["line_start_1based"], span["line_end_1based_inclusive"]
        if (
            type(first) is not int
            or type(last) is not int
            or not 1 <= first <= last <= len(lines)
            or sum(map(len, lines[: first - 1])) != start
            or sum(map(len, lines[:last])) != end
        ):
            raise ValueError("span line/byte mismatch")
    question_ids = set()
    for question in questions:
        identity = question["question_id"]
        expected = question["evidence_ids"]
        if identity in question_ids or not expected or len(set(expected)) != len(expected):
            raise ValueError("question identities")
        question_ids.add(identity)
        if not set(expected) <= identities:
            raise ValueError("unknown expected evidence")
        if not isinstance(question["question"], str) or not question["question"].strip():
            raise ValueError("question text")
    return fixture


def question_queries(question):
    """First four distinct non-stopword tokens, in question order; no answer input."""
    terms = re.findall(r"\w+", question.lower(), re.UNICODE)
    selected = list(dict.fromkeys(word for word in terms if word not in STOP_WORDS))
    return [word for word in selected if len(word.encode()) <= 1024][:4]


def validate_query_plan(plan, questions):
    """Bind an operator's frozen queries to question text, without answer inputs.

    A digest detects changed questions; it cannot prove when a human authored a
    plan. Keep the original plan and its creation record for that separate audit.
    """
    projection = [{"question_id": q["question_id"], "question": q["question"]} for q in questions]
    if (
        not isinstance(plan, dict)
        or plan.get("schema_version") != 1
        or plan.get("profile") != "bounded_operator_plan"
        or plan.get("question_projection_sha256") != _sha(_encoded(projection))
        or not isinstance(plan.get("questions"), list)
        or len(plan["questions"]) != len(projection)
    ):
        raise ValueError("query plan schema or question digest")
    result = {}
    for question, planned in zip(projection, plan["questions"]):
        if not isinstance(planned, dict) or any(
            planned.get(key) != value for key, value in question.items()
        ):
            raise ValueError("query plan question mismatch")
        queries = planned.get("queries")
        if not isinstance(queries, list) or not 1 <= len(queries) <= 4:
            raise ValueError("query plan requires one to four queries")
        for query in queries:
            if (
                not isinstance(query, str)
                or not query.strip()
                or len(query.encode()) > 1024
                or not 1 <= len(re.findall(r"\w+", query, re.UNICODE)) <= 16
            ):
                raise ValueError("query plan query bounds")
        result[question["question_id"]] = list(queries)
    return result


def _public_fixture(directory):
    texts = [
        "Quasar storage initial proposal: persist directly in a local database.\n",
        "Quasar storage correction: the API owns persistence; direct writes are superseded.\n",
        "Quasar restoration preserves exact UTF-8: žluťoučký 🙂\n\tspaces stay.\n",
    ]
    raw = "".join(texts).encode()
    path = directory / "public-synthetic-source.txt"
    _private_write(path, raw)
    digest, spans, offset, line = _sha(raw), [], 0, 1
    for index, text in enumerate(texts):
        encoded = text.encode()
        spans.append(
            dict(
                evidence_id=f"public-{index}",
                source_id="public",
                source_path=str(path),
                source_sha256=digest,
                span_sha256=_sha(encoded),
                byte_start_0based=offset,
                byte_end_0based_exclusive=offset + len(encoded),
                line_start_1based=line,
                line_end_1based_inclusive=line + len(text.splitlines()) - 1,
                quotation=text,
            )
        )
        offset += len(encoded)
        line += len(text.splitlines())
    return dict(
        schema_version=1,
        sources=[dict(source_id="public", path=str(path), sha256=digest)],
        evidence_spans=spans,
        questions=[
            dict(
                question_id="public-correction",
                question="What changed in Quasar storage?",
                evidence_ids=["public-0", "public-1"],
                expected_evidence_relationships=["public-1 supersedes public-0"],
            ),
            dict(
                question_id="public-exact",
                question="What does Quasar restoration preserve?",
                evidence_ids=["public-2"],
                expected_evidence_relationships=[],
            ),
        ],
    )


class _Meter:
    def __init__(self):
        self.maximum = 0

    def observe(self, response):
        size = len(_encoded(response))
        self.maximum = max(self.maximum, size)
        if size > BUDGET:
            raise RuntimeError("core response exceeded 8 KiB")
        if response.get("status") != "ok":
            raise RuntimeError("core operation failed: " + str(response.get("status")))
        return size


class _RecordingStore(MemoryStore):
    """Observe real capture receipts solely for the independent integrity audit."""

    def __init__(self, directory):
        super().__init__(directory)
        self.receipts = {}

    def remember(self, request_id, text, provenance=None, *, namespace="operator"):
        receipt = super().remember(request_id, text, provenance, namespace=namespace)
        if receipt["status"] == "ok":
            self.receipts[request_id] = (receipt["ids"], dict(provenance or {}))
        return receipt


def _record(text, label):
    return {
        "type": "response_item",
        "_evaluation": label,
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def _capture(store, path, directory, workspace, meter):
    queued = queue_source(store, path, allowed_root=directory, format="codex", workspace=workspace)
    meter.observe(queued)
    for _ in range(64):
        result = capture_one(store, queued["source_key"])
        meter.observe(result)
        if not result.get("pending_bytes") and result.get("text_coverage") != "pending":
            return queued["source_key"]
    raise RuntimeError("evaluation capture slice bound exhausted")


def _audit_originals(store, spans, receipts, records, source_key, meter):
    by_evidence = {span["evidence_id"]: [] for span in spans}
    for ids, provenance in receipts.values():
        if provenance.get("source") == source_key:
            eid = records[provenance["record_start"]]
            for index, identity in enumerate(ids):
                by_evidence[eid].append((provenance["block_start"], index, identity))
    indexed, lengths, evidence_ids = {}, {}, {}
    for span in spans:
        eid, restored = span["evidence_id"], []
        indexed[eid] = []
        for _, _, identity in sorted(by_evidence[eid]):
            indexed[eid].append(identity)
            evidence_ids[identity] = eid
            offset, expected_hash, parts = 0, None, []
            while True:
                page = store.page(identity, offset=offset, limit=256, expected_hash=expected_hash)
                meter.observe(page)
                expected_hash = page["text_hash"]
                parts.append(page["text"])
                if page["complete"]:
                    break
                if page["next_offset"] <= offset:
                    raise RuntimeError("integrity page made no progress")
                offset = page["next_offset"]
            text = "".join(parts)
            if _sha(text.encode()) != expected_hash:
                raise RuntimeError("stored chunk hash mismatch")
            lengths[identity] = len(text)
            restored.append(text)
        if "".join(restored).encode() != span["quotation"].encode():
            raise RuntimeError("captured original bytes differ")
    return indexed, lengths, evidence_ids


def _tensions(question):
    declared = set(question.get("contradicting_evidence_ids", []))
    for relation in question.get("expected_evidence_relationships", []):
        if re.search(r"conflict|contradict|counterevidence|supersed", relation, re.I):
            declared.update(eid for eid in question["evidence_ids"] if eid in relation)
    return sorted(declared & set(question["evidence_ids"]))


def _evaluate_question(store, question, indexed, lengths, evidence_ids, meter):
    started, returned, excerpts = time.perf_counter(), 0, 0
    found, delivered, hashes, queries = [], {}, {}, []
    planned = question_queries(question["question"])
    for query in planned:
        # One candidate is <=4096 bytes (1024-byte provenance + 256-char preview).
        # Reserve that bound before calling, rather than discarding returned data.
        if BUDGET - returned < 4096 or excerpts >= 8:
            break
        result = store.recall(query, limit=1)
        returned += meter.observe(result)
        queries.append(query)
        for candidate in result["sources"]:
            excerpts += 1
            identity = candidate["id"]
            if identity not in found:
                found.append(identity)
            delivered[identity] = candidate["text"]
            hashes[identity] = candidate["provenance"]["text_hash"]
    # Page only candidates actually returned by question-derived lexical recall.
    # Expected evidence IDs never select or rerank candidates.
    for identity in found:
        while len(delivered[identity]) < lengths.get(identity, len(delivered[identity])):
            remaining = BUDGET - returned
            page_limit = min(256, (remaining - 1536) // 6)
            if page_limit < 1:
                break
            page = store.page(
                identity,
                offset=len(delivered[identity]),
                limit=page_limit,
                expected_hash=hashes[identity],
            )
            returned += meter.observe(page)
            delivered[identity] += page["text"]
            if page["complete"]:
                break
    if returned > BUDGET:
        raise RuntimeError("question response aggregate exceeded 8 KiB")
    expected = question["evidence_ids"]
    complete = [
        eid
        for eid in expected
        if indexed[eid]
        and all(
            identity in delivered and len(delivered[identity]) == lengths[identity]
            for identity in indexed[eid]
        )
    ]
    candidate_hits = [
        eid for eid in expected if any(identity in found for identity in indexed[eid])
    ]
    tension = _tensions(question)
    return dict(
        question_id=question["question_id"],
        question=question["question"],
        queries=queries,
        planned_queries=planned,
        returned_bytes=returned,
        returned_candidate_excerpts=excerpts,
        budget_bytes=BUDGET,
        candidate_evidence_ids=candidate_hits,
        complete_evidence_ids=complete,
        expected_evidence_count=len(expected),
        candidate_evidence_recall_at_budget=len(candidate_hits) / len(expected),
        complete_evidence_recall_at_budget=len(complete) / len(expected),
        missing_complete_evidence_ids=[eid for eid in expected if eid not in complete],
        returned_nonanswer_evidence_ids=sorted(
            {evidence_ids[i] for i in found if i in evidence_ids} - set(expected)
        ),
        declared_tension_evidence_ids=tension,
        missing_tension_evidence_ids=[eid for eid in tension if eid not in complete],
        declared_relationships=question.get("expected_evidence_relationships", []),
        contradictions_resolved=False,
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )


def _retrieve_planned(store, planned, meter, budget, recall_limit):
    """Retrieve and page in returned rank order, without access to answer labels."""
    returned, excerpts, calls, candidates, delivered = 0, 0, [], {}, {}
    issued = []
    for query in planned:
        # Reserve the full response bound before dispatch. Nothing already
        # returned is discarded to make the measured aggregate look smaller.
        if budget - returned < BUDGET:
            break
        response = store.recall(query, limit=recall_limit)
        size = meter.observe(response)
        returned += size
        issued.append(query)
        calls.append(dict(kind="recall", query=query, limit=recall_limit, response_bytes=size))
        for source in response["sources"]:
            excerpts += 1
            identity = source["id"]
            if identity not in candidates:
                candidates[identity] = source
                delivered[identity] = source["text"]
    page_limited = False
    # The published chunk offsets give lengths. Audit lengths and expected IDs
    # are deliberately unavailable here, including for page selection/order.
    for identity, source in candidates.items():
        provenance = source["provenance"]
        length = provenance["chunk_end"] - provenance["chunk_start"]
        while len(delivered[identity]) < length:
            # A code point costs at most six bytes in compact UTF-8 JSON (an
            # escaped control). Reserve 1536 for the <=1024-byte provenance,
            # <=128-byte ID, field names, hash, offsets and response metadata.
            limit = min(2048, (min(BUDGET, budget - returned) - 1536) // 6)
            if limit < 1:
                page_limited = True
                break
            offset = len(delivered[identity])
            response = store.page(
                identity, offset=offset, limit=limit, expected_hash=provenance["text_hash"]
            )
            size = meter.observe(response)
            returned += size
            calls.append(
                dict(
                    kind="page", source_id=identity, offset=offset, limit=limit, response_bytes=size
                )
            )
            if response["next_offset"] <= offset:
                raise RuntimeError("evaluation page made no progress")
            delivered[identity] += response["text"]
            if response["complete"]:
                break
        if (
            len(delivered[identity]) == length
            and _sha(delivered[identity].encode()) != provenance["text_hash"]
        ):
            raise RuntimeError("evaluation delivered chunk hash mismatch")
    if returned > budget:
        raise RuntimeError("operator question response aggregate exceeded budget")
    return dict(
        candidates=candidates,
        delivered=delivered,
        calls=calls,
        queries=issued,
        returned_bytes=returned,
        returned_candidate_excerpts=excerpts,
        budget_exhausted=page_limited or len(issued) != len(planned),
    )


def _evaluate_planned_question(
    store, question, planned, indexed, lengths, evidence_ids, meter, budget, recall_limit
):
    started = time.perf_counter()
    observed = _retrieve_planned(store, planned, meter, budget, recall_limit)
    candidates, delivered = observed.pop("candidates"), observed.pop("delivered")
    expected = question["evidence_ids"]
    hits = [eid for eid in expected if any(i in candidates for i in indexed[eid])]
    complete = [
        eid
        for eid in expected
        if indexed[eid]
        and all(i in delivered and len(delivered[i]) == lengths[i] for i in indexed[eid])
    ]
    tension = _tensions(question)
    calls = observed["calls"]
    return dict(
        **observed,
        question_id=question["question_id"],
        question=question["question"],
        planned_queries=planned,
        unissued_queries=planned[len(observed["queries"]) :],
        budget_bytes=budget,
        remaining_budget_bytes=budget - observed["returned_bytes"],
        recall_calls=sum(c["kind"] == "recall" for c in calls),
        page_calls=sum(c["kind"] == "page" for c in calls),
        total_calls=len(calls),
        max_response_bytes=max((c["response_bytes"] for c in calls), default=0),
        unique_candidates=len(candidates),
        duplicate_candidate_excerpts=observed["returned_candidate_excerpts"] - len(candidates),
        incomplete_candidate_count=sum(
            len(delivered[i]) < s["provenance"]["chunk_end"] - s["provenance"]["chunk_start"]
            for i, s in candidates.items()
        ),
        identifier_evidence_ids=hits,
        candidate_evidence_ids=hits,
        complete_evidence_ids=complete,
        expected_evidence_count=len(expected),
        identifier_evidence_recall_at_budget=len(hits) / len(expected),
        candidate_evidence_recall_at_budget=len(hits) / len(expected),
        complete_evidence_recall_at_budget=len(complete) / len(expected),
        missing_identifier_evidence_ids=[eid for eid in expected if eid not in hits],
        missing_complete_evidence_ids=[eid for eid in expected if eid not in complete],
        identified_but_incomplete_evidence_ids=[eid for eid in hits if eid not in complete],
        returned_nonanswer_evidence_ids=sorted(
            {evidence_ids[i] for i in candidates if i in evidence_ids} - set(expected)
        ),
        declared_tension_evidence_ids=tension,
        missing_tension_evidence_ids=[eid for eid in tension if eid not in complete],
        declared_relationships=question.get("expected_evidence_relationships", []),
        contradictions_resolved=False,
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )


def _profile_summary(rows):
    total = sum(row["expected_evidence_count"] for row in rows)
    return dict(
        expected_evidence_instances=total,
        identifier_evidence_instances=sum(len(row["identifier_evidence_ids"]) for row in rows),
        complete_evidence_instances=sum(len(row["complete_evidence_ids"]) for row in rows),
        identifier_evidence_recall=sum(len(row["identifier_evidence_ids"]) for row in rows) / total,
        complete_evidence_recall=sum(len(row["complete_evidence_ids"]) for row in rows) / total,
        fully_delivered_questions=sum(not row["missing_complete_evidence_ids"] for row in rows),
        returned_bytes=sum(row["returned_bytes"] for row in rows),
        recall_calls=sum(row["recall_calls"] for row in rows),
        page_calls=sum(row["page_calls"] for row in rows),
        max_response_bytes=max(row["max_response_bytes"] for row in rows),
        budget_exhausted_questions=sum(row["budget_exhausted"] for row in rows),
    )


def evaluate(
    fixture=None, *, work_dir, query_plan=None, question_budget=QUESTION_BUDGET, recall_limit=8
):
    """Run real storage APIs in a caller-owned private temporary evaluation directory."""
    _privacy_supported()
    public = fixture is None
    if type(question_budget) is not int or not BUDGET <= question_budget <= QUESTION_BUDGET:
        raise ValueError("operator question budget must be 8192..32768")
    if type(recall_limit) is not int or not 1 <= recall_limit <= 8:
        raise ValueError("operator recall limit must be 1..8")
    if not public:
        verify_fixture(fixture)  # Reject stale or forged evidence before any replay writes.
        if query_plan is not None:
            planned = validate_query_plan(query_plan, fixture["questions"])
    directory = Path(work_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    if public:
        fixture = verify_fixture(_public_fixture(directory))
        if query_plan is not None:
            planned = validate_query_plan(query_plan, fixture["questions"])
    meter, records, raw = _Meter(), {}, bytearray()
    for span in fixture["evidence_spans"]:
        records[len(raw)] = span["evidence_id"]
        raw.extend(
            _encoded(
                _record(
                    span["quotation"],
                    {
                        "origin": "selected_repository_excerpt_replay"
                        if not public
                        else "public_synthetic_replay",
                        "evidence_id": span["evidence_id"],
                        "source_sha256": span["source_sha256"],
                        "span_sha256": span["span_sha256"],
                    },
                )
            )
            + b"\n"
        )
    replay = directory / "evaluation-replay.jsonl"
    _private_write(replay, raw)
    store = _RecordingStore(directory / "memory")
    workspace = str(directory / "selected-workspace")
    started = time.perf_counter()
    key = _capture(store, replay, directory, workspace, meter)
    capture_ms = round((time.perf_counter() - started) * 1000, 3)
    observed = coverage(store)
    meter.observe(observed)
    # Open a new object against persisted SQLite: an in-process storage restart,
    # not evidence of a new host process or supervised runtime/hook behavior.
    restarted = MemoryStore(store.directory)
    indexed, lengths, evidence_ids = _audit_originals(
        restarted, fixture["evidence_spans"], store.receipts, records, key, meter
    )
    decoy = directory / "unrelated-synthetic-control.jsonl"
    _private_write(
        decoy, _encoded(_record("offscope-only-synthetic-control", "scope_control")) + b"\n"
    )
    _capture(store, decoy, directory, str(directory / "other-workspace"), meter)
    ref = next(identity for identities in indexed.values() for identity in identities)
    meter.observe(
        update_context(
            restarted,
            workspace,
            namespace="evaluation",
            request_id="active",
            expected_revision=0,
            status="active",
            source_ids=[ref],
        )
    )
    active = restore_context(MemoryStore(store.directory), workspace, namespace="evaluation")
    meter.observe(active)
    meter.observe(
        update_context(
            restarted,
            workspace,
            namespace="evaluation",
            request_id="complete",
            expected_revision=1,
            status="completed",
            source_ids=[ref],
        )
    )
    completed = restore_context(MemoryStore(store.directory), workspace, namespace="evaluation")
    context_bytes = meter.observe(completed)
    other = restore_context(restarted, str(directory / "other-workspace"), namespace="evaluation")
    meter.observe(other)
    rows = [
        _evaluate_question(restarted, question, indexed, lengths, evidence_ids, meter)
        for question in fixture["questions"]
    ]
    profiles = {}
    if query_plan is not None:
        planned_rows = [
            _evaluate_planned_question(
                restarted,
                question,
                planned[question["question_id"]],
                indexed,
                lengths,
                evidence_ids,
                meter,
                question_budget,
                recall_limit,
            )
            for question in fixture["questions"]
        ]
        profiles["bounded_operator_plan"] = dict(
            query_policy="frozen operator question-derived queries; no oracle reranking; native rank order",
            query_plan_sha256=_sha(_encoded(query_plan)),
            question_projection_sha256=query_plan["question_projection_sha256"],
            plan_derivation=query_plan.get("derivation", "not supplied"),
            plan_frozen_at_utc=query_plan.get("frozen_at_utc"),
            plan_authorship_independently_verified=False,
            budget_bytes=question_budget,
            per_response_budget_bytes=BUDGET,
            max_queries=4,
            recall_limit=recall_limit,
            page_limit_codepoints=2048,
            serialization="complete core response; compact ensure_ascii=False UTF-8 JSON; no transport envelope",
            paging_policy="first-seen candidates in native retrieval order; exact hash-bound pages",
            budget_policy="reserve 8192 before recall; page size reserves metadata and worst-case JSON escaping",
            limitation="Deterministic question-derived retrieval is not understanding; an active assistant may need adaptive queries. Lower-ranked candidates and budget-limited pages can remain missing.",
            questions=planned_rows,
            summary=_profile_summary(planned_rows),
        )
    return dict(
        schema_version=1,
        dataset_kind="public_synthetic_replay" if public else "private_selected_excerpt_replay",
        historical_capture_demonstrated=False,
        runtime="direct_core_api_not_supervised_runtime",
        query_policy="first_four_unique_non_stopword_tokens_from_question_only; literal recall limit=1; no oracle reranking",
        budget_scope="all recall and exact-page response bytes combined per question; each core response <=8192",
        recall_scope="isolated evaluation store; MemoryStore.recall itself has no workspace filter",
        source_count=len(fixture["sources"]),
        span_count=len(fixture["evidence_spans"]),
        question_count=len(rows),
        source_hashes_verified=True,
        span_hashes_verified=True,
        integrity=dict(
            all_original_bytes_preserved=True,
            original_utf8_bytes=sum(
                len(s["quotation"].encode()) for s in fixture["evidence_spans"]
            ),
            audit="hash-checked exact pages after reopening storage; excluded from question recall scores",
        ),
        replay_provenance=[
            {
                k: span[k]
                for k in (
                    "evidence_id",
                    "source_id",
                    "source_sha256",
                    "span_sha256",
                    "byte_start_0based",
                    "byte_end_0based_exclusive",
                )
            }
            for span in fixture["evidence_spans"]
        ],
        capture=observed,
        capture_latency_ms=capture_ms,
        restart=dict(
            kind="new_MemoryStore_instance_same_process",
            active_state_restored=active["work_state"]["status"] == "active",
            completed_state_restored=completed["work_state"]["status"] == "completed",
            authority=completed["authority"],
            work_state_attribution=completed["work_state"]["attribution"],
            unrelated_workspace_excluded=all(s["source_key"] == key for s in completed["sources"])
            and other["work_state"] is None,
            context_bytes=context_bytes,
            context_source_count=len(completed["sources"]),
            context_evidence_ids=[evidence_ids[s["source_id"]] for s in completed["sources"]],
        ),
        questions=rows,
        profiles=profiles,
        max_response_bytes=meter.maximum,
        semantics=dict(
            understanding_verified=False,
            contradictions_resolved=False,
            limitation="Lexical evidence delivery does not establish understanding, truth, or semantic conflict resolution.",
            coverage="Selected evidence only; no complete project/history or real historical capture claim.",
            resources="No RSS or supervised deadline claim; measure actual runtime separately.",
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="optional private hashed evidence fixture")
    parser.add_argument("--output", type=Path, help="new report file, created mode 0600")
    parser.add_argument(
        "--query-plan", type=Path, help="frozen question-derived operator query plan"
    )
    parser.add_argument(
        "--question-budget",
        type=int,
        default=QUESTION_BUDGET,
        help="operator profile aggregate response bytes, 8192..32768",
    )
    parser.add_argument(
        "--recall-limit",
        type=int,
        default=8,
        help="operator profile native candidates per query, 1..8",
    )
    args = parser.parse_args(argv)
    private_input = args.fixture or args.query_plan
    if private_input and not args.output:
        parser.error(
            "private fixture or query plan requires --output; private reports are not printed"
        )
    if private_input and args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("private report must be outside this repository")
    fixture = (
        None if args.fixture is None else json.loads(_read_bounded(args.fixture, MAX_FIXTURE_BYTES))
    )
    plan_raw = (
        None if args.query_plan is None else _read_bounded(args.query_plan, MAX_FIXTURE_BYTES)
    )
    query_plan = None if plan_raw is None else json.loads(plan_raw)
    with tempfile.TemporaryDirectory(prefix="castle-evidence-evaluation-") as directory:
        report = evaluate(
            fixture,
            work_dir=Path(directory).resolve(),
            query_plan=query_plan,
            question_budget=args.question_budget,
            recall_limit=args.recall_limit,
        )
    if args.query_plan:
        report["profiles"]["bounded_operator_plan"]["query_plan_file_sha256"] = _sha(plan_raw)
    if args.output:
        _private_write(
            args.output, json.dumps(report, ensure_ascii=False, indent=2).encode() + b"\n"
        )
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

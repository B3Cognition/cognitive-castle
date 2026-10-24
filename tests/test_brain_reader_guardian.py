"""Deterministic process-table churn; run via scripts/safe_brain_tests.py."""

from types import SimpleNamespace

import psutil
import pytest

from cognitive_castle import brain_reader_guardian as guardian


def _process_table(monkeypatch, pids, process):
    monkeypatch.setattr(psutil, "pids", lambda: list(pids))
    monkeypatch.setattr(psutil, "Process", process)

    # Model a cold process_iter without its global cache hiding identity reads.
    def process_iter():
        for pid in psutil.pids():
            try:
                yield psutil.Process(pid)
            except psutil.NoSuchProcess:
                pass

    monkeypatch.setattr(psutil, "process_iter", process_iter)


def test_group_rss_constructs_identities_only_for_owned_members(monkeypatch):
    created = []
    groups = {0: 777, 11: 111, 42: 777, 57: 777}

    def process(pid):
        created.append(pid)
        return SimpleNamespace(pid=pid, memory_info=lambda: SimpleNamespace(rss=pid * 1024))

    _process_table(monkeypatch, groups, process)
    monkeypatch.setattr(guardian.os, "getpgid", groups.__getitem__, raising=False)

    assert guardian._group_rss(777) == 99 * 1024
    assert created == [42, 57]


def test_reused_pid_outside_group_is_excluded_after_identity_capture(monkeypatch):
    group = 777

    def process(pid):
        nonlocal group
        # The first process exits and its PID is reused before identity capture.
        group = 888
        return SimpleNamespace(pid=pid)

    _process_table(monkeypatch, [42], process)
    monkeypatch.setattr(guardian.os, "getpgid", lambda pid: group, raising=False)

    assert list(guardian._owned_group_members(777)) == []


@pytest.mark.parametrize("stage", ["prefilter", "identity", "recheck"])
def test_disappearing_group_member_is_skipped(monkeypatch, stage):
    reads = 0

    def getpgid(pid):
        nonlocal reads
        reads += 1
        if (stage == "prefilter" and reads == 1) or (stage == "recheck" and reads == 2):
            raise ProcessLookupError(pid)
        return 777

    def process(pid):
        if stage == "identity":
            raise psutil.NoSuchProcess(pid)
        return SimpleNamespace(pid=pid)

    _process_table(monkeypatch, [42], process)
    monkeypatch.setattr(guardian.os, "getpgid", getpgid, raising=False)

    assert list(guardian._owned_group_members(777)) == []


@pytest.mark.parametrize("stage", ["prefilter", "identity", "recheck"])
def test_inaccessible_group_member_fails_closed(monkeypatch, stage):
    reads = 0

    def getpgid(pid):
        nonlocal reads
        reads += 1
        if (stage == "prefilter" and reads == 1) or (stage == "recheck" and reads == 2):
            raise PermissionError(pid)
        return 777

    def process(pid):
        if stage == "identity":
            raise psutil.AccessDenied(pid)
        return SimpleNamespace(pid=pid)

    _process_table(monkeypatch, [42], process)
    monkeypatch.setattr(guardian.os, "getpgid", getpgid, raising=False)

    with pytest.raises((PermissionError, psutil.AccessDenied)):
        list(guardian._owned_group_members(777))

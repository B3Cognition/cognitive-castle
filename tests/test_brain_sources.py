"""Only synthetic storage; run via scripts/safe_brain_tests.py."""

import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import sys
import time

import pytest


macos_native = pytest.mark.skipif(
    sys.platform != "darwin", reason="native supervision is validated only on macOS"
)


def _sources():
    return importlib.import_module("cognitive_castle.brain_sources")


def test_public_capabilities_import_without_native_or_models():
    sources = _sources()
    result = sources.capabilities()
    assert result["model_free"] is True
    assert result["limits"]["native_rss_bytes"] == 512 * 1024**2
    assert result["limits"]["native_deadline_seconds"] == 10
    assert result["legacy_variable_width"] == "unavailable"


@pytest.mark.parametrize("query,limit", [("", 8), ("x" * 1025, 8), ("ok", 9), ("ok", True)])
def test_invalid_recall_is_rejected_before_worker(query, limit, tmp_path, monkeypatch):
    sources = _sources()
    monkeypatch.setattr(sources, "_run", lambda *a: pytest.fail("worker started"))
    with pytest.raises(ValueError):
        sources.recall(str(tmp_path), query, limit=limit)


def test_missing_palace_never_created(tmp_path):
    absent = tmp_path / "missing"
    result = _sources().recall(str(absent), "hello")
    assert result["status"] == "unavailable"
    assert not absent.exists()


def test_invalid_ids_rejected_before_reader(tmp_path):
    with pytest.raises(ValueError):
        _sources().read_sources(str(tmp_path), ["id"] * 9)


def _table(tmp_path, *, bounded=True, fts=False, text="A narrow lexical memory.", metadata=None):
    import lancedb
    import pyarrow as pa

    dbpath = tmp_path / "lancedb"
    dbpath.mkdir()
    db = lancedb.connect(str(dbpath))
    md = json.dumps(metadata or {}, ensure_ascii=False).encode()
    raw = text.encode()
    if bounded:
        schema = pa.schema(
            [
                pa.field("id", pa.int64()),
                pa.field("vector", pa.list_(pa.float32(), 2)),
                pa.field("search_text", pa.string()),
                pa.field("text", pa.binary(1024)),
                pa.field("metadata_json", pa.binary(1024)),
                pa.field("text_bytes", pa.int32()),
                pa.field("metadata_bytes", pa.int32()),
                pa.field("text_sha256", pa.binary(32)),
            ],
            metadata={b"castle_brain_format": b"fixed-v1"},
        )
        row = dict(
            id=1,
            vector=[0.1, 0.2],
            search_text=text,
            text=raw.ljust(1024, b"\0"),
            metadata_json=md.ljust(1024, b"\0"),
            text_bytes=len(raw),
            metadata_bytes=len(md),
            text_sha256=hashlib.sha256(raw).digest(),
        )
        table = db.create_table("castle_drawers", pa.Table.from_pylist([row], schema=schema))
    else:
        table = db.create_table(
            "castle_drawers",
            [{"id": "legacy", "text": text, "metadata_json": md.decode(), "vector": [0.1, 0.2]}],
        )
    if fts:
        table.create_fts_index("search_text" if bounded else "text", use_tantivy=False)
    return table


def _fingerprint(path):
    return {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in path.rglob("*")
        if p.is_file()
    }


@macos_native
def test_legacy_native_table_rejected_without_archive_mutation(tmp_path):
    _table(tmp_path, bounded=False)
    before = _fingerprint(tmp_path)
    result = _sources().read_sources(str(tmp_path), ["legacy"])
    assert result == {"status": "unavailable", "reason": "legacy_size_unprovable"}
    assert _fingerprint(tmp_path) == before


@macos_native
def test_missing_fts_explicitly_unavailable_and_no_index_created(tmp_path):
    _table(tmp_path)
    before = _fingerprint(tmp_path)
    result = _sources().recall(str(tmp_path), "lexical")
    assert result == {"status": "unavailable", "reason": "fts_index_missing"}
    assert _fingerprint(tmp_path) == before


@macos_native
def test_native_bounded_read_preserves_exact_bytes_and_snapshot(tmp_path):
    original = "A narrow memory.\nŽluťoučký 👋\0"
    table = _table(tmp_path, text=original, metadata={"source_file": "fixture.md"})
    version = table.version
    before = _fingerprint(tmp_path)
    result = _sources().read_sources(str(tmp_path), ["1"])
    assert result["status"] == "ok", result
    assert result["sources"][0]["text"] == original
    provenance = result["sources"][0]["provenance"]
    assert provenance["table_version"] == version
    assert provenance["local_only"] is True
    assert provenance["origin"] == "archive"
    assert provenance["text_sha256"] == hashlib.sha256(original.encode()).hexdigest()
    assert _fingerprint(tmp_path) == before


@macos_native
def test_native_fts_recall_uses_existing_index(tmp_path):
    _table(tmp_path, fts=True)
    result = _sources().recall(str(tmp_path), "lexical")
    assert result["status"] == "ok", result
    assert [s["id"] for s in result["sources"]] == ["1"]
    assert result["selection"]["exhaustive"] is False


@macos_native
def test_unknown_source_is_not_substituted(tmp_path):
    _table(tmp_path)
    assert _sources().read_sources(str(tmp_path), ["2"])["reason"] == "source_unavailable"


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation requires privileges")
def test_symbolic_archive_path_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    assert _sources().read_sources(str(link), ["1"])["reason"] == "unsafe_source_path"


@macos_native
def test_supervision_for_simple_bounded_worker():
    sources = _sources()
    fd = sources._admission()
    try:
        result = sources._supervise(
            {},
            fd,
            worker_command=[sys.executable, "-I", "-c", 'print(\'{"status":"ok","sources":[]}\')'],
        )
        assert result == {"status": "ok", "sources": []}
    finally:
        os.close(fd)


@macos_native
def test_admission_is_per_user_not_per_tmpdir(tmp_path, monkeypatch):
    sources = _sources()
    fd = sources._admission()
    try:
        monkeypatch.setattr(sources.tempfile, "gettempdir", lambda: str(tmp_path))
        with pytest.raises(BlockingIOError):
            second = sources._admission()
            os.close(second)
    finally:
        os.close(fd)


def _wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "bounded process transition did not happen"


def _alive(pid):
    import psutil

    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


@macos_native
def test_guardian_death_kills_reader_before_admission_released(tmp_path):
    import concurrent.futures
    import psutil

    sources = _sources()
    pidfile = tmp_path / "reader.pid"
    command = [
        sys.executable,
        "-I",
        "-c",
        f'import os,time;open({str(pidfile)!r},"w").write(str(os.getpid()));time.sleep(30)',
    ]
    fd = sources._admission()
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(sources._supervise, {}, fd, worker_command=command)
            _wait_for(pidfile.exists)
            worker_pid = int(pidfile.read_text())
            guardian_pid = psutil.Process(worker_pid).ppid()
            with pytest.raises(BlockingIOError):
                sources._admission()
            os.kill(guardian_pid, signal.SIGKILL)
            assert future.result(timeout=3)["status"] == "unavailable"
            _wait_for(lambda: not _alive(worker_pid))
    finally:
        os.close(fd)
    replacement = sources._admission()
    os.close(replacement)


@macos_native
def test_host_death_kills_reader_and_releases_inherited_lock(tmp_path):
    import subprocess

    sources = _sources()
    pidfile = tmp_path / "reader.pid"
    snapshot_file = tmp_path / "snapshot-path"
    package_root = str(Path(__file__).resolve().parents[1])
    command = [
        sys.executable,
        "-I",
        "-c",
        (
            "import os,time,json,sys,pathlib;r=json.load(sys.stdin);"
            f'open({str(snapshot_file)!r},"w").write(r["snapshot_dir"]);'
            '(pathlib.Path(r["snapshot_dir"])/"secret").write_text("private");'
            f'open({str(pidfile)!r},"w").write(str(os.getpid()));time.sleep(30)'
        ),
    ]
    script = (
        f"import sys;sys.path.insert(0,{package_root!r});"
        "from cognitive_castle import brain_sources as s;"
        f"fd=s._admission();s._supervise({{}},fd,worker_command={command!r})"
    )
    host = subprocess.Popen([sys.executable, "-I", "-c", script])
    try:
        _wait_for(pidfile.exists)
        worker_pid = int(pidfile.read_text())
        with pytest.raises(BlockingIOError):
            sources._admission()
        host.kill()
        host.wait(timeout=2)
        _wait_for(lambda: not _alive(worker_pid))
        _wait_for(lambda: not Path(snapshot_file.read_text()).exists())
        replacement = sources._admission()
        os.close(replacement)
    finally:
        if host.poll() is None:
            host.kill()
            host.wait(timeout=2)


@macos_native
def test_reader_deadline_stops_owned_descendants(tmp_path):
    sources = _sources()
    pidfile = tmp_path / "grandchild.pid"
    command = [
        sys.executable,
        "-I",
        "-c",
        (
            f'import os,time;pid=os.fork();open({str(pidfile)!r},"w").write(str(os.getpid())) '
            "if pid==0 else None;time.sleep(30)"
        ),
    ]
    fd = sources._admission()
    try:
        started = time.monotonic()
        result = sources._supervise({}, fd, worker_command=command, deadline=0.4)
        assert result["status"] == "unavailable"
        assert time.monotonic() - started < 2
        _wait_for(lambda: pidfile.exists() and not _alive(int(pidfile.read_text())))
    finally:
        os.close(fd)


class _FakeTable:
    """Only native storage boundary is fake; admission/extraction code is real."""

    def __init__(self, candidates, *, change_version=False):
        import pyarrow as pa

        self.schema = pa.schema(
            [
                pa.field("id", pa.int64()),
                pa.field("text", pa.binary(65536)),
                pa.field("metadata_json", pa.binary(8192)),
                pa.field("text_bytes", pa.int32()),
                pa.field("metadata_bytes", pa.int32()),
                pa.field("text_sha256", pa.binary(32)),
            ],
            metadata={b"castle_brain_format": b"fixed-v1"},
        )
        self.version = 7
        self.candidates = candidates
        self.change_version = change_version
        self.selected = []

    def checkout(self, version):
        assert version == 7

    def search(self):
        return _FakeQuery(self)


class _FakeQuery:
    def __init__(self, table):
        self.table = table

    def where(self, value):
        return self

    def limit(self, value):
        return self

    def select(self, columns):
        self.columns = columns
        return self

    def to_list(self):
        self.table.selected.append(self.columns)
        assert "vector" not in self.columns
        assert "text" not in self.columns, "unadmitted payload was materialized"
        if self.table.change_version:
            self.table.version += 1
        return self.table.candidates


@pytest.mark.parametrize(
    "sizes,reason",
    [
        ([(65537, 2)], "source_size_invalid"),
        ([(1, 8193)], "source_size_invalid"),
        ([(40000, 2), (40000, 2)], "text_byte_limit"),
        ([(1, 5000), (1, 5000)], "provenance_byte_limit"),
    ],
)
def test_size_admission_precedes_native_payload_projection(sizes, reason):
    from cognitive_castle.brain_reader import Unavailable, _read_table

    rows = [
        dict(id=index + 1, text_bytes=text, metadata_bytes=metadata, text_sha256=b"0" * 32)
        for index, (text, metadata) in enumerate(sizes)
    ]
    table = _FakeTable(rows)
    with pytest.raises(Unavailable, match=reason):
        _read_table(table, {"operation": "read", "ids": [str(row["id"]) for row in rows]}, "hash")
    assert len(table.selected) == 1


def test_version_change_aborts_before_payload_projection():
    from cognitive_castle.brain_reader import Unavailable, _read_table

    table = _FakeTable(
        [dict(id=1, text_bytes=1, metadata_bytes=2, text_sha256=b"0" * 32)], change_version=True
    )
    with pytest.raises(Unavailable, match="source_changed"):
        _read_table(table, {"operation": "read", "ids": ["1"]}, "hash")
    assert len(table.selected) == 1


@macos_native
def test_memory_tripwire_kills_owned_reader(tmp_path, monkeypatch):
    sources = _sources()
    monkeypatch.setattr(sources, "RSS_LIMIT", 48 * 1024**2)
    pidfile = tmp_path / "memory-reader.pid"
    command = [
        sys.executable,
        "-I",
        "-c",
        (
            f'import os,time;open({str(pidfile)!r},"w").write(str(os.getpid()));'
            "a=bytearray(64*1024**2);time.sleep(30)"
        ),
    ]
    fd = sources._admission()
    try:
        result = sources._supervise({}, fd, worker_command=command)
        assert result["status"] == "unavailable"
        if pidfile.exists():
            _wait_for(lambda: not _alive(int(pidfile.read_text())))
    finally:
        os.close(fd)


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_unsupported_platform_does_not_start_worker(tmp_path, monkeypatch, platform):
    sources = _sources()
    monkeypatch.setattr(sources.sys, "platform", platform)
    monkeypatch.setattr(sources, "_supervise", lambda *a, **k: pytest.fail("worker started"))
    assert sources.read_sources(str(tmp_path), ["1"]) == {
        "status": "unavailable",
        "reason": "platform_supervision_unavailable",
    }


@macos_native
def test_private_snapshot_cleanup_after_reader_success():
    sources = _sources()
    command = [
        sys.executable,
        "-I",
        "-c",
        'import json,sys,pathlib;r=json.load(sys.stdin);p=pathlib.Path(r["snapshot_dir"]);'
        '(p/"temporary-source").write_text("private");'
        'print(json.dumps({"status":"ok","path":str(p)}))',
    ]
    fd = sources._admission()
    try:
        result = sources._supervise({}, fd, worker_command=command)
        assert result["status"] == "ok", result
        assert not Path(result["path"]).exists()
    finally:
        os.close(fd)


@macos_native
def test_partial_guardian_frame_has_first_byte_deadline():
    import subprocess

    sources = _sources()
    guardian = Path(sources.__file__).with_name("brain_reader_guardian.py")
    process = subprocess.Popen(
        [sys.executable, "-I", str(guardian)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        started = time.monotonic()
        process.stdin.write(b'{"request":')
        process.stdin.flush()
        process.wait(timeout=2)
        assert time.monotonic() - started < 2
        assert process.returncode != 0
    finally:
        process.stdin.close()
        process.stdout.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)


def test_system_pressure_prevents_reader_spawn(monkeypatch):
    sources = _sources()
    monkeypatch.setattr(sources, "_pressure_ok", lambda: False, raising=False)
    monkeypatch.setattr(
        sources.subprocess, "Popen", lambda *a, **k: pytest.fail("reader spawned under pressure")
    )
    assert sources._supervise({}, -1) == {
        "status": "unavailable",
        "reason": "system_pressure_unavailable",
    }


@macos_native
def test_system_pressure_stops_running_reader(tmp_path, monkeypatch):
    sources = _sources()
    checks = iter([True, False])
    monkeypatch.setattr(sources, "_pressure_ok", lambda: next(checks, False), raising=False)
    pidfile = tmp_path / "pressure-reader.pid"
    command = [
        sys.executable,
        "-I",
        "-c",
        f'import os,time;open({str(pidfile)!r},"w").write(str(os.getpid()));time.sleep(30)',
    ]
    fd = sources._admission()
    try:
        result = sources._supervise({}, fd, worker_command=command, deadline=1)
        assert result == {"status": "unavailable", "reason": "system_pressure_unavailable"}
        _wait_for(lambda: pidfile.exists() and not _alive(int(pidfile.read_text())))
    finally:
        os.close(fd)


@macos_native
def test_reparented_reader_descendant_remains_in_aggregate_rss(tmp_path, monkeypatch):
    sources = _sources()
    monkeypatch.setattr(sources, "RSS_LIMIT", 48 * 1024**2)
    pidfile = tmp_path / "orphan-reader.pid"
    script = (
        "import os,time\n"
        "if os.fork():\n"
        "    os._exit(0)\n"
        f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
        "time.sleep(0.25)\n"
        "allocation = bytearray(48 * 1024**2)\n"
        "time.sleep(30)\n"
    )
    fd = sources._admission()
    try:
        started = time.monotonic()
        result = sources._supervise(
            {}, fd, worker_command=[sys.executable, "-I", "-c", script], deadline=2.5
        )
        elapsed = time.monotonic() - started
        assert result["status"] == "unavailable"
        _wait_for(lambda: pidfile.exists() and not _alive(int(pidfile.read_text())))
        assert elapsed < 1.5, "orphan RSS escaped accounting until the time deadline"
    finally:
        os.close(fd)


def test_process_group_scan_does_not_treat_kernel_pid_zero_as_own_group(monkeypatch):
    from types import SimpleNamespace
    import psutil
    from cognitive_castle import brain_reader_guardian as guardian

    monkeypatch.setattr(psutil, "pids", lambda: [0, 42])
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(pid=pid))
    monkeypatch.setattr(guardian.os, "getpgid", lambda pid: 777, raising=False)
    assert [member.pid for member in guardian._owned_group_members(777)] == [42]

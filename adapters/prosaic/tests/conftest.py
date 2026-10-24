import sys

import pytest


@pytest.fixture
def worker(tmp_path):
    """A real private subprocess speaking the public wire protocol."""
    script = tmp_path / "worker.py"
    script.write_text("""import json, os, subprocess, sys, time
from pathlib import Path
mode = sys.argv[1]
marker = Path(sys.argv[2])
if mode == 'recover':
    mode = 'normal' if marker.exists() else 'hang_read'
marker.write_text(str(os.getpid()))
if mode == 'descendant':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])
    marker.with_suffix('.child').write_text(str(child.pid))
if mode == 'hang_start':
    time.sleep(300)
for line in sys.stdin:
    req = json.loads(line)
    marker.with_suffix('.calls').open('a').write(req['op'] + '\\n')
    if mode == 'stderr':
        os.write(2, b'x' * 300000)
    if mode == 'oversize':
        os.write(1, b'x' * 1100000)
        time.sleep(300)
    if mode == 'eof':
        sys.exit(0)
    if req['op'] == 'hello':
        profile = sys.argv[sys.argv.index('--profile') + 1] if '--profile' in sys.argv else 'memory-v1'
        result = {'schema_version': 1, 'profile': profile, 'recency_boost': '--recency-boost' in sys.argv, 'fingerprint': 'a' * 64,
                  'capabilities': ['health', 'search', 'fetch', 'snapshot']}
        if mode == 'profile_mismatch':
            result['profile'] = 'memory-v1' if profile == 'memory-fts-v1' else 'memory-fts-v1'
        if mode == 'bad_hello':
            result['profile'] = 'max'
        if mode == 'recency_mismatch':
            result['recency_boost'] = not result['recency_boost']
        if mode == 'missing_recency':
            del result['recency_boost']
        if mode == 'invalid_recency':
            result['recency_boost'] = 0
        if mode == 'bad_fingerprint':
            result['fingerprint'] = 'unversioned'
    elif req['op'] == 'health':
        result = {'healthy': True}
    elif req['op'] == 'search':
        if mode in ('hang_read', 'descendant'):
            time.sleep(300)
        if mode == 'slow':
            time.sleep(.15)
        result = {'hits': [{'record_id': 'one', 'excerpt': req['args']['query']}], 'degraded_signals': []}
    elif req['op'] == 'fetch':
        result = {'record_id': req['args']['record_id'], 'text': 'exact source'}
    elif req['op'] == 'snapshot':
        result = {'sources': req['args']['record_ids'], 'texts': ['exact source']}
    else:
        result = {}
    answer = {'version': 1, 'id': req['id'], 'ok': True, 'result': result}
    if mode == 'bad_id':
        answer['id'] = 'foreign'
    if (mode == 'error' or mode.startswith('error:')) and req['op'] != 'hello':
        code = mode.split(':', 1)[1] if ':' in mode else 'not_found'
        answer = {'version': 1, 'id': req['id'], 'ok': False, 'error': {'code': code}}
    if mode == 'raw_error' and req['op'] != 'hello':
        answer = {'version': 1, 'id': req['id'], 'ok': False, 'error': {'code': 'private-secret'}}
    if mode == 'duplicate':
        print('{"version":1,"version":1,"id":' + json.dumps(req['id']) + ',"ok":true,"result":{}}', flush=True)
    elif mode == 'nonfinite':
        answer['result'] = {'score': float('nan')}
        print(json.dumps(answer), flush=True)
    else:
        print(json.dumps(answer), flush=True)
""")

    def command(mode="normal"):
        from prosaic_memory_castle import WorkerCommand

        marker = tmp_path / (mode + ".pid")
        return WorkerCommand((sys.executable, str(script), mode, str(marker))), marker

    return command


@pytest.fixture
def provider(worker, tmp_path):
    from prosaic_memory_castle import CastleMemoryProvider

    created = []

    def make(mode="normal", **kwargs):
        command, marker = worker(mode)
        instance = CastleMemoryProvider(
            command,
            palace_path=tmp_path / "palace",
            namespace="tenant-a",
            config_path=tmp_path / "castle.json",
            allowed_wings=("project",),
            **kwargs,
        )
        created.append(instance)
        return instance, marker

    yield make
    for instance in created:
        instance.close()

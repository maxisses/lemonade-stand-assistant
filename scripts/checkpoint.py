#!/usr/bin/env python3
"""Private, integrity-checked backups of the demo's three SQLite databases."""
import argparse
import base64
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

from project_env import ROOT, infrastructure_environment

NAMESPACE = 'lemonade-demo'
DATABASES = {
    'campaigns.sqlite': ('lemonade-stand', 'lemonade-stand', 'lemonade-campaign-data'),
    'audience.sqlite': ('lemonade-stand', 'lemonade-stand', 'lemonade-campaign-data'),
    'provider.sqlite': ('lemonade-provider-budget', 'budget', 'lemonade-provider-data'),
}
ENTRYPOINTS = ('lemonade-audience-gateway', 'lemonade-chat-proxy', 'lemonade-dashboard-proxy')
SCHEMAS = {
    'campaigns.sqlite': {'campaigns': {'id', 'idempotency_key', 'request_identity', 'status', 'created_at', 'document'}},
    'audience.sqlite': {
        'window': {'id', 'closes', 'opened'},
        'sessions': {'id', 'persona', 'created', 'expires'},
        'events': {'id', 'session', 'started', 'finished', 'outcome', 'latency'},
        'profiles': {'id', 'name', 'profile', 'options', 'revision', 'created'},
    },
    'provider.sqlite': {
        'calls': {'id', 'started', 'role', 'generation', 'tokens', 'estimated', 'status', 'model'},
        'state': {'key', 'value'},
    },
}


def check_database(path, name, *, empty=False):
    """Check real schemas and idle state; optionally require a fresh restore target."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Database must be a regular file: ' + name)
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('SQLite integrity check failed: ' + name)
        for table, expected in SCHEMAS[name].items():
            columns = {row[1] for row in db.execute('PRAGMA table_info(' + table + ')')}
            if not set(expected) <= columns:
                raise RuntimeError('Unexpected database schema: ' + name)
        if name == 'campaigns.sqlite':
            active = db.execute("SELECT count(*) FROM campaigns WHERE status IN ('queued','running','paused','stopping')").fetchone()[0]
        elif name == 'audience.sqlite':
            windows = db.execute('SELECT id,closes FROM window').fetchall()
            if len(windows) != 1 or windows[0][0] != 1:
                raise RuntimeError('Unexpected audience window state')
            active = windows[0][1] > time.time() or db.execute("SELECT count(*) FROM events WHERE outcome='pending'").fetchone()[0]
        else:
            active = db.execute("SELECT count(*) FROM calls WHERE status='pending'").fetchone()[0]
        if active:
            raise RuntimeError('Database contains active work: ' + name)
        if empty:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables - set(SCHEMAS[name]) - {'sqlite_sequence'}:
                raise RuntimeError('Refusing to overwrite unknown database tables: ' + name)
            protected = tables & {'campaigns', 'profiles', 'calls', 'events', 'sessions'}
            if any(db.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in protected):
                raise RuntimeError('Refusing to overwrite existing evidence: ' + name)
            if name == 'provider.sqlite':
                defaults = {'model': 'qwen38-27b', 'concurrency': '1', 'paused': ''}
                if any(key not in defaults or value != defaults[key] for key, value in db.execute('SELECT key,value FROM state')):
                    raise RuntimeError('Refusing to overwrite provider configuration')
    finally:
        db.close()


def snapshot_database(path, name):
    """Return a coherent snapshot including committed WAL, then validate that snapshot."""
    source = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / name
            target = sqlite3.connect(snapshot)
            try:
                source.backup(target)
            finally:
                target.close()
            check_database(snapshot, name)
            return snapshot.read_bytes()
    finally:
        source.close()


def restore_databases(payload, campaign_directory, provider_directory):
    """Validate every payload and destination before replacing any database."""
    if set(payload) != set(SCHEMAS):
        raise RuntimeError('Unexpected restore database list')
    targets = {name: Path(provider_directory if name == 'provider.sqlite' else campaign_directory) / name for name in SCHEMAS}
    # Staging uses private unique paths on the destination filesystems for atomic renames.
    staged = {}
    try:
        for name, target in targets.items():
            if target.is_symlink():
                raise RuntimeError('Refusing a symlink restore target')
            if target.exists():
                check_database(target, name, empty=True)
            elif any(Path(str(target) + suffix).exists() for suffix in ('-wal', '-shm')):
                raise RuntimeError('Refusing orphaned SQLite sidecars')
            raw = base64.b64decode(payload[name], validate=True)
            fd, temporary = tempfile.mkstemp(prefix=name + '.', suffix='.restore', dir=target.parent)
            staged[name] = Path(temporary)
            with os.fdopen(fd, 'wb') as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            check_database(staged[name], name)
        # All three databases and all existing evidence are checked before this phase.
        for name, target in targets.items():
            for suffix in ('-wal', '-shm'):
                sidecar = Path(str(target) + suffix)
                if sidecar.exists():
                    sidecar.unlink()
            staged[name].replace(target)
    finally:
        for temporary in staged.values():
            if temporary.exists():
                temporary.unlink()


def remote_helpers():
    schemas = {name: {table: sorted(columns) for table, columns in tables.items()} for name, tables in SCHEMAS.items()}
    return ('import base64,json,os,sqlite3,sys,tempfile,time\nfrom pathlib import Path\nSCHEMAS = '
            + repr(schemas) + '\n' + '\n'.join(inspect.getsource(function) for function in
                (check_database, snapshot_database, restore_databases)))


def command(args, *, data=None, env=None):
    result = subprocess.run(args, input=data, env=env, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError('Command failed; diagnostic output withheld: ' + ' '.join(args[:3]))
    return result.stdout


def context():
    env = infrastructure_environment()
    actual = json.loads(command(['aws', 'sts', 'get-caller-identity', '--output', 'json'], env=env))
    recorded = json.loads((ROOT / 'local/context.json').read_text())
    if actual['Account'] != recorded['aws_account_id']:
        raise RuntimeError('AWS account mismatch')
    server = command(['oc', '--kubeconfig', str(ROOT / 'local/kubeconfig'), 'config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}']).decode()
    if server.rstrip('/') != recorded['cluster_api_url'].rstrip('/'):
        raise RuntimeError('Cluster context mismatch')
    return recorded


def oc(*args, data=None):
    return command(['oc', '--kubeconfig', str(ROOT / 'local/kubeconfig'), '-n', NAMESPACE, *args], data=data)


def require_stopped(deployments):
    for deployment in deployments:
        item = json.loads(oc('get', 'deployment', deployment, '-o', 'json'))
        if item['spec'].get('replicas', 1) != 0:
            raise RuntimeError('Scale deployment to zero first: ' + deployment)
        selectors = item['spec']['selector']
        if selectors.get('matchExpressions') or not selectors.get('matchLabels'):
            raise RuntimeError('Unsupported deployment selector: ' + deployment)
        selector = ','.join(key + '=' + value for key, value in selectors['matchLabels'].items())
        if json.loads(oc('get', 'pods', '-l', selector, '-o', 'json'))['items']:
            raise RuntimeError('Wait for deployment pods to terminate: ' + deployment)


def private_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(data)


def verify(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if set(manifest['databases']) != set(DATABASES):
        raise RuntimeError('Unexpected checkpoint database list')
    for name, expected in manifest['databases'].items():
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']:
            raise RuntimeError('Checkpoint checksum mismatch: ' + name)
        check_database(path, name)
    return manifest


def backup(directory):
    recorded = context()
    require_stopped(ENTRYPOINTS)
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'context': recorded,
                'git_revision': command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip(),
                'databases': {}}
    for name, (deployment, container, claim) in DATABASES.items():
        code = remote_helpers() + "\nsys.stdout.write(base64.b64encode(snapshot_database(Path('/data')/sys.argv[1],sys.argv[1])).decode())"
        content = base64.b64decode(oc('exec', 'deployment/' + deployment, '-c', container, '--', 'python', '-c', code, name), validate=True)
        private_write(directory / name, content)
        manifest['databases'][name] = {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content), 'pvc': claim}
    private_write(directory / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    verify(directory)
    print('Verified private checkpoint: ' + str(directory))


def restore(directory):
    recorded = context()
    manifest = verify(directory)
    for field in ('aws_account_id', 'region'):
        if manifest['context'].get(field) != recorded.get(field):
            raise RuntimeError('Checkpoint belongs to another AWS account or region')
    require_stopped((*ENTRYPOINTS, 'lemonade-stand', 'lemonade-provider-budget'))
    image = json.loads(oc('get', 'deployment', 'lemonade-stand', '-o', 'json'))['spec']['template']['spec']['containers'][0]['image']
    if '@sha256:' not in image:
        raise RuntimeError('Restore requires the pinned application image')
    pod = {'apiVersion':'v1', 'kind':'Pod', 'metadata':{'name':'lemonade-checkpoint-restore','namespace':NAMESPACE},
           'spec':{'restartPolicy':'Never','automountServiceAccountToken':False,
                   'containers':[{'name':'restore','image':image,'command':['python','-c','import time; time.sleep(900)'],
                                  'securityContext':{'allowPrivilegeEscalation':False,'runAsNonRoot':True,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}},
                                  'resources':{'requests':{'cpu':'10m','memory':'64Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},
                                  'volumeMounts':[{'name':'campaign','mountPath':'/restore/campaign'},{'name':'provider','mountPath':'/restore/provider'}]}],
                   'volumes':[{'name':'campaign','persistentVolumeClaim':{'claimName':'lemonade-campaign-data'}},
                              {'name':'provider','persistentVolumeClaim':{'claimName':'lemonade-provider-data'}}]}}
    oc('create', '-f', '-', data=json.dumps(pod).encode())
    try:
        oc('wait', '--for=condition=Ready', 'pod/lemonade-checkpoint-restore', '--timeout=120s')
        payload = {name: base64.b64encode((directory / name).read_bytes()).decode() for name in DATABASES}
        code = remote_helpers() + "\nrestore_databases(json.load(sys.stdin),'/restore/campaign','/restore/provider')\nprint('Three databases restored; applications remain stopped.')"
        result = oc('exec', '-i', 'lemonade-checkpoint-restore', '--', 'python', '-c', code, data=json.dumps(payload).encode())
        print(result.decode().strip())
    finally:
        oc('delete', 'pod', 'lemonade-checkpoint-restore', '--wait=false')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup','verify','restore'])
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory.expanduser().resolve()
    if not directory.is_relative_to(ROOT / 'local'):
        raise RuntimeError('Checkpoints must remain under ignored local/')
    if args.action == 'verify':
        verify(directory); print('All three checkpoint hashes and SQLite integrity checks passed.')
    else:
        globals()[args.action](directory)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit('Checkpoint failed: ' + str(error) if isinstance(error, RuntimeError) else 'Checkpoint failed; diagnostic details withheld.')

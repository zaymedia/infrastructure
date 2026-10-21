"""Run the actual pinned Vector engine against routing and privacy fixtures."""
import json
from pathlib import Path
import subprocess
import tempfile

from render import FIELDS, render


ROOT = Path(__file__).parent
IMAGE = 'timberio/vector@sha256:98e7b4dfe50750e61470697bbd2fbeca643d12bea97f351005038ef506eab630'


def fixture(name, fields, condition, insert_at='normalize', extract_from='normalize'):
    prefix = 'message = string!(.message); ' if 'contains(.message,' in condition or 'length(.message)' in condition else ''
    condition = condition.replace('contains(.message,', 'contains(message,').replace('length(.message)', 'length(message)')
    return {'name': name, 'inputs': [{'insert_at': insert_at, 'type': 'log', 'log_fields': fields}], 'outputs': [{'extract_from': extract_from, 'conditions': [{'type': 'vrl', 'source': prefix + condition}]}]}


def main():
    inventory = json.loads((ROOT / 'inventory.json').read_text())
    config = render(inventory)
    assert all(s['buffer'] == {'type': 'memory', 'max_events': 256, 'when_full': 'block'} for s in config['sinks'].values())
    assert all(s['encoding']['only_fields'] == FIELDS for s in config['sinks'].values())
    config['tests'] = [
        fixture('compose survives a new container id', {'message': 'INFO ready', 'container_id': 'new-id', 'container_name': 'bugrain-web-2', 'label': {'com.docker.compose.project': 'bugrain', 'com.docker.compose.service': 'web', 'org.opencontainers.image.revision': 'a'*40}, 'timestamp': '2026-10-21T12:00:00Z'}, 'assert_eq!(._project,"bugrain"); assert_eq!(.service,"bugrain.web"); assert_eq!(.release,"'+ 'a'*40 + '"); assert_eq!(.time,1792584000000); assert_eq!(.context.containerId,"new-id")'),
        fixture('stable website name overrides release directory', {'message': 'ready', 'container_name': 'zaytcevcom', 'label': {'com.docker.compose.project': 'v_999'}}, 'assert_eq!(._project,"zaytcev"); assert_eq!(.service,"zaytcev.zaytcevcom")'),
        fixture('unknown application reaches infrastructure', {'message': 'ready', 'container_name': 'new-application', 'label': {'com.docker.compose.project': 'unknown'}}, 'assert_eq!(._project,"zay-infrastructure"); assert_eq!(.context.composeProject,"unknown")'),
        fixture('stderr is not an error level', {'message': 'ready', 'stream': 'stderr'}, 'assert_eq!(.level,"INFO")'),
        fixture('Bugrain sink route receives the event', {'message': 'ready', 'label': {'com.docker.compose.project': 'bugrain', 'com.docker.compose.service': 'web'}}, 'assert_eq!(.service,"bugrain.web")', extract_from='bugrain'),
        fixture('structured error level retained', {'message': '{"level":"error","msg":"failure"}'}, 'assert_eq!(.level,"ERROR"); assert!(contains(.message,"failure"))'),
        fixture('Pino numeric error level retained', {'message': '{"level":50,"msg":"failed"}'}, 'assert_eq!(.level,"ERROR")'),
        fixture('escaped credential and opaque token removed', {'message': json.dumps({'password':'abc"fixture-credential-tail', 'token':'fixture-opaque-token', 'privateKey':'fixture-private-key'})}, 'assert!(!contains(.message,"fixture-credential-tail")); assert!(!contains(.message,"fixture-opaque-token")); assert!(!contains(.message,"fixture-private-key"))'),
        fixture('Sentry DSN userinfo removed', {'message': 'https://fixture-sentry-token@duckbug.io/123'}, 'assert!(!contains(.message,"fixture-sentry-token"))'),
        fixture('plain panic normalized', {'message': 'panic: fixture failure'}, 'assert_eq!(.level,"FATAL")'),
        fixture('journal priority and message', {'source_type': 'journald', 'MESSAGE': 'host fixture failure', 'PRIORITY': '3', '_SYSTEMD_UNIT': 'ssh.service', '_CMDLINE': 'do-not-forward'}, 'assert_eq!(.level,"ERROR"); assert_eq!(.message,"host fixture failure"); assert_eq!(.service,"zay-infrastructure.ssh.service"); assert!(!exists(._CMDLINE)); assert!(!exists(.context._CMDLINE))'),
        fixture('credential scrubber', {'message': 'password=fixture-password Authorization: Bearer fixture-bearer sk-duck-fixture-mcp https://example.test/x?token=fixture-query postgres://fixture-user:fixture-pass@database/app /ingest/00000000-0000-4000-8000-000000000001:fixture-native-key', 'env': {'SECRET': 'fixture-env'}, 'label': {'auth.password': 'fixture-label'}}, 'assert!(!contains(.message,"fixture-password")); assert!(!contains(.message,"fixture-bearer")); assert!(!contains(.message,"fixture-mcp")); assert!(!contains(.message,"fixture-query")); assert!(!contains(.message,"fixture-user")); assert!(!contains(.message,"fixture-pass")); assert!(!contains(.message,"fixture-native-key")); assert!(!exists(.env)); assert!(!exists(.label))'),
        fixture('cookie header removed in full', {'message': 'Cookie: session=fixture-cookie; other=fixture-other'}, 'assert!(!contains(.message,"fixture-cookie")); assert!(!contains(.message,"fixture-other"))'),
        fixture('message size bounded', {'message': 'x'*40000}, 'assert!(length(.message) <= 32768)'),
        {'name': 'container journal is not collected twice', 'inputs': [{'insert_at': 'host_journal', 'type': 'log', 'log_fields': {'MESSAGE': 'duplicate docker line', 'CONTAINER_ID_FULL': 'fixture-id'}}], 'no_outputs_from': ['host_journal']},
    ]
    with tempfile.TemporaryDirectory(prefix='zay-vector-fixture-') as directory:
        folder = Path(directory)
        (folder / 'vector.json').write_text(json.dumps(config))
        secrets = {}
        for project in inventory['projects']:
            secrets[project['key'].replace('-', '_')] = '00000000-0000-4000-8000-000000000001:synthetic-test-only'
        (folder / 'secrets.json').write_text(json.dumps(secrets))
        command = ['docker', 'run', '--rm', '-v', str(folder)+':/work:ro', '-v', str(folder / 'secrets.json')+':/etc/vector/ingest-secrets.json:ro', IMAGE]
        subprocess.run([*command, 'validate', '--no-environment', '--skip-healthchecks', '/work/vector.json'], check=True)
        subprocess.run([*command, 'test', '/work/vector.json'], check=True)


if __name__ == '__main__':
    main()

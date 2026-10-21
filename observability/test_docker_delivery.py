"""Verify Docker discovery, wire format, bounded memory, retries and graceful drain.

The queue is intentionally volatile. A forced exit can lose pending events.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from render import render
from test_pipeline import IMAGE


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.STDOUT, timeout=90).strip()


def completed_rows(path):
    # The file sink can still be appending its final JSON frame when polled.
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text().rpartition('\n')[0].splitlines()]


def main():
    prefix = 'zay-observability-fixture-' + uuid.uuid4().hex[:10]
    network = prefix
    spool_volume = prefix + '-spool'
    receiver, collector, application = prefix + '-receiver', 'vector-' + prefix, prefix + '-app'
    with tempfile.TemporaryDirectory(prefix=prefix) as directory:
        root = Path(directory)
        shared = root / 'shared'
        shared.mkdir()
        (shared / 'receiver.mjs').write_text('''import http from 'node:http';import fs from 'node:fs';
const seen=new Set();
http.createServer((q,s)=>{let body='';q.on('data',c=>body+=c);q.on('end',()=>{
fs.appendFileSync('/shared/raw.jsonl',JSON.stringify({path:q.url,body})+'\\n');
let events;try{events=JSON.parse(body);if(!Array.isArray(events)||events.length!==1)throw Error('expected singleton array');}catch{s.writeHead(400).end();return;}
let status=201;let created=0;let duplicates=0;
if(fs.existsSync('/shared/unavailable'))status=503;
else{for(const e of events){if(seen.has(e.eventId))duplicates++;else{seen.add(e.eventId);created++;}}}
if(fs.existsSync('/shared/commit_then_503')){fs.unlinkSync('/shared/commit_then_503');status=503;}
fs.appendFileSync('/shared/requests.jsonl',JSON.stringify({path:q.url,contentType:q.headers['content-type'],status,created,duplicates,events})+'\\n');
s.writeHead(status,{'Content-Type':'application/json'}).end(JSON.stringify({created,duplicates,items:[]}));
});}).listen(9080,'0.0.0.0');
''')
        config = render(json.loads(Path(__file__).with_name('inventory.json').read_text()))
        config['sources'] = {'docker': {'type': 'docker_logs', 'include_containers': [application]}}
        config['sources']['fixture_metrics'] = {'type': 'internal_metrics', 'scrape_interval_secs': 1}
        config['transforms'] = {k:v for k,v in config['transforms'].items() if k in ['normalize', 'bugrain', 'zay_infrastructure']}
        config['transforms']['normalize']['inputs'] = ['docker']
        config['transforms']['fixture_metrics_log'] = {'type': 'metric_to_log', 'inputs': ['fixture_metrics']}
        config['sinks'] = {k:v for k,v in config['sinks'].items() if k in ['bugrain_http', 'zay_infrastructure_http']}
        for sink in config['sinks'].values():
            sink['uri'] = sink['uri'].replace('https://duckbug.io/api/ingest/', 'http://receiver:9080/ingest/')
            sink['proxy'] = {'enabled': False}
        for name, inputs in [('input', ['docker']), ('normalized', ['normalize']), ('routed', ['bugrain']), ('metrics', ['fixture_metrics_log'])]:
            config['sinks']['fixture_' + name + '_file'] = {'type': 'file', 'inputs': inputs, 'path': '/fixture/'+name+'.jsonl', 'encoding': {'codec': 'json'}}
        (root / 'vector.json').write_text(json.dumps(config))
        (root / 'secrets.json').write_text(json.dumps({'bugrain':'fixture-bugrain:synthetic', 'zay_infrastructure':'fixture-infrastructure:synthetic'}))

        def requests():
            path = shared / 'requests.jsonl'
            return completed_rows(path)

        def await_event(marker, status):
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                found = [row for row in requests() if row['status']==status and any(marker in e['message'] for e in row['events'])]
                if found: return found[-1]
                if docker('inspect', '--format', '{{.State.Running}}', collector) != 'true':
                    raise AssertionError('Fixture collector exited before delivery')
                time.sleep(0.2)
            raise AssertionError('Missing fixture delivery '+marker+' status '+str(status))

        def start_application(marker, project='bugrain'):
            program = 'setTimeout(()=>console.log('+json.dumps('INFO '+marker+' password=fixture-private-value')+'),1000);setInterval(()=>{},1000)'
            return docker('run', '-d', '--name', application, '--network', network,
                          '--label', 'com.docker.compose.project='+project, '--label', 'com.docker.compose.service=web',
                          '--label', 'org.opencontainers.image.revision='+'a'*40,
                          'node:24-alpine', 'node', '-e', program)

        def emit(marker):
            program = "require('fs').writeFileSync('/proc/1/fd/1',"+json.dumps('INFO '+marker+'\n')+")"
            docker('exec', application, 'node', '-e', program)

        try:
            docker('run', '--rm', '-v', str(root / 'vector.json')+':/etc/vector/vector.json:ro',
                   '-v', str(root / 'secrets.json')+':/etc/vector/ingest-secrets.json:ro',
                   IMAGE, 'validate', '--no-environment', '--skip-healthchecks', '/etc/vector/vector.json')
            docker('network', 'create', network)
            docker('volume', 'create', spool_volume)
            docker('run', '-d', '--name', receiver, '--network', network, '--network-alias', 'receiver', '-v', str(shared)+':/shared', 'node:24-alpine', 'node', '/shared/receiver.mjs')
            docker('run', '-d', '--name', collector, '--network', network,
                   '-v', str(root / 'secrets.json')+':/etc/vector/ingest-secrets.json:ro',
                   '-v', str(root / 'vector.json')+':/etc/vector/vector.json:ro', '-v', spool_volume+':/var/lib/vector',
                   '-v', str(shared)+':/fixture', '-e', 'VECTOR_LOG=info',
                   '-v', '/var/run/docker.sock:/var/run/docker.sock:ro', IMAGE, '--threads', '1', '--config', '/etc/vector/vector.json')
            print('FIXTURE_COLLECTOR', collector, flush=True)
            deadline = time.monotonic() + 20
            while 'Excluded self container' not in docker('logs', collector):
                if time.monotonic() >= deadline: raise AssertionError('Docker source did not initialize')
                time.sleep(0.2)
            first_id = start_application('first-container')
            first = await_event('first-container', 201)
            docker('rm', '-f', application)
            second_id = start_application('recreated-container')
            second = await_event('recreated-container', 201)
            assert first_id != second_id
            assert first['events'][0]['service'] == second['events'][0]['service'] == 'bugrain.web'
            assert first['events'][0]['context']['containerId'] != second['events'][0]['context']['containerId']

            # Isolated low-rate messages must not wait for a later event to wake a queue.
            for number in range(10):
                marker = 'isolated-event-' + str(number)
                emit(marker)
                await_event(marker, 201)

            # A committed event whose response is lost must be acknowledged on retry.
            (shared / 'commit_then_503').touch()
            emit('committed-before-retry')
            attempt = await_event('committed-before-retry', 503)
            retried = await_event('committed-before-retry', 201)
            assert attempt['events'][0]['eventId'] == retried['events'][0]['eventId']
            assert retried['duplicates'] == 1

            # Fill the memory queue during an outage, then recover without restarting.
            (shared / 'unavailable').touch()
            emit('outage-pending')
            pending = await_event('outage-pending', 503)
            program = "const fs=require('fs');for(let i=0;i<500;i++)fs.writeFileSync('/proc/1/fd/1','INFO bounded-backlog-'+i+' '+ 'x'.repeat(24000)+'\\n');"
            docker('exec', application, 'node', '-e', program)
            deadline = time.monotonic() + 30
            while True:
                metrics = completed_rows(shared/'metrics.jsonl')
                sizes = [m.get('gauge',{}).get('value',0) for m in metrics if m.get('name')=='buffer_size_events' and m.get('tags',{}).get('component_id')=='bugrain_http']
                # Batched producers may block before the approximate gauge reaches its limit.
                if sizes and 0 < sizes[-1] <= 256: break
                if time.monotonic() >= deadline: raise AssertionError('Memory queue did not fill under backpressure')
                time.sleep(0.2)
            # Wait past two buffer-metric reporting intervals to prove backpressure.
            plateau = {}
            for observation in range(2):
                time.sleep(5)
                for metric in completed_rows(shared/'metrics.jsonl'):
                    if metric.get('tags',{}).get('component_id')=='bugrain_http' and metric.get('name') in ['buffer_received_events_total', 'buffer_sent_events_total']:
                        plateau[metric['name']] = metric['counter']['value']
                if observation == 0: previous = plateau.copy()
                else: assert plateau == previous, 'Queue did not apply stable backpressure'
            occupancy = plateau['buffer_received_events_total'] - plateau['buffer_sent_events_total']
            assert 0 < occupancy <= 256
            assert plateau['buffer_received_events_total'] < 500, 'No upstream backlog remained blocked'
            rss_kib = int(docker('exec', collector, 'sh', '-c', "awk '/VmRSS:/ {print $2}' /proc/1/status"))
            assert rss_kib < 512 * 1024, 'Fixture RSS exceeded service memory budget'
            print('FULL_QUEUE_RSS_KIB', rss_kib, flush=True)
            (shared / 'unavailable').unlink()
            restored = await_event('outage-pending', 201)
            assert pending['events'][0]['eventId'] == restored['events'][0]['eventId']
            await_event('bounded-backlog-499 ', 201)
            delivered = {e['message'].split(' ', 2)[1] for r in requests() if r['status']==201 for e in r['events'] if 'bounded-backlog-' in e['message']}
            assert len(delivered) == 500

            # Graceful termination drains while the receiver is available.
            emit('graceful-drain')
            docker('stop', '-t', '40', collector)
            assert any(r['status']==201 and 'graceful-drain' in r['events'][0]['message'] for r in requests())
            docker('start', collector)
            time.sleep(1)

            docker('rm', '-f', application)
            start_application('unknown-project', 'unknown-new-project')
            fallback = await_event('unknown-project', 201)
            assert fallback['path'].endswith('/ingest/fixture-infrastructure:synthetic/logs/batch')
            assert fallback['events'][0]['service'] == 'zay-infrastructure.web'
            for row in requests():
                assert row['contentType'] == 'application/json'
                for event in row['events']:
                    assert uuid.UUID(event['eventId']).version == 4
                    assert 'fixture-private-value' not in event['message']
                    assert '_project' not in event
            print('REAL_DOCKER_DELIVERY_RECREATE_RETRY_MEMORY_DRAIN_PASS')
        except BaseException:
            # Only isolated synthetic fixtures are logged; production credentials never enter this test.
            try: print(docker('logs', '--tail', '80', collector))
            except subprocess.CalledProcessError: pass
            for filename in ['input.jsonl', 'normalized.jsonl', 'routed.jsonl', 'raw.jsonl']:
                path = shared / filename
                if path.exists(): print('SYNTHETIC_'+filename, path.read_text()[-8000:])
            metrics = shared / 'metrics.jsonl'
            if metrics.exists():
                latest = {}
                for metric in completed_rows(metrics):
                    name = metric.get('name', '')
                    if name.startswith(('buffer_', 'component_', 'http_client_')):
                        latest[(name, json.dumps(metric.get('tags', {}), sort_keys=True))] = metric
                print('SYNTHETIC_METRICS', json.dumps(list(latest.values())))
            try: print('SYNTHETIC_SPOOL', docker('exec', collector, 'find', '/var/lib/vector', '-type', 'f', '-printf', '%p %s bytes\\n'))
            except subprocess.CalledProcessError: pass
            raise
        finally:
            for name in [application, collector, receiver]:
                subprocess.run(['docker', 'rm', '-f', '-v', name], capture_output=True)
            subprocess.run(['docker', 'network', 'rm', network], capture_output=True)
            subprocess.run(['docker', 'volume', 'rm', spool_volume], capture_output=True)


if __name__ == '__main__':
    main()

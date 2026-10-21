#!/usr/bin/env python3
"""Render the reviewed host inventory into a Vector configuration without secrets."""
import argparse
import json
from pathlib import Path
import re


FIELDS = ['eventId', 'time', 'level', 'message', 'environment', 'serverName', 'service', 'release', 'dTags', 'context']


def render(inventory):
    projects = inventory['projects']
    keys = [project['key'] for project in projects]
    if len(keys) != len(set(keys)) or not all(re.fullmatch('[a-z][a-z0-9-]*', key) for key in keys):
        raise ValueError('Project keys must be unique safe identifiers')
    if inventory['fallbackProject'] not in keys:
        raise ValueError('Unknown fallback project')
    selectors = set()
    routes = []
    for project in projects:
        tests = []
        for field, variable in [('composeProjects', 'compose_project'), ('containerNames', 'container_name')]:
            for value in project[field]:
                selector = (field, value)
                if selector in selectors:
                    raise ValueError('Ambiguous project selector')
                selectors.add(selector)
                tests.append(variable + ' == ' + json.dumps(value))
        if tests:
            routes.append('if ' + ' || '.join(tests) + ' { project = ' + json.dumps(project['key']) + ' }')
    source = r'''
is_journal = .source_type == "journald"
message = to_string(.message) ?? ""
if message == "" { message = to_string(.MESSAGE) ?? "" }
if is_empty(strip_whitespace(message)) { abort }
compose_project = to_string(.label."com.docker.compose.project") ?? ""
compose_service = to_string(.label."com.docker.compose.service") ?? ""
container_name = to_string(.container_name) ?? ""
container_id = to_string(.container_id) ?? ""
stream = to_string(.stream) ?? ""
revision = to_string(.label."org.opencontainers.image.revision") ?? ""
if revision == "" { revision = to_string(.image) ?? "unknown" }
unit = to_string(._SYSTEMD_UNIT) ?? ""
project = FALLBACK
ROUTES
service = if compose_service != "" { compose_service } else if is_journal && unit != "" { unit } else if container_name != "" { container_name } else { "host" }
level = ""
parsed, parse_error = parse_json(message)
if parse_error == null && is_object(parsed) { level = upcase(to_string(parsed.level) ?? "") }
if level == "" && is_journal {
  priority = to_int(.PRIORITY) ?? 6
  level = if priority <= 2 { "FATAL" } else if priority == 3 { "ERROR" } else if priority == 4 { "WARN" } else if priority == 7 { "DEBUG" } else { "INFO" }
}
if level == "" {
  matched, match_error = parse_regex(message, r'(?i)(?:^|\s|\[)(?P<level>TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERR(?:OR)?|FATAL|CRITICAL|PANIC)(?:\]|\s|:|$)')
  if match_error == null { level = upcase(to_string(matched.level)) }
}
level = if includes(["FATAL", "PANIC", "CRITICAL", "EMERGENCY", "ALERT", "60"], level) { "FATAL" } else if includes(["ERROR", "ERR", "50"], level) { "ERROR" } else if includes(["WARN", "WARNING", "40"], level) { "WARN" } else if includes(["DEBUG", "TRACE", "10", "20"], level) { "DEBUG" } else { "INFO" }
# Scrub the original text as well as excluding arbitrary source metadata.
message = replace(message, r'(?i)\b(?:cookie|set-cookie)\s*:\s*[^\r\n]+', "[REDACTED_COOKIE]")
message = replace(message, r'(?i)\bBearer\s+[a-z0-9._~+/-]+=*', "Bearer [REDACTED]")
message = replace(message, r'(?i)"?(?:authorization|cookie|set-cookie|password|passwd|secret|api[-_]?key|token|id[-_]?token|access[-_]?token|refresh[-_]?token|session[-_]?token|client[-_]?secret|webhook[-_]?token|private[-_]?key)"?\s*[:=]\s*(?:"(?:[^"\\]|\\.)*"|\x27(?:[^\x27\\]|\\.)*\x27|[^\s,;}]+)', "[REDACTED]")
message = replace(message, r'(?:sk-duck-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)', "[REDACTED_TOKEN]")
message = replace(message, r'(?i)(?:https?|postgres(?:ql)?|mysql|redis|amqps?)://[^\s/@]+@', "[REDACTED_CREDENTIALS]@")
message = replace(message, r'/ingest/[0-9a-fA-F-]{36}:[A-Za-z0-9._~-]+', "/ingest/[REDACTED]")
message = replace(message, r'\?[^\s"<>]+', "?[REDACTED_QUERY]")
message = truncate(message, limit: 32768)
event_time = parse_timestamp(to_string(.timestamp) ?? "", format: "%+") ?? now()
source_tag = if is_journal { "source:journald" } else { "source:docker" }
context = if is_journal {
  {"source": "journald", "unit": unit}
} else {
  {"source": "docker", "composeProject": compose_project, "composeService": compose_service, "containerName": container_name, "containerId": container_id, "stream": stream}
}
. = {
  "eventId": uuid_v4(),
  "time": to_unix_timestamp(event_time, unit: "milliseconds"),
  "level": level,
  "message": message,
  "environment": ENVIRONMENT,
  "serverName": SERVER_NAME,
  "service": project + "." + service,
  "release": truncate(revision, limit: 200),
  "dTags": [source_tag],
  "context": context,
  "_project": project
}
'''.replace('FALLBACK', json.dumps(inventory['fallbackProject'])).replace('ROUTES', '\n'.join(routes)).replace('ENVIRONMENT', json.dumps(inventory['server']['environment'])).replace('SERVER_NAME', json.dumps(inventory['server']['name']))
    transforms = {
        'host_journal': {'type': 'filter', 'inputs': ['journal'], 'condition': '!exists(.CONTAINER_ID_FULL) && !exists(.CONTAINER_NAME)'},
        'normalize': {'type': 'remap', 'inputs': ['docker', 'host_journal'], 'source': source, 'drop_on_abort': True, 'drop_on_error': True},
    }
    sinks = {}
    for project in projects:
        name = project['key'].replace('-', '_')
        transforms[name] = {'type': 'filter', 'inputs': ['normalize'], 'condition': '._project == ' + json.dumps(project['key'])}
        sinks[name + '_http'] = {
            'type': 'http', 'inputs': [name],
            'uri': 'https://duckbug.io/api/ingest/SECRET[local_file.' + name + ']/logs/batch',
            'method': 'post', 'compression': 'none',
            'encoding': {'codec': 'json', 'only_fields': FIELDS},
            'framing': {'method': 'character_delimited', 'character_delimited': {'delimiter': ','}}, 'batch': {'max_events': 1},
            'request': {'concurrency': 1, 'headers': {'Content-Type': 'application/json'}},
            'healthcheck': {'enabled': False},
            # Vector disk_v2 currently stalls isolated events (upstream issue 26523).
            'buffer': {'type': 'memory', 'max_events': 256, 'when_full': 'block'},
            'acknowledgements': {'enabled': True},
        }
    return {
        'data_dir': '/var/lib/vector',
        'secret': {'local_file': {'type': 'file', 'path': '/etc/vector/ingest-secrets.json'}},
        'sources': {
            'docker': {'type': 'docker_logs', 'exclude_containers': ['vector']},
            'journal': {'type': 'journald', 'current_boot_only': False, 'since_now': True, 'exclude_units': ['vector.service'], 'remap_priority': False},
        },
        'transforms': transforms, 'sinks': sinks,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', type=Path, default=Path(__file__).with_name('inventory.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(render(json.loads(args.inventory.read_text())), indent=2) + '\n')

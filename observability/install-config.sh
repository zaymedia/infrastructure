#!/bin/sh
set -eu
umask 077

test "$(id -u)" -eq 0
test "$(hostname)" = p916391.kvmvps
test "$(dpkg-query -W -f='${Version}' vector)" = 0.59.0-1
vector_source=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
vector_secret=${1:?Path to the project-scoped ingest secrets is required}

install -d -o root -g root -m 0755 /usr/local/lib/zay-observability
install -m 0644 "$vector_source/render.py" "$vector_source/inventory.json" /usr/local/lib/zay-observability/
install -d -o root -g vector -m 0750 /etc/vector
install -d -o vector -g vector -m 0700 /var/lib/vector
vector_temporary=$(mktemp -d /etc/vector/.zay-install.XXXXXX)
trap 'rm -rf "$vector_temporary"' EXIT HUP INT TERM
install -o root -g vector -m 0640 "$vector_secret" "$vector_temporary/secrets.json"
python3 - "$vector_temporary/secrets.json" <<'PY'
import json, re, sys
from pathlib import Path
inventory=json.loads(Path('/usr/local/lib/zay-observability/inventory.json').read_text())
secrets=json.loads(Path(sys.argv[1]).read_text())
expected={p['key'].replace('-','_'):p['duckbugProjectId'] for p in inventory['projects']}
if set(secrets)!=set(expected):raise SystemExit('Ingest credential project set does not match inventory')
for key,project in expected.items():
    if not isinstance(secrets[key],str) or not re.fullmatch(re.escape(project)+r':[A-Za-z0-9._~-]+',secrets[key]):
        raise SystemExit('Invalid project-scoped ingest credential')
PY
python3 /usr/local/lib/zay-observability/render.py --output "$vector_temporary/zay.json"
chown root:vector "$vector_temporary/zay.json"
chmod 0640 "$vector_temporary/zay.json"

# This first installation must not silently replace a separately managed collector.
test ! -e /etc/vector/zay.json
test ! -e /etc/vector/ingest-secrets.json
install -o root -g vector -m 0640 "$vector_temporary/secrets.json" /etc/vector/ingest-secrets.json
install -o root -g vector -m 0640 "$vector_temporary/zay.json" /etc/vector/zay.json
install -d -m 0755 /etc/systemd/system/vector.service.d
install -m 0644 "$vector_source/vector-override.conf" /etc/systemd/system/vector.service.d/zay.conf
usermod -a -G docker,systemd-journal vector
runuser -u vector -- /usr/bin/vector validate --no-environment --skip-healthchecks /etc/vector/zay.json
systemctl daemon-reload
systemctl unmask vector.service
systemctl enable --now vector.service
systemctl is-active --quiet vector.service
printf '%s\n' 'ZAY_VECTOR_CONFIG_INSTALLED_ACTIVE'

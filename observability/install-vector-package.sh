#!/bin/sh
set -eu

test "$(id -u)" -eq 0
test "$(hostname)" = p916391.kvmvps
if command -v vector >/dev/null 2>&1; then
  test "$(dpkg-query -W -f='${Version}' vector)" = 0.59.0-1
  printf '%s\n' 'Vector 0.59.0 package is already installed'
  exit 0
fi

# Keep the package's demo configuration stopped until the reviewed configuration is installed.
systemctl mask vector.service
vector_stage=$(mktemp -d)
trap 'rm -rf "$vector_stage"' EXIT HUP INT TERM
for vector_key in DATADOG_APT_KEY_CURRENT.public DATADOG_APT_KEY_C0962C7D.public DATADOG_APT_KEY_F14F620E.public; do
  curl -fsSL --retry 3 "https://keys.datadoghq.com/$vector_key" >> "$vector_stage/keys.asc"
done
gpg --batch --yes --dearmor --output "$vector_stage/vector.gpg" "$vector_stage/keys.asc"
install -m 0644 "$vector_stage/vector.gpg" /usr/share/keyrings/zay-vector-datadog.gpg
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/zay-vector-datadog.gpg] https://apt.vector.dev/ stable vector-0' > /etc/apt/sources.list.d/zay-vector.list
apt-get update -o Dir::Etc::sourcelist=sources.list.d/zay-vector.list -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0
DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y --no-install-recommends vector=0.59.0-1
usermod -a -G docker,systemd-journal vector
test "$(dpkg-query -W -f='${Version}' vector)" = 0.59.0-1
vector --version
printf '%s\n' 'VECTOR_PACKAGE_INSTALLED_SERVICE_MASKED'

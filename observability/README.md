# ZAY → DuckBug

`inventory.json` maps the Docker applications on ZAY (`37.143.8.251`) to 15
projects in the **ZAY.MEDIA** organization and its six project groups. Known
Compose projects retain their destination when containers are recreated. The
Zaytcev.com site uses its stable container name because its Compose project is
a release directory. Unknown containers and host systemd journals go to
**ZAY Infrastructure**. Stopped applications are not started by this integration.

## Collection and privacy

The official Vector 0.59.0 package reads Docker stdout/stderr and the host
journal. Docker copies inside the journal and Vector's own journal are excluded
to avoid duplicates and recursive diagnostic forwarding. No application container
is recreated and no Docker logging driver is changed.

VRL normalizes levels, tags service/container/release, generates a UUID before
HTTP retry, truncates messages to 32 KiB and removes common credentials from
message text. Only explicit diagnostic fields leave the host; environment,
arbitrary Docker labels, command lines, cookies and request bodies are not copied.
Text redaction is best effort: applications must never log secrets themselves.

Each project uses its **own ingest-only credential**, read using Vector's file
secret backend. No MCP PAT, browser JWT, GitHub credential or SSH private key is
installed in the collector. Secret files stay outside Git. Do not paste DSNs
or full Vector internal diagnostics into issues: destination paths may contain
the ingest key.

`/logs/batch` receives a bare JSON array with one event. Repeated HTTP attempts
retain the same event UUID, allowing DuckBug to deduplicate an accepted request
whose response was lost. Re-reading an original source line after restart can
generate a new UUID and therefore a duplicate.

## Delivery limits

Collection has retries and a bounded **volatile memory queue**, 256 events per
project with blocking backpressure and one HTTP request in flight per project.
The whole service has a 512 MiB memory ceiling and a 50% CPU quota. The queue
event count alone is not an RSS limit. Blocking can propagate across projects.

Pending events can be lost on a crash, a forced stop, an expired shutdown
deadline or source rotation during a long outage. Graceful shutdown drains for
30 seconds; systemd allows 40 seconds. Docker discovery is best effort and
does not promise replay while Vector is stopped. Host journals use checkpoints
in `/var/lib/vector`; the initial installation starts from the current point.
This integration does not upload historical files automatically.

**Disk buffering is intentionally disabled.** Our isolated-event test reproduced
[Vector issue 26523](https://github.com/vectordotdev/vector/issues/26523): an event
can remain on disk until a later message arrives. The previous disk restart gate
failed; switching to memory does not establish disk durability. Do not enable
`disk_v2` or advertise crash-safe delivery without a fixed version and new tests.

Application file logs and browser exceptions require separate application SDK
instrumentation; stdout/journal collection does not create invented stack traces.
An ERROR line remains an ERROR log. Infrastructure source `ZAY monitoring`
registers the actual server resource, without uploading administrative SSH access.

## Verification

```sh
python3 observability/test_pipeline.py
python3 observability/test_docker_delivery.py
```

Tests run the pinned official Vector container. Fixtures contain synthetic
credentials only and verify routing, privacy, exact JSON framing, isolated
low-rate delivery, container recreation, unknown-project fallback, a committed
503 response and deduplicated retry, a full memory queue, measured RSS,
recovery after an HTTP outage and graceful drain before restart.

## First installation

On the reviewed host, run `install-vector-package.sh` as root to install the
signed official APT package while keeping the service masked. Stage the reviewed
`observability` directory and the existing project credential file privately.
Check the staged source hashes before running as root:

```sh
sh observability/install-config.sh /private/path/ingest-secrets.json
```

The configuration installer refuses to replace an existing ZAY configuration.
It installs root-owned configuration and project ingest secrets readable only
by root and the Vector service, validates the result, then activates the service.
Do not run it with shell tracing. Do not put credentials on command arguments.
Only the **path** appears in the example.

Inspect `systemctl is-active vector`, the service RSS, and a uniquely marked
Docker/journal canary read back from the destination DuckBug project. Check
`service`, `release`, `serverName` and timestamp, not just an HTTP success code.
Production canary receipts belong outside this public repository.

## Stop and rollback

`systemctl stop vector` gracefully stops collection. `systemctl disable vector`
prevents automatic startup. Neither command changes application containers or
their data. Keep `/var/lib/vector` when stopping; deleting it discards source
checkpoints. A later configuration change must be validated and reviewed before
reload; preserve the previous config and ingest secret file privately.

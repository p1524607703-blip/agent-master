# CPO rolling release operations

`release.py` verifies application and engine commits against GitHub. The existing
lock and expected-current guard remain mandatory; preparation does not switch traffic.

Activation starts an immutable blue/green service on loopback 8001/8002, verifies
its release header and anonymous authentication boundary, then warms the latest
daily/monthly read models. Candidate startup is enabled before cutover so a reboot
during draining can recover it. Nginx validates the complete configuration before
reload and retains existing connections. Public frontend/backend version and auth
checks must pass before the active state commits. Previous assets stay available.

Build, complete-day and catalog snapshots use release namespaces, inferred from
immutable release directories for scheduled warmers too. Activation never clears
live snapshots or locks. A legacy rollback app without namespace support uses the
verified launcher with Redis disabled; its local cache remains. This compatibility
path may be slower and needs separate verification.

Retirement requires three consecutive zero-connection samples before stopping the
inactive service. There is no forced deadline for active streams. The timer retries
every 15 seconds; another release refuses to reuse a draining slot. Persistent
streams need investigation. The original 8000 backend is pinned before cutover;
once it drains, Nginx provides the stable internal 8000 endpoint.

`cpo-console.service` becomes an aggregate requiring the active slot after
retirement. Active status alone does not prove health. Check `shared/rolling.json`,
actual slot process/readiness, `cpo-console-blue`/`cpo-console-green` journals,
request diagnostics and retirement timer. The monitor restores the aggregate after
slot restarts. Private recovery manifests and host backups are in
`shared/rolling-backups`; source and approval stay Git-pinned.

Pre-commit failure restores exact Nginx files and frontend/current links; a
candidate already serving requests drains even on rollback. Post-commit retirement
failure is a maintenance warning and cannot roll back to an exited process.
Reactivate a previous app in the other slot using the current verified engine.

Verification includes date contracts, complete/truncated/cancelled streams,
permissions/financial invariants, injected activation/rollback failures, cache
isolation and a controlled stream longer than the previous 90-second stop window
across cutover and rollback. No paid model calls are required.

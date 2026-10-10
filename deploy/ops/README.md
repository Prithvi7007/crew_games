# CREW Operations Gateway — Phase 2 candidate

**Not installed. Not connected to the live MCP bridge. Production deploys are not supported yet.**

This change introduces a candidate **host-side, finite-operation Unix-socket gateway** for CREW. The intention is to make limited vetted operations callable by ChatGPT without giving its development MCP general root shell access. All changes need host security review before systemd activation.

## Protocol

The request is a newline-terminated JSON object of at most 2048 bytes. Replies are newline-delimited JSON. Unknown operation names and extra fields fail closed. There is no arbitrary command, path, environment or database-name parameter.

| Operation | Effect |
|---|---|
| capabilities | Lists allowed operations; deployment_enabled is false |
| release_preflight | Read-only pinned commit, worktree and backup integrity checks |
| start_v15_rehearsal | Launches a fixed script that restores a backup and migrates ONLY a disposable DB |
| rehearsal_status | Returns the sanitized result of a rehearsal job |

The v15 release and recovery backup are pinned in code. Rehearsal refuses unexpected Git SHAs, modified backup contents and already-existing scratch databases. A missing local root-owned enablement marker forbids starting rehearsals.

**The gateway does not support production deployment, code rollback, live database upgrades, general command execution, or restoring a backup over production.**

## Trust boundary

ChatGPT -> existing restricted CREW MCP bridge -> dedicated group-protected Unix socket -> root-owned operations gateway -> fixed vetted script.

The host gateway, systemd unit and executable script must be copied by an operator into the root-owned, non-group-writable /usr/local/libexec/crew-ops directory. Never execute privileged scripts directly out of the /opt/crew deployment tree. Only the socket should be accessible to the bridge container, NOT any host secrets, PostgreSQL sockets, Docker socket, root filesystem, or SSH keys.

The example bridge client in bridge_client.py still requires an independently reviewed bridge adapter and Docker socket mount. The development bridge resides in a *different project* (/opt/crew-dev-bridge), so merging this branch does not add MCP tools to ChatGPT.

## Trust-boundary security correction (Phase 3)

The first candidate rehearsal sourced a helper script from the application checkout
as root and launched the application-owned Python interpreter as root. That would
have crossed the privilege boundary from an application-writable directory into
the host operations service. **Do not install or execute that earlier script.**

The hardened rehearsal parses the root-owned environment with system Python
instead, validates file and parent-directory ownership and permissions, refuses
an unexpected production database name/port, and runs production Git inspection
as the unprivileged CREW account. Timed-out subprocesses run in their own process
groups so the gateway can terminate children rather than only the parent shell.

These corrections are still only an offline review candidate. The host security
review, local PostgreSQL cluster confirmation and controlled acceptance test
remain mandatory.


## Read-only installation preflight (new)

The standalone `host_readiness.py` is an **inspection tool only**. It checks
the pinned production/staging commits, unchanged worktrees, root-owned
production configuration permissions **without loading credentials**, matching
backup hashes, PostgreSQL archive readability, active CREW service, and the
local PostgreSQL cluster with an unused scratch database. It reports only
PASS/FAIL/INFO, never database URLs or secrets.

An operator must review it and stage a copy in a private **root-owned**
directory before running it on the VPS. The check does not call systemctl
start/restart, create databases, change the deployed git checkout, or invoke
the migration. It does not install the gateway or expose any new MCP tool.

An existing or unexpected scratch database, modified release checkout, lost
checkpoint, unhealthy application, or differing PostgreSQL cluster fails
closed. The optional crew-ops group/service/socket status is informational
because these are not yet installed.

**The gateway should remain disabled until this audit and independent host
security review pass.** A passing inspection alone does not authorize a
production deployment.

## Unprivileged Git inspection (additional installation prerequisite)

The production checkout and the staged worktree share Git metadata under the
application repository. A privileged Git status command can invoke configured
helpers (for example, filesystem monitors) from that metadata. **Never run
Git status or commit inspection as root against either checkout.**

The gateway, preflight, and rehearsal now run all Git inspection as the
unprivileged `crew` user, with a narrowly pinned safe.directory setting for
the root-created staging path and `core.fsmonitor=false`. A staging path that
cannot be inspected as `crew` must fail closed; do not revert to root Git.
This change supersedes the earlier merged host_readiness.py version. Before
installation, stage the reviewed newer revision only.

## Mandatory host acceptance review before any activation

1. Review the pre-existing v15-migration-rehearsal.sh for scratch DB isolation, correct local PostgreSQL cluster/port, cleanup on failure, and secrets handling. Confirm preservation and age of the recovery checkpoint.
2. Review host_service.py and crew-ops.service; run systemd-analyze verify and a supervised installation test. This Git change does NOT install the service.
3. Create a dedicated crew-ops group. Grant only the verified bridge service identity permission to access the operations socket; check Docker UID/GID behavior after container recreation.
4. Initially leave /etc/crew/ops-rehearsal-enabled ABSENT and verify that only preflight/capability reads work. The optional marker must be a root-owned mode 0600 regular file containing exactly enable-v15-rehearsal. Enable only after a reviewed scratch-only test plan.
5. Verify the bridge cannot edit the installed gateway, change the installed scripts, inspect host credentials or execute arbitrary host commands.
6. Verify scratch migration, cleanup, and that live service health and production database revision remain unchanged.

## Important limitations and future work

- **No deployment method is implemented in this phase.** Later deployment must bind a short-lived human approval to exact commit SHA, artifact hashes, verified backup, migration plan and operation; an MCP-provided "approved=true" field must never count as approval.
- This rehearsal is pinned to the v15 migration and not a generic migration engine.
- Job statuses are in memory and reset by service restarts. The systemd proposal kills in-progress jobs on service shutdown. Durable jobs and recovery tracking are required before long-running production use.
- Never automatically downgrade the database or restore a previous backup over live user activity. Only code rollback where schema compatibility has been verified.
- CI and host acceptance tests must pass; current tests alone do not prove this host service is safe.

## Bridge adapter outline

After review and installation, copy bridge_client.py into the separate bridge project and register only four fixed FastMCP methods delegating to its four client functions. Refresh the ChatGPT MCP tool inventory. Do not add a general-purpose execute-shell MCP tool.

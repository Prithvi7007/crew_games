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

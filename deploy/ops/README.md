# CREW Operations Gateway — unprivileged read-only phase

**State: candidate update for the installed gateway. It is not deployed by
merging this PR. Production deployments and migrations remain disabled.**

## Why the gateway identity changes

On the VPS, the original root-owned gateway with
`NoNewPrivileges=yes` could not switch to `crew` with `runuser`.
All four Git preflight checks therefore failed. A supervised systemd
diagnostic running Git directly as `User=crew` passed under comparable
sandbox restrictions.

The correct design is to separate privileges, **not disable the protection**:

1. **MCP-facing read-only gateway:** `User=crew`, `Group=crew-ops`,
   `NoNewPrivileges=yes`, `ProtectSystem=strict`. It inspects only the
   pinned CREW production and staged Git worktrees, directly as `crew`.
   It accepts NO command, executable, filesystem path, environment or
   target database name from MCP.
2. **Future privileged worker:** Separate, tightly scoped service for
   verified backups, scratch migration rehearsals and eventually approved
   deployments. This does not exist yet. Never grant the gateway privileged
   host access or mount production secrets into the development MCP.

## Read-only protocol

Requests are newline-delimited JSON over `/run/crew-ops/ops.sock`:

| Operation | Result |
|---|---|
| `capabilities` | Reports the two read-only methods; `deployment_enabled=false` and `rehearsal_enabled=false` |
| `release_preflight` | Reports pinned production/staging SHAs and clean-worktree checks |

An explicit attempt to call `start_v15_rehearsal` is always rejected.
Arbitrary shell commands, production deployment and backup restoration are
also rejected. The read-only preflight returns `git_ready=true` when
Git checks pass, but **always returns `ready=false`** because protected
backup validation and migration rehearsal require the future privileged
worker. Do not interpret `git_ready` as authorization to deploy.

## Operator review / controlled VPS upgrade

After reviewing a specific, immutable merged commit:

- Leave the running CREW Games `crew.service` and its database untouched.
- The already-installed binary directory
  `/usr/local/libexec/crew-ops` is currently root-owned mode 0700,
  with `host_service.py` root-owned mode 0400. The new **unprivileged**
  service cannot read those paths. An operator must change the directory
  to root-owned mode 0755 and the gateway Python file to root-owned
  mode 0444. Neither directory nor file must ever become writable by
  `crew`, `www-data` or `crew-ops`.
- Stop **only** `crew-ops.service` before replacing its gateway file and
  systemd unit with the reviewed, pinned commit. Copy the corrected systemd
  unit to `/etc/systemd/system/crew-ops.service`, root-owned mode 0644.
  Run `systemd-analyze verify`, reload systemd and start
  `crew-ops.service` again. Do not enable the separate rehearsal marker.
- systemd's `RuntimeDirectory=crew-ops` creates
  `/run/crew-ops` with owner `crew:crew-ops` mode 0750. The gateway's
  Unix socket should have owner `crew:crew-ops` and mode 0660.
  Only the eventual restricted MCP bridge identity should gain access
  to the socket group; **do not** add the `crew` application service to
  a privileged group.
- Run explicit local protocol tests for capabilities, Git readiness,
  rejected shell/deployment/rehearsal requests and no credential disclosure.
  Verify production health and the deployed application commit independently.

No root-owned script in the gateway directory is executed by this read-only
service. The existing v15 migration rehearsal shell script remains only a
security-review candidate for a separate isolated execution worker.

## Next architecture milestones

- A strictly controlled **privileged backup/migration worker** with
  root-owned immutable scripts, scratch DB collision checks and tested
  cleanup behavior.
- Signed, short-lived, **out-of-band human approval** bound to release SHA,
  release artifact digest, verified fresh backup, migration plan and operation.
  An MCP-provided `approved=true` flag must never count as authorization.
- A deployment state machine with locking, accurate live-game maintenance
  handling, health checks, durable audit records and code-only rollback
  where schema compatibility permits. **Never** automatically downgrade
  or restore a prior database over new player progress.
- A separately reviewed adapter in the independent
  `/opt/crew-dev-bridge` project. Merging the CREW application repository
  does not update the installed MCP bridge.

The production database, player profiles, scores and activity should never
be touched by upgrading this read-only service.

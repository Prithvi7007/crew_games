# CREW Ops v2 — controlled MCP host operations

## Delivery boundary

This PR implements the **host service, offline tests, systemd unit, one-time
root-operated installer and external-bridge client adapter**. It does not
silently grant the existing Docker bridge root access. **Merging this PR
does not install or activate any VPS service or add tools to the already-running
MCP server.** The installer and bridge integration must be accepted once by a
human with host authority; see below.

This service is independent of `crew.service`, the existing unprivileged
`crew-ops.service`, and the already-installed *v15-only* deployment worker.
Do **not** clear or rewrite the worker's preserved
`halted / step_failed` status, rerun v15, or restore PostgreSQL.

## Fixed MCP operations (NO caller arguments)

| Bridge function | Root-host operation | Effect |
|---|---|---|
| `crew_maint_capabilities` | `capabilities` | Read operation list / limits |
| `crew_maint_dashboard` | `dashboard` | Read active services, live SHA, ready endpoint, DB revision and 3 **counts**, no personal details |
| `crew_maint_assets` | `asset_diagnostics` | Read exact JS/CSS file mode/size, www-data access, local HTTPS status/MIME |
| `crew_maint_incidents` | `incident_summary` | Categorized Nginx error-log tail + prior worker status; **never raw logs** |
| `crew_maint_status` | `maintenance_status` | Last action and approval presence, not the approval content |
| `crew_maint_plan_asset_repair` | `plan_repair_react_assets` | Exact owner/asset digest plan, read only |
| `crew_maint_plan_restart` | `plan_restart_crew` | Exact deployed commit plan, read only |
| `crew_maint_execute_asset_repair` | `execute_repair_react_assets` | One-time host-approved fd-scoped `0644` on player.js/CSS ONLY |
| `crew_maint_execute_restart` | `execute_restart_crew` | One-time host-approved `crew.service` restart and ready check |
| `crew_maint_code_release_plan` | `code_release_plan` | Read a **root-installed**, pinned, code-only release manifest |
| `crew_maint_execute_code_release` | `execute_code_release` | Host-approved backup → pinned checkout → assets → restart → integrity checks |

The RPC is finite JSONL on `/run/crew-maint/maint.sock`, owned
`root:crew-ops` mode `0660`. Requests can include **only** a single
`operation` enum; unknown fields, paths, URLs, commands, Git refs, SQL and
shell input are rejected. No database updates, restores or migrations are
accepted. Bridge access alone does not authorize production mutation.

The privileged service runs in its own systemd sandbox with strict filesystem
mounts, no non-local network access, and a root-owned code directory. Its
fixed Git operations execute under `crew`, never Git as root. The production
service itself runs separately. The service never executes any code from
a bridge-provided path. Both repairs and releases use a digest-bound,
root-only, single-use approval consumed BEFORE work starts, expiring in 10m.
Root-only audit entries are append-only within `/var/lib/crew-maint`.

## One-time host installation — after reviewed PR merge

**Before installing:** independently review the merged SHA, source, tests,
systemd policy, and exact hashes in the PR. Verify `crew.service` and
`/health/ready` are healthy. No installer command should change the production
checkout or its database.

From the VPS, with a `root` SSH session and the exact approved merge SHA
substituted for `<REVIEWED_MERGE_SHA>`:

```bash
set -euo pipefail
REVIEWED_SHA="<REVIEWED_MERGE_SHA>"
runuser -u crew -g www-data -- git -C /opt/crew fetch origin main
runuser -u crew -g www-data -- git -C /opt/crew show \
  "$REVIEWED_SHA:deploy/ops/install_maintenance_v2.py" \
  > /root/install_crew_maint_v2.py
chmod 0400 /root/install_crew_maint_v2.py
python3 -I -B /root/install_crew_maint_v2.py "$REVIEWED_SHA"
```

The root-only installer **refuses overwriting an existing v2 installation**.
It reads the three exact artifacts from that Git object, prints SHA-256s,
asks the human to type `INSTALL CREW OPS V2`, installs a separate unit,
runs `systemd-analyze verify`, and enables only
`crew-maint-v2.service`. There is **no CREW restart**, migration or code
checkout reset. It does not install future release plans by default.

### External MCP bridge integration (separate project)

The CREW development bridge is at `/opt/crew-dev-bridge`, outside this
application repository. It must be updated **once**, in its reviewed
source and Docker Compose configuration:

1. Mount **only** `/run/crew-maint:/run/crew-maint:ro` into the bridge
   container; leave root filesystem, database socket, Docker socket,
   PostgreSQL credentials, and private keys unmounted. Ensure the bridge
   identity has the existing restricted `crew-ops` group access.
2. Copy/review `deploy/ops/bridge_maintenance_v2_client.py` into the
   bridge source, and explicitly register the eleven zero-argument methods
   as MCP tools. Do **not** add a generic `command`, `path`,
   `release_sha`, or other user-input passthrough. Use the actual server
   framework's registration API, not an assumed decorator signature.
3. Recreate **only** the development bridge container (for a new bind
   mount/socket inode), then call `capabilities`, `dashboard`,
   `asset_diagnostics`, `incident_summary`, and `maintenance_status`
   as read-only acceptance tests.

Until that bridge installation is done, the newly authored MCP tool names
will NOT appear in ChatGPT. This repo's deployment bridge cannot directly
change the separately hosted bridge's Python registration/Compose files.
Do not report end-to-end installation as complete merely because this PR
merged.

## Repairs/restarts: operator approval (not MCP self-approval)

Ask MCP for `plan_repair_react_assets` or `plan_restart_crew`.
It returns the exact action, current production commit and plan digest.
An operator can independently run **only** the approval helper on the VPS:

```bash
python3 -I -B /usr/local/libexec/crew-maint/maintenance_v2.py approve repair_react_assets
# OR, for a different action:
python3 -I -B /usr/local/libexec/crew-maint/maintenance_v2.py approve restart_crew
```

Confirm the on-host plan matches the requested action, then type the exact
phrase shown. This only stages one root-owned, expiring approval and **does
not execute** it. The corresponding MCP `execute_*` call consumes it
exactly once. Failed steps are recorded using sanitized error codes; no
automatic retry or database restore.

## Future releases

The v15 release worker is intentionally fixed and cannot be reused for v16.
Ops v2 adds reusable **code-only** releases (no database schema migration,
new dependencies, Nginx/systemd change, or automatic restore).
When a release PR is reviewed and merged, prepare a clean, unprivileged
`/opt/crew-release-candidate` worktree pinned to the reviewed commit,
with compiled React assets already committed and CI evidence reviewed.
The host operator then installs a root-owned `0400` JSON manifest at
`/usr/local/libexec/crew-maint/code_release_manifest.json`:

```json
{
  "format": 1,
  "kind": "code_only",
  "base": "<CURRENT_PRODUCTION_40_HEX_COMMIT>",
  "release": "<REVIEWED_RELEASE_40_HEX_COMMIT>",
  "db_revision": "v15_badges",
  "reviewed_pr": 123
}
```

**This JSON is a format example; do not install placeholders.**
It must be installed by the operator in the protected host directory, never
generated from MCP parameters. The code-only plan requires the exact base,
clean production and candidate worktrees, matching staged SHA and DB
revision, healthy application, and zero differences in `alembic/`,
`app/migrations.py`, requirements or server deployment configuration.
Before a code switch it runs the existing backup unit, verifies the fresh
backup's SHA-256 and `pg_restore --list`, rechecks the candidate, switches
code as unprivileged `crew` with a safe child umask, verifies Nginx can
read React assets, restarts CREW, verifies readiness and non-decreasing
record counts + unchanged database revision. It **never restores or
downgrades PostgreSQL**, and preserves a failure record.

The host operator approves via:
```bash
python3 -I -B /usr/local/libexec/crew-maint/maintenance_v2.py approve deploy_code_only
```
Then MCP calls `execute_code_release`, which returns `phase=queued`
immediately. Poll `maintenance_status` and live health until it reports
`succeeded` or a sanitized failure code. The background operation may take
several minutes. An interrupted host worker records `worker_interrupted`
when it restarts; no automatic retries, restores or downgrades are performed.

Releases requiring database migrations or infrastructure changes are
**deliberately rejected** and need their own tested pinned migration plan,
operator approval, scratch rehearsal and backup protection. Do not call
a code-only release a general-purpose schema migration mechanism.

## Boundaries, testing and acceptance

- Independent host install + external MCP bridge registration is mandatory.
- Root approval always requires a human in an interactive host terminal;
  ChatGPT cannot create it through the MCP protocol.
- Use offline `pytest` and React build on the branch, test a live read-only
  diagnostic snapshot after installation, and check each result is sanitized.
- Check `crew.service`, `nginx`, `/health/ready`, the public
  `player.js` and `player.css`, 14 or more player profiles and 111 or
  more saved game completions after the original v15 incident; these are
  observational benchmarks, not values hardcoded into future releases.
- The historical `crew-deploy.service` v15 halt state must not be changed.

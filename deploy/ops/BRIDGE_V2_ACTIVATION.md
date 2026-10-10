# Activate CREW Ops v2 on the existing development bridge

## Scope

This patch is a one-time, **version-preserving** adapter installer.
The independent host-side `crew-maint-v2.service` has already been installed
through merged CREW PR #20. It creates a `root:crew-ops` 0660 socket at
`/run/crew-maint/maint.sock`.

**The separately hosted `Prithvi7007/crew-dev-bridge` repository's GitHub
`main` currently does not contain all the manually installed production
diagnostics and deploy-bridge integrations. Do not `git reset --hard`,
`git pull`, overwrite `bridge/server.py` or replace `compose.yaml`
from that stale upstream branch.** The live VPS bridge registers more tools
than the old GitHub copy. This script preserves them.

## What this installer does

1. Verify the root-owned live files `/opt/crew-dev-bridge/bridge/server.py`
   and `/opt/crew-dev-bridge/compose.yaml` match the inspected structures.
2. Insert the eleven fixed zero-argument maintenance MCP wrappers **before**
   `if __name__ == '__main__'` and add one read-only mount
   `/run/crew-maint:/run/crew-maint:ro` next to the existing
   `/run/crew-deploy` mount, without touching runner settings.
3. Back up both old files under a root-only timestamped
   `/root/crew-bridge-backups/` subdirectory.
4. Verify Python syntax and `docker compose config`; on this validation
   failure, automatically restore both files from the captured originals.
5. **Rebuild and recreate only the `bridge` service**, not runner or CREW.
6. Verify the bridge can see the socket and perform the fixed
   `capabilities` RPC as its unprivileged container identity.

The inserted MCP tools accept no commands, filesystem paths, URLs, SQL,
arbitrary arguments or caller-provided release revisions. Mutating host
operations still require root-owned, one-time, ten-minute approval via the
protected host service; v15 deployment cannot be rerun.

## Installation after PR merge and review

From the VPS root terminal, use the reviewed PR **merge commit** SHA (full
40 characters) after replacing the placeholder. This fetches code into
Git objects but **does not check out or deploy** the main CREW app:

```bash
set -e
MERGED_SHA="<EXACT_REVIEWED_40_CHAR_MERGE_SHA>"
runuser -u crew -g www-data -- git -c safe.directory=/opt/crew \
  -C /opt/crew fetch origin main
runuser -u crew -g www-data -- git -c safe.directory=/opt/crew \
  -C /opt/crew show "$MERGED_SHA:deploy/ops/activate_bridge_v2.py" \
  > /root/activate_crew_bridge_v2.py
chmod 0400 /root/activate_crew_bridge_v2.py
python3 -I -B /root/activate_crew_bridge_v2.py
```

Read the plan and type **ACTIVATE CREW OPS V2** at the host-only prompt.
The script will refuse to proceed if the live bridge is structurally
different, the socket is missing, or the tools appear partly installed.

On success it prints `CREW OPS V2 BRIDGE SOCKET CONNECTED`. Refresh or
reconnect ChatGPT's MCP tool list; tool-schema caching may require a new chat.

## Post-install verification

Check eleven new `crew_maint_*` tools are visible. Call
`crew_maint_capabilities`, `crew_maint_dashboard`,
`crew_maint_assets`, `crew_maint_incidents` and `crew_maint_status` as
read-only smoke tests. Do not execute an action merely to verify a tool.

If a container rebuild fails, the original files are preserved in the
root-only backup. Do **not** reset the CREW application, restore PostgreSQL
or rerun the pinned v15 migration. Review the diagnostic error and bridge
container logs; restore only the two modified bridge files if needed.

## Follow-up repository reconciliation

The host and upstream bridge repositories still need an independently
reviewed source reconciliation PR. Until this is done, do not deploy
`crew-dev-bridge` via `git reset --hard origin/main`: that could discard
the live production diagnostics and deployment socket tools. The activation
installer intentionally avoids modifying those existing functions.

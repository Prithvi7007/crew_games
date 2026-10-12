# CREW MCP auto-release trigger (one-time VPS installation)

The installer adds two fixed, zero-argument MCP tools: crew_trigger_auto_release (starts only the existing crew-auto-release.service), and crew_auto_release_status (reads unit state and deployed Git commit).

It does not start a deployment during installation. The merged-PR release watcher, five-minute timer, and independent pinned-release approval worker remain unchanged.

## Install from a pinned GitHub commit

1. Download ops/mcp/crew_mcp_auto_release_installer.py from the exact commit SHA and verify SHA-256 against the published value.
2. Review the source.
3. Dry run: python3 /root/crew_mcp_auto_release_installer.py
4. Install: python3 /root/crew_mcp_auto_release_installer.py --apply
5. Type ENABLE CREW MCP AUTO RELEASE at the prompt.
6. Refresh or reconnect the CREW MCP connection if the two tools don't appear immediately.

The installer backs up three root-owned Python files under /root/crew-mcp-autorelease-backups/, updates fixed allowlists/handlers, restarts crew-maint-v2.service, and rebuilds/recreates ONLY the MCP bridge container. It does not restart the game app or launch a release. It attempts rollback if installation fails.

## Safety

This adds a privileged capability: authorized MCP callers can request the existing production watcher to run. Keep the private MCP tunnel restricted to trusted administrators. No caller-supplied command, SHA, unit name, path, or shell is accepted.

A successful MCP trigger means queued or already_running, not deployed. Confirm the production commit and health after the watcher completes.

The installer was tested against supplied excerpts of the current gateway and bridge. The live VPS dry run is required because the full host environment is not available from MCP.

# CREW Operations Bridge — Phase 1 (review draft)

## Goal
Enable a future narrowly scoped MCP operations service to rehearse the v15 badge migration without risking the live PostgreSQL database. This PR is **not** the server-side bridge implementation, a deployment endpoint, or authorization to deploy.

## First operation: `v15_migration_rehearsal`
Proposed MCP payload: `{"operation":"v15_migration_rehearsal","release_sha":"f4a35026d1df0e86e987d4bca310b8d32aed4134"}`.

The host service would map that enum to `deploy/v15-migration-rehearsal.sh`, with a fixed working directory and no caller-supplied command, executable, script path, shell arguments, database name or environment. The script requires the already staged worktree and previously verified backup. It refuses dirty or unexpected checkout SHAs, rejects an existing scratch database, takes a rehearsal lock, and checks backup contents and SHA-256 equality with the protected copy. It restores into `crew_v15_migration_test`, runs the *staged release's* Alembic upgrade, validates the schema and saved-record counts, and deletes **only the scratch database it created**.

### Integration requirements — must be completed before enabling
- Audit and test the script *on the VPS* against a production-shaped copy. The development sandbox cannot execute it on the host.
- Keep MCP's existing production-health snapshot tool read-only; put operations behind a separate protected host service. Never mount the Docker socket, host root, PostgreSQL socket, environment file, or Git credentials into the development MCP container.
- Have the host service accept strict enums and full immutable commit SHA only. Enforce one-job-at-a-time locking, a wall-clock timeout, redacted capped output, and append-only per-job audit records.
- Protect host-service invocation with mutually authenticated Unix socket or equivalent internal authorization. No untrusted network-exposed shell execution.
- Check `crew_v15_migration_test` does not already exist *before* running the script; an existing scratch DB must never be deleted.
- Expose `prepare`, `status`, `rehearse`, `deploy`, and `rollback` as separate operations. They must not silently fall through to production writes.
- **Production execution must remain disabled** until a separate approval design binds a one-time, short-lived operator authorization to the exact SHA, artifact/build digest, backup, migration plan and operation. Do not treat model-provided `approved=true` as authorization.
- Deploys must check branch/CI, pinned dependencies/assets, fresh verified backup and scratch migration rehearsal. Plan for maintenance mode and concurrent game writes during schema migration.
- Treat application code rollback and *database recovery* separately. Never automatically downgrade Alembic or restore an old database over player activity.

## Deployment setup (not yet performed)
The operations agent must be installed, sandboxed, reviewed and connected independently of the production Flask process. Its script path should be host-owned and immutable to its executing identity; an MCP-callable tool must not be able to edit the scripts it runs.

## Current status
Draft rehearsal script in this feature branch only. No host execution or production deployment.

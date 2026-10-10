# CREW v15 pinned deployment worker — DRAFT, NOT LIVE

This is a new privileged service and must NOT be installed or enabled simply
because this PR merges. It requires host security review and a rehearsal
against a restored production backup. The running read-only CREW Operations
Gateway remains unchanged.

## Security architecture

The separate root-owned broker uses a Unix domain socket:
  /run/crew-deploy/deploy.sock

It accepts exactly four fixed operations:
- capabilities (read-only)
- release_plan (read-only; displays exact SHA and plan digest)
- release_status (read-only; redacted durable status)
- execute_v15 (production-changing, independently approved)

There is NO arbitrary shell, dynamic release SHA, DB restore, schema downgrade,
environment injection, or direct command execution. No secrets or PostgreSQL
credentials are passed to ChatGPT.

A production-changing request requires a separate, root-created approval at:
  /var/lib/crew-deploy/approval-v15.json

The approval is created ONLY by an operator running the root-only on-host
approve_v15.py script and typing DEPLOY CREW V15. It is valid ten minutes,
can only authorize the one pinned release and source commit, and contains a
plan hash binding the installed executor, scratch rehearsal script, and
preserved October 10 backup. The broker atomically consumes each approval
and rejects nonce reuse before starting the worker. ChatGPT cannot approve
itself by supplying a flag.

## Release execution order

1. Exclusive lock, pinned production and staged checkout checks, clean trees.
2. Production readiness and v14 Alembic revision.
3. Pre-migration integrity checks and production row counts.
4. Fresh CREW backup via the existing scheduled backup unit, verified SHA-256.
5. Fixed scratch-only v15 migration rehearsal using that fresh backup.
6. Staged v15 additive Alembic migration, running as crew via systemd-run.
7. Pinned production code update as crew; restart only crew.service.
8. HTTP readiness, exact commit, v15 revision and record-count verification.

If anything fails, halt with a safe error and require operator review.
NEVER automatically restore a stale backup over new player activity, downgrade
the DB or perform historical badge backfill.

## Pinned initial release

Previous production: c5a9275629ba4389c2b66a14b61a523868d40673
Target release: f4a35026d1df0e86e987d4bca310b8d32aed4134
Staged code: /opt/crew-v15-rehearsal
Recovery checkpoint:
  /var/backups/crew/release-checkpoints/pre_v15_20261010T001254Z.dump

The worker is NOT a general-purpose deployment system. Later releases need
reviewed pins, migrations, CI checks, and a new approval plan.

## Host installation checklist — not executed

- Independently inspect all script contents at the exact merged SHA.
- Confirm the deployed root-owned code is NOT writable by the crew user.
- Confirm the original read-only crew-ops.service remains unchanged.
- Copy the broker, engine, approval helper and tested migration-rehearsal
  script to /usr/local/libexec/crew-deploy, owned root and mode 0400, with
  a root-owned non-writable directory.
- Install the separate reviewed crew-deploy.service and run
  systemd-analyze verify before starting it.
- State directory /var/lib/crew-deploy must be root-only mode 0700.
- The new socket must be root:crew-ops mode 0660 under a protected directory.
  Never expose it externally. Never mount the host root filesystem, database
  socket, secrets or Docker socket in the MCP bridge.
- Before granting approval, ensure execute_v15 returns
  out_of_band_approval_required and does NOT modify production.
- Test the rehearsal on the real host against the dedicated scratch database.
  Verify the scratch database is deleted, player records remain intact and
  production remains on v14.
- Bridge the new socket through a separate restricted mount and register
  only three fixed additional MCP methods (plan, status, execute_v15).
- Validate production readiness and backup recovery immediately before
  authorizing the first live deployment.

## Known limitations requiring host review

- The worker and the v15 rehearsal are not yet host-tested.
- The rehearsal now restores and migrates the latest fresh checksum-verified
  backup into the dedicated scratch database, comparing existing record
  counts before and after the migration. This host behavior still requires
  independent end-to-end testing before allowing production writes.
- The privileged broker needs NoNewPrivileges=no to launch runuser and
  systemd-run. This exception is confined to the separately protected worker;
  it must NEVER weaken the original crew-ops.service.
- Authorization is intentionally on-host and requires one SSH approval step.
  Future GitHub protected environment approval or a separately authenticated
  operator UI can remove that step, but must not allow MCP to self-approve.
- Service crashes during deployment require incident review; there is no
  automatic database rollback or code rollback in this first candidate.

DO NOT activate the production-changing socket before completing the above.

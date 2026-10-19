# CREW merged-PR code-only automatic deployments

## Security contract

**Merge is the operator's release approval**, provided GitHub independently
reports that **Prithvi7007** merged the PR into **Prithvi7007/crew_games:main**
and the **push-triggered** CREW quality gate on that exact merged commit
completed successfully, including the React build and committed artifact
comparison, Python tests, migration smoke test and dependency audit.

This is a separate **root-installed, root-owned, periodic systemd one-shot
watcher**. It does not accept a release SHA or arbitrary command from ChatGPT,
the development bridge, a PR body, or a webpage. GitHub is queried over HTTPS
without any token or deployment secret. Git operations run as the unprivileged
CREW application user, not root.

### Requirements to release

- Current main SHA differs from the exact live production SHA.
- Candidate and production worktrees are clean, owned by crew, and have
  exactly the approved public GitHub origin.
- The first-parent path from production to target must consist *entirely* of
  GitHub PR merge commits, each merged by Prithvi7007 into main. Direct pushes
  and unverifiable commits block release. At most 32 intervening merges.
- A successful **push event** on the exact main SHA for the fixed CREW quality
  gate workflow ID, with all five named required steps successful.
  PR checks alone are not sufficient.
- DB revision matches the explicitly reviewed v16_trophy_tour guard. No changed Alembic migrations, requirements,
  app migrations, or protected Nginx/systemd configuration.
- No pending manually staged approval or simultaneous maintenance action,
  no previous failed/interrupted automatic release, and no unknown/manual release manifest already installed. The auto-deploy
  manifest is root-only in /var/lib/crew-maint/merge_auto_manifest.json;
  the original manually approved manifest location is unchanged.
- Reuses the existing host code-only release engine: fresh protected database
  backup + checksum and pg_restore validation, exact code checkout, asset
  readability, application restart, readiness and non-decreasing data counts.

**Not a migration deployer.** Dependency changes, infrastructure changes and
DB revisions other than v16_trophy_tour halt the path. No database migration or
restore is attempted. There is **no unattended rollback**. A failure after
code switch stays failed and blocks future automatic releases until reviewed.
Existing v15 deployment status remains untouched.

### Timing and control

The crew-auto-release.timer checks approximately every 15 minutes.
No future manual deployment approval is needed **for eligible releases**.
Merging alone does not skip any safety checks. An ineligible PR requires a
separate reviewed release plan. Disable as root at any time:

    systemctl disable --now crew-auto-release.timer

The service needs outbound HTTPS to the fixed GitHub API hostname. It does not
write GitHub, receive GitHub tokens, or merge PRs.

## Upgrading an existing v15 watcher after production reaches v16

The separately installed root-owned watcher does **not** automatically change
when application code is merged or deployed. A stale watcher pinned to
`v15_badges` rejects a healthy `v16_trophy_tour` production database with
`schema_release_requires_manual_plan`. This release only changes the
watcher's **fixed allowlisted database revision**, not migration permissions.

First inspect the actual incident; exit code 1 alone does not prove its cause:

```bash
sudo journalctl -u crew-auto-release.service -n 40 --no-pager -o cat
sudo cat /var/lib/crew-maint/merge_auto_state.json
sudo systemctl show crew-auto-release.service -p Result -p ExecMainStatus
```

If the failure is compatible with the schema guard, after this fix PR is
**owner-merged** and its push-triggered main quality gate is green, stop the
timer and confirm the oneshot is not active. Use that exact **merge SHA**,
not the feature branch SHA:

```bash
sudo systemctl stop crew-auto-release.timer
sudo systemctl is-active crew-auto-release.service || true

# Execute the following in a root terminal, substituting the reviewed merge SHA:
REVIEWED_SHA="<EXACT_REVIEWED_FIX_MERGE_SHA>"
sudo -i
# Re-enter REVIEWED_SHA in the root shell to avoid relying on sudo's environment.
REVIEWED_SHA="<EXACT_REVIEWED_FIX_MERGE_SHA>"
runuser -u crew -g www-data -- git -C /opt/crew fetch --no-tags origin main
runuser -u crew -g www-data -- git -C /opt/crew show \
  "$REVIEWED_SHA:deploy/ops/upgrade_merge_auto_deploy.py" \
  > /root/crew-watcher-v16-upgrade.py
chmod 0400 /root/crew-watcher-v16-upgrade.py
python3 -I -B /root/crew-watcher-v16-upgrade.py "$REVIEWED_SHA"
```

The interactive installer verifies GitHub main ancestry, the owner's exact
merged PR, successful CI on that merge, the existing root-owned watcher,
**only** the single revision change, production's v16 schema and app health,
a clean checkout, stopped watcher/timer, and no pending manual approval.
It requires the confirmation phrase `UPGRADE CREW WATCHER V16`. It keeps
an immutable root-only backup and atomically replaces the watcher, without
deploying CREW, resetting state, restarting the application, or re-enabling
the timer. A mismatch or unknown installed watcher version **stops** the
upgrade; never force-overwrite an unfamiliar root-owned script.

**Before re-enabling:** inspect the prior `merge_auto_state.json` phase and
the journal. If `phase` is `failed`, `running` or `blocked`, leave the timer
stopped and perform a separate human-reviewed incident reconciliation. Do
not delete the state or manifest: the watcher intentionally fails closed.
If the durable watcher state is safe, start the timer and verify another
fixed watcher tick:

```bash
sudo systemctl reset-failed crew-auto-release.service
sudo systemctl start crew-auto-release.timer
sudo systemctl list-timers crew-auto-release.timer --no-pager
sudo journalctl -u crew-auto-release.service -n 25 --no-pager -o cat
```

A root-controlled code upgrade is a **distinct** step from a guarded
application release. The bridge's trigger can start only the previously
installed watcher; it cannot upgrade root-owned policy.

## One-time installation after this PR merges and CI passes

The trusted root maintenance controller must already be present and healthy.
Review the merged implementation and tests first. **Never install from a
feature branch.** The installer refuses to overwrite an existing candidate
or watcher. It prints SHA-256 hashes of installed artifacts for verification.

With the exact **reviewed merge SHA** of this auto-deploy PR:

    set -euo pipefail
    REVIEWED_SHA="<EXACT_REVIEWED_MERGE_SHA>"
    runuser -u crew -g www-data -- git -C /opt/crew fetch --no-tags origin main
    runuser -u crew -g www-data -- git -C /opt/crew show \
      "$REVIEWED_SHA:deploy/ops/install_merge_auto_deploy.py" \
      > /root/install_crew_merge_auto.py
    chmod 0400 /root/install_crew_merge_auto.py
    python3 -I -B /root/install_crew_merge_auto.py "$REVIEWED_SHA"

The root operator types ENABLE CREW MERGE DEPLOY once at installation. The
installer verifies that commit is in main history, prepares an independent
unprivileged candidate clone, installs root-owned code and systemd units,
and enables **only the timer**. It does not reset /opt/crew, perform a
migration, or restart crew.service.

**The first timer tick may deploy previously merged code** if every gate
passes, including Trophy Room badge PR #24 if still pending in production.

## Read-only verification

    systemctl status crew-auto-release.timer --no-pager
    systemctl list-timers crew-auto-release.timer --no-pager
    journalctl -u crew-auto-release.service --since today --no-pager
    systemctl status crew.service --no-pager
    runuser -u crew -g www-data -- git -C /opt/crew rev-parse HEAD

No caller-provided release SHA or force option exists. For blocked releases,
inspect the sanitized journal reason; do not delete state, bypass evidence or
reset the production checkout to make a safety gate pass.


## PR #25 post-restart readiness incident (one-time recovery)

The first automatic release switched production from
`f4a35026d1df0e86e987d4bca310b8d32aed4134` to
`5e53a3d3d281dd039fd5d1edd1bc550a2189f9b1`, but the immediate,
single-shot health probe ran before the Unix socket became ready.
The watcher deliberately retained `phase=failed`; subsequent checks report
`previous_release_needs_review`. Production was later independently verified
healthy, with database `v15_badges`, at least 14 profiles, 111 completions,
and 14 user stats, and both React assets served with HTTP 200.

This is **not** a reason to delete `merge_auto_state.json` or override
the deployment engine. The reviewed recovery adds a bounded (20 probes,
two seconds apart, plus each probe's existing timeout) post-restart wait,
and a one-time incident-specific operator reconciliation. The existing
maintenance daemon, database and backup safeguards are not modified.

After the repair PR is merged by the owner **and its merged-main CI succeeds**,
execute the following on the VPS as root, replacing the SHA with that exact
reviewed **merge commit** (not the feature-branch commit). The reviewed repair
commit may be an ancestor of current main after later PR merges; the recovery
verifies ancestry, the owner-merged PR, and successful CI on the original
reviewed repair commit:

```bash
set -euo pipefail
REVIEWED_SHA="<EXACT_REVIEWED_REPAIR_MERGE_SHA>"
runuser -u crew -g www-data -- git -C /opt/crew fetch --no-tags origin main
runuser -u crew -g www-data -- git -C /opt/crew show \
  "$REVIEWED_SHA:deploy/ops/reconcile_merge_auto_pr25.py" \
  > /root/reconcile_crew_pr25.py
chmod 0400 /root/reconcile_crew_pr25.py
python3 -I -B /root/reconcile_crew_pr25.py "$REVIEWED_SHA"
```

The script requires a root terminal and the phrase `RECONCILE CREW PR25`.
It rejects mismatched GitHub main SHA, missing owner-merge / passing main CI,
a changed prior root-owned watcher, a different failed release, absent
`post_restart_health_failed` journal evidence, untrusted manifest or state,
a concurrent release, unhealthy app, unreadable assets or regressed DB counts.
It preserves the failed state as
`/var/lib/crew-maint/merge_auto_pr25_failed_snapshot.json` (root-only),
installs only the new reviewed watcher source as a root-owned file, then
reconciles the *already deployed and verified healthy* PR #25 release.
It does not restart CREW, reset Git or change production application files.
The normal timer then evaluates PR #26 and the repair PR together, with all
usual GitHub, backup, readiness, and data-integrity requirements.
A blocked or interrupted recovery remains blocked for operator review.

Read-only verification afterward:

```bash
systemctl list-timers crew-auto-release.timer --no-pager
journalctl -u crew-auto-release.service -n 25 --no-pager
runuser -u crew -g www-data -- git -C /opt/crew rev-parse HEAD
```

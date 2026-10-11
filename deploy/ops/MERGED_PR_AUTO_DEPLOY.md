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
- DB revision remains v15_badges. No changed Alembic migrations, requirements,
  app migrations, or protected Nginx/systemd configuration.
- No pending manually staged approval or simultaneous maintenance action,
  no previous failed/interrupted automatic release, and no unknown/manual release manifest already installed. The auto-deploy
  manifest is root-only in /var/lib/crew-maint/merge_auto_manifest.json;
  the original manually approved manifest location is unchanged.
- Reuses the existing host code-only release engine: fresh protected database
  backup + checksum and pg_restore validation, exact code checkout, asset
  readability, application restart, readiness and non-decreasing data counts.

**Not a migration deployer.** Dependency changes, infrastructure changes and
DB revisions other than v15_badges halt the path. No database migration or
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

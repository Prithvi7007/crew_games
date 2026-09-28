# CREW Monday kickoff email

The job sends one email to the department distribution list every Monday at 8:00 AM America/New_York.

It contains:
1. The previous CREW week's final Top 10.
2. The cumulative season Top 10, frozen through the previous Thursday.
3. The new week's four-game schedule and links to CREW.

Only `competitive = 1` completions are counted. Archive/catch-up points are excluded.

## Required production environment values

Add these to `/etc/crew/crew.env`:

```bash
RESEND_API_KEY=re_xxxxxxxxx
CREW_EMAIL_FROM=CREW Games <games@your-verified-domain.example>
CREW_WEEKLY_EMAIL_TO=your-department-distribution-list@example.com
CREW_PUBLIC_URL=https://cadacrew.fun
```

## Dry run

```bash
sudo -u crew -g www-data bash -lc   'set -a; source /etc/crew/crew.env; set +a; cd /opt/crew && .venv/bin/flask --app run.py send-weekly-kickoff --dry-run'
```

## Real test

Temporarily point `CREW_WEEKLY_EMAIL_TO` to a safe test mailbox first.

```bash
sudo -u crew -g www-data bash -lc   'set -a; source /etc/crew/crew.env; set +a; cd /opt/crew && .venv/bin/flask --app run.py send-weekly-kickoff --force'
```

The app stores a weekly send receipt in the existing `system_settings` table so a normal second run skips instead of sending a duplicate.

## Install timer

```bash
sudo cp /opt/crew/deploy/crew-weekly-email.service /etc/systemd/system/crew-weekly-email.service
sudo cp /opt/crew/deploy/crew-weekly-email.timer /etc/systemd/system/crew-weekly-email.timer
sudo systemctl daemon-reload
sudo systemctl enable --now crew-weekly-email.timer
systemctl list-timers crew-weekly-email.timer --no-pager
```

## Logs

```bash
sudo journalctl -u crew-weekly-email.service --since today --no-pager
```

## Reference-date dry run

```bash
sudo -u crew -g www-data bash -lc   'set -a; source /etc/crew/crew.env; set +a; cd /opt/crew && .venv/bin/flask --app run.py send-weekly-kickoff --dry-run --date 2026-09-28'
```

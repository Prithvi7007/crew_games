# CREW v11 security checklist

- [ ] `TRUSTED_HOSTS=cadacrew.fun,www.cadacrew.fun`
- [ ] `SECRET_KEY` is random and >= 32 characters
- [ ] admin password >= 16 characters
- [ ] admin TOTP enabled
- [ ] `/etc/crew/crew.env` remains mode 640 and is not in Git
- [ ] `pytest -q` passes
- [ ] `pip-audit -r requirements.txt` reviewed before deployment
- [ ] `db-upgrade` completed on `crew_prod`
- [ ] `/health` returns OK through the Unix socket (with `Host: cadacrew.fun`) and HTTPS
- [ ] HTTPS certificate is valid for apex and www
- [ ] `systemctl is-active crew` is active
- [ ] PostgreSQL backup exists before deployment
- [ ] password change revokes a second browser session
- [ ] repeated failed player/admin logins return HTTP 429
- [ ] browser console reports no CSP violations during normal flows

# Runbook

All commands run on the VM in `/opt/traveldeal` unless noted.

## Everyday

| Task | Command |
|---|---|
| App logs | `deploy/compose.sh logs -f app` |
| Proxy / certificate logs | `deploy/compose.sh logs -f caddy` |
| Deploy log | `journalctl -u traveldeal-update -n 50` |
| Backup log | `journalctl -u traveldeal-backup -n 50` |
| Restart the app | `deploy/compose.sh restart app` |
| Deploy now | `sudo systemctl start traveldeal-update.service` |
| Back up now | `sudo systemctl start traveldeal-backup.service` |

## The site is down

1. `deploy/compose.sh ps`: are both containers `Up (healthy)`? If not, check `deploy/compose.sh logs app`.
2. Database errors (`DPY-` or `ORA-` in the logs)? In the console, check the Autonomous Database is **Available**. If it's **Stopped**, click **Start** and wait about 5 minutes.
3. Certificate errors? Check that the domain's DNS still points at the VM IP and ports 80/443 are open in the security list.
4. VM unreachable? Check it's running in the console. If Oracle reclaimed it, follow **Rebuild the VM** below. With Autonomous Database your data is safe there; in personal mode (SQLite on the VM), restore the newest nightly backup.

## Roll back a bad release

```bash
git log --oneline -5
git reset --hard <last-good-sha>
deploy/compose.sh up -d --build
```

Then revert the bad commit on GitHub, or the timer will redeploy it once its checks pass.

## Restore user data

Backups are at `traveldeal-backups/traveldeal/YYYY-MM-DD.json.gz`.

1. Download the one you want (console → bucket → object → Download) and copy it to the VM.
2. Restore only into an **empty** database (a new Always Free ADB, or after dropping the four `TD_*` tables):
   ```bash
   deploy/compose.sh run --rm -v "$PWD/2026-11-05.json.gz:/tmp/b.json.gz:ro" app \
     python -m traveldeal.backup --restore /tmp/b.json.gz
   ```
3. If you created a new database, update `ORACLE_DSN` in `deploy/.env` and the database ACL, then `deploy/compose.sh up -d`.

**Personal mode (SQLite):** run step 2 on the rebuilt VM *before* anyone signs in, because signing in creates a user and restore refuses a non-empty database. To start the SQLite database over from scratch: `deploy/compose.sh down && docker volume rm traveldeal_traveldeal_db && deploy/compose.sh up -d`, then restore.

Practice this once on a second Always Free database (you're allowed two) so you know it works.

## Rebuild the VM

Follow `DEPLOY_OCI.md` steps 3 and 9, then:

- Update the database ACL with the new public IP.
- Update the DNS A record.
- Update the dynamic-group rule with the new instance OCID.
- Copy `deploy/.env` and `.streamlit/secrets.toml` back from your password manager.

## Rotate secrets

| Secret | How |
|---|---|
| Database password | `ALTER USER TRAVELDEAL IDENTIFIED BY "<new>";` in Database Actions → update `deploy/.env` → `deploy/compose.sh up -d` |
| Cookie secret | New value in `secrets.toml` → `deploy/compose.sh up -d` (signs everyone out) |
| Google client secret | Google Cloud console → reset secret → `secrets.toml` → `deploy/compose.sh up -d` |

## Quarterly

- Update rotating categories (Chase Freedom Flex, Discover it); the monthly "Card data needs review" issue lists them.
- Restore-test one backup.
- `sudo apt-get update && sudo apt-get upgrade -y && sudo reboot` for OS patches.

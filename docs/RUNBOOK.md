# Runbook

All commands run on the VM in `/opt/traveldeal` unless noted.

## Everyday

| Task | Command |
|---|---|
| App logs | `docker compose logs -f app` |
| Proxy / certificate logs | `docker compose logs -f caddy` |
| Deploy log | `journalctl -u traveldeal-update -n 50` |
| Backup log | `journalctl -u traveldeal-backup -n 50` |
| Restart the app | `docker compose restart app` |
| Deploy now | `sudo systemctl start traveldeal-update.service` |
| Back up now | `sudo systemctl start traveldeal-backup.service` |

## The site is down

1. `docker compose ps`: are both containers `Up (healthy)`? If not, check `docker compose logs app`.
2. Database errors (`DPY-` or `ORA-` in the logs)? In the console, check the Autonomous Database is **Available**. If it's **Stopped**, click **Start** and wait about 5 minutes.
3. Certificate errors? Check that the domain's DNS still points at the VM IP and ports 80/443 are open in the security list.
4. VM unreachable? Check it's running in the console. If Oracle reclaimed it, follow **Rebuild the VM** below. Your data is safe in the database.

## Roll back a bad release

```bash
git log --oneline -5
git reset --hard <last-good-sha>
docker compose up -d --build
```

Then revert the bad commit on GitHub, or the timer will redeploy it once its checks pass.

## Restore user data

Backups are at `traveldeal-backups/traveldeal/YYYY-MM-DD.json.gz`.

1. Download the one you want (console → bucket → object → Download) and copy it to the VM.
2. Restore only into an **empty** database (a new Always Free ADB, or after dropping the four `TD_*` tables):
   ```bash
   docker compose run --rm -v "$PWD/2026-11-05.json.gz:/tmp/b.json.gz:ro" app \
     python -m traveldeal.backup --restore /tmp/b.json.gz
   ```
3. If you created a new database, update `ORACLE_DSN` in `deploy/.env` and the database ACL, then `docker compose up -d`.

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
| Database password | `ALTER USER TRAVELDEAL IDENTIFIED BY "<new>";` in Database Actions → update `deploy/.env` → `docker compose up -d` |
| Cookie secret | New value in `secrets.toml` → `docker compose up -d` (signs everyone out) |
| Google client secret | Google Cloud console → reset secret → `secrets.toml` → `docker compose up -d` |

## Quarterly

- Update rotating categories (Chase Freedom Flex, Discover it); the monthly "Card data needs review" issue lists them.
- Restore-test one backup.
- `sudo apt-get update && sudo apt-get upgrade -y && sudo reboot` for OS patches.

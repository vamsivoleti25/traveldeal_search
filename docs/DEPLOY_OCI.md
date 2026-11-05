# Deploy to Oracle Cloud Always Free — step by step

About 60–90 minutes the first time. Everything below is Always Free; if a screen ever shows a price for something you're creating, stop and check you picked the Always Free option.

You'll need: your OCI account, a GitHub account, a Google account (for the Google sign-in client), and optionally a domain you control (for example a subdomain of a site you already own).

---

## Step 0. Guardrails first

1. Note your **home region** (top right of the console). Create everything there.
2. **Billing & Cost Management → Budgets → Create budget**: amount `$1`, alert at 100% of actual spend, your email. Any accidental paid resource will email you.
3. **Consider** **Billing → Upgrade and Manage Payment → Pay As You Go.** Oracle says Always Free resources stay free after upgrading, and it's the usual way to avoid idle-VM reclamation (check Oracle's Free Tier FAQ for your account). See `SYSTEM_DESIGN.md` §9.

## Step 1. Compartment

**Identity & Security → Compartments → Create compartment** named `traveldeal`. Create everything below inside it.

## Step 2. Network

1. **Networking → Virtual cloud networks → Start VCN Wizard → Create VCN with Internet Connectivity.** Name it `traveldeal-vcn` and accept the defaults.
2. Open the **public subnet → Default security list → Add ingress rules**:
   - Source `0.0.0.0/0`, TCP, destination port `80`
   - Source `0.0.0.0/0`, TCP, destination port `443`
3. Edit the existing port-22 rule so its source is **your IP** (`x.x.x.x/32`) instead of `0.0.0.0/0`.

## Step 3. Virtual machine

**Compute → Instances → Create instance**

- Name: `traveldeal-vm`
- Image: **Canonical Ubuntu 24.04** (choose the **aarch64** build)
- Shape: **Ampere → VM.Standard.A1.Flex**, **2 OCPUs, 12 GB** (shows *Always Free-eligible*)
- Networking: `traveldeal-vcn`, public subnet, **assign a public IPv4 address**
- SSH keys: upload your public key (`~/.ssh/id_ed25519.pub`; create one with `ssh-keygen -t ed25519` if needed)
- Boot volume: default 50 GB

If you get "Out of capacity", try another availability domain or try again later.

Copy the **public IP** and the instance **OCID** when it's running.

## Step 4. Autonomous Database

**Oracle Database → Autonomous Database → Create Autonomous Database**

- Display name and database name: `traveldeal`
- Workload: **Transaction Processing**
- Toggle **Always Free** on
- ADMIN password: generate a strong one and save it in your password manager
- Network access: **Secure access from allowed IPs and VCNs only**, and add the VM's public IP
- Uncheck **Require mutual TLS (mTLS) authentication** (walletless TLS; the IP allow-list protects it)

When it's available:

1. **Database actions → SQL**, signed in as ADMIN. Run `deploy/sql/create_app_user.sql` with a new strong password for `TRAVELDEAL`.
2. **Database connection → TLS** → copy the connection string for the **`_tp`** service. That is your `ORACLE_DSN`.

## Step 5. Backup bucket

1. **Storage → Buckets → Create bucket** `traveldeal-backups`: Standard tier, **private**.
2. In the bucket, go to **Lifecycle policy rules → Create rule**: delete objects older than **30 days**.

## Step 6. Let the VM write backups without API keys

1. **Identity & Security → Domains → Default → Dynamic groups → Create**: name `traveldeal-vm`, rule
   `instance.id = '<your instance OCID>'`
2. **Identity & Security → Policies → Create policy** in the `traveldeal` compartment:
   ```
   Allow dynamic-group traveldeal-vm to manage objects in compartment traveldeal where target.bucket.name='traveldeal-backups'
   ```

## Step 7. Domain name

You need a hostname that points at the VM's public IP, so Caddy can get a free HTTPS certificate.

- **If you own a domain:** add a DNS **A record**, e.g. `traveldeal.yourdomain.com → <VM public IP>`.
- **No domain:** use `<ip-with-dashes>.sslip.io`, for example `129-146-12-34.sslip.io`. It needs no setup and is free.

## Step 8. Google sign-in

1. Go to https://console.cloud.google.com → create a project `traveldeal` → **APIs & Services → OAuth consent screen**. Choose External and fill in the app name and your email. Scopes: `openid`, `email`, `profile`.
2. **Credentials → Create credentials → OAuth client ID → Web application.**
   Authorized redirect URI: `https://<your domain>/oauth2callback`
3. Copy the client ID and secret.

**Optional, email + password accounts:** in **Identity & Security → Domains → Default → Integrated applications → Add application → Confidential Application**, enable *Client configuration → Authorization code*, set the redirect URL to the same `/oauth2callback`, activate it, and copy its client ID and secret. Your discovery URL is `https://<idcs-domain-url>/.well-known/openid-configuration`. The Free domain type can't self-register users, so you create each user under **Users**.

## Step 9. Set up the VM

```bash
ssh ubuntu@<VM public IP>
git clone https://github.com/vamsivoleti25/traveldeal_search.git /tmp/td
bash /tmp/td/deploy/setup_vm.sh
```

Log out and back in (for the `docker` group), then:

```bash
cd /opt/traveldeal
cp deploy/env.example deploy/.env && chmod 600 deploy/.env && nano deploy/.env
cp .streamlit/secrets.toml.example .streamlit/secrets.toml && chmod 600 .streamlit/secrets.toml && nano .streamlit/secrets.toml
python3 -c "import secrets; print(secrets.token_urlsafe(48))"     # paste as cookie_secret
deploy/compose.sh up -d --build
deploy/compose.sh logs -f
```

Fill in `DOMAIN`, `ORACLE_*` and `BACKUP_*` in `deploy/.env`, and the redirect URI, cookie secret and Google (and optional OCI) client details in `secrets.toml`.

## Step 10. Verify

1. Open `https://<your domain>`. The padlock should show a valid certificate.
2. Sign in, add a card, save a trip, then refresh: everything should still be there.
3. Run a backup now and confirm a file appears in the bucket:
   ```bash
   sudo systemctl start traveldeal-backup.service && journalctl -u traveldeal-backup -n 20
   ```
4. Check the timers: `systemctl list-timers | grep traveldeal`.

## Step 11. Turn on monitoring

In GitHub: **Settings → Secrets and variables → Actions → Variables → New variable** `SITE_URL = https://<your domain>`. The hourly uptime workflow then opens an issue if the site goes down.

From now on, every push to `main` that passes CI is live within about 5 minutes.

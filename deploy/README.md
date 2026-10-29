# Deployment (Ansible)

Deploys Documind to `ls-dp-integration-test` (AlmaLinux 8.10) as the `documind`
SSH user — **fully rootless, everything under `~/.local`**, no sudo required:

- **Ollama** — official `ollama-linux-amd64` tarball into `~/.local/{bin,lib}`,
  `systemd --user` service, models stored under `~/.local/share/ollama/models`
- **Node.js** — latest v22 tarball into `~/.local/node` (frontend build only)
- **Backend** — git checkout at `~/.local/documind/app`, venv at
  `~/.local/documind/venv` (locked requirements), `documind.service`
  **user** unit; uvicorn serves `/api` **and** the built frontend
  (SPA fallback added in `backend/app/main.py`) on `0.0.0.0:8000`
- **State** — `~/.local/documind/data` (SQLite + Chroma + uploads), outside the
  git checkout, survives redeploys
- **No nginx / no port 80** — single uvicorn process, single port
- **No SELinux/firewalld changes** — nothing is installed system-wide

## Prerequisites

Control machine: Linux or WSL (Ansible does not run natively on Windows).
Only ansible-core built-ins are used — no extra collections.

```bash
pip install ansible
```

Target server — must already have (checked by pre_tasks, fail-fast otherwise):

- `git`
- `python3` >= 3.11 with `ensurepip` (verified: 3.11.9 on ls-dp-integration-test)
- Egress to github.com, nodejs.org, ollama.com, and the npm registry —
  via the corporate proxy (see below)

## Proxy

Outbound traffic on the server goes through `PROXY`
with authentication. The env vars already on the server are **malformed** —
the `@` inside the username must be URL-encoded (`%40`), otherwise curl/git
parse the proxy URL at the wrong `@` and connect to port 0.

Export the corrected vars in the shell before running the playbook (the
playbook picks them up via `ansible_env`):

```bash
export https_proxy='http://USER%40DOMAIN:PASS@PROXY'
export http_proxy="$https_proxy"
```

Or set `proxy_url` in `group_vars/all.yml` / via `-e proxy_url=...`. The
play-level `environment:` applies it to git, curl, npm ci, and pip;
`no_proxy` keeps 127.0.0.1 local. A pre_task verifies egress and fails
fast with this hint. Fix `~/.bashrc`/`/etc/environment` permanently
so future shells don't hit the malformed value.

**Why downloads use `curl`, not `get_url`/`uri`:** Ansible's urllib-based
modules only do Basic proxy auth and send `%40`-encoded credentials
literally — both cause 407s against the corporate (NTLM-capable) proxy.
curl (`--proxy-anyauth`) decodes `%40` and negotiates whatever scheme the
proxy offers. git and npm ride on libcurl too, so they are fine. `pip`
(urllib3) decodes userinfo properly.

The **ollama daemon** pulls models itself, so `ollama.service` carries the
proxy vars in its unit — the play-level `environment:` never reaches a
systemd service.

## Run

```bash
cd deploy
ansible-playbook playbooks/deploy.yml
# with SSH password instead of a key: add -k
```

App is then reachable at `http://ls-dp-integration-test:8000`.

Re-running the playbook is idempotent: it pulls `main`, rebuilds the frontend
only when the checkout changed (or `dist/` is missing), and restarts the user
services via handlers.

## Surviving reboot/logout (linger)

User units run under `systemd --user`, which normally stops when the last
session ends. The playbook tries `loginctl enable-linger` (permitted for the
user's own account); if it fails, an admin must run once:

```bash
sudo loginctl enable-linger documind
```

## Configuration

- `inventory/hosts.yml` — target host / SSH user
- `inventory/group_vars/all.yml` — `user_local`, `app_dir`, port, `git_ref`,
  `ollama_models`, `nodejs_major`
  (must live next to the inventory file — a top-level `deploy/group_vars/`
  is silently ignored)

## Useful commands on the server

```bash
systemctl --user status documind ollama
journalctl --user -u documind -f
```

## Notes / gotchas

- If the repo is private, embed a token in `git_repo`
  (`https://<token>@github.com/...`) or switch to SSH with a deploy key.
- `ollama_models` must stay in sync with `backend/app/settings.py` DEFAULTS.
- The Ollama install is pinned to whatever `ollama.com` serves at deploy time
  and is not upgraded on re-runs (`creates:` guard); to upgrade, delete
  `~/.local/bin/ollama` and re-run.

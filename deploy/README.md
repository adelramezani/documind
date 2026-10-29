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
- Egress to github.com, nodejs.org, ollama.com, and the npm registry

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
- `group_vars/all.yml` — `user_local`, `app_dir`, port, `git_ref`,
  `ollama_models`, `nodejs_major`

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

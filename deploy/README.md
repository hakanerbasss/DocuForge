# Deployment — from-scratch server install

Turns an empty Ubuntu box into a running DocuForge with one command. It has no
dependency on any existing server, and **no API keys are needed to install** —
the panel comes up empty and DeepSeek/Pexels/OpenAI keys are entered from
`/settings` afterwards.

```bash
curl -fsSL https://raw.githubusercontent.com/hakanerbasss/DocuForge/main/deploy/bootstrap.sh -o bootstrap.sh
bash bootstrap.sh
```

## Options

| Variable | Default | Effect |
|---|---|---|
| `DOMAIN` | *(unset)* | Install nginx and serve the panel on this hostname |
| `PANEL_USER` / `PANEL_PASS` | `docuforge` / *(unset)* | HTTP Basic Auth in nginx (needs `DOMAIN`) |
| `SSL=1` | off | Get a Let's Encrypt certificate (needs `DOMAIN`) |
| `WITH_XTTS=1` | off | Also install XTTS voice cloning (pulls torch, ~2 GB+) |
| `PORT` | `8090` | Port the app listens on |
| `APP_DIR` | `/root/docuforge` | Install directory |
| `FORCE=1` | — | Overwrite an existing install (see below) |

## ⚠️ The panel has no login

DocuForge ships **no authentication** — there is no login page and no
middleware in front of the routes. `/settings` displays and edits the DeepSeek,
Pexels, OpenAI and fal.ai API keys.

That decides how the service binds:

- **With `DOMAIN`** → app binds `127.0.0.1`, nginx sits in front, and
  `PANEL_PASS` can put Basic Auth on it. This is the recommended setup.
- **Without `DOMAIN`** → app binds `0.0.0.0` so you can reach it at
  `http://IP:8090` (this is how it runs today). Anyone who knows the address
  can read your API keys. Restrict the port in the firewall, or better:

```bash
DOMAIN=df.example.com PANEL_PASS=somepassword SSL=1 bash bootstrap.sh
```

HTTPS is not only cosmetic here: the XTTS reference-audio **microphone
recording** in `/settings` uses `MediaRecorder`/`getUserMedia`, which browsers
only allow in a secure context. On plain HTTP that feature never activates.

## What it installs

| Step | Detail |
|---|---|
| System packages | `ffmpeg` (render, voice, thumbnail, subtitle burn-in), **`espeak-ng`** (the *default* voice provider — without it a project with untouched settings fails at narration), `python3-venv`, `git`, and `nginx` only when `DOMAIN` is set |
| Code | Clones into `APP_DIR` |
| Python | venv + `pip install -e ".[web,voices]"` |
| Verification | Imports `app.web` and checks `ffmpeg`/`ffprobe`/`espeak-ng` **before** starting the service, so systemd never lands in a restart loop |
| systemd | `docuforge-web.service` |
| nginx | Only with `DOMAIN`; long proxy timeouts (a build takes minutes), 500M body limit, optional Basic Auth |

Re-running is safe: the venv and clone are reused, dependencies are just
re-resolved.

## Why the extras exist

`pip install -e .` alone produced a working CLI and a **dead web panel** —
`import app.web` raised `ModuleNotFoundError: No module named 'fastapi'`,
because fastapi/uvicorn/pydantic/python-multipart lived only in a manual
README step. They are now `[web]`. Similarly Supertonic is offered as a voice
in the wizard but was declared nowhere and is imported lazily, so it failed at
generation time on a fresh box — now `[voices]`. XTTS stays separate (`[xtts]`)
because it drags in torch.

## Guard against running this on a live server

The script **stops** if `/etc/systemd/system/docuforge-web.service` already
exists. Continuing would overwrite the unit (and nginx config), losing the port,
directory, hand-made settings and certbot's HTTPS blocks. Worse, if the running
service used a different directory, existing projects and jobs would disappear
from the panel — the code resolves `jobs/`, `projects/` and `models/`
**relative to the working directory**.

To update code on a server that is already running, use this instead:

```bash
cd /root/docuforge && git pull \
  && .venv/bin/pip install -e ".[web,voices]" \
  && systemctl restart docuforge-web
```

If you really do want a fresh install, back up first and pass `FORCE=1`.

## Not automated

- **Piper voice model** — download into
  `APP_DIR/models/piper/tr_TR-fahrettin-medium/` if you want that provider.
  eSpeak and Supertonic need nothing extra.
- **DNS** — point the hostname at the server before `SSL=1`.

## Verification status

Actually executed and verified while writing this: `pip install -e .` reproducing
the missing-fastapi failure, `pip install -e ".[web,voices]"` succeeding,
`import app.web` and `from supertonic import TTS` both importing, and the panel
serving `/`, `/new`, `/settings` (all HTTP 200) and `/api/jobs/active` with **no
API keys configured at all**.

Not verified: the script has not been run end-to-end on a real server, and the
nginx config was not syntax-checked by nginx itself (bootstrap still runs
`nginx -t` and aborts on error). Whoever runs it first should record the result
here.

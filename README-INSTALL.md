# DocFetch Security Lab — Install & Use (Arch / Web / Mobile)

Quick-start guide for running the lab **on an Arch laptop**, **in a browser**,
and **from your phone**. The existing `README.md` covers the full stack; this
file is only about getting it running.

---

## 1. One-time prerequisites (Arch)

Install the base toolchain (system packages + Node + Python):

```bash
sudo pacman -S --needed python python-pip nodejs npm base-devel git

# for the optional Tauri desktop app
sudo pacman -S --needed webkit2gtk-4.1 gtk3 libsoup3
```

Node is **not** required if you only run back end + lab targets; it is required
for the web app and desktop app.

---

## 2. Run it from the source tree (easiest)

From the project root:

```bash
cd "$HOME/Documents/Fun Project/Web Pdf Scrbe"

# (a) backend API  ->  http://127.0.0.1:8000
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
# (b) lab target servers  ->  ports 9101/9102/9103 (second terminal)
cd "$HOME/Documents/Fun Project/Web Pdf Scrbe"
bash scripts/run_lab_targets.sh
```

```bash
# (c) web app  ->  http://127.0.0.1:5173 (third terminal, from project root)
npm install
npm run dev
```

Or run all three with the root npm scripts (customize ports as needed):

```bash
npm run lab:up      # lab targets
npm run dev:api     # backend on :8000
npm run dev         # web app on :5173
```

---

## 3. Install as a native Arch package (desktop app)

The desktop app is a Tauri 2 shell that wraps the same UI and connects to the
backend on `http://127.0.0.1:8000`. Build & install with `makepkg`:

```bash
cd "$HOME/Documents/Fun Project/Web Pdf Scrbe"

# 1. create the source tarball the PKGBUILD expects
tar --exclude='node_modules' --exclude='.venv' \
    --exclude='apps/desktop/src-tauri/target' --exclude='.run' \
    -czf packaging/docfetch-security-lab-0.1.0.tar.gz .

# 2. build and install (network required for npm + cargo deps)
cd packaging
makepkg -si
```

Then launch it from the app menu (**DocFetch Security Lab**) or:

```bash
docfetch-security-lab &
```

Start the backend first (Section 2a) — the desktop shell is just the frontend.

---

## 4. Use it like a web app on the same laptop

No installation needed — run Section 2, then open one of:

| URL | What you get |
| --- | --- |
| http://127.0.0.1:5173 | Dev web app (hot reload) |
| http://127.0.0.1:8000/api/v1/health | Backend health JSON |
| http://127.0.0.1:8000/docs | Interactive API docs (Swagger) |

---

## 5. Use it from your phone (same Wi-Fi)

The API and web server must be reachable over Wi-Fi, so start everything bound
to all interfaces and point the phone at the laptop's LAN IP.

Find the laptop's Wi-Fi IP first:

```bash
ip -4 addr show | grep -E 'inet .*(wlan|eth)'   # e.g. 10.163.48.187
```

Start the stack on `0.0.0.0` (backend already bound above; frontend needs it):

```bash
npm run lab:up
# backend: already running with --host 0.0.0.0 (Section 2a)
npm run dev -- --host 0.0.0.0                  # web app now on :5173 for LAN
```

On the phone browser open: `http://<LAPTOP_IP>:5173` (e.g. `http://10.163.48.187:5173`).

The dev server proxies `/api` to the local backend, so **no firewall rule for
:8000 is needed** for the dev flow.

### Production-ish build for the phone

If you want the built (non-dev) bundle reachable from the phone, rebuild the
frontend pointing at your LAN IP, then serve it:

```bash
cd apps/web
VITE_API_BASE_URL="http://<LAPTOP_IP>:8000" npm run build
npm run preview -- --host 0.0.0.0 --port 4173
```

Phone: `http://<LAPTOP_IP>:4173` → requires port 8000 open too
(backend already bound to 0.0.0.0).

### Add to home screen (PWA)

The web app ships a PWA manifest + icons. In Chrome/Android:
browser menu → **Add to Home screen** → it installs as a standalone
"DocFetch Security Lab" app that opens full-screen.

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `port 8000 is already ...` | Stop the old backend: `pkill -f uvicorn` (or `npm run lab:down` — that stops lab targets only) |
| Lab target ports busy | `bash scripts/stop_lab_targets.sh` before re-running `lab:up` |
| Phone can't reach :5173 | Check laptop firewall: `sudo ufw status`; ensure phone is on the SAME Wi-Fi / subnet as the laptop IP shown by `ip` |
| Backend reachable but slow on LAN | Normal for HTTP/1.0 lab targets; run target + API on the same laptop |
| `makepkg` fails on npm/cargo | `makepkg -sf` (skip checksum) — network is required for dependencies |
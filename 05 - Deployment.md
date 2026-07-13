# Deployment

## Live site

**https://tvtalk.fun** (also `www.tvtalk.fun`)

Hosted on **Cloudflare Workers + Static Assets** (not Pages — Cloudflare deprecated the Pages creation flow for new projects in favor of Workers serving static assets).

- **GitHub repo**: https://github.com/davidrogowski/TvTalk (public)
- **Cloudflare project name**: `tvtalk`
- **Custom domain**: `tvtalk.fun` (apex + `www`) — **attached and live** (see [Custom domain](#custom-domain-tvtalkfun) below)
- **Legacy URL**: `tvtalk.davrogowski.workers.dev` still resolves but **301-redirects to `tvtalk.fun`** (preserving path + query) via `worker.js`, so previously-shared links keep working

## Key deployment files

| File | Purpose |
|---|---|
| `wrangler.jsonc` | Worker name `tvtalk`. Serves the repo root (`./`) as static assets via the `ASSETS` binding. Declares the `tvtalk.fun` + `www.tvtalk.fun` `custom_domain` routes, keeps `workers_dev: true`, and sets `main: worker.js` + `run_worker_first: true` so the redirect runs on every request (incl. the homepage). |
| `worker.js` | Minimal Worker entry: 301-redirects any `*.workers.dev` host to `tvtalk.fun` (path + query preserved); otherwise hands off to `env.ASSETS.fetch()`. |
| `.assetsignore` | Excludes `.git`, `.gitignore`, `.assetsignore`, `wrangler.jsonc`, `worker.js`, `scripts/`, `*.md`, `Clock The Quote/`, `.wrangler/`, `.DS_Store`, `node_modules/`, `.superpowers/`, `.claude/`, `dropper-engine/`, `docs/` from the uploaded asset bundle. Without this, wrangler tries to upload the 399 MB `.git` pack file and fails (25 MB per-asset limit); excluding `worker.js` keeps the Worker source from being served as a public asset. |

## Deploying an update

Auto-deploy-on-git-push is **NOT set up** (Cloudflare never registered a GitHub webhook — the project was created as a manual Worker, not a Git-connected one). So updates are a manual two-step:

```sh
cd /Users/dave/Desktop/Obsidian/TvTalk

# 1. Push to GitHub (version history)
git add -A && git commit -m "..." && git push

# 2. Deploy to Cloudflare (the actual live update) — PIN wrangler@4.40.0
npm_config_cache=/tmp/npm-cache npx --yes wrangler@4.40.0 deploy
```

Notes:
- **⚠️ PIN THE WRANGLER VERSION.** `wrangler@4.97.0` (current latest) **hangs forever** on the asset-upload step: it prints "Read ~8100 files from the assets directory" then sits at **0% CPU** indefinitely (confirmed on two machines, after a successful auth `200`, so it's a wrangler bug, not network/access). **`wrangler@4.40.0` works** — uploads the same site in ~2 min. So always deploy with the pinned older version (the command above). A bare `npx wrangler deploy` pulls 4.97 and hangs.
- **The `npm_config_cache=/tmp/npm-cache` prefix is mandatory** — `~/.npm` is corrupted (a bare `npx wrangler` there fails with `npm error Invalid Version:`). `sudo chown -R 501:20 ~/.npm` fixed ownership but **not** the corruption, so keep using the `/tmp` cache. To fully fix `~/.npm` someday: `npm cache clean --force` didn't help; would need to wipe/rebuild it.
- **Run it in a real Terminal, from the project dir.** `sudo`/`npx` need a real TTY (the Claude Code `!` prefix and the Bash sandbox lack one — `sudo` errors "a terminal is required"). And `cd ~/Desktop/Obsidian/TvTalk` first, or wrangler scans your home dir and chokes on `~/.Trash`. (Claude *can* run it via its Bash tool with the sandbox disabled — but the version pin still applies.)
- **Verify the live URL**, not npx's exit code (`npx` reports 0 even on failure): `curl -sI https://tvtalk.fun/clockthequote`.
- Wrangler is authenticated via `wrangler login` OAuth (account `davrogowski@gmail.com` / `b331d50040451dd56b64535ec1381a09`).
- Only changed files upload (delta), but wrangler still **hashes every asset file locally every deploy** (~8,100 files / 774 MB when this was written; the catalog has since grown to 99 titles so counts are higher now — no persistent hash cache), so even a 2-file change takes ~2 min of local hashing. That's expected, not a hang.
- Commits use env-var author identity (`davidrogowski` / `davidrogowski@users.noreply.github.com`) since global git config is intentionally unset.

## To wire up auto-deploy on push (optional, not done)

Cloudflare dashboard → `tvtalk` project → Settings → Builds → connect to `davidrogowski/TvTalk` + `main` branch. Once connected, every `git push` rebuilds and redeploys. Until then, the manual `wrangler deploy` is required.

## Custom domain (`tvtalk.fun`)

Attached 2026-05-28. `tvtalk.fun` was registered at **GoDaddy** (registrar), but **DNS is managed by Cloudflare**. How it was wired:

1. Cloudflare dashboard → **Add a site → Connect a domain** → `tvtalk.fun` (Free plan). Continued with 0 DNS records — activation only needs nameserver delegation, not records.
2. At GoDaddy → repointed the nameservers to the two Cloudflare ones (`irma`/`pranab`.ns.cloudflare.com). Propagated in ~4 min; zone went **Active**.
3. Added the `custom_domain` routes for `tvtalk.fun` + `www.tvtalk.fun` to `wrangler.jsonc`, then `wrangler deploy` — Cloudflare auto-creates the proxied DNS records and provisions free SSL (cert issued in ~minutes).

Notes:
- **Don't add A/CNAME records by hand** — the `custom_domain` route creates them. A manual record just conflicts.
- The first deploy with `routes` but no `workers_dev: true` **disabled** the `*.workers.dev` URL; re-added `workers_dev: true` to keep it alive (now redirected — see live-site section).
- Registrar stays GoDaddy; only nameservers moved. A full registrar transfer to Cloudflare (cheaper renewals) is possible later but not done.

## Copyright note

The deployed audio is unlicensed clips from copyrighted shows. For a friends-only URL this is low practical risk, but wide distribution invites DMCA takedowns. Repo visibility (public/private) doesn't change this — the *deployed* files are public regardless.

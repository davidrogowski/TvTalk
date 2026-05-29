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
| `.assetsignore` | Excludes `.git/`, `scripts/`, `*.md`, `wrangler.jsonc`, `worker.js` from the uploaded asset bundle. Without this, wrangler tries to upload the 399 MB `.git` pack file and fails (25 MB per-asset limit); excluding `worker.js` keeps the Worker source from being served as a public asset. |

## Deploying an update

Auto-deploy-on-git-push is **NOT set up** (Cloudflare never registered a GitHub webhook — the project was created as a manual Worker, not a Git-connected one). So updates are a manual two-step:

```sh
cd /Users/dave/Desktop/Obsidian/TvTalk

# 1. Push to GitHub (version history)
git add -A && git commit -m "..." && git push

# 2. Deploy to Cloudflare (the actual live update)
npm_config_cache=/tmp/npm-cache npx wrangler deploy
```

Notes:
- The `npm_config_cache=/tmp/npm-cache` prefix works around root-owned files in `~/.npm` (a one-time npm permission bug). To fix permanently: `sudo chown -R 501:20 ~/.npm`, then the prefix isn't needed.
- Wrangler is already authenticated (via `wrangler login` OAuth). If it ever logs out, re-run `npx wrangler login`.
- Re-deploys only upload changed files (delta), so they're fast (~1-10 sec for small changes).
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

# Deployment

## Live site

**https://tvtalk.davrogowski.workers.dev**

Hosted on **Cloudflare Workers + Static Assets** (not Pages — Cloudflare deprecated the Pages creation flow for new projects in favor of Workers serving static assets).

- **GitHub repo**: https://github.com/davidrogowski/TvTalk (public)
- **Cloudflare project name**: `tvtalk`
- **Custom domain**: `tvtalking.com` — *planned, not yet attached* (see below)

## Key deployment files

| File | Purpose |
|---|---|
| `wrangler.jsonc` | Tells Cloudflare to serve the repo root (`./`) as static assets. Worker name is `tvtalk`. |
| `.assetsignore` | Excludes `.git/`, `scripts/`, `*.md`, `wrangler.jsonc` from the uploaded asset bundle. Without this, wrangler tries to upload the 399 MB `.git` pack file and fails (25 MB per-asset limit). |

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

## To attach the custom domain (when tvtalking.com is bought)

1. Buy `tvtalking.com` (Cloudflare Registrar is at-cost and auto-connects DNS).
2. Cloudflare dashboard → `tvtalk` project → Settings → Domains → Add → `tvtalking.com`.
3. Cloudflare auto-creates the DNS records + provisions free SSL (~1-5 min).
4. Optionally add `www.tvtalking.com` with a redirect rule.

## Copyright note

The deployed audio is unlicensed clips from copyrighted shows. For a friends-only URL this is low practical risk, but wide distribution invites DMCA takedowns. Repo visibility (public/private) doesn't change this — the *deployed* files are public regardless.

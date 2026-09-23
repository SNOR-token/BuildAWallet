# HUMAN API on Cloudflare Workers

This project runs the existing wallet architect in a Python Worker. Pages continues to serve the `static/` directory. D1 stores saved blueprints, gallery entries, and stats. It does not hold signing keys or implement `/v1`.

## Prepare and verify

From the repository root:

```bash
./cloudflare-human/prepare.sh
cd cloudflare-human
uv run pywrangler deploy --dry-run
```

`prepare.sh` copies the canonical `app/brain.py`, `app/catalog.py`, and `human_worker.py` into this isolated Worker build. Never edit the copies in `src/`.

## Provision and deploy

A Cloudflare account with the active `buildawallet.xyz` zone is required. From the repository root:

```bash
cd cloudflare-human
npx wrangler login
./deploy.sh
```

The script creates the `buildawallet` D1 database if needed, applies its migration, packages the Python Worker, deploys the `/api/*` and `/healthz` routes, and checks the public endpoints. It writes the real database ID into an ignored local config file. No local web server is involved.

Keep the existing Pages custom domain attached for all other paths. The Pages project must use `static` as its build output directory and the repository root as its project root so that `functions/w/[code].js` can serve saved blueprint URLs. Test a chat, save, shared link, gallery, and stats after deployment.

**Security:** Never put `AGENT_BOOTSTRAP_SECRET`, `BAW_MASTER_KEY`, or mainnet broadcast settings in this Worker. The `/v1` agent API is a separate migration and must remain unavailable until its key storage, policy checks, and durable transaction state are verified.

# BuildAWallet mainnet deployment runbook

This release has a static Pages site, a HUMAN Python Worker and a paid NON-HUMAN Worker. `wrangler deploy` at the repository root is not the complete deployment. Use a Cloudflare account that owns the `buildawallet.xyz` zone. The Pages project build output is `static` with repository root as its project root; retain `functions/w/[code].js` for saved blueprints. The Cloudflare domain and route configuration must be checked in the dashboard before deployment.

## 1. Review and build

```bash
python -m pip install -r requirements.txt
pytest -q
cd agent-pay
npm ci
npm run typecheck
npm test
npx wrangler deploy --dry-run
cd ..
```

Review the two USDC recipients against the owner's wallets, including network: Base `0xBcCA6AED433d9020C50D44560F9679F1B5eB511d`; Solana `Ew8mbrKwD6LGaSX28a6XGmXqeQSs2hykRibjXVhftTRC`. A correct receiving address is necessary but does not prove a buyer's USDC balance, facilitator support or settlement.

## 2. Publish the HUMAN site and API

Merge the reviewed changes to the Pages-connected branch and wait for the Pages deployment. Verify `/human`, `/human/build`, `/human/studio`, `/human/live`, `/docs`, `/pricing`, `/agent-offer.json` and `/.well-known/agent.json`. The `_redirects` file rewrites clean URLs to their HTML files. A separate see.io deployment may also be triggered by a main branch push; its Docker service still excludes the signer.

From repository root, with the correct Cloudflare account selected:

```bash
./cloudflare-human/prepare.sh
cd cloudflare-human
uv run pywrangler deploy --dry-run
./deploy.sh
cd ..
```

`deploy.sh` provisions or finds the D1 database, applies migrations and deploys `/api/*` and `/healthz`. It needs Wrangler authentication and `uv`. Check chat, save, share, gallery and stats through the public domain. Do not put `BAW_MASTER_KEY`, `AGENT_BOOTSTRAP_SECRET` or signing keys into this Worker.

## 3. Deploy the paid machine Worker

Run these from `agent-pay/` after confirming the intended Cloudflare zone and account. The RPC URLs are secrets; each must target its named mainnet. The Worker independently verifies Base chain ID 8453 and Solana's mainnet genesis hash before issuing a payment challenge.

```bash
cd agent-pay
npm ci
npx wrangler secret put BASE_RPC_URL
npx wrangler secret put SOLANA_RPC_URL
npm run deploy
```

Do not paste RPC credentials into Git or `.dev.vars.example`. Confirm PayAI's production facilitator supports the exact Base and Solana payment schemes for these USDC networks, and monitor its availability. Verify `GET /machine/info` on the public domain, invalid addresses returning 400, configuration or RPC failure returning 503, and valid unpaid requests returning 402 on both data routes. Decode both payment options and compare the chain-specific collectors and $0.01 USDC amount. Complete a controlled paid call on **each** chain and confirm settlement and the balance response before directing paying customers to the endpoints. Keep enough USDC and gas in the test payer; avoid reusing a production customer payment for tests.

## Release boundary

The local `agent_protocol.py` signer and `/v1` endpoints remain unmounted. The public page does not ship a generated APK or a transaction signing flow. The proposed $1.99 monthly crypto subscription has no receipt verification, entitlement store, renewal/expiry logic or gated delivery. Do not advertise these as purchasable or enable broadcast by setting an environment variable. They require separate custody architecture, durable state, replay-resistant confirmed payment accounting, policy and approval enforcement, security review, and end-to-end mainnet checks before release.

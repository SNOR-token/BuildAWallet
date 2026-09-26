# BuildAWallet.xyz

BuildAWallet has a HUMAN wallet designer and a NON-HUMAN read-only machine data API. The public website does **not** create custodial wallets or sign and broadcast transactions.

| Surface | Current capability | Deployment |
| --- | --- | --- |
| HUMAN Pages site | Guided wallet blueprint, JSON export, external wallet connection and read-only Base/Solana native balance | Cloudflare Pages serves `static/` |
| HUMAN API | Architect chat, saved designs, gallery and stats | `cloudflare-human/` Python Worker with D1, routes `/api/*` and `/healthz` |
| NON-HUMAN data | Paid Base and Solana native balance snapshots, $0.01 USDC per request through x402 | `agent-pay/` Worker, route `/machine/*` |
| Agent wallet signer | Local prototype only | Not mounted on the public container or Cloudflare |

The optional Docker/see.io server in `main.py` serves the website and a read-only MCP preview. It deliberately does not mount `agent_protocol.py`. A `BAW_MASTER_KEY` environment variable does not turn the public server into a signer. Do not put signing keys or bootstrap credentials into either Cloudflare Worker.

## HUMAN flow

1. `/human` introduces the designer.
2. `/human/build` collects wallet preferences.
3. `/human/studio` previews the blueprint and downloads its JSON configuration.
4. `/human/live` connects an existing injected wallet for free read-only Base or Solana mainnet balances.

Sending, generated APK wallets, and the proposed $1.99 monthly crypto subscription are not released. A production subscription requires confirmed payment, entitlement checks, expiration and renewal handling before gated signing or delivery can be enabled.

## NON-HUMAN payment flow

`GET /machine/info` is free discovery. `GET /machine/wallet?address=0x...` reads Base mainnet and `GET /machine/solana-wallet?address=...` reads Solana mainnet. A valid unpaid request gets an x402 HTTP 402 challenge for $0.01 USDC on either chain. Payments on Base go to `0xBcCA6AED433d9020C50D44560F9679F1B5eB511d`; payments on Solana go to `Ew8mbrKwD6LGaSX28a6XGmXqeQSs2hykRibjXVhftTRC`. The Worker needs separate mainnet RPC URLs and a production facilitator. See [the machine service README](agent-pay/README.md).

## Deploy

See [the mainnet deployment runbook](DEPLOY_MAINNET.md) for the three Cloudflare surfaces, Wrangler commands, checks and remaining release gates. Pushing `main` also triggers the separate see.io container build per `AGENTS.md`; the Cloudflare Workers require their own deployment commands. A Pages build must use `static/` as output and keep the repository root as project root for `functions/w/[code].js`.

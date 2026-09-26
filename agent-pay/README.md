# BuildAWallet machine payments pilot

This is an isolated Cloudflare Worker in the existing BuildAWallet repository. It uses
the `/machine/*` route on `buildawallet.xyz`; it does not mount the local signing
prototype, handle private keys, or change the human designer and its $1.99/month
mainnet subscription concept.

The first paid capability is `GET /machine/wallet?address=0x...`: Base mainnet
native balance, transaction count, and current block. The Worker validates the
address, obtains the complete snapshot from the configured Base RPC, then issues an x402 challenge for
**$0.01 USDC on Base or Solana mainnet**. PayAI verifies and settles the
payment to the designated collector on the selected network:

| Payment network | USDC receiving address |
| --- | --- |
| Base | `0xBcCA6AED433d9020C50D44560F9679F1B5eB511d` |
| Solana | `Ew8mbrKwD6LGaSX28a6XGmXqeQSs2hykRibjXVhftTRC` |
No claim of wallet custody, transaction signing, risk analysis, or token holdings is made.

## Local setup

```bash
cd agent-pay
npm ci
cp .dev.vars.example .dev.vars
# edit .dev.vars with a reliable Base mainnet RPC URL
npm run typecheck
npm test
npm run dev
```

`BASE_RPC_URL` must point to Base mainnet (chain ID 8453). Do not place a
private key in this Worker. `.dev.vars` is ignored. The receiving addresses
are public and were supplied by the owner for Base and Solana respectively.

Call the free discovery endpoint at `/machine/info`. A valid unpaid request to
`/machine/wallet?address=...` returns HTTP 402 with an x402 payment challenge.
A compatible client with Base or Solana mainnet USDC can pay and retry. Invalid addresses return
400 before payment. Missing deployment configuration returns 503. The Worker
limits calls to the paid path to 60 per minute per requesting IP at each Cloudflare
location, before fetching from the RPC or facilitator. Shared IPs can hit this
limit together.

## Deploy

Set `BASE_RPC_URL` with `npx wrangler secret put BASE_RPC_URL`, then run
`npm run deploy` from this directory. Verify `/machine/info`, invalid address
400, unpaid valid address 402, and a paid request with real USDC. The custom
domain route requires the zone in the Cloudflare account used by Wrangler.

The x402 payment network can be Base or Solana mainnet. The returned data is
from Base mainnet. PayAI is an external production facilitator. Confirm its
`/supported` response for both exact schemes before accepting traffic.
This endpoint is a first real-payment capability; wallet balances themselves
are public data. A broader business needs data whose value exceeds RPC and
facilitator costs, plus rate controls and observability.

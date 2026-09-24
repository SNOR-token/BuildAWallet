# BuildAWallet.xyz

HUMAN wallet designer + NON-HUMAN mainnet agentic wallet infrastructure.

Live site: https://buildawallet.xyz

## Production requirements

Set these environment variables on the host that serves `/v1`:

| Variable | Purpose |
|----------|---------|
| `BAW_MASTER_KEY` | 32+ char secret used to encrypt agent wallet keys at rest |
| `AGENT_BOOTSTRAP_SECRET` | Secret header to create the first agent/operator credentials |
| `ETHEREUM_RPC_URL` / `BASE_RPC_URL` / … | Mainnet RPC endpoints (see `chains.py`) |
| `SOLANA_RPC_URL` | Solana mainnet RPC |
| `BITCOIN_RPC_URL` / `LITECOIN_RPC_URL` | Full-node JSON-RPC for UTXO chains |
| `DATA_DIR` | Persistent volume path (default `/data`) |

When `BAW_MASTER_KEY` is set, the container mounts the full Agent Protocol:

- `POST /v1/credentials/bootstrap`
- `POST /v1/wallets` (creates mainnet addresses, encrypted keys)
- `GET /v1/wallets/{id}/balance`
- `POST /v1/wallets/{id}/transactions`
- `POST /v1/transactions/{id}/approval`
- `POST /v1/transactions/{id}/execute` (signs + broadcasts)
- `GET /v1/transactions/{id}/receipt`
- `GET /v1/capabilities`

Without `BAW_MASTER_KEY`, only the HUMAN builder and read-only discovery endpoints run.

## HUMAN flow

1. `/human` — intro
2. `/human/build` — multi-step option wizard
3. `/human/studio` — phone preview + feature toggles + **Package APK** (downloads an Android project zip configured from the blueprint)

## Deploy

Docker:

```bash
docker build -t buildawallet .
docker run -p 8080:8080 \
  -e BAW_MASTER_KEY='...' \
  -e AGENT_BOOTSTRAP_SECRET='...' \
  -e ETHEREUM_RPC_URL='https://...' \
  -v baw-data:/data \
  buildawallet
```

Cloudflare: Pages continues to serve `static/`. Route `/api/*` to the human Worker. Point `/v1/*` at a durable container origin (Workers cannot host the signing libraries). Set secrets only on that origin.

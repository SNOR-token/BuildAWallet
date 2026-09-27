# Build-a-Wallet Agent Protocol v1

**Wallet infrastructure for the agentic internet.**

> Humans set the rules. Agents transact within them.

**Status: local prototype only.** The public Docker/see.io and Cloudflare services do not mount `/v1/*`. Setting `BAW_MASTER_KEY` on those services does not enable agent signing. This document describes the unmounted `agent_protocol.py` prototype, not an available production service.

## Discovery

- `/.well-known/agent.json` — machine-readable service manifest
- `/openapi.json` — generated OpenAPI contract
- `/llms.txt` — concise model-readable product context
- `/docs/api` — API explorer
- `/v1/capabilities` — local prototype capability declaration only
- `/mcp` — read-only preview on the Python container only

The separate paid read-only Cloudflare service is documented at `GET /machine/info` and in `agent-pay/README.md`.

## Core model

Agent -> credential -> wallet authority -> policy evaluation -> approval/signing boundary -> chain adapter -> machine-readable receipt.

The AI/agent layer never receives raw private keys. Signing stays behind the wallet adapter and policy boundary.

## Wallet types

- persistent — durable agent identity/treasury
- task — authority scoped to a job
- session — short-lived authority
- budget — spending-constrained wallet
- escrow — conditional agent-to-agent settlement (adapter pending)
- multisig — agent + human / organization authority (adapter pending)

## Policy controls

- maximum USD value per transaction
- daily USD spend limit
- human approval threshold
- asset allowlist
- destination allowlist
- authority expiration
- capability allowlist: balance / receive / send

## API

### Bootstrap credential

`POST /v1/credentials/bootstrap` with header `X-Bootstrap-Secret: $AGENT_BOOTSTRAP_SECRET`

### Create wallet

`POST /v1/wallets`

### Request transaction

`POST /v1/wallets/{wallet_id}/transactions` with `Idempotency-Key`

### Approve

`POST /v1/transactions/{tx_id}/approval` (operator scope)

### Execute (sign + broadcast)

`POST /v1/transactions/{tx_id}/execute` (operator scope)

The local prototype contains an operator-scoped execution path and broadcast switch. It is not a production custody boundary and must not be mounted on the public site.

## Required environment

- `BAW_MASTER_KEY` — encrypts wallet secrets at rest
- `AGENT_BOOTSTRAP_SECRET` — one-time bootstrap of credentials
- Chain RPC URLs from `chains.py` (`ETHEREUM_RPC_URL`, `BASE_RPC_URL`, `SOLANA_RPC_URL`, …)

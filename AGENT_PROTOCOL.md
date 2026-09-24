# Build-a-Wallet Agent Protocol v1

**Wallet infrastructure for the agentic internet.**

> Humans set the rules. Agents transact within them.

**Status: production mainnet path.** When `BAW_MASTER_KEY` is set on the host, `/v1/*` is mounted with encrypted key custody, policy evaluation, operator approval, signing and broadcast.

## Discovery

- `/.well-known/agent.json` — machine-readable service manifest
- `/openapi.json` — generated OpenAPI contract
- `/llms.txt` — concise model-readable product context
- `/docs/api` — API explorer
- `/v1/capabilities` — runtime capability declaration
- `/mcp` — MCP entry point

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

Mainnet execution is enabled for authorized operator credentials. Policy, idempotency, freeze and revocation still apply.

## Required environment

- `BAW_MASTER_KEY` — encrypts wallet secrets at rest
- `AGENT_BOOTSTRAP_SECRET` — one-time bootstrap of credentials
- Chain RPC URLs from `chains.py` (`ETHEREUM_RPC_URL`, `BASE_RPC_URL`, `SOLANA_RPC_URL`, …)

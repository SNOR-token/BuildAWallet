# Build-a-Wallet Agent Protocol v1

**Wallet infrastructure for the agentic internet.**

> Humans set the rules. Agents transact within them.

**Status: local legacy prototype only.** The public container does not mount
`/v1/*` or include the signing code. The endpoints below describe local
prototype behavior; they are not available on buildawallet.xyz.

This file describes the archived local implementation, not a public API.

## Discovery

- `/.well-known/agent.json` — machine-readable service manifest
- `/openapi.json` — generated OpenAPI contract
- `/llms.txt` — concise model-readable product and safety context
- `/docs/api` — human/developer API explorer
- `/v1/capabilities` — runtime capability declaration
- `/mcp` — MCP integration status/entry point

## Core model

Agent -> credential -> wallet authority -> policy evaluation -> approval/signing boundary -> chain adapter -> machine-readable receipt.

The AI/agent layer must never receive unrestricted private-key access. Signing belongs behind an explicit wallet/key adapter and policy boundary.

## Wallet types

- persistent — durable agent identity/treasury
- task — authority scoped to a job
- session — short-lived authority
- budget — spending-constrained wallet
- escrow — conditional agent-to-agent settlement (adapter pending)
- multisig — agent + human / organization authority (adapter pending)

## Policy controls in alpha

- maximum USD value per transaction
- daily USD spend limit
- human approval threshold
- asset allowlist
- destination allowlist
- authority expiration
- capability allowlist: balance / receive / send

## API alpha

### Create wallet

`POST /v1/wallets`

```json
{
  "chain": "litecoin",
  "custody": "self",
  "purpose": "temporary-agent-wallet",
  "wallet_type": "task",
  "policy": {
    "daily_spend_limit_usd": 20,
    "max_transaction_usd": 10,
    "require_human_approval_above_usd": 15,
    "allowed_actions": ["balance", "receive", "send"],
    "allowed_assets": ["LTC"],
    "expires_in_seconds": 604800
  }
}
```

### Request transaction

`POST /v1/wallets/{wallet_id}/transactions`

A request can return `denied`, `approval_required`, or `ready_for_signing`. Alpha deliberately stops at the signing boundary until a production key/chain adapter is installed.

## Production hardening required before mainnet execution

1. Persistent wallet/policy/transaction tables instead of the prototype in-memory Agent Protocol store.
2. Real scoped API credentials stored as hashes; rotation, revocation and tenant ownership.
3. Signed requests/nonces or equivalent replay protection, strict rate limits and audit logs.
4. Fiat-price source policy for USD-denominated limits; never trust caller-provided USD valuation in production.
5. Litecoin key/address adapter with encrypted local/HSM/MPC-backed signing according to custody mode.
6. Chain adapter for fee estimation, UTXO selection, transaction construction, simulation/validation, broadcast and confirmations.
7. Human approval workflow with authenticated approver identity and immutable approval receipts.
8. Idempotency keys for all money-moving operations.
9. Destination policy resolution that cannot be bypassed by aliases or alternate encodings.
10. MCP tools only after they inherit exactly the same credential, policy and signing boundaries as REST.
11. 402 machine-payment flow only after authentication, replay protection, settlement verification and abuse controls are production-ready.

## Next protocol milestone

Persist the agent model in SQLite, implement API-key scopes and idempotency, then attach a Litecoin **testnet** adapter. Keep mainnet transaction execution disabled until policy, signing, audit and approval tests pass.

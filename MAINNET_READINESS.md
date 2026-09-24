# Release gate: mainnet wallet services

**Decision: NO-GO for handling real funds.** This assessment covers the staging branch as inspected on 2026-09-24. Passing local tests does not constitute a security audit, chain integration test, or production deployment.

| Area | Evidence | Gate before handling funds |
| --- | --- | --- |
| HUMAN extension | Manifest V3 popup imports a JSON design; no key generation, transaction signing, origin permissions, network requests or recovery flow. An isolated AES-GCM vault prototype now has local tests but is not bundled into the extension. | Implement and independently review recovery, chain-specific address derivation and transaction signing, explicit origin permissions and human-readable transaction confirmation. Test against each advertised network. |
| NON-HUMAN API | `agent_protocol.py` stores encrypted signing keys and execution state in local SQLite; the Worker project only serves `/api/*` blueprint routes. | Define a separate durable execution and key-management boundary, multi-tenant operator authority, RPC trust and rate limits, crash recovery, on-chain reconciliation, approval audit, and tests before routing `/v1/*` publicly. |
| Replay control | This branch commits the `executing` state before external broadcast and marks exceptions `execution_unknown` to prevent blind retries. | Reconcile uncertain outcomes by transaction fingerprint and chain receipt; test process death at each signing/broadcast transition, concurrent operators, nonce/UTXO contention and chain reorgs. |
| Destination policy | An empty allowlist now denies when `deny_unknown_destinations=true`. | Validate destination and asset against the wallet's actual chain; fuzz amounts, precision, NaN/infinity, encodings, and unsupported operations. |
| User authentication | Studio Pages Function requires Cloudflare Access JWT; its team domain and audience are not configured in this environment. Blueprint API remains public. | Configure and verify Access, protect personal API records, bind them to verified identities, and confirm account recovery before exposing user wallets. |
| Cloudflare release | `wrangler whoami` reports unauthenticated; D1 config contains a placeholder database ID; `/v1/*` has no Worker migration. | Provision D1 and Access, deploy the HUMAN Worker, verify real routes and monitoring, and perform controlled production checks with no real funds initially. |

The exact broadcast environment switch is intentionally left **off**. No real-fund transfer or production wallet deployment was attempted. The checked-in extension ZIP remains a design preview; do not label it a wallet or solicit deposits to it.

Local checks on this branch: `python -m pytest -q` (3 passed), `node tests/studio_access.mjs` (passed), `python extension/package.py` (packaged), `git diff --check` (clean). The focused transaction test asserts that an uncertain broadcast cannot be executed twice and an empty destination allowlist denies a transfer.

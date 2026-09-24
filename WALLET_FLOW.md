# BuildAWallet flow and deployment status

## HUMAN visitor flow

1. `/human`: introduction and Start building.
2. `/build`: five steps for assets, networks, custody/security, features/privacy, and platform/style. Answers are kept on the visitor's device as a draft.
3. `/auth`: instructions to confirm email via Cloudflare Access one-time PIN.
4. `/studio`: wallet preview, blueprint, option vault, gallery, and a default-open AI architect chat powered by the `/api/*` Python Worker. The Studio route verifies the Cloudflare Access application JWT before serving HTML.
5. Extension preview: Studio exports a local `buildawallet-extension-config.json` with the current design. The downloadable `blueprint-extension.zip` contains a Manifest V3 popup that imports and displays this configuration. Unzip it and load its directory through the browser's extension developer mode. It has only local storage permission; it has no key generation, site connection or transaction signing. This is a design preview, not a spend-capable wallet extension. A production extension needs a secure key vault, chain-specific signing, permission prompts, transaction review, release signing and security review.

The earlier Android WebView prototype remains under `android/` for reference. It opens `https://buildawallet.xyz/wallet`, which this repository does not serve. No APK download is offered by Studio.

## Cloudflare setup required

- Pages: project root is this repository root; build output is `static`. Keep `buildawallet.xyz` attached.
- HUMAN API: deploy `cloudflare-human` per its README. Its `/api/*` and `/healthz` Worker routes use D1 for saved blueprints.
- Access: create a self-hosted application for `buildawallet.xyz/studio*`, with One-time PIN as a login method and an Allow policy appropriate for customers. If using a Login Methods rule for any email address, understand that anyone who controls an email address can sign in. In Pages environment settings, configure `ACCESS_TEAM_DOMAIN` (the team subdomain, without `.cloudflareaccess.com`) and `ACCESS_AUD` (that application's audience tag) for Production. The Studio Pages Function validates `Cf-Access-Jwt-Assertion` with Cloudflare's current public keys and fails closed if either setting is absent.
- Protect user-specific API records separately. The current blueprint API is public and share links are accessible by code; it is not an authenticated personal vault. Do not store wallet secrets there.
- NON-HUMAN: the legacy FastAPI agent API is **not** deployed on Workers. It stores signing keys and transactions in local SQLite and has not been migrated to D1 with an audited signing boundary. `/v1/*` must remain unavailable until that migration passes policy, idempotency, concurrency, authorization and chain-adapter tests. Keep `BAW_MAINNET_BROADCAST` disabled.

Cloudflare Access and the Worker route cannot be created from this checkout until the account is authenticated. `wrangler whoami` in the current environment reports unauthenticated. The Pages Function will answer 503 until the Access settings above are configured.

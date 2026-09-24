# Build-a-Wallet: notes

## What this site is
An interactive toy-but-serious tool: a visitor talks to a "wallet architect"
and designs their own crypto wallet. The conversation drives a live phone
preview and ends in a shareable blueprint. Owner's brief (2026-08-25):
"start with a live AI prompt, then interactively build the crypto wallet
solely based on what the user wants, as many features as options."

## Decisions
- The architect is a self-contained conversation engine in `app/brain.py`.
  No external AI API and no keys: the site must stay self-contained, and an
  API key would be a secret in the repo. It parses free text against the
  option catalog, handles refusals ("no memecoins"), answers questions, and
  keeps asking the next useful question.
- 150 options live in `app/catalog.py`: assets, networks, custody, security,
  features, platforms, privacy, look. Adding one there makes it available to
  the chat, the vault and the blueprint at once.
- Eight personas (beginner, trader, privacy, business, bitcoiner, payments,
  family, gaming) let one sentence lay down a whole starting build. They are
  additive only: they never overwrite a decision already made.
- New saved builds get a 26 character random code and live at /w/<code> in
  SQLite at /data/app.db. Earlier six character links remain readable.
  Anyone opening a link can view the design and edit their own copy.
- Preview prices and balances are illustrative, generated deterministically
  from the wallet name. Nothing here touches a real chain and there is no
  wallet software behind it: the output is a design spec.
- The owner prefers a browser extension over an Android APK for HUMAN wallets.
  The separate extension signing prototype supports Sepolia testnet only.
  It has not been released as a wallet for real funds.
- The NON-HUMAN Worker prototype records watch-only Sepolia addresses and
  refuses signing and transfers. Production mainnet service remains gated.
- The public container does not ship or mount the legacy signing API. Its
  saved designs do not collect email or list private link codes in stats.

## Open questions for the owner
- Any interest in a gallery of public builds on the home page?

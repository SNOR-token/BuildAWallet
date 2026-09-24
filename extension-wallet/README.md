# Wallet vault prototype

This is a separate **Sepolia testnet** extension prototype. It derives an EVM address from a 24-word recovery phrase, encrypts its entropy locally with a password-derived AES-GCM key, and signs explicitly reviewed Sepolia EIP-1559 native transfers offline. It cannot broadcast, query balances, connect to websites, or sign for Ethereum mainnet. It is **not included** in the downloadable blueprint extension and is **not a production wallet**. Use only disposable testnet funds.

Run `npm ci`, `npm test`, then `npm run build` in this directory. Load `dist/` as an unpacked extension through `chrome://extensions` Developer mode. Back up the recovery phrase offline before closing its one-time display; there is no provider recovery service. Never enter an existing funded mainnet phrase into this prototype.

`vault.mjs` encrypts 32 bytes of entropy with PBKDF2-SHA256 and AES-256-GCM. The extension restricts its local storage to trusted extension contexts. This protects the stored record from casual disclosure, not from a compromised browser, malicious device or weak password.

The missing work includes reviewed key lifecycle and recovery, checked nonce and fee discovery, simulations, origin permissions, chain-specific adapters beyond Sepolia, transaction broadcast/reconciliation, cross-browser testing and independent security review. Never place raw key material in `chrome.storage.local`, D1, a Worker, or a blueprint JSON file.

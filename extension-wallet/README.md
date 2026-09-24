# Wallet vault prototype

`vault.mjs` encrypts an existing 32-byte secret using a password-derived AES-GCM key. It has tests for round-trip, tampering and wrong passwords. It is **not included** in the downloadable blueprint extension, and it is **not a production wallet**. No secret should be persisted or funded through this prototype.

The missing work includes audited secp256k1 address derivation and chain-aware signing, reliable backup/recovery, secure lifecycle and lock behavior, transaction review, origin permissions, RPC verification, a release bundle with pinned dependencies, cross-browser testing and independent security review. Never place raw key material in `chrome.storage.local`, D1, a Worker, or a blueprint JSON file.

"""Encrypted server-side EVM key custody for Build-a-Wallet.
Master key is supplied only through BAW_MASTER_KEY. Private keys are never returned by HTTP APIs.
"""
from __future__ import annotations
import base64, hashlib, os
from cryptography.fernet import Fernet, InvalidToken
from eth_account import Account

def _fernet() -> Fernet:
    raw=os.environ.get("BAW_MASTER_KEY","")
    if not raw: raise RuntimeError("BAW_MASTER_KEY is not configured")
    # Accept a 32-byte urlsafe-base64 Fernet key, or derive one from a high-entropy deployment secret.
    try:
        decoded=base64.urlsafe_b64decode(raw.encode())
        if len(decoded)==32:return Fernet(raw.encode())
    except Exception: pass
    if len(raw)<32: raise RuntimeError("BAW_MASTER_KEY must contain at least 32 characters of entropy")
    key=base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)

def generate_evm_key() -> tuple[str,str]:
    acct=Account.create(os.urandom(32))
    encrypted=_fernet().encrypt(acct.key).decode()
    return acct.address,encrypted

def decrypt_private_key(ciphertext:str) -> bytes:
    try:return _fernet().decrypt(ciphertext.encode())
    except InvalidToken as e: raise RuntimeError("wallet key cannot be decrypted with configured BAW_MASTER_KEY") from e

"""Build-a-Wallet Agent Protocol v1.

Machine-first wallet infrastructure surface. This module intentionally models
wallet authority and transaction requests; it does not hold private keys or
broadcast blockchain transactions yet. Execution adapters can be added behind
the policy boundary without changing the public protocol.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["Agent Protocol v1"])

# Prototype store. Replace with the project's persistent DB before production.
WALLETS: dict[str, dict] = {}
TRANSACTIONS: dict[str, dict] = {}


class WalletPolicy(BaseModel):
    max_transaction_usd: float | None = Field(default=None, gt=0)
    daily_spend_limit_usd: float | None = Field(default=None, gt=0)
    require_human_approval_above_usd: float | None = Field(default=None, gt=0)
    allowed_actions: list[Literal["balance", "receive", "send"]] = ["balance", "receive"]
    allowed_assets: list[str] = ["LTC"]
    allowed_destinations: list[str] = []
    deny_unknown_destinations: bool = True
    expires_in_seconds: int | None = Field(default=None, ge=60, le=31_536_000)


class CreateWalletIn(BaseModel):
    chain: Literal["litecoin"] = "litecoin"
    custody: Literal["self"] = "self"
    purpose: str = Field(default="agent-wallet", max_length=120)
    wallet_type: Literal["persistent", "task", "session", "budget", "escrow", "multisig"] = "task"
    policy: WalletPolicy = WalletPolicy()


class TransactionIn(BaseModel):
    asset: str = "LTC"
    amount: float = Field(gt=0)
    amount_usd: float = Field(gt=0)
    destination: str = Field(min_length=1, max_length=200)
    memo: str | None = Field(default=None, max_length=240)


def _auth(authorization: str | None) -> None:
    # Protocol boundary is in place now; production should verify hashed API keys,
    # scoped agent credentials, signatures/nonces, rate limits, and tenant identity.
    if authorization is not None and not authorization.startswith("Bearer "):
        raise HTTPException(401, "expected Bearer agent credential")


def _wallet(wallet_id: str) -> dict:
    wallet = WALLETS.get(wallet_id)
    if not wallet:
        raise HTTPException(404, "wallet not found")
    expires_at = wallet.get("expires_at")
    if expires_at and datetime.now(timezone.utc) >= datetime.fromisoformat(expires_at):
        raise HTTPException(403, "wallet authority expired")
    return wallet


@router.post("/wallets", status_code=201)
def create_wallet(body: CreateWalletIn, authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    wallet_id = "wal_" + secrets.token_hex(8)
    now = datetime.now(timezone.utc)
    expires_at = None
    if body.policy.expires_in_seconds:
        expires_at = (now + timedelta(seconds=body.policy.expires_in_seconds)).isoformat()
    wallet = {
        "wallet_id": wallet_id,
        "status": "created",
        "chain": body.chain,
        "custody": body.custody,
        "purpose": body.purpose,
        "wallet_type": body.wallet_type,
        "policy": body.policy.model_dump(),
        "policy_enforced": True,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
        "spent_today_usd": 0.0,
    }
    WALLETS[wallet_id] = wallet
    return {
        **wallet,
        "capabilities": body.policy.allowed_actions,
        "endpoints": {
            "balance": f"/v1/wallets/{wallet_id}/balance",
            "receive": f"/v1/wallets/{wallet_id}/receive",
            "transactions": f"/v1/wallets/{wallet_id}/transactions",
        },
    }


@router.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: str, authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    return _wallet(wallet_id)


@router.get("/wallets/{wallet_id}/balance")
def get_balance(wallet_id: str, authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    wallet = _wallet(wallet_id)
    if "balance" not in wallet["policy"]["allowed_actions"]:
        raise HTTPException(403, "balance capability denied by policy")
    return {"wallet_id": wallet_id, "asset": "LTC", "balance": None, "status": "adapter_required"}


@router.get("/wallets/{wallet_id}/receive")
def get_receive(wallet_id: str, authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    wallet = _wallet(wallet_id)
    if "receive" not in wallet["policy"]["allowed_actions"]:
        raise HTTPException(403, "receive capability denied by policy")
    return {"wallet_id": wallet_id, "address": None, "status": "key_adapter_required"}


@router.post("/wallets/{wallet_id}/transactions", status_code=202)
def create_transaction(wallet_id: str, body: TransactionIn, authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    wallet = _wallet(wallet_id)
    policy = wallet["policy"]
    if "send" not in policy["allowed_actions"]:
        raise HTTPException(403, "send capability denied by policy")
    if body.asset.upper() not in {x.upper() for x in policy["allowed_assets"]}:
        raise HTTPException(403, "asset denied by policy")
    if policy["max_transaction_usd"] and body.amount_usd > policy["max_transaction_usd"]:
        return {"status": "denied", "reason": "max_transaction", "requested_amount_usd": body.amount_usd}
    if policy["daily_spend_limit_usd"] and wallet["spent_today_usd"] + body.amount_usd > policy["daily_spend_limit_usd"]:
        return {"status": "denied", "reason": "daily_spend_limit", "requested_amount_usd": body.amount_usd}
    approved = set(policy["allowed_destinations"])
    if policy["deny_unknown_destinations"] and approved and body.destination not in approved:
        return {"status": "denied", "reason": "destination_not_allowed"}
    threshold = policy["require_human_approval_above_usd"]
    if threshold and body.amount_usd > threshold:
        return {"status": "approval_required", "reason": "human_approval_threshold", "requested_amount_usd": body.amount_usd}

    tx_id = "txr_" + secrets.token_hex(8)
    tx = {"transaction_id": tx_id, "wallet_id": wallet_id, **body.model_dump(), "status": "ready_for_signing"}
    TRANSACTIONS[tx_id] = tx
    # No key access or broadcasting here: signing remains behind an explicit adapter/approval boundary.
    return tx


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "protocol": "Build-a-Wallet Agent Protocol",
        "version": "1.0.0-alpha",
        "chains": ["litecoin"],
        "wallet_types": ["persistent", "task", "session", "budget", "escrow", "multisig"],
        "policy_controls": ["max_transaction", "daily_spend_limit", "human_approval", "asset_allowlist", "destination_allowlist", "expiry"],
        "execution": "policy-and-orchestration-prototype",
    }

from __future__ import annotations
import base64
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from chains import rpc_call

def generate_keypair():
    kp=Keypair()
    return str(kp.pubkey()), bytes(kp)

def balance(address:str):
    Pubkey.from_string(address)
    r=rpc_call("solana","getBalance",[address,{"commitment":"confirmed"}])
    lamports=int(r["value"])
    return {"address":address,"balance_lamports":lamports,"balance_native":str(lamports/1_000_000_000)}

def latest_blockhash():
    return rpc_call("solana","getLatestBlockhash",[{"commitment":"confirmed"}])["value"]

def simulate_transaction(raw:bytes):
    b64=base64.b64encode(raw).decode()
    return rpc_call("solana","simulateTransaction",[b64,{"encoding":"base64","sigVerify":True,"commitment":"confirmed"}])

def broadcast(raw:bytes):
    b64=base64.b64encode(raw).decode()
    return rpc_call("solana","sendTransaction",[b64,{"encoding":"base64","preflightCommitment":"confirmed","skipPreflight":False,"maxRetries":3}])

def receipt(signature:str):
    r=rpc_call("solana","getSignatureStatuses",[[signature],{"searchTransactionHistory":True}])
    row=(r.get("value") or [None])[0]
    if not row:return {"status":"pending","transaction_hash":signature}
    if row.get("err") is not None:return {"status":"failed","transaction_hash":signature,"error":row.get("err")}
    confirmation=row.get("confirmationStatus")
    return {"status":"confirmed" if confirmation in ("confirmed","finalized") else "pending","transaction_hash":signature,"confirmation_status":confirmation,"slot":row.get("slot")}

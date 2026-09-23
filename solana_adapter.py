from __future__ import annotations
import base64
from solders.hash import Hash
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import TransferParams,transfer
from solders.transaction import Transaction
from chains import rpc_call

def generate_keypair():
    kp=Keypair()
    return str(kp.pubkey()), bytes(kp)

def keypair_from_secret(secret:bytes)->Keypair:
    return Keypair.from_bytes(secret)

def balance(address:str):
    Pubkey.from_string(address)
    r=rpc_call("solana","getBalance",[address,{"commitment":"confirmed"}])
    lamports=int(r["value"])
    return {"address":address,"balance_lamports":lamports,"balance_native":str(lamports/1_000_000_000)}

def latest_blockhash():
    return rpc_call("solana","getLatestBlockhash",[{"commitment":"confirmed"}])["value"]

def build_signed_native_transfer(secret:bytes,destination:str,lamports:int)->bytes:
    if int(lamports)<=0: raise ValueError("lamports must be positive")
    kp=keypair_from_secret(secret)
    dest=Pubkey.from_string(destination)
    bh=Hash.from_string(latest_blockhash()["blockhash"])
    ix=transfer(TransferParams(from_pubkey=kp.pubkey(),to_pubkey=dest,lamports=int(lamports)))
    msg=Message.new_with_blockhash([ix],kp.pubkey(),bh)
    tx=Transaction([kp],msg,bh)
    return bytes(tx)

def simulate_transaction(raw:bytes):
    b64=base64.b64encode(raw).decode()
    return rpc_call("solana","simulateTransaction",[b64,{"encoding":"base64","sigVerify":True,"commitment":"confirmed","replaceRecentBlockhash":False}])

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

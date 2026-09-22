"""Build-a-Wallet Agent Protocol v1: persistent policy-controlled agent wallets."""
from __future__ import annotations
import hashlib, json, os, secrets, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router=APIRouter(prefix="/v1",tags=["Agent Protocol v1"])
DATA_DIR=Path(os.environ.get("DATA_DIR","/data")); DB_PATH=DATA_DIR/"app.db"

def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def now(): return datetime.now(timezone.utc)
def token_hash(v:str): return hashlib.sha256(v.encode()).hexdigest()
def jid(prefix): return prefix+secrets.token_hex(12)

def init_agent_db():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS agent_credentials(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,scopes TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_wallets(id TEXT PRIMARY KEY,credential_id TEXT NOT NULL,chain TEXT NOT NULL,wallet_type TEXT NOT NULL,purpose TEXT NOT NULL,policy TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT,FOREIGN KEY(credential_id) REFERENCES agent_credentials(id));
        CREATE TABLE IF NOT EXISTS agent_transactions(id TEXT PRIMARY KEY,wallet_id TEXT NOT NULL,idempotency_key TEXT,asset TEXT NOT NULL,amount REAL NOT NULL,destination TEXT NOT NULL,amount_usd REAL NOT NULL,status TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL,approved_at TEXT,FOREIGN KEY(wallet_id) REFERENCES agent_wallets(id),UNIQUE(wallet_id,idempotency_key));
        CREATE TABLE IF NOT EXISTS agent_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,credential_id TEXT,wallet_id TEXT,kind TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
        """)

def audit(c,kind,detail,wallet_id=None,credential_id=None):
    c.execute("INSERT INTO agent_audit(credential_id,wallet_id,kind,detail,created_at) VALUES(?,?,?,?,?)",(credential_id,wallet_id,kind,json.dumps(detail,separators=(",",":")),now().isoformat()))

class BootstrapIn(BaseModel):
    name:str=Field(default="primary-agent",min_length=1,max_length=80)
class Policy(BaseModel):
    max_transaction_usd:float|None=Field(default=None,gt=0)
    daily_spend_limit_usd:float|None=Field(default=None,gt=0)
    require_human_approval_above_usd:float|None=Field(default=None,gt=0)
    allowed_actions:list[Literal["balance","receive","send"]]=["balance","receive"]
    allowed_assets:list[str]=["LTC"]
    allowed_destinations:list[str]=[]
    deny_unknown_destinations:bool=True
    expires_in_seconds:int|None=Field(default=None,ge=60,le=31536000)
class CreateWalletIn(BaseModel):
    chain:Literal["litecoin"]="litecoin"; purpose:str=Field(default="agent-wallet",max_length=120)
    wallet_type:Literal["persistent","task","session","budget","escrow","multisig"]="task"; policy:Policy=Policy()
class TxIn(BaseModel):
    asset:str="LTC"; amount:float=Field(gt=0); amount_usd:float=Field(gt=0); destination:str=Field(min_length=1,max_length=200); memo:str|None=Field(default=None,max_length=240)
class ApprovalIn(BaseModel): approved:bool; note:str|None=Field(default=None,max_length=240)

def auth(authorization:str|None,scope:str):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"Bearer agent credential required")
    raw=authorization[7:].strip()
    with db() as c: r=c.execute("SELECT * FROM agent_credentials WHERE token_hash=? AND revoked=0",(token_hash(raw),)).fetchone()
    if not r: raise HTTPException(401,"invalid or revoked credential")
    scopes=set(json.loads(r["scopes"]))
    if scope not in scopes and "admin" not in scopes: raise HTTPException(403,"credential scope denied")
    return dict(r)

def wallet_for(wallet_id,cred):
    with db() as c: r=c.execute("SELECT * FROM agent_wallets WHERE id=? AND credential_id=?",(wallet_id,cred["id"])).fetchone()
    if not r: raise HTTPException(404,"wallet not found")
    w=dict(r); w["policy"]=json.loads(w["policy"])
    if w["expires_at"] and now()>=datetime.fromisoformat(w["expires_at"]): raise HTTPException(403,"wallet authority expired")
    return w

@router.post("/credentials/bootstrap",status_code=201)
def bootstrap(body:BootstrapIn,x_bootstrap_secret:str|None=Header(default=None)):
    expected=os.environ.get("AGENT_BOOTSTRAP_SECRET")
    if not expected or not secrets.compare_digest(x_bootstrap_secret or "",expected): raise HTTPException(403,"bootstrap disabled or secret invalid")
    raw="baw_"+secrets.token_urlsafe(32); cid=jid("cred_"); scopes=["wallet:create","wallet:read","tx:create","tx:approve","audit:read"]
    with db() as c:
        c.execute("INSERT INTO agent_credentials VALUES(?,?,?,?,0,?)",(cid,body.name,token_hash(raw),json.dumps(scopes),now().isoformat())); audit(c,"credential.created",{"name":body.name,"scopes":scopes},credential_id=cid)
    return {"credential_id":cid,"token":raw,"scopes":scopes,"warning":"Token is shown once; store it securely."}

@router.post("/wallets",status_code=201)
def create_wallet(body:CreateWalletIn,authorization:str|None=Header(default=None)):
    cred=auth(authorization,"wallet:create"); wid=jid("wal_"); exp=(now()+timedelta(seconds=body.policy.expires_in_seconds)).isoformat() if body.policy.expires_in_seconds else None
    with db() as c:
        c.execute("INSERT INTO agent_wallets VALUES(?,?,?,?,?,?,?,?,?)",(wid,cred["id"],body.chain,body.wallet_type,body.purpose,json.dumps(body.policy.model_dump()),"active",now().isoformat(),exp)); audit(c,"wallet.created",{"type":body.wallet_type,"purpose":body.purpose},wid,cred["id"])
    return {"wallet_id":wid,"status":"active","chain":body.chain,"wallet_type":body.wallet_type,"policy":body.policy.model_dump(),"expires_at":exp,"capabilities":body.policy.allowed_actions}

@router.get("/wallets/{wallet_id}")
def get_wallet(wallet_id:str,authorization:str|None=Header(default=None)):
    cred=auth(authorization,"wallet:read"); return wallet_for(wallet_id,cred)

@router.post("/wallets/{wallet_id}/transactions",status_code=202)
def transaction(wallet_id:str,body:TxIn,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
    cred=auth(authorization,"tx:create"); w=wallet_for(wallet_id,cred); p=w["policy"]
    if not idempotency_key: raise HTTPException(400,"Idempotency-Key header required")
    with db() as c:
        old=c.execute("SELECT * FROM agent_transactions WHERE wallet_id=? AND idempotency_key=?",(wallet_id,idempotency_key)).fetchone()
        if old:return dict(old)
        status="ready_for_signing"; reason=None
        if "send" not in p["allowed_actions"]: status,reason="denied","send_capability"
        elif body.asset.upper() not in {x.upper() for x in p["allowed_assets"]}: status,reason="denied","asset_not_allowed"
        elif p["max_transaction_usd"] and body.amount_usd>p["max_transaction_usd"]: status,reason="denied","max_transaction"
        elif p["deny_unknown_destinations"] and p["allowed_destinations"] and body.destination not in set(p["allowed_destinations"]): status,reason="denied","destination_not_allowed"
        else:
            day=now().date().isoformat(); spent=c.execute("SELECT COALESCE(SUM(amount_usd),0) FROM agent_transactions WHERE wallet_id=? AND status IN ('ready_for_signing','broadcast','confirmed') AND substr(created_at,1,10)=?",(wallet_id,day)).fetchone()[0]
            if p["daily_spend_limit_usd"] and spent+body.amount_usd>p["daily_spend_limit_usd"]: status,reason="denied","daily_spend_limit"
            elif p["require_human_approval_above_usd"] and body.amount_usd>p["require_human_approval_above_usd"]: status,reason="approval_required","human_approval_threshold"
        tid=jid("txr_"); c.execute("INSERT INTO agent_transactions(id,wallet_id,idempotency_key,asset,amount,destination,amount_usd,status,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(tid,wallet_id,idempotency_key,body.asset.upper(),body.amount,body.destination,body.amount_usd,status,reason,now().isoformat())); audit(c,"transaction.requested",{"transaction_id":tid,"status":status,"reason":reason},wallet_id,cred["id"])
        return dict(c.execute("SELECT * FROM agent_transactions WHERE id=?",(tid,)).fetchone())

@router.post("/transactions/{tx_id}/approval")
def approve(tx_id:str,body:ApprovalIn,authorization:str|None=Header(default=None)):
    cred=auth(authorization,"tx:approve")
    with db() as c:
        tx=c.execute("SELECT t.* FROM agent_transactions t JOIN agent_wallets w ON w.id=t.wallet_id WHERE t.id=? AND w.credential_id=?",(tx_id,cred["id"])).fetchone()
        if not tx: raise HTTPException(404,"transaction not found")
        if tx["status"]!="approval_required": raise HTTPException(409,"transaction is not awaiting approval")
        status="ready_for_signing" if body.approved else "denied"; reason=None if body.approved else "human_rejected"; approved_at=now().isoformat() if body.approved else None
        c.execute("UPDATE agent_transactions SET status=?,reason=?,approved_at=? WHERE id=?",(status,reason,approved_at,tx_id)); audit(c,"transaction.approval",{"transaction_id":tx_id,"approved":body.approved,"note":body.note},tx["wallet_id"],cred["id"])
        return dict(c.execute("SELECT * FROM agent_transactions WHERE id=?",(tx_id,)).fetchone())

@router.get("/audit")
def audit_log(authorization:str|None=Header(default=None),limit:int=50):
    cred=auth(authorization,"audit:read"); limit=max(1,min(limit,200))
    with db() as c: rows=c.execute("SELECT * FROM agent_audit WHERE credential_id=? ORDER BY id DESC LIMIT ?",(cred["id"],limit)).fetchall()
    return {"events":[dict(x) for x in rows]}

@router.get("/capabilities")
def capabilities():
    return {"protocol":"Build-a-Wallet Agent Protocol","version":"1.0.0-alpha.2","chains":["litecoin"],"persistence":True,"authentication":"hashed bearer credentials","idempotency":True,"audit_log":True,"approval_workflow":True,"execution":"signing adapter not enabled"}

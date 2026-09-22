"""Build-a-Wallet Agent Protocol v1: persistent multi-chain policy authority."""
from __future__ import annotations
import hashlib,json,os,secrets,sqlite3
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,Field
from chains import CHAINS,public_registry,health
router=APIRouter(prefix="/v1",tags=["Agent Protocol v1"]);DATA_DIR=Path(os.environ.get("DATA_DIR","/data"));DB_PATH=DATA_DIR/"app.db"
def db():c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def now():return datetime.now(timezone.utc)
def token_hash(v):return hashlib.sha256(v.encode()).hexdigest()
def jid(p):return p+secrets.token_hex(12)
def init_agent_db():
 DATA_DIR.mkdir(parents=True,exist_ok=True)
 with db() as c:c.executescript("""CREATE TABLE IF NOT EXISTS agent_credentials(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,scopes TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS agent_wallets(id TEXT PRIMARY KEY,credential_id TEXT NOT NULL,chain TEXT NOT NULL,wallet_type TEXT NOT NULL,purpose TEXT NOT NULL,policy TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT);CREATE TABLE IF NOT EXISTS agent_transactions(id TEXT PRIMARY KEY,wallet_id TEXT NOT NULL,idempotency_key TEXT,asset TEXT NOT NULL,amount REAL NOT NULL,destination TEXT NOT NULL,amount_usd REAL NOT NULL,status TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL,approved_at TEXT,UNIQUE(wallet_id,idempotency_key));CREATE TABLE IF NOT EXISTS agent_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,credential_id TEXT,wallet_id TEXT,kind TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);""")
def audit(c,k,d,w=None,cr=None):c.execute("INSERT INTO agent_audit(credential_id,wallet_id,kind,detail,created_at) VALUES(?,?,?,?,?)",(cr,w,k,json.dumps(d,separators=(",",":")),now().isoformat()))
class BootstrapIn(BaseModel):name:str=Field(default="primary-agent",min_length=1,max_length=80)
class Policy(BaseModel):
 max_transaction_usd:float|None=Field(default=None,gt=0);daily_spend_limit_usd:float|None=Field(default=None,gt=0);require_human_approval_above_usd:float|None=Field(default=None,gt=0);allowed_actions:list[Literal["balance","receive","send"]]=["balance","receive"];allowed_assets:list[str]=[];allowed_destinations:list[str]=[];deny_unknown_destinations:bool=True;expires_in_seconds:int|None=Field(default=None,ge=60,le=31536000)
class CreateWalletIn(BaseModel):chain:str;purpose:str=Field(default="agent-wallet",max_length=120);wallet_type:Literal["persistent","task","session","budget","escrow","multisig"]="task";policy:Policy=Policy()
class TxIn(BaseModel):asset:str;amount:float=Field(gt=0);amount_usd:float=Field(gt=0);destination:str=Field(min_length=1,max_length=200);memo:str|None=Field(default=None,max_length=240)
class ApprovalIn(BaseModel):approved:bool;note:str|None=Field(default=None,max_length=240)
def auth(a,scope):
 if not a or not a.startswith("Bearer "):raise HTTPException(401,"Bearer agent credential required")
 with db() as c:r=c.execute("SELECT * FROM agent_credentials WHERE token_hash=? AND revoked=0",(token_hash(a[7:].strip()),)).fetchone()
 if not r:raise HTTPException(401,"invalid or revoked credential")
 if scope not in set(json.loads(r["scopes"])) and "admin" not in set(json.loads(r["scopes"])):raise HTTPException(403,"credential scope denied")
 return dict(r)
def wallet_for(wid,cred):
 with db() as c:r=c.execute("SELECT * FROM agent_wallets WHERE id=? AND credential_id=?",(wid,cred["id"])).fetchone()
 if not r:raise HTTPException(404,"wallet not found")
 w=dict(r);w["policy"]=json.loads(w["policy"])
 if w["expires_at"] and now()>=datetime.fromisoformat(w["expires_at"]):raise HTTPException(403,"wallet authority expired")
 return w
@router.post("/credentials/bootstrap",status_code=201)
def bootstrap(b:BootstrapIn,x_bootstrap_secret:str|None=Header(default=None)):
 e=os.environ.get("AGENT_BOOTSTRAP_SECRET")
 if not e or not secrets.compare_digest(x_bootstrap_secret or "",e):raise HTTPException(403,"bootstrap disabled or secret invalid")
 raw="baw_"+secrets.token_urlsafe(32);cid=jid("cred_");sc=["wallet:create","wallet:read","tx:create","tx:approve","audit:read","chain:read"]
 with db() as c:c.execute("INSERT INTO agent_credentials VALUES(?,?,?,?,0,?)",(cid,b.name,token_hash(raw),json.dumps(sc),now().isoformat()));audit(c,"credential.created",{"name":b.name,"scopes":sc},cr=cid)
 return {"credential_id":cid,"token":raw,"scopes":sc,"warning":"Token is shown once."}
@router.get("/chains")
def chains():return {"network":"mainnet","chains":public_registry()}
@router.get("/chains/{chain}/health")
def chain_health(chain:str,authorization:str|None=Header(default=None)):
 auth(authorization,"chain:read")
 if chain not in CHAINS:raise HTTPException(404,"unsupported chain")
 try:return health(chain)
 except Exception as e:raise HTTPException(503,str(e))
@router.post("/wallets",status_code=201)
def create_wallet(b:CreateWalletIn,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"wallet:create")
 if b.chain not in CHAINS:raise HTTPException(400,"unsupported chain")
 wid=jid("wal_");exp=(now()+timedelta(seconds=b.policy.expires_in_seconds)).isoformat() if b.policy.expires_in_seconds else None;p=b.policy.model_dump();p["allowed_assets"]=p["allowed_assets"] or [CHAINS[b.chain]["symbol"]]
 with db() as c:c.execute("INSERT INTO agent_wallets VALUES(?,?,?,?,?,?,?,?,?)",(wid,cr["id"],b.chain,b.wallet_type,b.purpose,json.dumps(p),"active",now().isoformat(),exp));audit(c,"wallet.created",{"chain":b.chain,"type":b.wallet_type},wid,cr["id"])
 return {"wallet_id":wid,"network":"mainnet","chain":b.chain,"status":"active","wallet_type":b.wallet_type,"policy":p,"expires_at":exp}
@router.get("/wallets/{wallet_id}")
def get_wallet(wallet_id:str,authorization:str|None=Header(default=None)):return wallet_for(wallet_id,auth(authorization,"wallet:read"))
@router.post("/wallets/{wallet_id}/transactions",status_code=202)
def transaction(wallet_id:str,b:TxIn,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
 cr=auth(authorization,"tx:create");w=wallet_for(wallet_id,cr);p=w["policy"]
 if not idempotency_key:raise HTTPException(400,"Idempotency-Key header required")
 with db() as c:
  old=c.execute("SELECT * FROM agent_transactions WHERE wallet_id=? AND idempotency_key=?",(wallet_id,idempotency_key)).fetchone()
  if old:return dict(old)
  s="ready_for_signing";r=None
  if "send" not in p["allowed_actions"]:s,r="denied","send_capability"
  elif b.asset.upper() not in {x.upper() for x in p["allowed_assets"]}:s,r="denied","asset_not_allowed"
  elif p["max_transaction_usd"] and b.amount_usd>p["max_transaction_usd"]:s,r="denied","max_transaction"
  elif p["deny_unknown_destinations"] and p["allowed_destinations"] and b.destination not in set(p["allowed_destinations"]):s,r="denied","destination_not_allowed"
  else:
   spent=c.execute("SELECT COALESCE(SUM(amount_usd),0) FROM agent_transactions WHERE wallet_id=? AND status IN ('ready_for_signing','broadcast','confirmed') AND substr(created_at,1,10)=?",(wallet_id,now().date().isoformat())).fetchone()[0]
   if p["daily_spend_limit_usd"] and spent+b.amount_usd>p["daily_spend_limit_usd"]:s,r="denied","daily_spend_limit"
   elif p["require_human_approval_above_usd"] and b.amount_usd>p["require_human_approval_above_usd"]:s,r="approval_required","human_approval_threshold"
  tid=jid("txr_");c.execute("INSERT INTO agent_transactions(id,wallet_id,idempotency_key,asset,amount,destination,amount_usd,status,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(tid,wallet_id,idempotency_key,b.asset.upper(),b.amount,b.destination,b.amount_usd,s,r,now().isoformat()));audit(c,"transaction.requested",{"transaction_id":tid,"chain":w["chain"],"status":s,"reason":r},wallet_id,cr["id"]);return dict(c.execute("SELECT * FROM agent_transactions WHERE id=?",(tid,)).fetchone())
@router.post("/transactions/{tx_id}/approval")
def approve(tx_id:str,b:ApprovalIn,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"tx:approve")
 with db() as c:
  tx=c.execute("SELECT t.* FROM agent_transactions t JOIN agent_wallets w ON w.id=t.wallet_id WHERE t.id=? AND w.credential_id=?",(tx_id,cr["id"])).fetchone()
  if not tx:raise HTTPException(404,"transaction not found")
  if tx["status"]!="approval_required":raise HTTPException(409,"transaction is not awaiting approval")
  s="ready_for_signing" if b.approved else "denied";r=None if b.approved else "human_rejected";at=now().isoformat() if b.approved else None;c.execute("UPDATE agent_transactions SET status=?,reason=?,approved_at=? WHERE id=?",(s,r,at,tx_id));audit(c,"transaction.approval",{"transaction_id":tx_id,"approved":b.approved},tx["wallet_id"],cr["id"]);return dict(c.execute("SELECT * FROM agent_transactions WHERE id=?",(tx_id,)).fetchone())
@router.get("/audit")
def audit_log(authorization:str|None=Header(default=None),limit:int=50):
 cr=auth(authorization,"audit:read");limit=max(1,min(limit,200))
 with db() as c:r=c.execute("SELECT * FROM agent_audit WHERE credential_id=? ORDER BY id DESC LIMIT ?",(cr["id"],limit)).fetchall()
 return {"events":[dict(x) for x in r]}
@router.get("/capabilities")
def capabilities():return {"protocol":"Build-a-Wallet Agent Protocol","version":"1.0.0-alpha.3","network":"mainnet","chains":list(CHAINS),"persistence":True,"authentication":"hashed bearer credentials","idempotency":True,"audit_log":True,"approval_workflow":True,"execution":{"evm":"prepare/simulate adapter available","solana":"registry/RPC available","utxo":"registry/RPC available"}}

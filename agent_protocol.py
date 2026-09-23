"""Build-a-Wallet Agent Protocol: multi-chain policy authority and mainnet execution."""
from __future__ import annotations
import hashlib,json,os,secrets,sqlite3
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,Field
from chains import CHAINS,public_registry,health
from evm import balance as evm_balance,prepare_native,sign_transaction,broadcast_signed,receipt as evm_receipt
from solana_adapter import generate_keypair as generate_solana_keypair,balance as sol_balance,receipt as sol_receipt,build_signed_native_transfer as sol_build,broadcast as sol_broadcast,simulate_transaction as sol_simulate
from utxo_adapter import generate_key as generate_utxo_key,balance as utxo_balance,receipt as utxo_receipt,build_signed_native_transfer as utxo_build,broadcast as utxo_broadcast
from wallet_crypto import generate_evm_key,encrypt_secret,decrypt_private_key,decrypt_secret
from pricing import value_usd
router=APIRouter(prefix="/v1",tags=["Agent Protocol v1"]);DATA_DIR=Path(os.environ.get("DATA_DIR",str(Path.home()/".build-a-wallet")));DB_PATH=DATA_DIR/"app.db"
def db():c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def now():return datetime.now(timezone.utc)
def token_hash(v):return hashlib.sha256(v.encode()).hexdigest()
def jid(p):return p+secrets.token_hex(12)
def cols(c,t):return {x["name"] for x in c.execute(f"PRAGMA table_info({t})").fetchall()}
def init_agent_db():
 DATA_DIR.mkdir(parents=True,exist_ok=True)
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS agent_credentials(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,scopes TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS agent_wallets(id TEXT PRIMARY KEY,credential_id TEXT NOT NULL,chain TEXT NOT NULL,wallet_type TEXT NOT NULL,purpose TEXT NOT NULL,policy TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT);CREATE TABLE IF NOT EXISTS agent_transactions(id TEXT PRIMARY KEY,wallet_id TEXT NOT NULL,idempotency_key TEXT,asset TEXT NOT NULL,amount REAL NOT NULL,destination TEXT NOT NULL,amount_usd REAL NOT NULL,status TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL,approved_at TEXT,UNIQUE(wallet_id,idempotency_key));CREATE TABLE IF NOT EXISTS agent_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,credential_id TEXT,wallet_id TEXT,kind TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);""")
  wc=cols(c,"agent_wallets")
  if "address" not in wc:c.execute("ALTER TABLE agent_wallets ADD COLUMN address TEXT")
  if "encrypted_key" not in wc:c.execute("ALTER TABLE agent_wallets ADD COLUMN encrypted_key TEXT")
  tc=cols(c,"agent_transactions")
  if "tx_hash" not in tc:c.execute("ALTER TABLE agent_transactions ADD COLUMN tx_hash TEXT")
  if "execution_json" not in tc:c.execute("ALTER TABLE agent_transactions ADD COLUMN execution_json TEXT")
  if "valuation_json" not in tc:c.execute("ALTER TABLE agent_transactions ADD COLUMN valuation_json TEXT")
  if "request_hash" not in tc:c.execute("ALTER TABLE agent_transactions ADD COLUMN request_hash TEXT")
def audit(c,k,d,w=None,cr=None):c.execute("INSERT INTO agent_audit(credential_id,wallet_id,kind,detail,created_at) VALUES(?,?,?,?,?)",(cr,w,k,json.dumps(d,separators=(",",":")),now().isoformat()))
class BootstrapIn(BaseModel):name:str=Field(default="primary-agent",min_length=1,max_length=80);role:Literal["agent","operator"]="agent"
class Policy(BaseModel):
 max_transaction_usd:float|None=Field(default=None,gt=0);daily_spend_limit_usd:float|None=Field(default=None,gt=0);require_human_approval_above_usd:float|None=Field(default=None,gt=0);allowed_actions:list[Literal["balance","receive","send"]]=["balance","receive"];allowed_assets:list[str]=[];allowed_destinations:list[str]=[];deny_unknown_destinations:bool=True;expires_in_seconds:int|None=Field(default=None,ge=60,le=31536000)
class CreateWalletIn(BaseModel):chain:str;purpose:str=Field(default="agent-wallet",max_length=120);wallet_type:Literal["persistent","task","session","budget","escrow","multisig"]="task";policy:Policy=Policy()
class TxIn(BaseModel):asset:str;amount:float=Field(gt=0);destination:str=Field(min_length=1,max_length=200);memo:str|None=Field(default=None,max_length=240)
class ApprovalIn(BaseModel):approved:bool;note:str|None=Field(default=None,max_length=240)
def auth(a,scope):
 if not a or not a.startswith("Bearer "):raise HTTPException(401,"Bearer credential required")
 with db() as c:r=c.execute("SELECT * FROM agent_credentials WHERE token_hash=? AND revoked=0",(token_hash(a[7:].strip()),)).fetchone()
 if not r:raise HTTPException(401,"invalid or revoked credential")
 ss=set(json.loads(r["scopes"]));
 if scope not in ss and "admin" not in ss:raise HTTPException(403,"credential scope denied")
 return dict(r)
def wallet_for(wid,cred,operator=False):
 with db() as c:r=c.execute("SELECT * FROM agent_wallets WHERE id=?"+("" if operator else " AND credential_id=?"),(wid,) if operator else (wid,cred["id"])).fetchone()
 if not r:raise HTTPException(404,"wallet not found")
 w=dict(r);w["policy"]=json.loads(w["policy"])
 if w["status"]!="active":raise HTTPException(403,"wallet is not active")
 if w["expires_at"] and now()>=datetime.fromisoformat(w["expires_at"]):raise HTTPException(403,"wallet authority expired")
 return w
@router.post("/credentials/bootstrap",status_code=201)
def bootstrap(b:BootstrapIn,x_bootstrap_secret:str|None=Header(default=None)):
 e=os.environ.get("AGENT_BOOTSTRAP_SECRET")
 if not e or not secrets.compare_digest(x_bootstrap_secret or "",e):raise HTTPException(403,"bootstrap disabled or secret invalid")
 raw="baw_"+secrets.token_urlsafe(32);cid=jid("cred_");sc=["wallet:create","wallet:read","tx:create","chain:read"] if b.role=="agent" else ["tx:approve","tx:execute","audit:read","wallet:freeze","credential:revoke","chain:read"]
 with db() as c:c.execute("INSERT INTO agent_credentials VALUES(?,?,?,?,0,?)",(cid,b.name,token_hash(raw),json.dumps(sc),now().isoformat()));audit(c,"credential.created",{"name":b.name,"role":b.role,"scopes":sc},cr=cid)
 return {"credential_id":cid,"role":b.role,"token":raw,"scopes":sc,"warning":"Token is shown once."}
@router.post("/credentials/{credential_id}/revoke")
def revoke(credential_id:str,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"credential:revoke")
 with db() as c:
  if not c.execute("SELECT 1 FROM agent_credentials WHERE id=?",(credential_id,)).fetchone():raise HTTPException(404,"credential not found")
  c.execute("UPDATE agent_credentials SET revoked=1 WHERE id=?",(credential_id,));audit(c,"credential.revoked",{"credential_id":credential_id},cr=cr["id"])
 return {"credential_id":credential_id,"revoked":True}
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
 cfg=CHAINS[b.chain]
 try:
  if cfg["family"]=="evm":address,enc=generate_evm_key()
  elif cfg["family"]=="solana":address,secret=generate_solana_keypair();enc=encrypt_secret(secret)
  elif cfg["family"]=="utxo":address,wif=generate_utxo_key(b.chain);enc=encrypt_secret(wif.encode())
  else:raise RuntimeError("unsupported chain family")
 except Exception as e:raise HTTPException(503,str(e))
 wid=jid("wal_");exp=(now()+timedelta(seconds=b.policy.expires_in_seconds)).isoformat() if b.policy.expires_in_seconds else None;p=b.policy.model_dump();p["allowed_assets"]=p["allowed_assets"] or [cfg["symbol"]]
 with db() as c:c.execute("INSERT INTO agent_wallets(id,credential_id,chain,wallet_type,purpose,policy,status,created_at,expires_at,address,encrypted_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(wid,cr["id"],b.chain,b.wallet_type,b.purpose,json.dumps(p),"active",now().isoformat(),exp,address,enc));audit(c,"wallet.created",{"chain":b.chain,"type":b.wallet_type,"address":address},wid,cr["id"])
 return {"wallet_id":wid,"network":"mainnet","chain":b.chain,"address":address,"status":"active","wallet_type":b.wallet_type,"policy":p,"expires_at":exp}
@router.get("/wallets/{wallet_id}")
def get_wallet(wallet_id:str,authorization:str|None=Header(default=None)):
 w=wallet_for(wallet_id,auth(authorization,"wallet:read"));w.pop("encrypted_key",None);return w
@router.get("/wallets/{wallet_id}/balance")
def get_balance(wallet_id:str,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"wallet:read");w=wallet_for(wallet_id,cr);family=CHAINS[w["chain"]]["family"]
 try:data=evm_balance(w["chain"],w["address"]) if family=="evm" else sol_balance(w["address"]) if family=="solana" else utxo_balance(w["chain"],w["address"]);return {"wallet_id":wallet_id,"chain":w["chain"],**data}
 except Exception as e:raise HTTPException(503,str(e))
@router.post("/wallets/{wallet_id}/freeze")
def freeze(wallet_id:str,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"wallet:freeze");wallet_for(wallet_id,cr,True)
 with db() as c:c.execute("UPDATE agent_wallets SET status='frozen' WHERE id=?",(wallet_id,));audit(c,"wallet.frozen",{},wallet_id,cr["id"])
 return {"wallet_id":wallet_id,"status":"frozen"}
@router.post("/wallets/{wallet_id}/transactions",status_code=202)
def transaction(wallet_id:str,b:TxIn,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
 cr=auth(authorization,"tx:create");w=wallet_for(wallet_id,cr);p=w["policy"]
 if not idempotency_key:raise HTTPException(400,"Idempotency-Key header required")
 req_hash=hashlib.sha256(json.dumps(b.model_dump(),sort_keys=True,separators=(",",":")).encode()).hexdigest()
 try:v=value_usd(b.asset,b.amount)
 except Exception as e:raise HTTPException(503,f"authoritative valuation failed: {e}")
 amount_usd=v["value_usd"]
 with db() as c:
  c.execute("BEGIN IMMEDIATE")
  old=c.execute("SELECT * FROM agent_transactions WHERE wallet_id=? AND idempotency_key=?",(wallet_id,idempotency_key)).fetchone()
  if old:
   if old["request_hash"] and old["request_hash"]!=req_hash:raise HTTPException(409,"Idempotency-Key reused with different request")
   return dict(old)
  s="ready_for_signing";r=None
  if "send" not in p["allowed_actions"]:s,r="denied","send_capability"
  elif b.asset.upper() not in {x.upper() for x in p["allowed_assets"]}:s,r="denied","asset_not_allowed"
  elif p["max_transaction_usd"] and amount_usd>p["max_transaction_usd"]:s,r="denied","max_transaction"
  elif p["deny_unknown_destinations"] and p["allowed_destinations"] and b.destination not in set(p["allowed_destinations"]):s,r="denied","destination_not_allowed"
  else:
   spent=c.execute("SELECT COALESCE(SUM(amount_usd),0) FROM agent_transactions WHERE wallet_id=? AND status IN ('approval_required','ready_for_signing','executing','broadcast','confirmed') AND substr(created_at,1,10)=?",(wallet_id,now().date().isoformat())).fetchone()[0]
   if p["daily_spend_limit_usd"] and spent+amount_usd>p["daily_spend_limit_usd"]:s,r="denied","daily_spend_limit"
   elif p["require_human_approval_above_usd"] and amount_usd>p["require_human_approval_above_usd"]:s,r="approval_required","human_approval_threshold"
  tid=jid("txr_");c.execute("INSERT INTO agent_transactions(id,wallet_id,idempotency_key,asset,amount,destination,amount_usd,status,reason,created_at,valuation_json,request_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(tid,wallet_id,idempotency_key,b.asset.upper(),b.amount,b.destination,amount_usd,s,r,now().isoformat(),json.dumps(v),req_hash));audit(c,"transaction.requested",{"transaction_id":tid,"chain":w["chain"],"status":s,"reason":r,"valuation":v},wallet_id,cr["id"]);return dict(c.execute("SELECT * FROM agent_transactions WHERE id=?",(tid,)).fetchone())
@router.post("/transactions/{tx_id}/approval")
def approve(tx_id:str,b:ApprovalIn,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"tx:approve")
 with db() as c:
  tx=c.execute("SELECT * FROM agent_transactions WHERE id=?",(tx_id,)).fetchone()
  if not tx:raise HTTPException(404,"transaction not found")
  if tx["status"]!="approval_required":raise HTTPException(409,"transaction is not awaiting approval")
  s="ready_for_signing" if b.approved else "denied";r=None if b.approved else "human_rejected";at=now().isoformat() if b.approved else None;c.execute("UPDATE agent_transactions SET status=?,reason=?,approved_at=? WHERE id=?",(s,r,at,tx_id));audit(c,"transaction.approval",{"transaction_id":tx_id,"approved":b.approved},tx["wallet_id"],cr["id"]);return dict(c.execute("SELECT * FROM agent_transactions WHERE id=?",(tx_id,)).fetchone())
@router.post("/transactions/{tx_id}/execute")
def execute(tx_id:str,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"tx:execute")
 if os.environ.get("BAW_MAINNET_BROADCAST")!="I_UNDERSTAND_MAINNET":raise HTTPException(403,"mainnet broadcast safety switch is disabled")
 with db() as c:
  c.execute("BEGIN IMMEDIATE")
  tx=c.execute("SELECT * FROM agent_transactions WHERE id=?",(tx_id,)).fetchone()
  if not tx:raise HTTPException(404,"transaction not found")
  if tx["status"]!="ready_for_signing":raise HTTPException(409,"transaction is not ready for signing")
  w=dict(c.execute("SELECT * FROM agent_wallets WHERE id=?",(tx["wallet_id"],)).fetchone());cfg=CHAINS[w["chain"]]
  if not w or w["status"]!="active":raise HTTPException(403,"wallet is not active")
  if tx["asset"].upper()!=cfg["symbol"].upper():raise HTTPException(501,"token execution not enabled in this endpoint")
  c.execute("UPDATE agent_transactions SET status='executing' WHERE id=? AND status='ready_for_signing'",(tx_id,))
  try:
   if cfg["family"]=="evm":
    prepared=prepare_native(w["chain"],w["address"],tx["destination"],int(round(float(tx["amount"])*10**18)));raw=sign_transaction(prepared["unsigned_transaction"],decrypt_private_key(w["encrypted_key"]));txh=broadcast_signed(w["chain"],raw);meta={"family":"evm","fee_wei":prepared["fee_wei"],"simulation":prepared["simulation"]}
   elif cfg["family"]=="solana":
    raw=sol_build(decrypt_secret(w["encrypted_key"]),tx["destination"],int(round(float(tx["amount"])*1_000_000_000)));sim=sol_simulate(raw);err=(sim.get("value") or {}).get("err")
    if err is not None:raise RuntimeError(f"Solana simulation failed: {err}")
    txh=sol_broadcast(raw);meta={"family":"solana","simulation":"passed"}
   elif cfg["family"]=="utxo":
    built=utxo_build(w["chain"],decrypt_secret(w["encrypted_key"]).decode(),w["address"],tx["destination"],float(tx["amount"]));txh=utxo_broadcast(w["chain"],built["raw_hex"]);meta={"family":"utxo",**{k:v for k,v in built.items() if k!="raw_hex"}}
   else:raise RuntimeError("unsupported execution family")
  except Exception as e:
   c.execute("UPDATE agent_transactions SET status='ready_for_signing',reason=? WHERE id=?",(f"execution_error:{type(e).__name__}",tx_id));audit(c,"transaction.execution_failed",{"transaction_id":tx_id,"error":str(e)},w["id"],cr["id"]);raise HTTPException(503,str(e))
  c.execute("UPDATE agent_transactions SET status='broadcast',tx_hash=?,execution_json=?,reason=NULL WHERE id=?",(txh,json.dumps(meta),tx_id));audit(c,"transaction.broadcast",{"transaction_id":tx_id,"tx_hash":txh,"family":cfg["family"]},w["id"],cr["id"])
  return {"transaction_id":tx_id,"status":"broadcast","chain":w["chain"],"tx_hash":txh,"execution":meta}
@router.get("/transactions/{tx_id}/receipt")
def tx_receipt(tx_id:str,authorization:str|None=Header(default=None)):
 cr=auth(authorization,"chain:read")
 with db() as c:
  tx=c.execute("SELECT * FROM agent_transactions WHERE id=?",(tx_id,)).fetchone()
  if not tx:raise HTTPException(404,"transaction not found")
  if not tx["tx_hash"]:return {"transaction_id":tx_id,"status":tx["status"]}
  w=c.execute("SELECT * FROM agent_wallets WHERE id=?",(tx["wallet_id"],)).fetchone();family=CHAINS[w["chain"]]["family"]
  try:r=evm_receipt(w["chain"],tx["tx_hash"]) if family=="evm" else sol_receipt(tx["tx_hash"]) if family=="solana" else utxo_receipt(w["chain"],tx["tx_hash"])
  except Exception as e:raise HTTPException(503,str(e))
  if r["status"] in ("confirmed","failed"):
   c.execute("UPDATE agent_transactions SET status=? WHERE id=?",(r["status"],tx_id));audit(c,"transaction.receipt",r,w["id"],cr["id"])
  return {"transaction_id":tx_id,"chain":w["chain"],**r}
@router.get("/audit")
def audit_log(authorization:str|None=Header(default=None),limit:int=50):
 cr=auth(authorization,"audit:read");limit=max(1,min(limit,200))
 with db() as c:r=c.execute("SELECT * FROM agent_audit ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
 return {"events":[dict(x) for x in r]}
@router.get("/capabilities")
def capabilities():return {"protocol":"Build-a-Wallet Agent Protocol","version":"1.0.0-alpha.6","network":"mainnet","chains":list(CHAINS),"custody":{"evm":"encrypted","solana":"encrypted","utxo":"encrypted"},"balances":{"evm":True,"solana":True,"utxo":True},"authoritative_pricing":True,"operator_separation":True,"credential_revocation":True,"wallet_freeze":True,"execution":{"evm_native":"enabled behind safety switch","sol_native":"enabled behind safety switch with simulation","btc_native":"enabled behind safety switch","ltc_native":"enabled behind safety switch","tokens":"not yet enabled"},"broadcast_safety_switch":"BAW_MAINNET_BROADCAST=I_UNDERSTAND_MAINNET"}

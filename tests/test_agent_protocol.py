import os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
os.environ["DATA_DIR"]="/tmp/baw-test-data"
os.environ["AGENT_BOOTSTRAP_SECRET"]="test-bootstrap-secret"
os.environ["BAW_MASTER_KEY"]="test-master-key-with-at-least-32-bytes-of-entropy"
shutil.rmtree(os.environ["DATA_DIR"],ignore_errors=True)
from fastapi.testclient import TestClient
from fastapi import FastAPI
import agent_protocol
from main import app as public_app
# Exercise the legacy code only in an explicit local test app. The public app
# never mounts this router and cannot create keys or execute transactions.
local_app=FastAPI()
local_app.include_router(agent_protocol.router)
agent_protocol.init_agent_db()
client=TestClient(local_app)

def credential(role="agent",name=None):
 r=client.post("/v1/credentials/bootstrap",headers={"X-Bootstrap-Secret":"test-bootstrap-secret"},json={"name":name or f"test-{role}","role":role});assert r.status_code==201;return r.json()
def fake_value(symbol,amount):return {"symbol":symbol.upper(),"price_usd":10000.0,"source":"test","source_timestamp":1,"fetched_at":1,"amount":float(amount),"value_usd":float(amount)*10000.0}

def test_all_protocol_paths(monkeypatch):
 monkeypatch.setattr(agent_protocol,"value_usd",fake_value)
 with client:
  r=client.get("/v1/chains");assert r.status_code==200;ids={x["id"] for x in r.json()["chains"]};assert {"ethereum","base","arbitrum","optimism","avalanche","solana","bitcoin","litecoin","bnb","polygon"}<=ids;assert r.json()["network"]=="mainnet"
  m=TestClient(public_app).get("/.well-known/agent.json");assert m.status_code==200;assert m.json()["agent_api"]=="not deployed"

  agent=credential("agent","test-agent");operator=credential("operator","test-operator")
  ah={"Authorization":f"Bearer {agent['token']}"};oh={"Authorization":f"Bearer {operator['token']}"}
  assert "tx:approve" not in agent["scopes"] and "tx:approve" in operator["scopes"]
  rw=client.post("/v1/wallets",headers=ah,json={"chain":"base","wallet_type":"task","purpose":"test","policy":{"allowed_actions":["balance","receive","send"],"allowed_assets":["ETH"],"max_transaction_usd":25,"daily_spend_limit_usd":50,"require_human_approval_above_usd":10,"expires_in_seconds":3600}});assert rw.status_code==201;wid=rw.json()["wallet_id"];assert rw.json()["address"].startswith("0x") and len(rw.json()["address"])==42
  th={**ah,"Idempotency-Key":"job-1"};body={"asset":"ETH","amount":0.0015,"destination":"0x000000000000000000000000000000000000dEaD"}
  a=client.post(f"/v1/wallets/{wid}/transactions",headers=th,json=body);assert a.status_code==202;assert a.json()["status"]=="approval_required";assert a.json()["amount_usd"]==15
  b=client.post(f"/v1/wallets/{wid}/transactions",headers=th,json=body);assert b.json()["id"]==a.json()["id"]
  bad=client.post(f"/v1/wallets/{wid}/transactions",headers=th,json={**body,"amount":0.002});assert bad.status_code==409
  assert client.post(f"/v1/transactions/{a.json()['id']}/approval",headers=ah,json={"approved":True}).status_code==403
  c=client.post(f"/v1/transactions/{a.json()['id']}/approval",headers=oh,json={"approved":True});assert c.status_code==200;assert c.json()["status"]=="ready_for_signing"
  audit=client.get("/v1/audit",headers=oh);assert audit.status_code==200;assert len(audit.json()["events"])>=3

  sol=client.post("/v1/wallets",headers=ah,json={"chain":"solana"});assert sol.status_code==201;assert len(sol.json()["address"])>=32
  btc=client.post("/v1/wallets",headers=ah,json={"chain":"bitcoin"});assert btc.status_code==201;assert len(btc.json()["address"])>=26
  ltc=client.post("/v1/wallets",headers=ah,json={"chain":"litecoin"});assert ltc.status_code==201;assert len(ltc.json()["address"])>=26

  r2=client.post("/v1/wallets",headers=ah,json={"chain":"base","policy":{"allowed_actions":["send"],"allowed_assets":["ETH"]}});assert r2.status_code==201;wid2=r2.json()["wallet_id"]
  tx=client.post(f"/v1/wallets/{wid2}/transactions",headers={**ah,"Idempotency-Key":"no-broadcast"},json={"asset":"ETH","amount":0.0001,"destination":"0x000000000000000000000000000000000000dEaD"});assert tx.status_code==202
  assert client.post(f"/v1/transactions/{tx.json()['id']}/execute",headers=oh).status_code==403
  assert client.post(f"/v1/wallets/{wid2}/freeze",headers=oh).json()["status"]=="frozen"
  assert client.post(f"/v1/credentials/{agent['credential_id']}/revoke",headers=oh).status_code==200
  assert client.get(f"/v1/wallets/{wid2}",headers=ah).status_code==401

  other=credential("agent","unsupported-check");h2={"Authorization":f"Bearer {other['token']}"}
  assert client.post("/v1/wallets",headers=h2,json={"chain":"madeup"}).status_code==400
  assert client.post("/v1/wallets",json={"chain":"base"}).status_code==401

import os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
os.environ["DATA_DIR"]="/tmp/baw-test-data"
os.environ["AGENT_BOOTSTRAP_SECRET"]="test-bootstrap-secret"
os.environ["BAW_MASTER_KEY"]="test-master-key-with-at-least-32-bytes-of-entropy"
shutil.rmtree(os.environ["DATA_DIR"],ignore_errors=True)
from fastapi.testclient import TestClient
from main import app
client=TestClient(app)
def credential(role="agent",name=None):
 r=client.post("/v1/credentials/bootstrap",headers={"X-Bootstrap-Secret":"test-bootstrap-secret"},json={"name":name or f"test-{role}","role":role});assert r.status_code==201;return r.json()
def test_registry_and_manifest():
 with client:
  r=client.get("/v1/chains");assert r.status_code==200;ids={x["id"] for x in r.json()["chains"]};assert {"ethereum","base","arbitrum","optimism","avalanche","solana","bitcoin","litecoin","bnb","polygon"}<=ids;assert r.json()["network"]=="mainnet"
  m=client.get("/.well-known/agent.json");assert m.status_code==200;assert "base" in m.json()["chains"] and "litecoin" in m.json()["chains"]
def test_policy_operator_separation_and_idempotency():
 with client:
  agent=credential("agent","test-agent");operator=credential("operator","test-operator")
  ah={"Authorization":f"Bearer {agent['token']}"};oh={"Authorization":f"Bearer {operator['token']}"}
  assert "tx:approve" not in agent["scopes"] and "tx:approve" in operator["scopes"]
  r=client.post("/v1/wallets",headers=ah,json={"chain":"base","wallet_type":"task","purpose":"test","policy":{"allowed_actions":["balance","receive","send"],"allowed_assets":["ETH"],"max_transaction_usd":25,"daily_spend_limit_usd":50,"require_human_approval_above_usd":10,"expires_in_seconds":3600}});assert r.status_code==201;wid=r.json()["wallet_id"];assert r.json()["address"].startswith("0x") and len(r.json()["address"])==42
  th={**ah,"Idempotency-Key":"job-1"};body={"asset":"ETH","amount":0.001,"amount_usd":15,"destination":"0x000000000000000000000000000000000000dEaD"}
  a=client.post(f"/v1/wallets/{wid}/transactions",headers=th,json=body);assert a.status_code==202;assert a.json()["status"]=="approval_required"
  b=client.post(f"/v1/wallets/{wid}/transactions",headers=th,json=body);assert b.json()["id"]==a.json()["id"]
  assert client.post(f"/v1/transactions/{a.json()['id']}/approval",headers=ah,json={"approved":True}).status_code==403
  c=client.post(f"/v1/transactions/{a.json()['id']}/approval",headers=oh,json={"approved":True});assert c.status_code==200;assert c.json()["status"]=="ready_for_signing"
  audit=client.get("/v1/audit",headers=oh);assert audit.status_code==200;assert len(audit.json()["events"])>=3
def test_broadcast_switch_and_controls():
 with client:
  agent=credential("agent","agent-two");operator=credential("operator","operator-two")
  ah={"Authorization":f"Bearer {agent['token']}"};oh={"Authorization":f"Bearer {operator['token']}"}
  r=client.post("/v1/wallets",headers=ah,json={"chain":"base","policy":{"allowed_actions":["send"],"allowed_assets":["ETH"]}});assert r.status_code==201;wid=r.json()["wallet_id"]
  tx=client.post(f"/v1/wallets/{wid}/transactions",headers={**ah,"Idempotency-Key":"no-broadcast"},json={"asset":"ETH","amount":0.000001,"amount_usd":1,"destination":"0x000000000000000000000000000000000000dEaD"});assert tx.status_code==202
  assert client.post(f"/v1/transactions/{tx.json()['id']}/execute",headers=oh).status_code==403
  assert client.post(f"/v1/wallets/{wid}/freeze",headers=oh).json()["status"]=="frozen"
  assert client.post(f"/v1/credentials/{agent['credential_id']}/revoke",headers=oh).status_code==200
  assert client.get(f"/v1/wallets/{wid}",headers=ah).status_code==401
def test_unsupported_chain_and_auth():
 with client:
  a=credential("agent");h={"Authorization":f"Bearer {a['token']}"};assert client.post("/v1/wallets",headers=h,json={"chain":"madeup"}).status_code==400;assert client.post("/v1/wallets",json={"chain":"base"}).status_code==401

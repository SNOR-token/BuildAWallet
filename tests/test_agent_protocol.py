import os,shutil
os.environ["DATA_DIR"]="/tmp/baw-test-data";os.environ["AGENT_BOOTSTRAP_SECRET"]="test-bootstrap-secret"
shutil.rmtree(os.environ["DATA_DIR"],ignore_errors=True)
from fastapi.testclient import TestClient
from main import app
client=TestClient(app)
def token():
 r=client.post("/v1/credentials/bootstrap",headers={"X-Bootstrap-Secret":"test-bootstrap-secret"},json={"name":"test-agent"});assert r.status_code==201;return r.json()["token"]
def test_registry():
 with client:
  r=client.get("/v1/chains");assert r.status_code==200;ids={x["id"] for x in r.json()["chains"]};assert {"ethereum","base","solana","bitcoin","litecoin","bnb","polygon"}<=ids;assert r.json()["network"]=="mainnet"
def test_policy_and_idempotency():
 with client:
  t=token();h={"Authorization":f"Bearer {t}"}
  r=client.post("/v1/wallets",headers=h,json={"chain":"base","wallet_type":"task","purpose":"test","policy":{"allowed_actions":["balance","receive","send"],"allowed_assets":["ETH"],"max_transaction_usd":25,"daily_spend_limit_usd":50,"require_human_approval_above_usd":10,"expires_in_seconds":3600}});assert r.status_code==201;wid=r.json()["wallet_id"];assert r.json()["network"]=="mainnet"
  th={**h,"Idempotency-Key":"job-1"};body={"asset":"ETH","amount":0.001,"amount_usd":15,"destination":"0x000000000000000000000000000000000000dEaD"}
  a=client.post(f"/v1/wallets/{wid}/transactions",headers=th,json=body);assert a.status_code==202;assert a.json()["status"]=="approval_required"
  b=client.post(f"/v1/wallets/{wid}/transactions",headers=th,json=body);assert b.json()["id"]==a.json()["id"]
  c=client.post(f"/v1/transactions/{a.json()['id']}/approval",headers=h,json={"approved":True});assert c.status_code==200;assert c.json()["status"]=="ready_for_signing"
  assert len(client.get("/v1/audit",headers=h).json()["events"])>=3
def test_unsupported_chain_and_auth():
 with client:
  t=token();h={"Authorization":f"Bearer {t}"};assert client.post("/v1/wallets",headers=h,json={"chain":"madeup"}).status_code==400;assert client.post("/v1/wallets",json={"chain":"base"}).status_code==401

"""Mainnet chain registry and read-only RPC health probes.
Execution code consumes this registry; chain IDs are server-owned, never agent-supplied truth.
"""
from __future__ import annotations
import json, os, urllib.request

CHAINS={
 "ethereum":{"family":"evm","chain_id":1,"symbol":"ETH","rpc_env":"ETHEREUM_RPC_URL","rpc_default":"https://cloudflare-eth.com/v1/mainnet","capabilities":["native_transfer","erc20","contracts","fee_estimation","simulation","confirmation_tracking"]},
 "base":{"family":"evm","chain_id":8453,"symbol":"ETH","rpc_env":"BASE_RPC_URL","capabilities":["native_transfer","erc20","contracts","fee_estimation","simulation","confirmation_tracking"]},
 "arbitrum":{"family":"evm","chain_id":42161,"symbol":"ETH","rpc_env":"ARBITRUM_RPC_URL","capabilities":["native_transfer","erc20","contracts","fee_estimation","simulation","confirmation_tracking"]},
 "optimism":{"family":"evm","chain_id":10,"symbol":"ETH","rpc_env":"OPTIMISM_RPC_URL","capabilities":["native_transfer","erc20","contracts","fee_estimation","simulation","confirmation_tracking"]},
 "polygon":{"family":"evm","chain_id":137,"symbol":"POL","rpc_env":"POLYGON_RPC_URL","capabilities":["native_transfer","erc20","contracts","fee_estimation","simulation","confirmation_tracking"]},
 "bnb":{"family":"evm","chain_id":56,"symbol":"BNB","rpc_env":"BNB_RPC_URL","capabilities":["native_transfer","erc20","contracts","fee_estimation","simulation","confirmation_tracking"]},
 "avalanche":{"family":"evm","chain_id":43114,"symbol":"AVAX","rpc_env":"AVALANCHE_RPC_URL","capabilities":["native_transfer","erc20","contracts","fee_estimation","simulation","confirmation_tracking"]},
 "solana":{"family":"solana","symbol":"SOL","rpc_env":"SOLANA_RPC_URL","capabilities":["native_transfer","spl","fee_estimation","simulation","confirmation_tracking"]},
 "bitcoin":{"family":"utxo","symbol":"BTC","rpc_env":"BITCOIN_RPC_URL","capabilities":["native_transfer","utxo","fee_estimation","confirmation_tracking"]},
 "litecoin":{"family":"utxo","symbol":"LTC","rpc_env":"LITECOIN_RPC_URL","capabilities":["native_transfer","utxo","fee_estimation","confirmation_tracking"]},
}

def _rpc_url(cfg):
 return os.getenv(cfg["rpc_env"]) or cfg.get("rpc_default")

def public_registry():
 return [{"id":k,**{x:y for x,y in v.items() if x not in ("rpc_env","rpc_default")},"configured":bool(_rpc_url(v))} for k,v in CHAINS.items()]

def rpc_call(chain,method,params=None):
 cfg=CHAINS.get(chain)
 if not cfg: raise ValueError("unsupported chain")
 url=_rpc_url(cfg)
 if not url: raise RuntimeError(f"{cfg['rpc_env']} is not configured")
 body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params or []}).encode()
 req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json","User-Agent":"BuildAWallet/1.0"})
 with urllib.request.urlopen(req,timeout=10) as r: out=json.loads(r.read())
 if out.get("error"): raise RuntimeError(str(out["error"]))
 return out.get("result")

def health(chain):
 cfg=CHAINS[chain]
 if cfg["family"]=="evm":
  remote=int(rpc_call(chain,"eth_chainId"),16)
  return {"ok":remote==cfg["chain_id"],"expected_chain_id":cfg["chain_id"],"remote_chain_id":remote,"latest_block":int(rpc_call(chain,"eth_blockNumber"),16)}
 if cfg["family"]=="solana":
  version=rpc_call(chain,"getVersion"); slot=rpc_call(chain,"getSlot",[{"commitment":"confirmed"}]); return {"ok":True,"slot":slot,"version":version}
 # Bitcoin/Litecoin JSON-RPC nodes may require credentials embedded in their configured RPC URL.
 info=rpc_call(chain,"getblockchaininfo"); return {"ok":info.get("chain")=="main","chain":info.get("chain"),"blocks":info.get("blocks"),"headers":info.get("headers")}

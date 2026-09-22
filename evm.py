"""EVM mainnet adapter. Prepares and simulates policy-approved native transfers.
Broadcast is intentionally a separate signed-transaction endpoint; raw private keys never enter HTTP requests.
"""
from __future__ import annotations
from chains import CHAINS,rpc_call

def _addr(v):
 if not isinstance(v,str) or len(v)!=42 or not v.startswith("0x"):
  raise ValueError("invalid EVM address")
 int(v[2:],16); return v

def prepare_native(chain,sender,destination,amount_wei):
 cfg=CHAINS.get(chain)
 if not cfg or cfg["family"]!="evm": raise ValueError("not an EVM chain")
 sender=_addr(sender); destination=_addr(destination); value=hex(int(amount_wei))
 nonce=int(rpc_call(chain,"eth_getTransactionCount",[sender,"pending"]),16)
 gas_price=int(rpc_call(chain,"eth_gasPrice"),16)
 tx={"from":sender,"to":destination,"value":value,"nonce":hex(nonce),"chainId":hex(cfg["chain_id"]),"gasPrice":hex(gas_price)}
 gas=int(rpc_call(chain,"eth_estimateGas",[tx]),16); tx["gas"]=hex(gas)
 # eth_call catches many reverts before signing; native transfer should return 0x.
 rpc_call(chain,"eth_call",[tx,"pending"])
 return {"chain":chain,"chain_id":cfg["chain_id"],"unsigned_transaction":tx,"fee_native":gas*gas_price,"simulation":"passed"}

def broadcast_signed(chain,raw_tx):
 cfg=CHAINS.get(chain)
 if not cfg or cfg["family"]!="evm": raise ValueError("not an EVM chain")
 if not isinstance(raw_tx,str) or not raw_tx.startswith("0x"): raise ValueError("signed transaction must be 0x hex")
 return rpc_call(chain,"eth_sendRawTransaction",[raw_tx])

def receipt(chain,tx_hash):
 r=rpc_call(chain,"eth_getTransactionReceipt",[tx_hash])
 if r is None:return {"status":"pending","transaction_hash":tx_hash}
 return {"status":"confirmed" if int(r["status"],16)==1 else "failed","transaction_hash":tx_hash,"block_number":int(r["blockNumber"],16),"gas_used":int(r["gasUsed"],16)}

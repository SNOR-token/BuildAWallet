"""EVM mainnet execution adapter.
Server-owned chain IDs, RPC-derived nonce/fees, simulation, isolated signing, broadcast and receipts.
"""
from __future__ import annotations
from eth_account import Account
from chains import CHAINS,rpc_call

def _addr(v):
 if not isinstance(v,str) or len(v)!=42 or not v.startswith("0x"): raise ValueError("invalid EVM address")
 int(v[2:],16); return v

def _u256(v:int)->str:return hex(int(v))[2:].rjust(64,"0")
def _addr_word(v:str)->str:return _addr(v)[2:].lower().rjust(64,"0")
def _call_uint(chain,contract,data):
 r=rpc_call(chain,"eth_call",[{"to":_addr(contract),"data":data},"latest"])
 if not isinstance(r,str) or not r.startswith("0x"):raise RuntimeError("invalid token contract response")
 return int(r,16)

def balance(chain,address):
 address=_addr(address); wei=int(rpc_call(chain,"eth_getBalance",[address,"latest"]),16)
 return {"address":address,"balance_wei":wei,"balance_native":str(wei/10**18)}

def erc20_decimals(chain,contract):return _call_uint(chain,contract,"0x313ce567")
def erc20_balance(chain,contract,address):return _call_uint(chain,contract,"0x70a08231"+_addr_word(address))

def prepare_native(chain,sender,destination,amount_wei):
 cfg=CHAINS.get(chain)
 if not cfg or cfg["family"]!="evm": raise ValueError("not an EVM chain")
 sender=_addr(sender); destination=_addr(destination); amount_wei=int(amount_wei)
 if amount_wei<=0: raise ValueError("amount must be positive")
 nonce=int(rpc_call(chain,"eth_getTransactionCount",[sender,"pending"]),16)
 gas_price=int(rpc_call(chain,"eth_gasPrice"),16)
 call={"from":sender,"to":destination,"value":hex(amount_wei)}
 gas=int(rpc_call(chain,"eth_estimateGas",[call]),16);rpc_call(chain,"eth_call",[call,"pending"])
 tx={"to":destination,"value":amount_wei,"nonce":nonce,"chainId":cfg["chain_id"],"gasPrice":gas_price,"gas":gas}
 return {"chain":chain,"chain_id":cfg["chain_id"],"unsigned_transaction":tx,"fee_wei":gas*gas_price,"simulation":"passed","kind":"native"}

def prepare_erc20(chain,sender,contract,destination,amount_base_units):
 cfg=CHAINS.get(chain)
 if not cfg or cfg["family"]!="evm":raise ValueError("not an EVM chain")
 sender=_addr(sender);contract=_addr(contract);destination=_addr(destination);amount_base_units=int(amount_base_units)
 if amount_base_units<=0:raise ValueError("amount must be positive")
 data="0xa9059cbb"+_addr_word(destination)+_u256(amount_base_units)
 nonce=int(rpc_call(chain,"eth_getTransactionCount",[sender,"pending"]),16);gas_price=int(rpc_call(chain,"eth_gasPrice"),16)
 call={"from":sender,"to":contract,"value":"0x0","data":data};gas=int(rpc_call(chain,"eth_estimateGas",[call]),16)
 result=rpc_call(chain,"eth_call",[call,"pending"])
 if isinstance(result,str) and len(result)>2 and int(result,16)==0:raise RuntimeError("ERC-20 transfer simulation returned false")
 tx={"to":contract,"value":0,"data":data,"nonce":nonce,"chainId":cfg["chain_id"],"gasPrice":gas_price,"gas":gas}
 return {"chain":chain,"chain_id":cfg["chain_id"],"unsigned_transaction":tx,"fee_wei":gas*gas_price,"simulation":"passed","kind":"erc20","contract":contract}

def sign_transaction(unsigned_tx,private_key):
 signed=Account.sign_transaction(unsigned_tx,private_key);raw=getattr(signed,"raw_transaction",getattr(signed,"rawTransaction",None));return "0x"+bytes(raw).hex()

def broadcast_signed(chain,raw_tx):
 cfg=CHAINS.get(chain)
 if not cfg or cfg["family"]!="evm": raise ValueError("not an EVM chain")
 if not isinstance(raw_tx,str) or not raw_tx.startswith("0x"): raise ValueError("signed transaction must be 0x hex")
 return rpc_call(chain,"eth_sendRawTransaction",[raw_tx])

def receipt(chain,tx_hash):
 r=rpc_call(chain,"eth_getTransactionReceipt",[tx_hash])
 if r is None:return {"status":"pending","transaction_hash":tx_hash}
 return {"status":"confirmed" if int(r["status"],16)==1 else "failed","transaction_hash":tx_hash,"block_number":int(r["blockNumber"],16),"gas_used":int(r["gasUsed"],16)}

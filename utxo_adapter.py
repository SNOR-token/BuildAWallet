from __future__ import annotations
from bitcoinlib.keys import Key
from chains import rpc_call

def generate_key(chain:str):
    network='bitcoin' if chain=='bitcoin' else 'litecoin'
    k=Key(network=network)
    return k.address(), k.wif()

def balance(chain:str,address:str):
    # Requires a node/indexer RPC exposing scantxoutset; fails closed if unavailable.
    r=rpc_call(chain,'scantxoutset',['start',[f'addr({address})']])
    total=float(r.get('total_amount') or 0)
    return {'address':address,'balance_native':str(total),'unspents':r.get('unspents') or []}

def fee_rate(chain:str,target_blocks:int=3):
    r=rpc_call(chain,'estimatesmartfee',[target_blocks])
    fr=r.get('feerate')
    if fr is None: raise RuntimeError('fee estimate unavailable')
    return float(fr)

def broadcast(chain:str,raw_hex:str):
    if not isinstance(raw_hex,str) or not raw_hex: raise ValueError('raw transaction required')
    return rpc_call(chain,'sendrawtransaction',[raw_hex])

def receipt(chain:str,txid:str):
    try:r=rpc_call(chain,'getrawtransaction',[txid,True])
    except Exception:return {'status':'pending','transaction_hash':txid}
    conf=int(r.get('confirmations') or 0)
    return {'status':'confirmed' if conf>0 else 'pending','transaction_hash':txid,'confirmations':conf,'blockhash':r.get('blockhash')}

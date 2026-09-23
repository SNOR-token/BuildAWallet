from __future__ import annotations
from decimal import Decimal
from bitcoinlib.keys import Key
from bitcoinlib.transactions import Input,Output,Transaction
from chains import rpc_call

def _network(chain:str)->str:
    if chain=='bitcoin': return 'bitcoin'
    if chain=='litecoin': return 'litecoin'
    raise ValueError('unsupported UTXO chain')

def generate_key(chain:str):
    network=_network(chain);k=Key(network=network)
    return k.address(),k.wif()

def balance(chain:str,address:str):
    r=rpc_call(chain,'scantxoutset',['start',[f'addr({address})']])
    total=Decimal(str(r.get('total_amount') or 0))
    return {'address':address,'balance_native':str(total),'unspents':r.get('unspents') or []}

def fee_rate(chain:str,target_blocks:int=3):
    r=rpc_call(chain,'estimatesmartfee',[target_blocks]);fr=r.get('feerate')
    if fr is None: raise RuntimeError('fee estimate unavailable')
    return Decimal(str(fr))

def _to_sats(v): return int((Decimal(str(v))*Decimal(100_000_000)).to_integral_value())

def build_signed_native_transfer(chain:str,wif:str,source_address:str,destination:str,amount_native:float):
    network=_network(chain);amount_sat=_to_sats(amount_native)
    if amount_sat<=0: raise ValueError('amount must be positive')
    scan=rpc_call(chain,'scantxoutset',['start',[f'addr({source_address})']])
    rows=sorted(scan.get('unspents') or [],key=lambda x: Decimal(str(x.get('amount') or 0)),reverse=True)
    if not rows: raise RuntimeError('wallet has no spendable UTXOs')
    rate_btc_kvb=fee_rate(chain);rate_sat_vb=max(1,int((rate_btc_kvb*Decimal(100_000_000)/Decimal(1000)).to_integral_value()))
    chosen=[];total=0
    for u in rows:
        chosen.append(u);total+=_to_sats(u['amount'])
        est_vbytes=10+148*len(chosen)+34*2
        fee=rate_sat_vb*est_vbytes
        if total>=amount_sat+fee: break
    else: raise RuntimeError('insufficient confirmed UTXO balance')
    change=total-amount_sat-fee
    dust=546 if chain=='bitcoin' else 1000
    outputs=[Output(value=amount_sat,address=destination,network=network)]
    if change>=dust: outputs.append(Output(value=change,address=source_address,network=network))
    else: fee+=max(0,change);change=0
    key=Key(import_key=wif,network=network)
    inputs=[]
    for u in chosen:
        inputs.append(Input(prev_txid=u['txid'],output_n=int(u['vout']),keys=[key],value=_to_sats(u['amount']),network=network))
    tx=Transaction(inputs=inputs,outputs=outputs,network=network)
    tx.sign(keys=[key])
    if not tx.verify(): raise RuntimeError('signed UTXO transaction failed local verification')
    return {'raw_hex':tx.raw_hex(),'fee_sats':fee,'input_sats':total,'send_sats':amount_sat,'change_sats':change,'inputs':len(inputs)}

def broadcast(chain:str,raw_hex:str):
    if not isinstance(raw_hex,str) or not raw_hex: raise ValueError('raw transaction required')
    return rpc_call(chain,'sendrawtransaction',[raw_hex])

def receipt(chain:str,txid:str):
    try:r=rpc_call(chain,'getrawtransaction',[txid,True])
    except Exception:return {'status':'pending','transaction_hash':txid}
    conf=int(r.get('confirmations') or 0)
    return {'status':'confirmed' if conf>0 else 'pending','transaction_hash':txid,'confirmations':conf,'blockhash':r.get('blockhash')}

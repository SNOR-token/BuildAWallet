"""Authoritative server-side USD valuation.
Uses a configured CoinGecko-compatible HTTP endpoint and fails closed when pricing is unavailable or stale.
"""
from __future__ import annotations
import json, os, time, urllib.parse, urllib.request

COINGECKO_IDS={
    "ETH":"ethereum","POL":"polygon-ecosystem-token","BNB":"binancecoin","AVAX":"avalanche-2",
    "SOL":"solana","BTC":"bitcoin","LTC":"litecoin","USDC":"usd-coin","USDT":"tether",
}
_CACHE={}

def price_usd(symbol:str)->dict:
    symbol=symbol.upper()
    ttl=int(os.getenv("PRICE_CACHE_SECONDS","30"))
    cached=_CACHE.get(symbol)
    if cached and time.time()-cached["fetched_at"] <= ttl:return cached
    coin_id=COINGECKO_IDS.get(symbol)
    if not coin_id: raise RuntimeError(f"no authoritative price mapping for {symbol}")
    base=os.getenv("PRICE_API_URL","https://api.coingecko.com/api/v3/simple/price")
    q=urllib.parse.urlencode({"ids":coin_id,"vs_currencies":"usd","include_last_updated_at":"true"})
    req=urllib.request.Request(base+"?"+q,headers={"Accept":"application/json","User-Agent":"Build-a-Wallet/1.0"})
    with urllib.request.urlopen(req,timeout=10) as r:data=json.loads(r.read())
    row=data.get(coin_id) or {}; px=row.get("usd"); updated=row.get("last_updated_at")
    if not isinstance(px,(int,float)) or px<=0: raise RuntimeError(f"price unavailable for {symbol}")
    max_age=int(os.getenv("PRICE_MAX_AGE_SECONDS","180"))
    if updated and time.time()-float(updated)>max_age: raise RuntimeError(f"stale price for {symbol}")
    out={"symbol":symbol,"price_usd":float(px),"source":"coingecko","source_timestamp":updated,"fetched_at":time.time()}
    _CACHE[symbol]=out;return out

def value_usd(symbol:str,amount:float)->dict:
    p=price_usd(symbol);return {**p,"amount":float(amount),"value_usd":float(amount)*p["price_usd"]}

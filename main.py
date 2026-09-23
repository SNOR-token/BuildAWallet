"""Build-a-Wallet HTTP layer: human builder + Agent Protocol v1."""
from __future__ import annotations
import base64, json, os, random, sqlite3, sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
sys.path.insert(0,str(Path(__file__).parent/"app"))
import brain
from catalog import ACCENTS,BY_ID,GROUPS,THEMES,TOTAL_OPTIONS
from agent_protocol import router as agent_router, init_agent_db
from chains import CHAINS
from mcp_server import mcp, mcp_app
DATA_DIR=Path(os.environ.get("DATA_DIR",str(Path.home()/".build-a-wallet"))); DB_PATH=DATA_DIR/"app.db"; STATIC=Path(__file__).parent/"static"; CODE_CHARS="abcdefghjkmnpqrstuvwxyz23456789"; VERSION="1.0.0-alpha.8"; PUBLIC_BASE_URL="https://buildawallet.xyz"
def db(): c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c
def init_db():
 DATA_DIR.mkdir(parents=True,exist_ok=True)
 with db() as c:
  c.execute("CREATE TABLE IF NOT EXISTS wallets (code TEXT PRIMARY KEY,name TEXT NOT NULL,spec TEXT NOT NULL,email TEXT,is_public INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"); cols={r["name"] for r in c.execute("PRAGMA table_info(wallets)").fetchall()}
  if "email" not in cols:c.execute("ALTER TABLE wallets ADD COLUMN email TEXT")
  if "is_public" not in cols:c.execute("ALTER TABLE wallets ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0")
  c.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
 init_agent_db()
@asynccontextmanager
async def lifespan(app:FastAPI):
 init_db()
 async with mcp.session_manager.run():
  yield
app=FastAPI(title="BuildAWallet.xyz",version=VERSION,lifespan=lifespan,docs_url="/docs/api",redoc_url=None,openapi_url="/openapi.json"); app.include_router(agent_router)
LIST_FIELDS=("assets","networks","security","features","platforms","privacy"); SINGLE_FIELDS={"custody":"custody","style":"style","theme":"theme","accent":"accent"}; GROUP_OF=brain.GROUP_OF
def clean_spec(raw):
 s=brain.blank_spec()
 if not isinstance(raw,dict):return s
 s["name"]=str(raw.get("name") or "")[:32].strip();s["purpose"]=str(raw.get("purpose") or "")[:140].strip()
 for f in LIST_FIELDS:
  v=raw.get(f)
  if isinstance(v,list):s[f]=[x for x in dict.fromkeys(x for x in v if isinstance(x,str)) if GROUP_OF.get(x)==f][:200]
 for f in SINGLE_FIELDS:
  v=raw.get(f)
  if isinstance(v,str) and GROUP_OF.get(v)==f:s[f]=v
 s["theme"]=s["theme"] or "t_dark";s["accent"]=s["accent"] or "a_green";return s
def clean_state(raw):
 s=brain.fresh_state()
 if not isinstance(raw,dict):return s
 for k in {"asked","answered","skipped","said","pending"}:
  if isinstance(raw.get(k),list):s[k]=[str(x)[:40] for x in raw[k][:400]]
 for k in ("current","last_q"):
  if isinstance(raw.get(k),str):s[k]=raw[k][:200]
 if isinstance(raw.get("turns"),int):s["turns"]=max(0,min(raw["turns"],100000))
 s["finished"]=bool(raw.get("finished"));return s
class ChatIn(BaseModel): message:str=Field(default="",max_length=600);spec:dict|None=None;state:dict|None=None
class SaveIn(BaseModel): spec:dict|None=None;email:str|None=Field(default=None,max_length=120);is_public:bool=False
@app.get("/healthz")
def healthz():return {"ok":True,"agent_protocol":VERSION,"network":"mainnet","public_base_url":PUBLIC_BASE_URL,"broadcast_enabled":os.environ.get("BAW_MAINNET_BROADCAST")=="I_UNDERSTAND_MAINNET","mcp":"streamable-http"}
@app.get("/api/start")
def start():return brain.opening()
@app.post("/api/chat")
def chat(b:ChatIn):return brain.respond(b.message,clean_spec(b.spec),clean_state(b.state))
@app.get("/api/catalog")
def catalog():return {"groups":[{"key":g["key"],"title":g["title"],"multi":g["multi"],"items":[{"id":i["id"],"label":i["label"],"blurb":i.get("blurb",""),"sym":i.get("sym",""),"color":i.get("color","") ,"tab":i.get("tab","")} for i in g["items"]]} for g in GROUPS],"themes":[{"id":t["id"],"label":t["label"],"mode":t["mode"]} for t in THEMES],"accents":[{"id":a["id"],"label":a["label"],"hex":a["hex"]} for a in ACCENTS],"total":TOTAL_OPTIONS,"meta":{i["id"]:{"label":i["label"],"sym":i.get("sym",""),"color":i.get("color","") } for i in BY_ID.values()}}
def new_code(c):
 for _ in range(60):
  x="".join(random.choice(CODE_CHARS) for _ in range(6))
  if not c.execute("SELECT 1 FROM wallets WHERE code=?",(x,)).fetchone():return x
 raise HTTPException(503,"could not allocate a code")
@app.post("/api/save")
def save(b:SaveIn):
 s=clean_spec(b.spec)
 if brain.filled_count(s)<1:raise HTTPException(400,"nothing to save yet")
 with db() as c:x=new_code(c);c.execute("INSERT INTO wallets(code,name,spec,email,is_public) VALUES(?,?,?,?,?)",(x,s["name"] or "Untitled wallet",json.dumps(s),(b.email or "").strip().lower()[:120],1 if b.is_public else 0));c.execute("INSERT INTO events(kind) VALUES('save')")
 return {"code":x,"url":f"{PUBLIC_BASE_URL}/w/{x}"}
@app.get("/api/gallery")
def gallery():
 with db() as c:r=c.execute("SELECT name,code,spec FROM wallets WHERE is_public=1 ORDER BY created_at DESC LIMIT 24").fetchall()
 return {"items":[{"name":x["name"],"code":x["code"],"count":brain.filled_count(json.loads(x["spec"]))} for x in r]}
@app.get("/api/wallet/{code}")
def saved(code:str):
 with db() as c:r=c.execute("SELECT code,name,spec,created_at FROM wallets WHERE code=?",(code[:12].lower(),)).fetchone()
 if not r:raise HTTPException(404,"no wallet with that code")
 return {"code":r["code"],"name":r["name"],"created_at":r["created_at"],"spec":clean_spec(json.loads(r["spec"]))}
@app.get("/api/stats")
def stats():
 with db() as c:n=c.execute("SELECT COUNT(*) FROM wallets").fetchone()[0];r=c.execute("SELECT name,code FROM wallets ORDER BY rowid DESC LIMIT 8").fetchall()
 return {"built":int(n),"options":TOTAL_OPTIONS,"recent":[{"name":x["name"],"code":x["code"]} for x in r]}
@app.get("/.well-known/agent.json")
def manifest():return {"name":"BuildAWallet.xyz","homepage":PUBLIC_BASE_URL,"category":"agentic wallet infrastructure","tagline":"Humans set the rules. Agents transact within them.","description":"Policy-controlled multichain wallet infrastructure for autonomous AI agents.","protocol":"BuildAWallet Agent Protocol","version":VERSION,"openapi":f"{PUBLIC_BASE_URL}/openapi.json","api_base":f"{PUBLIC_BASE_URL}/v1","capabilities":f"{PUBLIC_BASE_URL}/v1/capabilities","authentication":"Bearer","network":"mainnet","chains":list(CHAINS),"mcp":f"{PUBLIC_BASE_URL}/mcp","pricing":f"{PUBLIC_BASE_URL}/pricing","offer":f"{PUBLIC_BASE_URL}/agent-offer.json","llms_txt":f"{PUBLIC_BASE_URL}/llms.txt","docs":f"{PUBLIC_BASE_URL}/docs","human":f"{PUBLIC_BASE_URL}/human","privacy":f"{PUBLIC_BASE_URL}/privacy","terms":f"{PUBLIC_BASE_URL}/terms","broadcast_enabled":os.environ.get("BAW_MAINNET_BROADCAST")=="I_UNDERSTAND_MAINNET"}
@app.get("/llms.txt",response_class=PlainTextResponse)
def llms():return f"# BuildAWallet.xyz\n\nCanonical site: {PUBLIC_BASE_URL}\nNON-HUMAN: wallet infrastructure for autonomous agents.\nHUMAN: guided wallet design for people.\nDocs: {PUBLIC_BASE_URL}/docs\nOpenAPI: {PUBLIC_BASE_URL}/openapi.json\nMCP: {PUBLIC_BASE_URL}/mcp\nPricing: {PUBLIC_BASE_URL}/pricing\n"
@app.get("/agent-offer.json")
def agent_offer():return FileResponse(STATIC/"agent-offer.json",media_type="application/json")
@app.get("/pricing")
def pricing():return FileResponse(STATIC/"pricing.html")
@app.get("/human")
def human():return FileResponse(STATIC/"human.html")
@app.get("/docs")
def docs_home():return FileResponse(STATIC/"docs.html")
@app.get("/privacy")
def privacy():return FileResponse(STATIC/"privacy.html")
@app.get("/terms")
def terms():return FileResponse(STATIC/"terms.html")
@app.get("/hero-portrait")
def hero_portrait():
 p=STATIC/"buildawallet-human-robot.webp"
 if not p.exists():raise HTTPException(404,"hero portrait asset missing")
 try:
  raw=p.read_text(encoding="ascii").strip()
  data=base64.b64decode(raw,validate=False)
  if not data.startswith(b"RIFF"):
   raise ValueError("decoded asset is not WebP")
  return Response(content=data,media_type="image/webp",headers={"Cache-Control":"no-store"})
 except (UnicodeDecodeError,ValueError,base64.binascii.Error):
  return FileResponse(p,media_type="image/webp",headers={"Cache-Control":"no-store"})
@app.get("/robots.txt",response_class=PlainTextResponse)
def robots():return f"User-agent: *\nAllow: /\nSitemap: {PUBLIC_BASE_URL}/sitemap.xml\n"
@app.get("/sitemap.xml")
def sitemap():
 paths=('/','/human','/docs','/pricing','/privacy','/terms','/docs/api','/openapi.json','/.well-known/agent.json','/llms.txt','/agent-offer.json','/mcp')
 body='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{PUBLIC_BASE_URL}{p}</loc></url>' for p in paths)+'</urlset>'
 return Response(content=body,media_type="application/xml")
@app.get("/")
def index():return FileResponse(STATIC/"index.html")
@app.get("/w/{code}")
def shared(code:str):return FileResponse(STATIC/"human.html")
@app.exception_handler(404)
async def nf(req,exc):
 if req.url.path.startswith(("/api/","/v1/","/.well-known/","/mcp","/hero-portrait")):return JSONResponse({"detail":"not found"},status_code=404)
 return FileResponse(STATIC/"index.html",status_code=404)
app.mount("/mcp",mcp_app)
app.mount("/static",StaticFiles(directory=STATIC),name="static")

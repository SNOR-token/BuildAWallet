"""Build-a-Wallet HTTP layer: human builder + Agent Protocol v1."""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent / "app"))
import brain  # noqa: E402
from catalog import ACCENTS, BY_ID, GROUPS, THEMES, TOTAL_OPTIONS  # noqa: E402
from agent_protocol import router as agent_router  # noqa: E402

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "app.db"
STATIC = Path(__file__).parent / "static"
CODE_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS wallets (code TEXT PRIMARY KEY,name TEXT NOT NULL,spec TEXT NOT NULL,email TEXT,is_public INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(wallets)").fetchall()}
        if "email" not in cols: conn.execute("ALTER TABLE wallets ADD COLUMN email TEXT")
        if "is_public" not in cols: conn.execute("ALTER TABLE wallets ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); yield


app = FastAPI(title="Build-a-Wallet", version="1.0.0-alpha", lifespan=lifespan, docs_url="/docs/api", redoc_url=None, openapi_url="/openapi.json")
app.include_router(agent_router)

LIST_FIELDS = ("assets", "networks", "security", "features", "platforms", "privacy")
SINGLE_FIELDS = {"custody": "custody", "style": "style", "theme": "theme", "accent": "accent"}
GROUP_OF = brain.GROUP_OF


def clean_spec(raw: dict | None) -> dict:
    spec = brain.blank_spec()
    if not isinstance(raw, dict): return spec
    spec["name"] = str(raw.get("name") or "")[:32].strip(); spec["purpose"] = str(raw.get("purpose") or "")[:140].strip()
    for f in LIST_FIELDS:
        vals = raw.get(f)
        if isinstance(vals, list):
            strs = [v for v in vals if isinstance(v, str)]; spec[f] = [v for v in dict.fromkeys(strs) if GROUP_OF.get(v) == f][:200]
    for f in SINGLE_FIELDS:
        v = raw.get(f)
        if isinstance(v, str) and GROUP_OF.get(v) == f: spec[f] = v
    spec["theme"] = spec["theme"] or "t_dark"; spec["accent"] = spec["accent"] or "a_green"
    return spec


def clean_state(raw: dict | None) -> dict:
    state = brain.fresh_state()
    if not isinstance(raw, dict): return state
    for k in {"asked", "answered", "skipped", "said", "pending"}:
        if isinstance(raw.get(k), list): state[k] = [str(x)[:40] for x in raw[k][:400]]
    for k in ("current", "last_q"):
        if isinstance(raw.get(k), str): state[k] = raw[k][:200]
    if isinstance(raw.get("turns"), int): state["turns"] = max(0, min(raw["turns"], 100000))
    state["finished"] = bool(raw.get("finished")); return state


class ChatIn(BaseModel):
    message: str = Field(default="", max_length=600); spec: dict | None = None; state: dict | None = None
class SaveIn(BaseModel):
    spec: dict | None = None; email: str | None = Field(default=None, max_length=120); is_public: bool = False


@app.get("/healthz")
def healthz(): return {"ok": True, "agent_protocol": "1.0.0-alpha"}
@app.get("/api/start")
def start(): return brain.opening()
@app.post("/api/chat")
def chat(body: ChatIn): return brain.respond(body.message, clean_spec(body.spec), clean_state(body.state))

@app.get("/api/catalog")
def catalog():
    groups=[]
    for g in GROUPS:
        groups.append({"key":g["key"],"title":g["title"],"multi":g["multi"],"items":[{"id":i["id"],"label":i["label"],"blurb":i.get("blurb",""),"sym":i.get("sym",""),"color":i.get("color",""),"tab":i.get("tab","")} for i in g["items"]]})
    return {"groups":groups,"themes":[{"id":t["id"],"label":t["label"],"mode":t["mode"]} for t in THEMES],"accents":[{"id":a["id"],"label":a["label"],"hex":a["hex"]} for a in ACCENTS],"total":TOTAL_OPTIONS,"meta":{i["id"]:{"label":i["label"],"sym":i.get("sym",""),"color":i.get("color",""),"tab":i.get("tab",""),"blurb":i.get("blurb","")} for i in BY_ID.values()}}


def new_code(conn):
    for _ in range(60):
        code="".join(random.choice(CODE_CHARS) for _ in range(6))
        if not conn.execute("SELECT 1 FROM wallets WHERE code = ?",(code,)).fetchone(): return code
    raise HTTPException(503,"could not allocate a code")

@app.post("/api/save")
def save(body: SaveIn):
    spec=clean_spec(body.spec)
    if brain.filled_count(spec)<1: raise HTTPException(400,"nothing to save yet")
    with db() as conn:
        code=new_code(conn); conn.execute("INSERT INTO wallets (code,name,spec,email,is_public) VALUES (?,?,?,?,?)",(code,spec["name"] or "Untitled wallet",json.dumps(spec),(body.email or "").strip().lower()[:120],1 if body.is_public else 0)); conn.execute("INSERT INTO events (kind) VALUES ('save')")
    return {"code":code,"url":f"/w/{code}"}

@app.get("/api/gallery")
def gallery():
    with db() as conn: rows=conn.execute("SELECT name,code,spec FROM wallets WHERE is_public=1 ORDER BY created_at DESC LIMIT 24").fetchall()
    return {"items":[{"name":r["name"],"code":r["code"],"count":brain.filled_count(json.loads(r["spec"]))} for r in rows]}

@app.get("/api/wallet/{code}")
def get_saved_wallet(code: str):
    with db() as conn: row=conn.execute("SELECT code,name,spec,created_at FROM wallets WHERE code=?",(code[:12].lower(),)).fetchone()
    if not row: raise HTTPException(404,"no wallet with that code")
    return {"code":row["code"],"name":row["name"],"created_at":row["created_at"],"spec":clean_spec(json.loads(row["spec"]))}

@app.get("/api/stats")
def stats():
    with db() as conn: built=conn.execute("SELECT COUNT(*) FROM wallets").fetchone()[0]; recent=conn.execute("SELECT name,code FROM wallets ORDER BY rowid DESC LIMIT 8").fetchall()
    return {"built":int(built),"options":TOTAL_OPTIONS,"recent":[{"name":r["name"],"code":r["code"]} for r in recent]}

# Machine discovery
@app.get("/.well-known/agent.json")
def agent_manifest():
    return {"name":"Build-a-Wallet","description":"Wallet infrastructure for autonomous agents. Humans set the rules; agents transact within them.","protocol":"Build-a-Wallet Agent Protocol","version":"1.0.0-alpha","openapi":"/openapi.json","api_base":"/v1","capabilities":"/v1/capabilities","mcp":"/mcp","authentication":{"type":"bearer","status":"prototype"},"chains":["litecoin"]}

@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    return "# Build-a-Wallet\nWallet infrastructure for the agentic internet.\n\n## Agent entry points\n- OpenAPI: /openapi.json\n- Agent manifest: /.well-known/agent.json\n- Capabilities: /v1/capabilities\n- API docs: /docs/api\n- MCP: /mcp\n\n## Safety model\nHumans define policy. Agents receive scoped authority. Private-key signing is not exposed to the AI layer.\n"

@app.get("/mcp")
def mcp_info():
    return {"status":"planned","protocol":"MCP","note":"Tool definitions will map to Agent Protocol operations after credential and signing adapters are production-ready."}

@app.get("/")
def index(): return FileResponse(STATIC/"index.html")
@app.get("/w/{code}")
def shared(code: str): return FileResponse(STATIC/"index.html")

@app.exception_handler(404)
async def not_found(request, exc):
    if request.url.path.startswith(("/api/","/v1/","/.well-known/")): return JSONResponse({"detail":"not found"},status_code=404)
    return FileResponse(STATIC/"index.html",status_code=404)

app.mount("/static",StaticFiles(directory=STATIC),name="static")

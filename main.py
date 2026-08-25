"""Build-a-Wallet: the site's HTTP layer.

State lives only in /data, which is empty on first boot and is the one path
that survives a deploy, so the schema is created at startup.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import string
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent / "app"))

import brain  # noqa: E402
from catalog import ACCENTS, BY_ID, GROUPS, THEMES, TOTAL_OPTIONS  # noqa: E402

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "app.db"
STATIC = Path(__file__).parent / "static"
CODE_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """First boot: /data may be empty or missing entirely."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS wallets ("
            "  code TEXT PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  spec TEXT NOT NULL,"
            "  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  kind TEXT NOT NULL,"
            "  ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    init_db()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


# ------------------------------------------------------------ spec hygiene --

LIST_FIELDS = ("assets", "networks", "security", "features", "platforms", "privacy")
SINGLE_FIELDS = {"custody": "custody", "style": "style", "theme": "theme", "accent": "accent"}
GROUP_OF = brain.GROUP_OF


def clean_spec(raw: dict | None) -> dict:
    """Never trust the round trip: keep only ids this build actually knows."""
    spec = brain.blank_spec()
    if not isinstance(raw, dict):
        return spec
    spec["name"] = str(raw.get("name") or "")[:32].strip()
    spec["purpose"] = str(raw.get("purpose") or "")[:140].strip()
    for f in LIST_FIELDS:
        vals = raw.get(f)
        if isinstance(vals, list):
            strs = [v for v in vals if isinstance(v, str)]
            spec[f] = [v for v in dict.fromkeys(strs) if GROUP_OF.get(v) == f][:200]
    for f in SINGLE_FIELDS:
        v = raw.get(f)
        if isinstance(v, str) and GROUP_OF.get(v) == f:
            spec[f] = v
    if not spec["theme"]:
        spec["theme"] = "t_dark"
    if not spec["accent"]:
        spec["accent"] = "a_green"
    return spec


def clean_state(raw: dict | None) -> dict:
    state = brain.fresh_state()
    if not isinstance(raw, dict):
        return state
    keys = {"asked", "answered", "skipped", "said", "pending"}
    for k in keys:
        v = raw.get(k)
        if isinstance(v, list):
            state[k] = [str(x)[:40] for x in v[:400]]
    if isinstance(raw.get("current"), str):
        state["current"] = raw["current"][:40]
    if isinstance(raw.get("turns"), int):
        state["turns"] = max(0, min(raw["turns"], 100000))
    state["finished"] = bool(raw.get("finished"))
    return state


# ---------------------------------------------------------------- payloads --

class ChatIn(BaseModel):
    message: str = Field(default="", max_length=600)
    spec: dict | None = None
    state: dict | None = None


class SaveIn(BaseModel):
    spec: dict | None = None


# ------------------------------------------------------------------ routes --

@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/start")
def start() -> dict:
    return brain.opening()


@app.post("/api/chat")
def chat(body: ChatIn) -> dict:
    spec = clean_spec(body.spec)
    state = clean_state(body.state)
    return brain.respond(body.message, spec, state)


@app.get("/api/catalog")
def catalog() -> dict:
    groups = []
    for g in GROUPS:
        groups.append({
            "key": g["key"], "title": g["title"], "multi": g["multi"],
            "items": [{"id": i["id"], "label": i["label"], "blurb": i.get("blurb", ""),
                       "sym": i.get("sym", ""), "color": i.get("color", ""), "tab": i.get("tab", "")}
                      for i in g["items"]],
        })
    return {
        "groups": groups,
        "themes": [{"id": t["id"], "label": t["label"], "mode": t["mode"]} for t in THEMES],
        "accents": [{"id": a["id"], "label": a["label"], "hex": a["hex"]} for a in ACCENTS],
        "total": TOTAL_OPTIONS,
        "meta": {i["id"]: {"label": i["label"], "sym": i.get("sym", ""), "color": i.get("color", ""),
                           "tab": i.get("tab", ""), "blurb": i.get("blurb", "")}
                 for i in BY_ID.values()},
    }


def new_code(conn: sqlite3.Connection) -> str:
    for _ in range(60):
        code = "".join(random.choice(CODE_CHARS) for _ in range(6))
        if not conn.execute("SELECT 1 FROM wallets WHERE code = ?", (code,)).fetchone():
            return code
    raise HTTPException(status_code=503, detail="could not allocate a code")


@app.post("/api/save")
def save(body: SaveIn) -> dict:
    spec = clean_spec(body.spec)
    if brain.filled_count(spec) < 1:
        raise HTTPException(status_code=400, detail="nothing to save yet")
    name = spec["name"] or "Untitled wallet"
    with db() as conn:
        code = new_code(conn)
        conn.execute("INSERT INTO wallets (code, name, spec) VALUES (?, ?, ?)",
                     (code, name, json.dumps(spec)))
        conn.execute("INSERT INTO events (kind) VALUES ('save')")
    return {"code": code, "url": f"/w/{code}"}


@app.get("/api/wallet/{code}")
def get_wallet(code: str) -> dict:
    with db() as conn:
        row = conn.execute("SELECT code, name, spec, created_at FROM wallets WHERE code = ?",
                           (code[:12].lower(),)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="no wallet with that code")
    return {"code": row["code"], "name": row["name"], "created_at": row["created_at"],
            "spec": clean_spec(json.loads(row["spec"]))}


@app.get("/api/stats")
def stats() -> dict:
    with db() as conn:
        (built,) = conn.execute("SELECT COUNT(*) FROM wallets").fetchone()
        recent = conn.execute(
            "SELECT name, code FROM wallets ORDER BY rowid DESC LIMIT 8").fetchall()
    return {"built": int(built), "options": TOTAL_OPTIONS,
            "recent": [{"name": r["name"], "code": r["code"]} for r in recent]}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/w/{code}")
def shared(code: str) -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.exception_handler(404)
async def not_found(request, exc):  # noqa: ANN001, ANN201
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "not found"}, status_code=404)
    return FileResponse(STATIC / "index.html", status_code=404)


app.mount("/static", StaticFiles(directory=STATIC), name="static")

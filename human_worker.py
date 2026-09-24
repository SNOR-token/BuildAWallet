"""Cloudflare Python Worker for the HUMAN builder. D1 stores public blueprints."""
import json
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from workers import asgi

from app import brain
from app.catalog import ACCENTS, BY_ID, GROUPS, THEMES, TOTAL_OPTIONS

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
PUBLIC_BASE_URL = "https://buildawallet.xyz"
LIST_FIELDS = ("assets", "networks", "security", "features", "platforms", "privacy")
SINGLE_FIELDS = ("custody", "style", "theme", "accent")
CODE_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"


def clean_spec(raw):
    spec = brain.blank_spec()
    if not isinstance(raw, dict):
        return spec
    spec["name"] = str(raw.get("name") or "")[:32].strip()
    spec["purpose"] = str(raw.get("purpose") or "")[:140].strip()
    for field in LIST_FIELDS:
        values = raw.get(field)
        if isinstance(values, list):
            spec[field] = list(dict.fromkeys(
                item for item in values if isinstance(item, str) and brain.GROUP_OF.get(item) == field
            ))[:200]
    for field in SINGLE_FIELDS:
        value = raw.get(field)
        if isinstance(value, str) and brain.GROUP_OF.get(value) == field:
            spec[field] = value
    return spec


def clean_state(raw):
    state = brain.fresh_state()
    if not isinstance(raw, dict):
        return state
    for key in ("asked", "answered", "skipped", "said", "pending"):
        if isinstance(raw.get(key), list):
            state[key] = [str(value)[:40] for value in raw[key][:400]]
    for key in ("current", "last_q"):
        if isinstance(raw.get(key), str):
            state[key] = raw[key][:200]
    if isinstance(raw.get("turns"), int):
        state["turns"] = max(0, min(raw["turns"], 100000))
    state["finished"] = bool(raw.get("finished"))
    return state


class ChatIn(BaseModel):
    message: str = Field(default="", max_length=600)
    spec: dict | None = None
    state: dict | None = None


class SaveIn(BaseModel):
    spec: dict | None = None
    is_public: bool = False


def database(request: Request):
    env = request.scope.get("env")
    if env is None or getattr(env, "DB", None) is None:
        raise HTTPException(503, "Blueprint storage is unavailable")
    return env.DB


def row_py(row):
    return row.to_py() if hasattr(row, "to_py") else row


@app.get("/healthz")
async def healthz(request: Request):
    try:
        db = database(request)
        await db.prepare("SELECT 1 FROM wallets LIMIT 1").run()
        return {"ok": True, "builder": "available", "agent_api": "not deployed"}
    except Exception:
        raise HTTPException(503, "Builder storage is unavailable")


@app.get("/api/start")
async def start():
    return brain.opening()


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    answer = brain.respond(body.message, clean_spec(body.spec), clean_state(body.state))
    env = request.scope.get("env")
    ai = getattr(env, "AI", None) if env is not None else None
    if ai is not None and body.message.strip():
        try:
            from pyodide.ffi import to_js
            prompt = {
                "messages": [
                    {"role": "system", "content": "You are the BuildAWallet wallet design assistant. Offer concise, practical explanations about wallet options. Never claim a blueprint is a deployed wallet, an APK exists, keys were generated, or transactions were sent. Never request recovery phrases or private keys. The application decides the selected options; do not imply you changed them."},
                    {"role": "user", "content": "Wallet options: " + json.dumps(answer["spec"], ensure_ascii=True)[:2500] + "\nQuestion: " + body.message + "\nBuilder guidance: " + answer["reply"][:800]},
                ],
                "max_tokens": 200,
            }
            result = await ai.run("@cf/meta/llama-3.1-8b-instruct-fp8", to_js(prompt, dict_converter=__import__("js").Object.fromEntries))
            data = result.to_py() if hasattr(result, "to_py") else result
            reply = data.get("response") if isinstance(data, dict) else None
            if isinstance(reply, str) and reply.strip():
                answer["reply"] = reply.strip()[:1200]
        except Exception:
            # Model availability must never change validated option selections.
            pass
    return answer


@app.get("/api/catalog")
async def catalog():
    return {
        "groups": [{"key": group["key"], "title": group["title"], "multi": group["multi"],
                    "items": [{key: item.get(key, "") for key in ("id", "label", "blurb", "sym", "color", "tab")}
                              for item in group["items"]]} for group in GROUPS],
        "themes": [{key: theme[key] for key in ("id", "label", "mode")} for theme in THEMES],
        "accents": [{key: accent[key] for key in ("id", "label", "hex")} for accent in ACCENTS],
        "total": TOTAL_OPTIONS,
        "meta": {item_id: {key: item.get(key, "") for key in ("label", "sym", "color")}
                 for item_id, item in BY_ID.items()},
    }


@app.post("/api/save")
async def save(body: SaveIn, request: Request):
    spec = clean_spec(body.spec)
    if brain.filled_count(spec) < 1:
        raise HTTPException(400, "nothing to save yet")
    db = database(request)
    for _ in range(5):
        code = "".join(secrets.choice(CODE_CHARS) for _ in range(26))
        try:
            await db.prepare("INSERT INTO wallets(code,name,spec,is_public) VALUES(?,?,?,?)").bind(
                code, spec["name"] or "Untitled wallet", json.dumps(spec), int(body.is_public)
            ).run()
            return {"code": code, "url": f"{PUBLIC_BASE_URL}/w/{code}"}
        except Exception as exc:
            if "UNIQUE" not in str(exc):
                raise HTTPException(503, "Blueprint storage failed") from exc
    raise HTTPException(503, "could not allocate a code")


@app.get("/api/gallery")
async def gallery(request: Request):
    result = await database(request).prepare(
        "SELECT name,code,spec FROM wallets WHERE is_public=1 ORDER BY created_at DESC LIMIT 24"
    ).run()
    return {"items": [{"name": row["name"], "code": row["code"],
                       "count": brain.filled_count(json.loads(row["spec"]))}
                      for row in row_py(result.results)]}


@app.get("/api/wallet/{code}")
async def saved(code: str, request: Request):
    row = await database(request).prepare(
        "SELECT code,name,spec,created_at FROM wallets WHERE code=?"
    ).bind(code[:32].lower()).first()
    if row is None:
        raise HTTPException(404, "no wallet with that code")
    record = row_py(row)
    return {"code": record["code"], "name": record["name"],
            "created_at": record["created_at"], "spec": clean_spec(json.loads(record["spec"]))}


@app.get("/api/stats")
async def stats(request: Request):
    db = database(request)
    count = row_py(await db.prepare("SELECT COUNT(*) AS n FROM wallets").first())
    return {"built": count["n"], "options": TOTAL_OPTIONS}


Default = asgi.entrypoint(app)

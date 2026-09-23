"""Smoke-test the Worker endpoints without a Cloudflare account."""
import sqlite3
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("workers", types.SimpleNamespace(asgi=types.SimpleNamespace(entrypoint=lambda app: None)))

from fastapi.testclient import TestClient
import human_worker


class Result:
    def __init__(self, rows):
        self.results = [dict(row) for row in rows]


class Statement:
    def __init__(self, conn, sql, args=()):
        self.conn, self.sql, self.args = conn, sql, args

    def bind(self, *args):
        return Statement(self.conn, self.sql, args)

    async def run(self):
        rows = self.conn.execute(self.sql, self.args).fetchall()
        self.conn.commit()
        return Result(rows)

    async def first(self):
        row = self.conn.execute(self.sql, self.args).fetchone()
        return dict(row) if row else None


class DB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript((Path(__file__).resolve().parents[1] / "cloudflare-human/migrations/0001_human.sql").read_text())

    def prepare(self, sql):
        return Statement(self.conn, sql)


def test_cloudflare_builder_conversation_and_saved_blueprint():
    db = DB()
    @human_worker.app.middleware("http")
    async def bind_database(request, call_next):
        request.scope["env"] = types.SimpleNamespace(DB=db)
        return await call_next(request)

    client = TestClient(human_worker.app)
    assert (health := client.get("/healthz")).json().get("ok") is True, (health.status_code, health.text)
    opening = client.get("/api/start").json()
    assert client.get("/api/catalog").json()["total"] >= 150
    response = client.post("/api/chat", json={"message": "Call it Northvault. I want Bitcoin and Litecoin",
                                              "spec": opening["spec"], "state": opening["state"]})
    assert response.status_code == 200
    spec = response.json()["spec"]
    assert {"btc", "ltc"}.issubset(spec["assets"])
    saved = client.post("/api/save", json={"spec": spec, "is_public": True})
    assert saved.status_code == 200
    code = saved.json()["code"]
    assert client.get(f"/api/wallet/{code}").json()["spec"]["assets"] == spec["assets"]
    assert client.get("/api/gallery").json()["items"][0]["code"] == code
    assert client.get("/api/stats").json()["built"] == 1

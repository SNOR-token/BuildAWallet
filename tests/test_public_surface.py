"""The public container must not expose the legacy agent signer or leak share links."""
import sqlite3

from fastapi.testclient import TestClient

import main


def test_public_site_disables_agent_execution_and_keeps_private_links_private(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "app.db")
    main.init_db()
    client = TestClient(main.app)
    assert client.get("/healthz").json()["agent_api"] == "not deployed"
    assert client.get("/.well-known/agent.json").json()["broadcast_enabled"] is False
    assert client.get("/v1/capabilities").status_code == 404
    assert client.post("/v1/wallets", json={"chain": "ethereum"}).status_code == 404
    assert not any(path.startswith("/v1/") for path in main.app.openapi()["paths"])

    spec = {"name": "Test", "assets": ["eth"]}
    record = client.post("/api/save", json={"spec": spec, "email": "sensitive@example.com"}).json()
    assert len(record["code"]) == 26
    assert client.get(f"/api/wallet/{record['code']}").json()["name"] == "Test"
    stats = client.get("/api/stats").json()
    assert stats["built"] == 1 and "recent" not in stats
    assert record["code"] not in str(stats)
    assert not client.get("/api/gallery").json()["items"]
    with sqlite3.connect(main.DB_PATH) as db:
        assert db.execute("SELECT email FROM wallets").fetchone()[0] is None
        db.execute("UPDATE wallets SET email='legacy@example.com'")
        db.commit()
    main.init_db()
    with sqlite3.connect(main.DB_PATH) as db:
        assert db.execute("SELECT email FROM wallets").fetchone()[0] is None

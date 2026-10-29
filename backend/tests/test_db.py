"""Database tests: schema, settings roundtrip, FTS trigger, cascade."""
import pytest

from app.db import Database


def test_schema_created(tmp_path):
    db = Database(tmp_path / "t.db")
    tables = {r["name"] for r in db.fetchall(
        "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')")}
    assert {"sessions", "messages", "documents", "chunks",
            "jobs", "settings", "chunks_ai"} <= tables
    db.close()


def test_settings_roundtrip(tmp_path):
    db = Database(tmp_path / "t.db")
    db.set_setting("chunk_size", 500)
    db.set_setting("chat_mode", "always")
    s = db.get_settings()
    assert s["chunk_size"] == 500 and s["chat_mode"] == "always"
    db.close()


def test_fts_trigger_indexed(tmp_path):
    db = Database(tmp_path / "t.db")
    with db.tx() as c:
        c.execute(
            "INSERT INTO documents(id,name,rel_path,sha256,size,status,"
            "created_at,updated_at) VALUES('d','a.txt','a.txt','h',1,"
            "'indexed','now','now')")
        c.execute(
            "INSERT INTO chunks(id,document_id,ord,text) "
            "VALUES('c1','d',0,'quantum banana')")
    rows = db.fetchall(
        "SELECT c.id FROM chunks_fts f JOIN chunks c ON c.rowid=f.rowid"
        " WHERE chunks_fts MATCH 'banana'")
    assert [r["id"] for r in rows] == ["c1"]
    db.close()


def test_cascade_delete(tmp_path):
    db = Database(tmp_path / "t.db")
    with db.tx() as c:
        c.execute(
            "INSERT INTO sessions(id,title,created_at,updated_at) "
            "VALUES('s','t','n','n')")
        c.execute(
            "INSERT INTO messages(session_id,role,content,created_at) "
            "VALUES('s','user','hi','n')")
        c.execute("DELETE FROM sessions WHERE id='s'")
    assert db.fetchall("SELECT * FROM messages") == []
    db.close()


def test_rollback_on_error(tmp_path):
    db = Database(tmp_path / "t.db")
    with pytest.raises(Exception):
        with db.tx() as c:
            c.execute(
                "INSERT INTO sessions(id,title,created_at,updated_at) "
                "VALUES('s','t','n','n')")
            raise RuntimeError("boom")
    assert db.fetchall("SELECT * FROM sessions") == []
    db.close()

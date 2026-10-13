import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_document_ids_are_unique():
    docs = json.loads((ROOT / "data" / "documents.json").read_text(encoding="utf-8"))
    ids = [doc["id"] for doc in docs]
    assert len(ids) == len(set(ids))


def test_user_ids_are_unique():
    users = json.loads((ROOT / "data" / "users.json").read_text(encoding="utf-8"))
    ids = [user["id"] for user in users]
    assert len(ids) == len(set(ids))


def test_access_lists_exist():
    docs = json.loads((ROOT / "data" / "documents.json").read_text(encoding="utf-8"))
    assert all(doc.get("access") for doc in docs)

"""Hybrid storage: MongoDB when MONGODB_URI is set, else local JSON-file store.

Keeps the app runnable without Mongo while preserving the exact collection
names required by the spec. File store lives in <repo>/data/*.json.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .config import get_settings

COLLECTIONS = [
    "users", "profiles", "opportunities", "opportunity_evidence", "matches",
    "applications", "contacts", "outreach", "monitoring_jobs", "agent_runs",
    "search_history", "notifications", "approvals", "integrations",
    "search_cache", "search_usage",
]

_mongo_client = None
_mongo_db = None
_lock = threading.Lock()


def _mongo():
    global _mongo_client, _mongo_db
    s = get_settings()
    if not s.MONGODB_URI:
        return None
    if _mongo_db is not None:
        return _mongo_db
    try:
        from pymongo import MongoClient

        _mongo_client = MongoClient(s.MONGODB_URI, serverSelectionTimeoutMS=3000)
        _mongo_client.server_info()  # force connect
        _mongo_db = _mongo_client[s.MONGODB_DB]
        return _mongo_db
    except Exception:
        return None


def backend_kind() -> str:
    return "mongodb" if _mongo() is not None else "localfile"


def _data_dir() -> Path:
    d = Path(get_settings().DATA_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(name: str) -> list[dict]:
    f = _data_dir() / f"{name}.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(name: str, rows: list[dict]) -> None:
    f = _data_dir() / f"{name}.json"
    f.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def _match(doc: dict, flt: dict) -> bool:
    for k, v in (flt or {}).items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class Store:
    """Minimal collection API used by the whole backend."""

    def __init__(self, name: str):
        self.name = name

    def _coll(self):
        db = _mongo()
        return db[self.name] if db is not None else None

    # -- writes --
    def insert(self, doc: dict) -> dict:
        doc = dict(doc)
        doc.setdefault("_id", uuid.uuid4().hex[:12])
        doc.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        coll = self._coll()
        if coll is not None:
            coll.insert_one(dict(doc))
            return doc
        with _lock:
            rows = _load(self.name)
            rows.append(doc)
            _save(self.name, rows)
        return doc

    def upsert(self, flt: dict, doc: dict) -> dict:
        existing = self.find_one(flt)
        if existing:
            return self.update(existing["_id"], doc)
        return self.insert({**flt, **doc})

    def update(self, _id: str, patch: dict) -> Optional[dict]:
        coll = self._coll()
        if coll is not None:
            from pymongo import ReturnDocument

            return coll.find_one_and_update(
                {"_id": _id}, {"$set": patch}, return_document=ReturnDocument.AFTER
            )
        with _lock:
            rows = _load(self.name)
            for r in rows:
                if r.get("_id") == _id:
                    r.update(patch)
                    _save(self.name, rows)
                    return r
        return None

    def delete(self, flt: dict) -> int:
        coll = self._coll()
        if coll is not None:
            return coll.delete_many(flt).deleted_count
        with _lock:
            rows = _load(self.name)
            kept = [r for r in rows if not _match(r, flt)]
            _save(self.name, kept)
            return len(rows) - len(kept)

    # -- reads --
    def find_one(self, flt: dict) -> Optional[dict]:
        coll = self._coll()
        if coll is not None:
            doc = coll.find_one(flt or {})
            if doc and "_id" in doc and not isinstance(doc["_id"], str):
                doc["_id"] = str(doc["_id"])
            return doc
        for r in _load(self.name):
            if _match(r, flt or {}):
                return r
        return None

    def find(self, flt: Optional[dict] = None, limit: int = 200, sort_key: str = "") -> list[dict]:
        coll = self._coll()
        if coll is not None:
            cur = coll.find(flt or {}).limit(limit)
            out = list(cur)
            for d in out:
                if "_id" in d and not isinstance(d["_id"], str):
                    d["_id"] = str(d["_id"])
            if sort_key:
                out.sort(key=lambda d: str(d.get(sort_key, "")), reverse=True)
            return out
        rows = [r for r in _load(self.name) if _match(r, flt or {})]
        if sort_key:
            rows.sort(key=lambda d: str(d.get(sort_key, "")), reverse=True)
        return rows[:limit]


def col(name: str) -> Store:
    return Store(name)

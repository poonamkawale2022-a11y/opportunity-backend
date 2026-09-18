"""Centralized SerpApi client. All SerpApi traffic flows through here.

Engines (common shape GET /search?engine=...):
  google, google_jobs, google_scholar, google_news, google_maps,
  google_flights, google_hotels

Features: timeout, retries, structured logs, search metadata capture,
normalized errors, file-backed cache, usage budget, history, dedupe.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

import httpx

from .config import get_settings
from .store import col

log = logging.getLogger("serpapi")

ENGINE_RESULT_KEYS = {
    "google": "organic_results",
    "google_jobs": "jobs_results",
    "google_scholar": "organic_results",
    "google_news": "news_results",
    "google_maps": "local_results",
    "google_flights": "best_flights",
    "google_hotels": "properties",
}


def _norm_params(engine: str, params: dict) -> dict:
    p = {k: v for k, v in (params or {}).items() if v not in (None, "", [])}
    p["engine"] = engine
    return dict(sorted(p.items(), key=lambda kv: kv[0]))


def cache_key(engine: str, params: dict) -> str:
    norm = _norm_params(engine, {k: v for k, v in params.items() if k != "api_key"})
    raw = json.dumps(norm, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def remaining_budget() -> dict:
    s = get_settings()
    used = 0
    for r in col("search_usage").find():
        used += int(r.get("count", 0))
    return {"budget": s.SERPAPI_MONTHLY_BUDGET, "used": used,
            "remaining": max(0, s.SERPAPI_MONTHLY_BUDGET - used)}


def _record_usage(cache_hit: bool, engine: str):
    if cache_hit:
        return  # cached searches are free per SerpApi docs
    col("search_usage").insert({"engine": engine, "count": 1})


def _get_cached(key: str) -> Optional[dict]:
    row = col("search_cache").find_one({"key": key})
    if not row:
        return None
    if time.time() - row.get("stored_at", 0) > 3600:  # 1h SerpApi cache window
        return None
    return row.get("response")


def _put_cache(key: str, engine: str, params: dict, response: dict):
    col("search_cache").upsert({"key": key}, {
        "key": key, "engine": engine, "params": _norm_params(engine, params),
        "response": response, "stored_at": time.time(),
    })


class SerpApiError(Exception):
    def __init__(self, message: str, status: int = 0, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def raw_search(engine: str, params: dict, force_fresh: bool = False,
               timeout: Optional[int] = None) -> dict:
    s = get_settings()
    if not s.SERPAPI_API_KEY:
        raise SerpApiError("SERPAPI_API_KEY is not configured", status=401)
    clean = {k: v for k, v in (params or {}).items() if k != "api_key"}
    key = cache_key(engine, clean)
    if not force_fresh:
        hit = _get_cached(key)
        if hit is not None:
            col("search_history").insert({
                "engine": engine, "params": _norm_params(engine, clean),
                "cache_hit": True, "status": (hit.get("search_metadata") or {}).get("status", "Cached"),
                "search_id": (hit.get("search_metadata") or {}).get("id", ""),
            })
            return {"response": hit, "cache_hit": True, "cache_key": key,
                    "budget": remaining_budget()}
    rb = remaining_budget()
    if rb["remaining"] <= 0:
        raise SerpApiError(f"Monthly SerpApi budget exhausted ({rb['budget']})", status=429)

    query = dict(clean)
    query["engine"] = engine
    query["api_key"] = s.SERPAPI_API_KEY
    t0 = time.time()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout or s.SERPAPI_TIMEOUT_S) as c:
                r = c.get(s.SERPAPI_BASE_URL, params=query)
            latency = round((time.time() - t0) * 1000)
            if r.status_code == 200:
                data = r.json()
                meta = data.get("search_metadata", {}) or {}
                _put_cache(key, engine, clean, data)
                _record_usage(False, engine)
                col("search_history").insert({
                    "engine": engine, "params": _norm_params(engine, clean),
                    "cache_hit": False, "status": meta.get("status", "Success"),
                    "search_id": meta.get("id", ""), "latency_ms": latency,
                })
                log.info("serpapi engine=%s status=%s latency=%sms cached=no",
                         engine, meta.get("status"), latency)
                return {"response": data, "cache_hit": False, "cache_key": key,
                        "latency_ms": latency, "budget": remaining_budget()}
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = SerpApiError(f"SerpApi transient {r.status_code}", status=r.status_code)
                time.sleep(1.2 * (attempt + 1))
                continue
            try:
                payload = r.json()
            except Exception:
                payload = r.text[:500]
            raise SerpApiError(f"SerpApi error {r.status_code}: {payload}",
                               status=r.status_code, payload=payload)
        except SerpApiError as e:
            if e.status in (429, 500, 502, 503, 504) and attempt < 2:
                last_err = e
                time.sleep(1.2 * (attempt + 1))
                continue
            raise
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = SerpApiError(f"SerpApi transport/timeout: {e}", status=0)
            time.sleep(1.2 * (attempt + 1))
    raise last_err or SerpApiError("SerpApi request failed", status=0)


def _normalize(engine: str, data: dict) -> dict:
    meta = data.get("search_metadata", {}) or {}
    params = data.get("search_parameters", {}) or {}
    info = data.get("search_information", {}) or {}
    key = ENGINE_RESULT_KEYS.get(engine, "organic_results")
    results = data.get(key) or data.get("organic_results") or []
    if isinstance(results, dict):
        results = [results]
    return {
        "engine": engine,
        "status": meta.get("status", "Success"),
        "search_id": meta.get("id", ""),
        "params": params,
        "total_results": info.get("total_results"),
        "results": results[:20],
        "result_count": len(results[:20]),
    }


def _search(engine: str, params: dict, force_fresh: bool = False) -> dict:
    try:
        out = raw_search(engine, params, force_fresh=force_fresh)
        norm = _normalize(engine, out["response"])
        norm.update({k: v for k, v in out.items() if k != "response"})
        norm["raw_keys"] = sorted(list(out["response"].keys()))
        return norm
    except SerpApiError as e:
        return {"engine": engine, "status": "Error", "error": str(e),
                "http_status": e.status, "results": [], "result_count": 0,
                "budget": remaining_budget()}


class SerpApiClient:
    """Reusable engine methods used by agents and tools."""

    def searchWeb(self, query: str, location: str = "", num: int = 10,
                  extra: dict | None = None, force_fresh: bool = False) -> dict:
        p = {"q": query, "num": num}
        if location:
            p["location"] = location
        if extra:
            p.update(extra)
        return _search("google", p, force_fresh)

    def searchJobs(self, query: str, location: str = "", extra: dict | None = None,
                   force_fresh: bool = False) -> dict:
        p = {"q": query}
        if location:
            p["location"] = location
        if extra:
            p.update(extra)
        return _search("google_jobs", p, force_fresh)

    def searchScholar(self, query: str, extra: dict | None = None,
                      force_fresh: bool = False) -> dict:
        p = {"q": query}
        if extra:
            p.update(extra)
        return _search("google_scholar", p, force_fresh)

    def searchNews(self, query: str, extra: dict | None = None,
                   force_fresh: bool = False) -> dict:
        p = {"q": query}
        if extra:
            p.update(extra)
        return _search("google_news", p, force_fresh)

    def searchMaps(self, query: str, location: str = "", extra: dict | None = None,
                   force_fresh: bool = False) -> dict:
        p = {"q": query}
        if location:
            p["location"] = location
        if extra:
            p.update(extra)
        if p.get("location") and not any(k in p for k in ("z", "m", "ll")):
            p["z"] = "13"  # SerpApi requires z/m/ll alongside location
        return _search("google_maps", p, force_fresh)

    def searchLinkedinPosts(self, query: str, location: str = "",
                            extra: dict | None = None,
                            force_fresh: bool = False) -> dict:
        """Public LinkedIn posts via Google site: search (no LinkedIn API assumed)."""
        q = query if "site:linkedin.com" in query else f"site:linkedin.com/posts {query}"
        p = {"q": q.strip()}
        if location:
            p["location"] = location
        if extra:
            p.update(extra)
        out = _search("google", p, force_fresh)
        out["linkedin_kind"] = "posts"
        return out

    def searchLinkedinJobs(self, query: str, location: str = "",
                           extra: dict | None = None,
                           force_fresh: bool = False) -> dict:
        """Public LinkedIn job pages via Google site: search."""
        q = query if "site:linkedin.com" in query else f"site:linkedin.com/jobs/view {query}"
        p = {"q": q.strip()}
        if location:
            p["location"] = location
        if extra:
            p.update(extra)
        out = _search("google", p, force_fresh)
        out["linkedin_kind"] = "jobs"
        return out

    def searchFlights(self, departure_id: str, arrival_id: str, outbound_date: str,
                      return_date: str = "", extra: dict | None = None) -> dict:
        p = {"departure_id": departure_id, "arrival_id": arrival_id,
             "outbound_date": outbound_date}
        if return_date:
            p["return_date"] = return_date
        if extra:
            p.update(extra)
        return _search("google_flights", p)

    def searchHotels(self, query: str, check_in_date: str = "", check_out_date: str = "",
                     extra: dict | None = None) -> dict:
        p = {"q": query}
        if check_in_date:
            p["check_in_date"] = check_in_date
        if check_out_date:
            p["check_out_date"] = check_out_date
        if extra:
            p.update(extra)
        return _search("google_hotels", p)


client = SerpApiClient()

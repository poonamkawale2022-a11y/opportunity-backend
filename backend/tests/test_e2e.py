"""End-to-end lifecycle test with ZERO network/credit spend.

Monkeypatches SerpApi + OpenRouter so the full loop runs deterministically:
goal -> plan -> discover -> investigate -> verify -> match -> application ->
outreach draft -> approval gate -> monitoring -> change detection -> notification.
"""
import app.agents as AG  # noqa: F401
import app.openrouter_client as OC
import app.serpapi_client as SC
from app.config import get_settings


def _fail(*a, **k):
    raise RuntimeError("network disabled in e2e (zero-credit)")


CANNED_JOBS = {
    "engine": "google_jobs", "status": "Success", "result_count": 2,
    "results": [
        {"title": "AI Research Intern", "company_name": "Test University Lab",
         "location": "Bengaluru, India", "link": "https://example.com/a",
         "description": "Needs Python, PyTorch. B.Tech eligible."},
        {"title": "ML Intern", "company_name": "Test Startup",
         "location": "Remote, India", "link": "https://example.com/b",
         "description": "Needs Python, SQL."},
    ],
    "budget": {"remaining": 249}, "cache_hit": False,
}
CANNED_WEB = {
    "engine": "google", "status": "Success", "result_count": 1,
    "results": [{"title": "Test University Lab", "link": "https://example.com/lab",
                 "snippet": "AI lab working on NLP."}],
    "budget": {}, "cache_hit": False,
}
CANNED_EMPTY = {"engine": "x", "status": "Success", "result_count": 0,
                "results": [], "budget": {}, "cache_hit": False}


def test_full_lifecycle_zero_credit(tmp_path, monkeypatch):
    s = get_settings()
    s.DATA_DIR = str(tmp_path)  # isolate storage
    s.DEMO_MODE = True
    monkeypatch.setattr(OC, "chat", _fail)
    monkeypatch.setattr(SC.client, "searchJobs", lambda *a, **k: dict(CANNED_JOBS))
    monkeypatch.setattr(SC.client, "searchWeb", lambda *a, **k: dict(CANNED_WEB))
    monkeypatch.setattr(SC.client, "searchScholar", lambda *a, **k: dict(CANNED_EMPTY))
    monkeypatch.setattr(SC.client, "searchNews", lambda *a, **k: dict(CANNED_EMPTY))
    monkeypatch.setattr(SC.client, "searchMaps", lambda *a, **k: dict(CANNED_EMPTY))

    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)

    # profile + resume text (no file parsing needed)
    assert c.post("/api/profile", json={
        "name": "E2E User", "skills": ["python", "pytorch", "sql"],
        "location": "India"}).status_code == 200
    r = c.post("/api/profile/resume",
               json={"text": "E2E User\nB.Tech CSE\nPython PyTorch SQL"})
    assert r.status_code == 200, r.text
    assert "python" in r.json()["data"]["skills"]

    # discover (heuristic planner + canned search, zero credit)
    r = c.post("/api/opportunities/discover",
               json={"user_goal": "AI research internships in India", "max_results": 5})
    assert r.status_code == 200, r.text
    mission = r.json()["data"]
    assert len(mission["opportunity_ids"]) >= 2  # 2 jobs + 1 web refinement
    oid = mission["opportunity_ids"][0]
    assert mission["results"][0]["match"]["skill_match"]["matched"]

    # verify + match endpoints
    assert c.post(f"/api/opportunities/{oid}/verify").status_code == 200
    assert c.post(f"/api/opportunities/{oid}/match", json={}).status_code == 200

    # application (LLM disabled -> truthful heuristic draft, nothing invented)
    r = c.post(f"/api/opportunities/{oid}/prepare-application", json={})
    assert r.status_code == 200
    assert r.json()["data"]["materials"]["cover_letter"]

    # outreach: contact from canned web (never invented), draft + pending approval
    r = c.post(f"/api/opportunities/{oid}/generate-outreach", json={})
    assert r.status_code == 200, r.text
    ovid = r.json()["data"]["outreach_id"]
    assert r.json()["data"]["approval_id"]

    # send blocked before approval (gate works)
    assert c.post(f"/api/outreach/{ovid}/send", json={}).status_code == 409

    # approve -> draft (gmail not connected -> local .eml, never fake-sent)
    assert c.post(f"/api/outreach/{ovid}/approve", json={}).status_code == 200
    r = c.post(f"/api/outreach/{ovid}/draft", json={})
    assert r.json()["data"]["mode"] == "local-draft"
    r = c.post(f"/api/outreach/{ovid}/send", json={})
    assert r.json()["data"]["ok"] is False  # honestly reports not-sent
    assert c.get(f"/api/outreach/{ovid}/status").json()["data"]["status"] != "sent"

    # monitoring: watch -> no change -> simulated change -> notification
    assert c.post(f"/api/opportunities/{oid}/watch", json={}).status_code == 200
    r = c.post(f"/api/opportunities/{oid}/check-now", json={})
    assert all(ch["importance"] == "low" for ch in r.json()["data"]["changes"])
    r = c.post(f"/api/opportunities/{oid}/check-now",
               json={"simulated": {"deadline": "2026-12-31"}})
    changes = r.json()["data"]["changes"]
    assert any(ch["field"] == "deadline" and ch["importance"] == "high" for ch in changes)
    assert len(c.get("/api/notifications").json()["data"]) >= 1

    # timeline + evidence recorded
    assert len(c.get(f"/api/opportunities/{oid}/activity").json()["data"]) >= 5
    assert len(c.get(f"/api/opportunities/{oid}/evidence").json()["data"]) >= 1

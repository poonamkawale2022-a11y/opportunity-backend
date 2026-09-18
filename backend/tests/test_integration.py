"""Integration smoke: uses real env keys when present, skips cleanly otherwise."""
import os

import pytest

pytestmark = pytest.mark.integration

from app import openrouter_client as OC
from app import serpapi_client as SC

HAS_SERP = bool(os.getenv("SERPAPI_API_KEY"))
HAS_OR = bool(os.getenv("OPENROUTER_API_KEY"))


@pytest.mark.skipif(not HAS_SERP, reason="SERPAPI_API_KEY not set")
def test_serpapi_web():
    r = SC.client.searchWeb("IIT Bombay AI research lab", num=3)
    assert r.get("status") in ("Success", "Cached", "Error")
    assert "budget" in r


@pytest.mark.skipif(not HAS_SERP, reason="SERPAPI_API_KEY not set")
def test_serpapi_jobs():
    r = SC.client.searchJobs("AI intern India", "India")
    assert "results" in r


@pytest.mark.skipif(not HAS_SERP, reason="SERPAPI_API_KEY not set")
def test_serpapi_scholar():
    r = SC.client.searchScholar("transformers language models")
    assert "results" in r


@pytest.mark.skipif(not HAS_SERP, reason="SERPAPI_API_KEY not set")
def test_serpapi_news():
    r = SC.client.searchNews("AI research India")
    assert "results" in r


@pytest.mark.skipif(not HAS_SERP, reason="SERPAPI_API_KEY not set")
def test_serpapi_maps():
    r = SC.client.searchMaps("IIT Bombay", "Mumbai")
    assert "results" in r


@pytest.mark.skipif(not HAS_OR, reason="OPENROUTER_API_KEY not set")
def test_openrouter_minimal():
    out = OC.minimal_ping()
    assert out["ok"] is True
    assert out.get("usage") is not None


@pytest.mark.skipif(not (HAS_OR and HAS_SERP), reason="need both keys")
def test_openrouter_tool_calling_loop():
    data = OC.chat(
        [{"role": "user", "content": "Call search_jobs with query 'AI intern India'."}],
        tools=[t for t in __import__("app.schemas", fromlist=["AGENT_TOOLS"]).AGENT_TOOLS
               if t["function"]["name"] == "search_jobs"],
        tool_choice="auto", max_tokens=300)
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    assert msg.get("tool_calls"), "model must return tool_calls"

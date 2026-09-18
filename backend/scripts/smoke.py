"""CLI smoke test: exercises every integration with sanitized output.

Usage:
    python -m scripts.smoke            # unit-safe parts always run
    python -m scripts.smoke --live     # also hit SerpApi/OpenRouter when keys exist
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import openrouter_client as OC  # noqa: E402
from app import serpapi_client as SC  # noqa: E402
from app import gmail as gmail_mod  # noqa: E402
from app import logic as L  # noqa: E402


def check(name, fn):
    try:
        r = fn()
        print(f"[PASS] {name}: {json.dumps(r, default=str)[:300]}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name}: {str(e)[:300]}")
        return False


def main():
    live = "--live" in sys.argv
    print("== unit-safe checks (always run) ==")
    check("norm_url", lambda: {"v": L.norm_url("https://www.Example.com/a?x=1")})
    check("dedupe", lambda: {"v": L.deduplicate_opportunities([
        {"title": "A", "organization": "O", "location": "L", "canonical_url": "x.com/a"},
        {"title": "A", "organization": "O", "location": "L", "canonical_url": "x.com/a"}])[1]})
    check("change_detect", lambda: {"v": L.compare_opportunity_state({"deadline": "a"}, {"deadline": "b"})})
    check("gmail_status", lambda: gmail_mod.status())
    print(f"== live checks (keys present: serp={bool(os.getenv('SERPAPI_API_KEY'))} or={bool(os.getenv('OPENROUTER_API_KEY'))}) ==")
    if not live:
        print("skip live (pass --live to hit real APIs)")
        return
    if os.getenv("SERPAPI_API_KEY"):
        check("serp_google", lambda: {"n": SC.client.searchWeb("IIT Bombay AI lab", num=3).get("result_count")})
        check("serp_jobs", lambda: {"n": SC.client.searchJobs("AI intern India", "India").get("result_count")})
        check("serp_scholar", lambda: {"n": SC.client.searchScholar("transformers").get("result_count")})
        check("serp_news", lambda: {"n": SC.client.searchNews("AI research India").get("result_count")})
        check("serp_maps", lambda: {"n": SC.client.searchMaps("IIT Bombay", "Mumbai").get("result_count")})
    else:
        print("[SKIP] SerpApi (no key)")
    if os.getenv("OPENROUTER_API_KEY"):
        check("or_ping", OC.minimal_ping)
    else:
        print("[SKIP] OpenRouter (no key)")


if __name__ == "__main__":
    main()

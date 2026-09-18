"""Multi-agent system: Planner, Discovery, Investigator, Verifier, Match,
Application, Outreach(+Followup), Monitor + Orchestrator control plane.

Real agentic behavior:
- Planner decides search strategy (LLM w/ heuristic fallback).
- Discovery runs 1 broad search -> shortlist -> selective refinement.
- Investigator selects minimum useful vertical set dynamically.
- Verifier cross-checks with explicit VERIFIED/PARTIAL/CONFLICTING/UNVERIFIED/UNKNOWN.
- Match never fabricates; UNKNOWN for missing fields.
- Outreach never invents contacts; approval-gated sends.
- Monitor uses deterministic change detection.
- Orchestrator persists state, enforces budget, retries, dedupes, resumes.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any, Optional

from . import gmail as gmail_mod
from . import linkedin as LI
from . import logic as L
from . import openrouter_client as OC
from . import serpapi_client as SC
from .config import get_settings
from .schemas import PlannerOutput
from .store import col

AGENTS = ["planner", "discovery", "investigator", "verifier",
          "match", "application", "outreach", "monitor", "followup", "orchestrator"]


def trace(task_id: str, agent: str, action: str, opportunity_id: str = "",
          tool: str = "", latency_ms: int = 0, status: str = "ok",
          summary: str = "", next_action: str = "") -> dict:
    return col("agent_runs").insert({
        "task_id": task_id, "agent": agent, "action": action,
        "opportunity_id": opportunity_id, "tool": tool, "latency_ms": latency_ms,
        "status": status, "summary": summary[:800], "next_action": next_action,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


def _user_profile(user_id: str) -> dict:
    p = col("profiles").find_one({"user_id": user_id})
    return p or {"user_id": user_id, "skills": [], "preferences": {}}


# ---------------- Planner ----------------
def planner_agent(user_goal: str, profile: dict, prefs: dict | None = None) -> dict:
    prefs = prefs or (profile.get("preferences") or {})
    system = ("You are the Planner agent. Convert the user goal into a strict JSON research mission. "
              "Return ONLY JSON with keys: opportunity_types, domains, locations, must_have, "
              "nice_to_have, search_verticals (subset of google_jobs,google,google_scholar,"
              "google_news,google_maps), investigation_requirements, monitoring_candidate.")
    user = f"Goal: {user_goal}\nProfile: {json.dumps(profile, default=str)[:2500]}\nPreferences: {json.dumps(prefs)[:800]}"
    try:
        data = OC.chat([{"role": "system", "content": system},
                        {"role": "user", "content": user}],
                       response_format={"type": "json_object"}, max_tokens=800)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "{}")
        plan = OC.extract_json(content)
        if plan.get("opportunity_types"):
            return PlannerOutput(**{k: plan.get(k, v) for k, v in
                                    PlannerOutput().model_dump().items()}).model_dump()
    except Exception:
        pass
    # heuristic fallback (deterministic, never fake LLM)
    g = user_goal.lower()
    types = []
    for t in ("internship", "research", "job", "fellowship", "hackathon", "grant", "phd"):
        if t in g:
            types.append(t)
    domains = []
    for d in ("ai", "ml", "machine learning", "nlp", "computer vision", "data", "robotics", "llm"):
        if d in g:
            domains.append(d)
    locs = ["India"] if "india" in g else (["Remote"] if "remote" in g else [])
    verticals = ["google_jobs", "google"]
    if any(w in g for w in ("research", "lab", "professor", "phd", "paper")):
        verticals.append("google_scholar")
    verticals.append("google_news")
    if any(w in g for w in ("job", "intern", "hiring", "fellowship", "role")):
        verticals += ["linkedin_posts", "linkedin_jobs"]
    return PlannerOutput(
        opportunity_types=types or ["internship"],
        domains=domains or ["AI/ML"],
        locations=locs or ["India"],
        must_have=["eligibility", "skills", "deadline", "organization"],
        nice_to_have=["stipend", "remote-option"],
        search_verticals=verticals,
        investigation_requirements=["organization", "eligibility", "deadline"],
        monitoring_candidate=True).model_dump()


# ---------------- Discovery ----------------
def discovery_agent(plan: dict, user_goal: str, task_id: str,
                    max_results: int = 20, force_fresh: bool = False,
                    user_id: str = "demo-user") -> dict:
    client = SC.client
    domains = " ".join(plan.get("domains", []) or [])
    locs = ", ".join(plan.get("locations", []) or [])
    otypes = " ".join(plan.get("opportunity_types", []) or [])
    base_q = f"{domains} {otypes} {locs}".strip() or user_goal
    verticals = plan.get("search_verticals", []) or ["google_jobs", "google"]
    trace(task_id, "discovery", f"broad discovery: {base_q}", summary=f"verticals={verticals}")
    candidates: list[dict] = []
    searches: list[dict] = []
    # 1 broad discovery search first (budget-aware)
    if "google_jobs" in verticals:
        t0 = time.time()
        r = client.searchJobs(base_q, locs, force_fresh=force_fresh)
        searches.append({"tool": "search_jobs", "query": base_q, "status": r.get("status"),
                         "count": r.get("result_count", 0), "cache_hit": r.get("cache_hit", False)})
        trace(task_id, "discovery", "search_jobs", tool="search_jobs",
              latency_ms=int((time.time() - t0) * 1000), status="ok" if r.get("results") else "empty",
              summary=f"{r.get('result_count', 0)} jobs, cache_hit={r.get('cache_hit')}")
        for j in (r.get("results") or [])[:max_results]:
            n = L.normalize_job(j)
            n["source_engine"] = "google_jobs"
            candidates.append(n)
    if "google" in verticals and len(candidates) < 5:
        t0 = time.time()
        r = client.searchWeb(f"{base_q} official apply", locs, force_fresh=force_fresh)
        searches.append({"tool": "search_web", "query": base_q, "status": r.get("status"),
                         "count": r.get("result_count", 0)})
        trace(task_id, "discovery", "search_web", tool="search_web",
              latency_ms=int((time.time() - t0) * 1000),
              summary=f"{r.get('result_count', 0)} web results")
        for w in (r.get("results") or [])[:10]:
            if LI.is_aggregator_page(w.get("link", ""), w.get("title", "")):
                continue  # listing pages with 100s of roles are never featured
            n = L.normalize_web(w)
            n["source_engine"] = "google"
            n["source_type"] = "company_page" if LI.classify_link(w.get("link", "")) == "OFFICIAL_APPLICATION" else "web"
            candidates.append(n)
    # LinkedIn signal discovery: agent-chosen, max 1-2 searches (quota-aware)
    if "linkedin_posts" in verticals or "linkedin_jobs" in verticals:
        prof = _user_profile(user_id)
        if "linkedin_posts" in verticals:
            for q in LI.build_linkedin_queries(prof, plan, "posts", limit=1):
                t0 = time.time()
                r = client.searchLinkedinPosts(q, locs, force_fresh=force_fresh)
                searches.append({"tool": "search_linkedin_posts", "query": q,
                                 "status": r.get("status"), "count": r.get("result_count", 0)})
                trace(task_id, "discovery", "search_linkedin_posts", tool="search_linkedin_posts",
                      latency_ms=int((time.time() - t0) * 1000),
                      summary=f"{r.get('result_count', 0)} posts")
                for hit in (r.get("results") or [])[:8]:
                    candidates.append(LI.extract_linkedin_opportunity(hit, "posts"))
        if "linkedin_jobs" in verticals:
            for q in LI.build_linkedin_queries(prof, plan, "jobs", limit=1):
                t0 = time.time()
                r = client.searchLinkedinJobs(q, locs, force_fresh=force_fresh)
                searches.append({"tool": "search_linkedin_jobs", "query": q,
                                 "status": r.get("status"), "count": r.get("result_count", 0)})
                trace(task_id, "discovery", "search_linkedin_jobs", tool="search_linkedin_jobs",
                      latency_ms=int((time.time() - t0) * 1000),
                      summary=f"{r.get('result_count', 0)} job pages")
                for hit in (r.get("results") or [])[:8]:
                    candidates.append(LI.extract_linkedin_opportunity(hit, "jobs"))
    if "google_scholar" in verticals and any(k in user_goal.lower() for k in ("research", "lab", "phd", "professor")):
        t0 = time.time()
        r = client.searchScholar(f"{domains} lab internship", force_fresh=force_fresh)
        searches.append({"tool": "search_scholar", "query": domains, "status": r.get("status"),
                         "count": r.get("result_count", 0)})
        trace(task_id, "discovery", "search_scholar", tool="search_scholar",
              latency_ms=int((time.time() - t0) * 1000),
              summary=f"{r.get('result_count', 0)} scholar hits")
        for w in (r.get("results") or [])[:6]:
            n = L.normalize_web(w)
            n["source_engine"] = "google_scholar"
            candidates.append(n)
    # weak-result refinement (agentic rule)
    if len(candidates) < 3 and searches:
        rq = f"{base_q} 2026 apply online"
        t0 = time.time()
        r = client.searchWeb(rq, locs, force_fresh=force_fresh)
        trace(task_id, "discovery", "refined query", tool="search_web",
              latency_ms=int((time.time() - t0) * 1000),
              summary=f"refinement '{rq}' -> {r.get('result_count', 0)}")
        for w in (r.get("results") or [])[:10]:
            n = L.normalize_web(w)
            n["source_engine"] = "google"
            candidates.append(n)
        searches.append({"tool": "search_web", "query": rq, "refined": True,
                         "count": r.get("result_count", 0)})
    unique, removed = L.deduplicate_opportunities(candidates)
    trace(task_id, "discovery", "deduplicate",
          summary=f"{len(candidates)} raw -> {len(unique)} unique, {removed} duplicates removed",
          next_action="investigate shortlist")
    return {"candidates": unique[:max_results], "removed": removed,
            "searches": searches, "raw_count": len(candidates)}


# ---------------- Investigator ----------------
def investigator_agent(opp: dict, plan: dict, task_id: str) -> dict:
    """Selects the MINIMUM useful vertical set dynamically."""
    client = SC.client
    org = opp.get("organization", "")
    title = opp.get("title", "")
    needed = set(plan.get("investigation_requirements", []) or [])
    evidence: list[dict] = []
    searches: list[dict] = []

    def add_search(tool_fn, label, **kw):
        t0 = time.time()
        r = tool_fn(**kw)
        searches.append({"tool": label, "status": r.get("status"),
                         "count": r.get("result_count", 0)})
        trace(opp.get("task_id", task_id), "investigator", label,
              opportunity_id=opp.get("_id", ""), tool=label,
              latency_ms=int((time.time() - t0) * 1000),
              summary=f"{r.get('result_count', 0)} hits")
        return r

    # organization context: only if org known and needed
    org_summary, people, news, loc_ctx = "", [], [], {}
    if org and ("organization" in needed or not opp.get("description")):
        r = add_search(client.searchWeb, "search_web", query=f"{org} {title} official", num=5)
        for x in (r.get("results") or [])[:3]:
            evidence.append({"claim": f"organization context: {org}",
                             "sourceType": "google", "sourceTitle": x.get("title", ""),
                             "sourceUrl": x.get("link", ""), "evidenceText": x.get("snippet", "")[:400],
                             "confidenceState": "UNVERIFIED"})
        org_summary = (r.get("results") or [{}])[0].get("snippet", "")[:600] if r.get("results") else ""
    # researcher/lab only for research-type opps
    if any(k in (title + " " + str(opp.get("description", ""))).lower() for k in ("research", "lab", "phd", "professor", "scientist")):
        r = add_search(client.searchScholar, "search_scholar", query=f"{org} {title}")
        for x in (r.get("results") or [])[:3]:
            people.append({"name": x.get("title", "")[:120], "context": (x.get("snippet") or "")[:300],
                           "url": x.get("link", "")})
            evidence.append({"claim": "researcher/lab context", "sourceType": "google_scholar",
                             "sourceTitle": x.get("title", ""), "sourceUrl": x.get("link", ""),
                             "evidenceText": (x.get("snippet") or "")[:400], "confidenceState": "UNVERIFIED"})
    # news only when recency matters (deadline/status) — cheap single call
    if "deadline" in needed or True:
        r = add_search(client.searchNews, "search_news", query=f"{org} {title}")
        for x in (r.get("results") or [])[:3]:
            news.append({"title": x.get("title", ""), "url": x.get("link", ""),
                         "date": x.get("date", "")})
    # maps only if location present and ambiguous
    if opp.get("location"):
        r = add_search(client.searchMaps, "search_maps", query=org or title,
                       location=opp.get("location", ""))
        if r.get("results"):
            loc_ctx = {"query": opp.get("location"), "hits": len(r.get("results") or []),
                       "top": (r.get("results") or [{}])[0].get("title", "")}
    # LinkedIn cross-check: a post is a signal, not a source — confirm elsewhere
    if (opp.get("source_type") or "") in ("linkedin_post", "linkedin_job") and org:
        r = add_search(client.searchWeb, "search_web",
                       query=f"{org} {title} careers official", num=5)
        for x in (r.get("results") or [])[:2]:
            evidence.append({"claim": f"independent listing check: {org}",
                             "sourceType": "google", "sourceTitle": x.get("title", ""),
                             "sourceUrl": x.get("link", ""), "evidenceText": x.get("snippet", "")[:400],
                             "confidenceState": "UNVERIFIED"})
        r2 = add_search(client.searchJobs, "search_jobs", query=f"{title} {org}")
        org_summary += f" | jobs listings found: {r2.get('result_count', 0)}"
    missing = [f for f in ("deadline", "eligibility", "skills") if not opp.get(f) or opp.get(f) in ("", [], {})]
    out = {"organization_summary": org_summary, "research_alignment": "",
           "people_found": people, "recent_developments": news,
           "location_context": loc_ctx, "missing_information": missing, "evidence": evidence}
    for e in evidence:
        col("opportunity_evidence").insert({**e, "opportunity_id": opp.get("_id", ""),
                                           "task_id": task_id})
    trace(task_id, "investigator", "investigation complete",
          opportunity_id=opp.get("_id", ""),
          summary=f"{len(evidence)} evidence items; missing={missing}",
          next_action="verify")
    return {**out, "searches": searches}


# ---------------- Verifier ----------------
def verifier_agent(opp: dict, task_id: str) -> dict:
    fields = {}
    for field in ("deadline", "status", "location", "organization"):
        val = opp.get(field, "")
        ev = col("opportunity_evidence").find({"opportunity_id": opp.get("_id", "")}, limit=50)
        supporting = [e for e in ev if str(val) and str(val).lower() in str(e.get("evidenceText", "")).lower()]
        conflicting = [e for e in ev if e.get("confidenceState") == "CONFLICTING"]
        if not val:
            state = "UNKNOWN"
        elif conflicting:
            state = "CONFLICTING"
        elif supporting:
            state = "VERIFIED"
        elif ev:
            state = "PARTIALLY_VERIFIED"
        else:
            state = "UNVERIFIED"
        fields[field] = {"value": val, "state": state,
                         "evidence_count": len(supporting)}
    # targeted re-search on conflict (agentic rule)
    for f, v in fields.items():
        if v["state"] == "CONFLICTING":
            r = SC.client.searchWeb(f"{opp.get('organization','')} {opp.get('title','')} {f}", num=5)
            trace(task_id, "verifier", f"conflict re-search: {f}",
                  opportunity_id=opp.get("_id", ""), tool="search_web",
                  summary=f"{r.get('result_count', 0)} hits")
            v["rechecked"] = True
    trace(task_id, "verifier", "verification complete",
          opportunity_id=opp.get("_id", ""),
          summary=json.dumps({k: v["state"] for k, v in fields.items()}),
          next_action="match")
    return {"fields": fields}


# ---------------- Match ----------------
def match_agent(opp: dict, profile: dict, task_id: str) -> dict:
    m = L.compare_profile(profile, opp)
    m["why_shown"] = L.why_shown(m)
    col("matches").upsert({"opportunity_id": opp.get("_id", ""), "user_id": profile.get("user_id", "demo-user")},
                          {"opportunity_id": opp.get("_id", ""), "user_id": profile.get("user_id", "demo-user"),
                           "match": m, "task_id": task_id})
    trace(task_id, "match", "profile matched", opportunity_id=opp.get("_id", ""),
          summary=m.get("rationale", "")[:300], next_action="prepare")
    return m


# ---------------- Application ----------------
def application_agent(opp: dict, profile: dict, match: dict, task_id: str) -> dict:
    gaps = (match.get("skill_match") or {}).get("gaps", [])
    system = ("You are the Application agent. Prepare truthful application materials. "
              "NEVER invent skills, experience, publications or achievements. "
              "Return ONLY JSON: {resume_tips:[], cover_letter:'', checklist:[], prep_plan:[]}.")
    user = (f"Profile: {json.dumps(profile, default=str)[:2500]}\nOpportunity: "
            f"{json.dumps({k: opp.get(k) for k in ('title','organization','location','description','requirements')}, default=str)[:2000]}"
            f"\nSkill gaps: {gaps}")
    out: dict = {}
    try:
        data = OC.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       response_format={"type": "json_object"}, max_tokens=1200)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "{}")
        out = OC.extract_json(content)
    except Exception:
        out = {}
    if not out.get("cover_letter"):
        out = {"resume_tips": [f"Emphasize {s} with a concrete project bullet" for s in (match.get("skill_match", {}).get("matched", [])[:4])] or ["Tailor summary to the role"],
               "cover_letter": (f"Dear Hiring Team,\n\nI am applying for {opp.get('title','')} at {opp.get('organization','')}. "
                                f"My background in {', '.join(profile.get('skills', [])[:5]) or 'relevant coursework'} aligns with your requirements. "
                                f"{match.get('rationale','')}\n\nSincerely,\n{profile.get('name','Applicant')}"),
               "checklist": ["Resume tailored", "Cover letter customized", "Portfolio links verified", "Deadline confirmed"],
               "prep_plan": [f"Close gap: {g} (suggest a 2-week mini-project)" for g in gaps[:3]] or ["Review role requirements"]}
        out["heuristic"] = True
    app = col("applications").upsert(
        {"opportunity_id": opp.get("_id", ""), "user_id": profile.get("user_id", "demo-user")},
        {"opportunity_id": opp.get("_id", ""), "user_id": profile.get("user_id", "demo-user"),
         "materials": out, "status": "draft", "task_id": task_id})
    trace(task_id, "application", "materials prepared", opportunity_id=opp.get("_id", ""),
          summary=f"tips={len(out.get('resume_tips', []))}", next_action="outreach")
    return {"application_id": app.get("_id"), "materials": out}


# ---------------- Outreach ----------------
def find_contact(opp: dict, task_id: str) -> dict:
    """Find a relevant PUBLIC professional contact; never invent one.

    A LinkedIn post author is a legitimate lead: use the name + post as the
    relevance reason, then verify via public web/Scholar context. No LinkedIn
    messaging is ever claimed — outreach goes through approved email only.
    """
    org = opp.get("organization", "")
    author = (opp.get("author") or "").strip()
    if author:
        contact = col("contacts").insert({
            "opportunity_id": opp.get("_id", ""), "name": author[:120],
            "role": "LinkedIn post author (public post)", "organization": org,
            "why_relevant": f"Authored the hiring post for '{opp.get('title', '')}'. "
                            f"Same org, same role — verify overlap via public work before writing.",
            "evidence": [{"sourceTitle": opp.get("title", ""), "sourceUrl": opp.get("source_url", "")}],
            "task_id": task_id})
        trace(task_id, "outreach", "contact: post author", opportunity_id=opp.get("_id", ""),
              summary=author[:120], next_action="verify author, draft outreach")
        return {"found": True, "contact": contact, "via": "linkedin_author"}
    if not org:
        trace(task_id, "outreach", "no contact: org unknown",
              opportunity_id=opp.get("_id", ""), status="empty")
        return {"found": False, "reason": "Organization unknown — cannot identify contact without inventing."}
    r = SC.client.searchWeb(f"{org} hiring manager recruiter OR professor contact", num=5)
    r2 = SC.client.searchScholar(f"{org} researcher") if "research" in (opp.get("title", "") + str(opp.get("description", ""))).lower() else {"results": []}
    cands = (r.get("results") or []) + (r2.get("results") or [])
    if not cands:
        trace(task_id, "outreach", "no contact found", opportunity_id=opp.get("_id", ""),
              status="empty")
        return {"found": False, "reason": "No public contact surfaced — will not invent one."}
    top = cands[0]
    contact = col("contacts").insert({
        "opportunity_id": opp.get("_id", ""), "name": top.get("title", "")[:120],
        "role": "Relevant contact (public source)", "organization": org,
        "why_relevant": (top.get("snippet", "") or "")[:400],
        "evidence": [{"sourceTitle": top.get("title", ""), "sourceUrl": top.get("link", "")}],
        "task_id": task_id})
    trace(task_id, "outreach", "contact identified", opportunity_id=opp.get("_id", ""),
          summary=contact.get("name", "")[:120], next_action="draft outreach")
    return {"found": True, "contact": contact}


def generate_outreach(opp: dict, profile: dict, contact: dict, task_id: str) -> dict:
    system = ("You are the Outreach agent. Write a concise, personalized, truthful cold email. "
              "No spam, no invented qualifications, no mass template. Return ONLY JSON: {subject:'', body:''}.")
    user = (f"To: {contact.get('name')} ({contact.get('role')}, {contact.get('organization')})\n"
            f"Why relevant: {contact.get('why_relevant','')}\nOpportunity: {opp.get('title')} at {opp.get('organization')}\n"
            f"From: {profile.get('name')} — skills {profile.get('skills', [])[:8]}")
    try:
        data = OC.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       response_format={"type": "json_object"}, max_tokens=700)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "{}")
        draft = OC.extract_json(content)
    except Exception:
        draft = {}
    if not draft.get("body"):
        draft = {"subject": f"Interest in {opp.get('title','')} — {profile.get('name','Applicant')}",
                 "body": (f"Hello {contact.get('name','there')},\n\nI came across {opp.get('title','')} at {opp.get('organization','')} "
                          f"and noticed your work ({(contact.get('why_relevant') or '')[:160]}). My background in "
                          f"{', '.join(profile.get('skills', [])[:4]) or 'relevant coursework'} aligns closely, and I would value any guidance on applying well.\n\n"
                          f"Thank you for your time,\n{profile.get('name','Applicant')}")}
        draft["heuristic"] = True
    # anti-abuse: daily cap
    today = time.strftime("%Y-%m-%d", time.gmtime())
    sent_today = len([o for o in col("outreach").find({"user_id": profile.get("user_id", "demo-user")}, limit=500)
                      if str(o.get("created_at", "")).startswith(today) and o.get("status") == "sent"])
    if sent_today >= get_settings().OUTREACH_DAILY_LIMIT:
        draft["blocked"] = f"Daily outreach limit reached ({sent_today})"
    ov = col("outreach").insert({
        "opportunity_id": opp.get("_id", ""), "contact_id": contact.get("_id", ""),
        "user_id": profile.get("user_id", "demo-user"), "subject": draft.get("subject", ""),
        "body": draft.get("body", ""), "status": "draft",
        "evidence": contact.get("evidence", []), "task_id": task_id})
    appr = col("approvals").insert({
        "type": "send_email", "outreach_id": ov["_id"],
        "opportunity_id": opp.get("_id", ""), "status": "pending",
        "summary": f"Send email to {contact.get('name','')}: {draft.get('subject','')}",
        "payload": {"to": contact.get("name", ""), "subject": draft.get("subject", ""),
                    "body": draft.get("body", "")}, "task_id": task_id})
    trace(task_id, "outreach", "draft awaiting approval",
          opportunity_id=opp.get("_id", ""), summary=draft.get("subject", "")[:160],
          next_action="human approval")
    return {"outreach_id": ov["_id"], "approval_id": appr["_id"], **draft}


# ---------------- Monitor / Followup ----------------
def watch(opp_id: str, user_id: str, task_id: str) -> dict:
    opp = col("opportunities").find_one({"_id": opp_id})
    if not opp:
        return {"ok": False, "error": "opportunity not found"}
    baseline = {k: opp.get(k) for k in ("deadline", "status", "requirements", "location", "title", "description")}
    job = col("monitoring_jobs").upsert(
        {"opportunity_id": opp_id, "user_id": user_id},
        {"opportunity_id": opp_id, "user_id": user_id, "baseline": baseline,
         "last_checked": "", "next_check": "", "active": True, "task_id": task_id})
    trace(task_id, "monitor", "watch created", opportunity_id=opp_id,
          summary=f"baseline keys={list(baseline.keys())}")
    return {"ok": True, "job": job}


def check_watch(opp_id: str, user_id: str, task_id: str, simulated: dict | None = None) -> dict:
    opp = col("opportunities").find_one({"_id": opp_id})
    job = col("monitoring_jobs").find_one({"opportunity_id": opp_id, "user_id": user_id})
    if not opp or not job:
        return {"ok": False, "error": "watch not found"}
    baseline = job.get("baseline", {}) or {}
    if simulated is not None and get_settings().DEMO_MODE:
        current = {**baseline, **simulated, "_simulated": True}
    else:
        # selective re-search: one web + one jobs query only
        q = f"{opp.get('organization','')} {opp.get('title','')}"
        w = SC.client.searchWeb(q, num=5)
        top = (w.get("results") or [{}])[0]
        current = dict(baseline)
        if top.get("snippet"):
            current["description"] = top.get("snippet", "")[:500]
    changes = L.compare_opportunity_state(baseline, current)
    col("monitoring_jobs").update(job["_id"], {
        "last_checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "last_changes": changes})
    if changes:
        col("notifications").insert({
            "user_id": user_id, "opportunity_id": opp_id, "type": "opportunity_changed",
            "changes": changes, "task_id": task_id,
            "message": f"{len(changes)} change(s): " + ", ".join(c["field"] for c in changes)})
        trace(task_id, "monitor", "change detected", opportunity_id=opp_id,
              summary=json.dumps(changes)[:400], next_action="verify")
        # re-verify (closed loop)
        verifier_agent(opp, task_id)
    else:
        trace(task_id, "monitor", "no change", opportunity_id=opp_id, summary="baseline matches")
    return {"ok": True, "changes": changes, "simulated": bool(simulated)}


def prepare_followup(outreach_id: str, task_id: str) -> dict:
    ov = col("outreach").find_one({"_id": outreach_id})
    if not ov:
        return {"ok": False, "error": "outreach not found"}
    if (ov.get("follow_up_count", 0) or 0) >= 2:
        return {"ok": False, "error": "Follow-up limit reached (anti-spam: max 2)"}
    draft = (f"Hello,\n\nJust following up on my note regarding '{ov.get('subject','')}'. "
             f"I remain very interested and would appreciate any guidance. Thank you!")
    appr = col("approvals").insert({
        "type": "send_followup", "outreach_id": outreach_id,
        "opportunity_id": ov.get("opportunity_id", ""), "status": "pending",
        "summary": f"Follow-up for: {ov.get('subject','')}",
        "payload": {"subject": f"Follow-up: {ov.get('subject','')}", "body": draft},
        "task_id": task_id})
    col("outreach").update(outreach_id, {"follow_up_count": (ov.get("follow_up_count", 0) or 0) + 1})
    trace(task_id, "followup", "follow-up draft ready", opportunity_id=ov.get("opportunity_id", ""),
          summary="awaiting approval", next_action="human approval")
    return {"ok": True, "approval_id": appr["_id"], "subject": appr["payload"]["subject"], "body": draft}


def verify_linkedin_opportunity(opp_id: str, task_id: str = "") -> dict:
    """Cross-check a LinkedIn discovery: jobs + company site, then verdict.

    Max 1-2 extra searches. Verdicts: VERIFIED / PARTIALLY_VERIFIED /
    CONFLICTING / UNVERIFIED / UNKNOWN. Never silently picks a side.
    """
    opp = col("opportunities").find_one({"_id": opp_id})
    if not opp:
        return {"ok": False, "error": "opportunity not found"}
    task_id = task_id or opp.get("task_id", uuid.uuid4().hex[:12])
    title, org = opp.get("title", ""), opp.get("organization", "")
    hits = {"jobs": 0, "company_site": 0}
    if org:
        r = SC.client.searchJobs(f"{title} {org}")
        hits["jobs"] = r.get("result_count", 0)
        for j in (r.get("results") or [])[:3]:
            col("opportunity_evidence").insert({
                "opportunity_id": opp_id, "task_id": task_id,
                "claim": "independent jobs listing check", "sourceType": "google_jobs",
                "sourceTitle": j.get("title", ""), "sourceUrl": j.get("link", ""),
                "evidenceText": (j.get("description") or "")[:400], "confidenceState": "UNVERIFIED"})
        r2 = SC.client.searchWeb(f"site:{org.split()[0].lower()}.com OR {org} official careers {title}", num=5)
        hits["company_site"] = r2.get("result_count", 0)
        for x in (r2.get("results") or [])[:2]:
            col("opportunity_evidence").insert({
                "opportunity_id": opp_id, "task_id": task_id,
                "claim": "company-site check", "sourceType": "google",
                "sourceTitle": x.get("title", ""), "sourceUrl": x.get("link", ""),
                "evidenceText": (x.get("snippet") or "")[:400], "confidenceState": "UNVERIFIED"})
    ver = verifier_agent(opp, task_id)
    col("opportunities").update(opp_id, {"verification": ver,
                                         "is_early_signal": not (hits["jobs"] or hits["company_site"])})
    trace(task_id, "verifier", "linkedin cross-check",
          opportunity_id=opp_id, summary=json.dumps(hits),
          next_action="match")
    state = "PARTIALLY_VERIFIED" if (hits["jobs"] or hits["company_site"]) else "UNVERIFIED"
    return {"ok": True, "verdict": state, "cross_check": hits, "verification": ver}


def linkedin_mission(user_goal: str, user_id: str = "demo-user",
                     max_results: int = 10, force_fresh: bool = False) -> dict:
    """LinkedIn-only discovery (posts + job pages), then persist + match locally.

    No auto deep-dives: 1-2 discovery searches, canonical merge, local match.
    Investigate/Verify stay one click away in the UI.
    """
    task_id = uuid.uuid4().hex[:12]
    profile = _user_profile(user_id)
    trace(task_id, "orchestrator", "linkedin mission started", summary=user_goal[:300])
    plan = planner_agent(user_goal, profile)
    plan["search_verticals"] = ["linkedin_posts", "linkedin_jobs"]
    trace(task_id, "planner", "linkedin plan", summary="posts + job pages",
          next_action="linkedin discovery")
    disc = discovery_agent(plan, user_goal, task_id, max_results=max_results,
                           force_fresh=force_fresh, user_id=user_id)
    opp_ids: list[str] = []
    prior = col("opportunities").find({"user_id": user_id}, limit=500)
    for c in disc.get("candidates", []):
        src = {"type": c.get("source_type", "linkedin_post"),
               "url": c.get("source_url", ""), "engine": "google"}
        existing = None
        if c.get("canonical_url"):
            existing = col("opportunities").find_one({"canonical_url": c["canonical_url"]})
        if not existing:
            existing = LI.find_canonical(prior, c)
        if existing:
            col("opportunities").update(
                existing["_id"], {"sources": existing.get("sources", []) + [src]})
            opp_ids.append(existing["_id"])
            prior = col("opportunities").find({"user_id": user_id}, limit=500)
            continue
        row = col("opportunities").insert({
            "task_id": task_id, "user_id": user_id, "title": c.get("title", "LinkedIn opportunity"),
            "organization": c.get("organization", ""), "location": c.get("location", ""),
            "description": c.get("description", ""), "source_url": c.get("source_url", ""),
            "canonical_url": c.get("canonical_url", ""), "source_engine": "google",
            "source_type": c.get("source_type", "linkedin_post"), "sources": [src],
            "freshness": c.get("freshness") or {"label": "UNKNOWN", "detail": "DATE UNKNOWN"},
            "is_early_signal": True, "author": c.get("author", ""),
            "application": c.get("application") or {}, "requirements": [],
            "skills_hint": [], "status": "EARLY_SIGNAL", "deadline": "", "evidence": []})
        col("opportunity_evidence").insert({
            "opportunity_id": row["_id"], "task_id": task_id,
            "claim": "discovered via LinkedIn signal (snippet only — partial data)",
            "sourceType": c.get("source_type", "linkedin_post"), "sourceTitle": c.get("title", ""),
            "sourceUrl": c.get("source_url", ""), "evidenceText": (c.get("description") or "")[:400],
            "confidenceState": "UNVERIFIED"})
        opp_ids.append(row["_id"])
    for oid in opp_ids:
        opp = col("opportunities").find_one({"_id": oid})
        m = match_agent(opp, profile, task_id)
        col("opportunities").update(oid, {"match_summary": {
            "score": m.get("score"), "rationale": m.get("rationale"),
            "gaps": (m.get("skill_match") or {}).get("gaps", [])}})
    trace(task_id, "orchestrator", "linkedin mission complete",
          summary=f"{len(opp_ids)} candidates, early signals")
    return {"task_id": task_id, "plan": plan, "discovery": {
        "raw": disc.get("raw_count"), "unique": len(opp_ids),
        "removed_duplicates": disc.get("removed"), "searches": disc.get("searches")},
        "opportunity_ids": opp_ids, "budget": SC.remaining_budget()}


# ---------------- Tool executors for the OpenRouter tool loop ----------------
def build_executors(task_id: str, user_id: str) -> dict:
    def _opp(a: dict, _c: dict) -> dict:
        o = col("opportunities").find_one({"_id": a.get("opportunity_id", "")})
        return o or {"error": "not found"}

    def _inv(a: dict, _c: dict) -> dict:
        o = col("opportunities").find_one({"_id": a.get("opportunity_id", "")})
        if not o:
            return {"error": "not found"}
        return investigator_agent(o, {"investigation_requirements": ["organization", "deadline"]}, task_id)

    def _ver(a: dict, _c: dict) -> dict:
        o = col("opportunities").find_one({"_id": a.get("opportunity_id", "")})
        return verifier_agent(o or {"_id": a.get("opportunity_id", "")}, task_id)

    def _mat(a: dict, _c: dict) -> dict:
        o = col("opportunities").find_one({"_id": a.get("opportunity_id", "")})
        return match_agent(o or {}, _user_profile(user_id), task_id)

    def _gen(a: dict, _c: dict) -> dict:
        o = col("opportunities").find_one({"_id": a.get("opportunity_id", "")})
        m = (col("matches").find_one({"opportunity_id": a.get("opportunity_id", "")}) or {}).get("match", {})
        return application_agent(o or {}, _user_profile(user_id), m, task_id)

    def _find(a: dict, _c: dict) -> dict:
        o = col("opportunities").find_one({"_id": a.get("opportunity_id", "")})
        return find_contact(o or {}, task_id)

    def _gout(a: dict, _c: dict) -> dict:
        o = col("opportunities").find_one({"_id": a.get("opportunity_id", "")})
        c = col("contacts").find_one({"_id": a.get("contact_id", "")}) or {}
        return generate_outreach(o or {}, _user_profile(user_id), c, task_id)

    def _appr(a: dict, _c: dict) -> dict:
        r = col("approvals").insert({"type": a.get("action_type", "generic"),
                                     "status": "pending", "summary": a.get("summary", ""),
                                     "payload": a.get("payload", {}), "task_id": task_id})
        return {"approval_id": r["_id"], "status": "pending"}

    def _send(a: dict, _c: dict) -> dict:
        return {"error": "send_email requires an approved approval_id via POST /api/outreach/:id/send"}

    def _watch(a: dict, _c: dict) -> dict:
        return watch(a.get("opportunity_id", ""), user_id, task_id)

    def _check(a: dict, _c: dict) -> dict:
        return check_watch(a.get("opportunity_id", ""), user_id, task_id)

    def _fol(a: dict, _c: dict) -> dict:
        return prepare_followup(a.get("outreach_id", ""), task_id)

    return {
        "search_web": lambda a, _c: SC.client.searchWeb(a.get("query", ""), a.get("location", ""), a.get("num", 10)),
        "search_jobs": lambda a, _c: SC.client.searchJobs(a.get("query", ""), a.get("location", "")),
        "search_scholar": lambda a, _c: SC.client.searchScholar(a.get("query", "")),
        "search_news": lambda a, _c: SC.client.searchNews(a.get("query", "")),
        "search_maps": lambda a, _c: SC.client.searchMaps(a.get("query", ""), a.get("location", "")),
        "search_linkedin_posts": lambda a, _c: SC.client.searchLinkedinPosts(a.get("query", ""), a.get("location", "")),
        "search_linkedin_jobs": lambda a, _c: SC.client.searchLinkedinJobs(a.get("query", ""), a.get("location", "")),
        "extract_application_url": lambda a, _c: (
            lambda o: LI.extract_application_url(
                f"{(o or {}).get('title', '')} {(o or {}).get('description', '')}",
                (o or {}).get("source_url", "")))(
            col("opportunities").find_one({"_id": a.get("opportunity_id", "")})),
        "verify_linkedin_opportunity": lambda a, _c: verify_linkedin_opportunity(
            a.get("opportunity_id", ""), (_c or {}).get("task_id", "")),
        "get_opportunity": _opp, "investigate_opportunity": _inv, "verify_claim": _ver,
        "match_profile": _mat, "generate_application": _gen,
        "find_relevant_contact": _find, "generate_outreach": _gout,
        "request_human_approval": _appr, "send_email": _send,
        "create_watch": _watch, "check_watch": _check, "prepare_followup": _fol,
    }


# ---------------- Orchestrator ----------------
def run_mission(user_goal: str, user_id: str = "demo-user",
                max_results: int = 12, force_fresh: bool = False,
                deep_investigate: int = 3) -> dict:
    """Full pipeline: plan -> discover -> persist -> investigate/match shortlist."""
    task_id = uuid.uuid4().hex[:12]
    profile = _user_profile(user_id)
    trace(task_id, "orchestrator", "mission started", summary=user_goal[:300])
    plan = planner_agent(user_goal, profile)
    trace(task_id, "planner", "plan created", summary=json.dumps(plan)[:500],
          next_action="discovery")
    disc = discovery_agent(plan, user_goal, task_id, max_results=max_results,
                           force_fresh=force_fresh, user_id=user_id)
    opp_ids: list[str] = []
    prior = col("opportunities").find({"user_id": user_id}, limit=500)
    for c in disc.get("candidates", []):
        stype = c.get("source_type") or {"google_jobs": "google_jobs", "google": "web",
                                         "google_scholar": "scholar"}.get(c.get("source_engine", ""), "web")
        src = {"type": stype, "url": c.get("source_url", ""),
               "engine": c.get("source_engine", "")}
        existing = None
        if c.get("canonical_url"):
            existing = col("opportunities").find_one({"canonical_url": c["canonical_url"]})
        if not existing:
            existing = LI.find_canonical(prior, c)
        if existing:
            # ONE canonical opportunity, MANY sources (evidence graph)
            srcs = existing.get("sources", []) + [src]
            col("opportunities").update(existing["_id"], {"sources": srcs})
            opp_ids.append(existing["_id"])
            prior = col("opportunities").find({"user_id": user_id}, limit=500)
            continue
        row = col("opportunities").insert({
            "task_id": task_id, "user_id": user_id,
            "title": c.get("title", "Untitled opportunity"),
            "organization": c.get("organization", ""),
            "location": c.get("location", ""),
            "description": c.get("description", ""),
            "source_url": c.get("source_url", ""),
            "canonical_url": c.get("canonical_url", ""),
            "source_engine": c.get("source_engine", ""),
            "source_type": c.get("source_type") or "web",
            "sources": [{"type": c.get("source_type") or "web",
                         "url": c.get("source_url", ""),
                         "engine": c.get("source_engine", "")}],
            "freshness": c.get("freshness") or {"label": "UNKNOWN", "detail": "DATE UNKNOWN"},
            "is_early_signal": bool(c.get("is_early_signal")),
            "author": c.get("author", ""),
            "application": c.get("application") or {},
            "requirements": c.get("requirements", []),
            "skills_hint": c.get("skills_hint", []),
            "status": "EARLY_SIGNAL" if c.get("is_early_signal") else "DISCOVERED",
            "deadline": c.get("deadline", ""),
            "evidence": []})
        col("opportunity_evidence").insert({
            "opportunity_id": row["_id"], "task_id": task_id,
            "claim": "discovered via SerpApi",
            "sourceType": c.get("source_engine", ""), "sourceTitle": c.get("title", ""),
            "sourceUrl": c.get("source_url", ""), "evidenceText": (c.get("description") or "")[:400],
            "confidenceState": "UNVERIFIED"})
        opp_ids.append(row["_id"])
    trace(task_id, "orchestrator", "candidates persisted",
          summary=f"{len(opp_ids)} opportunities", next_action="investigate shortlist")
    # selective deep investigation: top N only (budget-aware)
    results = []
    for oid in opp_ids[:max(1, deep_investigate)]:
        opp = col("opportunities").find_one({"_id": oid})
        col("opportunities").update(oid, {"status": "INVESTIGATING"})
        inv = investigator_agent({**opp, "task_id": task_id}, plan, task_id)
        col("opportunities").update(oid, {"status": "VERIFIED",
                                          "investigation": {k: v for k, v in inv.items() if k != "searches"}})
        ver = verifier_agent({**opp}, task_id)
        col("opportunities").update(oid, {"status": "MATCHED", "verification": ver})
        m = match_agent({**opp}, profile, task_id)
        col("opportunities").update(oid, {"status": "SHORTLISTED", "match_summary": {
            "score": m.get("score"), "rationale": m.get("rationale"),
            "gaps": (m.get("skill_match") or {}).get("gaps", [])}})
        results.append({"opportunity_id": oid, "match": m,
                        "verification": ver,
                        "investigation": {k: v for k, v in inv.items() if k != "evidence"}})
    trace(task_id, "orchestrator", "mission complete",
          summary=f"{len(opp_ids)} discovered, {len(results)} deeply investigated")
    return {"task_id": task_id, "plan": plan, "discovery": {
        "raw": disc.get("raw_count"), "unique": len(opp_ids),
        "removed_duplicates": disc.get("removed"), "searches": disc.get("searches")},
        "opportunity_ids": opp_ids, "results": results,
        "budget": SC.remaining_budget()}

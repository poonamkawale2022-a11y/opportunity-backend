"""Opportunity Intelligence Agent — FastAPI backend.

Serves the full REST contract, OpenAPI at /api/docs, health + integration
smoke endpoints, Gmail OAuth, approvals, monitoring, agent timeline.
"""
from __future__ import annotations

import io
import json
import re
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from . import agents as AG
from . import gmail as gmail_mod
from . import logic as L
from . import openrouter_client as OC
from . import serpapi_client as SC
from .config import get_settings
from .schemas import AGENT_TOOLS, DiscoverIn, ProfileIn
from .store import backend_kind, col

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Opportunity Intelligence Agent",
              description="Multi-agent opportunity lifecycle OS: discover→investigate→verify→match→prepare→approve→act→monitor.",
              version="1.0.0", docs_url="/api/docs", redoc_url="/api/redoc",
              openapi_url="/api/openapi.json")
app.state.limiter = limiter
s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def ok(data: Any = None, **kw) -> dict:
    return {"ok": True, **({"data": data} if data is not None else {}), **kw}


def err(msg: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=msg)


# ---------- health / meta ----------
@app.get("/api/health")
def health():
    st = get_settings()
    return {"ok": True, "service": "opportunity-intel", "db": backend_kind(),
            "serpapi_configured": bool(st.SERPAPI_API_KEY),
            "openrouter_configured": bool(st.OPENROUTER_API_KEY),
            "gmail_configured": bool(st.GOOGLE_CLIENT_ID and st.GOOGLE_CLIENT_SECRET),
            "demo_mode": st.DEMO_MODE, "budget": SC.remaining_budget(),
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


@app.get("/api/meta")
def meta():
    return ok({"agents": AG.AGENTS, "lifecycle": [
        "DISCOVERED", "INVESTIGATING", "VERIFIED", "MATCHED", "SHORTLISTED",
        "PREPARING", "APPLICATION_READY", "AWAITING_APPROVAL", "APPLIED",
        "OUTREACH_READY", "OUTREACH_SENT", "WAITING", "FOLLOW_UP_DUE",
        "MONITORING", "CHANGED", "CLOSED", "REJECTED", "OFFER"],
        "tools": [t["function"]["name"] for t in AGENT_TOOLS]})


# ---------- auth (local accounts; Gmail OAuth stays separate) ----------
import hashlib as _hl
import hmac as _hmac
import secrets as _secrets


def _hash_pw(pw: str, salt_hex: str) -> str:
    try:
        salt = bytes.fromhex(salt_hex)
    except Exception:
        salt = b"fallback"
    return _hl.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000).hex()


@app.post("/api/auth/register")
def register(body: dict):
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    pw = body.get("password") or ""
    if not name or "@" not in email or len(pw) < 6:
        raise err("name, a valid email and a 6+ character password are required", 400)
    if col("users").find_one({"email": email}):
        raise err("email already registered — log in instead", 409)
    salt = _secrets.token_hex(16)
    token = _secrets.token_urlsafe(32)
    col("users").insert({"name": name, "email": email, "user_id": email,
                         "password_salt": salt, "password_hash": _hash_pw(pw, salt),
                         "sessions": [{"token": token, "created": time.time()}]})
    col("profiles").upsert({"user_id": email},
                            {"user_id": email, "name": name, "email": email,
                             "skills": [], "location": "", "preferences": {}})
    AG.trace(token[:8], "orchestrator", "user registered", summary=email)
    return ok({"token": token, "user": {"name": name, "email": email}})


@app.post("/api/auth/login")
def login(body: dict):
    email = (body.get("email") or "").strip().lower()
    u = col("users").find_one({"email": email})
    if not u or not _hmac.compare_digest(
            u.get("password_hash", ""),
            _hash_pw(body.get("password") or "", u.get("password_salt", "00"))):
        raise err("invalid email or password", 401)
    token = _secrets.token_urlsafe(32)
    sessions = (u.get("sessions") or []) + [{"token": token, "created": time.time()}]
    col("users").update(u["_id"], {"sessions": sessions[-10:]})
    return ok({"token": token, "user": {"name": u.get("name"), "email": email}})


def _who(request: Request) -> Optional[dict]:
    auth = request.headers.get("authorization", "")
    tok = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not tok:
        return None
    for u in col("users").find(limit=500):
        if any(s.get("token") == tok for s in (u.get("sessions") or [])):
            return {"name": u.get("name"), "email": u.get("email")}
    return None


@app.get("/api/auth/me")
def me(request: Request):
    u = _who(request)
    if not u:
        raise err("not authenticated", 401)
    return ok(u)


@app.post("/api/auth/logout")
def logout(request: Request):
    auth = request.headers.get("authorization", "")
    tok = auth[7:] if auth.lower().startswith("bearer ") else ""
    if tok:
        for u in col("users").find(limit=500):
            sessions = [s for s in (u.get("sessions") or []) if s.get("token") != tok]
            if len(sessions) != len(u.get("sessions") or []):
                col("users").update(u["_id"], {"sessions": sessions})
    return ok({"logged_out": True})


# ---------- profile / resume ----------
@app.post("/api/profile")
def save_profile(p: ProfileIn):
    row = col("profiles").upsert({"user_id": p.user_id}, p.model_dump())
    return ok(row)


@app.get("/api/profile")
def get_profile(user_id: str = "demo-user"):
    p = col("profiles").find_one({"user_id": user_id})
    if not p:
        raise err("profile not found — create one via POST /api/profile", 404)
    return ok(p)


@app.patch("/api/profile")
def patch_profile(body: dict):
    user_id = body.pop("user_id", "demo-user")
    p = col("profiles").find_one({"user_id": user_id}) or {"user_id": user_id}
    p.update(body)
    # preference learning: likes/dislikes merge
    if "like" in body or "dislike" in body:
        prefs = p.get("preferences", {}) or {}
        likes = set(prefs.get("likes", []) or [])
        dislikes = set(prefs.get("dislikes", []) or [])
        if body.get("like"):
            likes.add(body["like"])
        if body.get("dislike"):
            dislikes.add(body["dislike"])
        p["preferences"] = {**prefs, "likes": sorted(likes), "dislikes": sorted(dislikes)}
    row = col("profiles").upsert({"user_id": user_id}, p)
    return ok(row)


@app.post("/api/profile/resume")
async def upload_resume(request: Request, user_id: str = "demo-user"):
    """Accept JSON {text} or multipart form (file + text)."""
    raw = ""
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        body = await request.json()
        raw = (body or {}).get("text", "") or ""
        user_id = (body or {}).get("user_id", user_id)
    else:
        try:
            form = await request.form()
        except Exception:
            form = None
        if form is not None:
            raw = str(form.get("text", "") or "")
            user_id = str(form.get("user_id", user_id) or user_id)
            up = form.get("file")
            if up is not None and hasattr(up, "read"):
                blob = await up.read()
                name = (getattr(up, "filename", "") or "").lower()
                try:
                    if name.endswith(".pdf"):
                        from PyPDF2 import PdfReader

                        reader = PdfReader(io.BytesIO(blob))
                        raw = "\n".join((pg.extract_text() or "") for pg in reader.pages)
                    elif name.endswith(".docx"):
                        from docx import Document

                        doc = Document(io.BytesIO(blob))
                        raw = "\n".join(p.text for p in doc.paragraphs)
                    else:
                        raw = blob.decode("utf-8", errors="ignore")
                except Exception as e:
                    raise err(f"resume parse failed: {e}", 400)
    if not raw.strip():
        raise err("empty resume — upload PDF/DOCX or paste text", 400)
    template_info: dict = {}
    try:
        from . import resume_template as RT

        if "blob" in dir() and blob and name:
            p = RT.save_upload(get_settings().DATA_DIR, user_id,
                               getattr(up, "filename", "resume.bin"), blob)
            template_info = {"template_file": p.split("resumes")[-1],
                             "template_type": name.rsplit(".", 1)[-1] if "." in name else "bin"}
    except Exception:
        pass
    parsed = L.parse_resume_text(raw)
    existing = col("profiles").find_one({"user_id": user_id}) or {"user_id": user_id}
    merged = {**existing, **{k: v for k, v in parsed.items() if v},
              "skills": sorted(set((existing.get("skills") or []) + parsed.get("skills", [])))}
    row = col("profiles").upsert({"user_id": user_id}, merged)
    AG.trace(uuid.uuid4().hex[:12], "orchestrator", "resume ingested",
             summary=f"skills={parsed.get('skills', [])[:10]}")
    return ok(row, template=template_info or None)


# ---------- discovery ----------
@app.post("/api/opportunities/discover")
def discover(body: DiscoverIn):
    try:
        return ok(AG.run_mission(body.user_goal, body.user_id,
                                 max_results=body.max_results,
                                 force_fresh=body.force_fresh))
    except Exception as e:
        raise err(f"discovery failed: {e}", 500)


@app.post("/api/opportunities/discover/linkedin")
def discover_linkedin(body: DiscoverIn):
    """LinkedIn-signal discovery: posts + job pages, canonical merge, local match."""
    try:
        return ok(AG.linkedin_mission(body.user_goal, body.user_id,
                                      max_results=body.max_results,
                                      force_fresh=body.force_fresh))
    except Exception as e:
        raise err(f"linkedin discovery failed: {e}", 500)


@app.post("/api/opportunities/{oid}/verify-linkedin")
def verify_linkedin(oid: str):
    out = AG.verify_linkedin_opportunity(oid)
    if not out.get("ok"):
        raise err(out.get("error", "verify failed"), 404)
    return ok(out)


@app.post("/api/opportunities/{oid}/extract-application-link")
def extract_app_link(oid: str):
    from . import linkedin as LI

    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    texts = [o.get("title", ""), o.get("description", "")]
    for e in col("opportunity_evidence").find({"opportunity_id": oid}, limit=50):
        texts.append(e.get("evidenceText", ""))
    app = LI.extract_application_url(" ".join(texts), o.get("source_url", ""))
    col("opportunities").update(oid, {"application": app})
    if app.get("found"):
        col("opportunity_evidence").insert({
            "opportunity_id": oid, "claim": "application destination",
            "sourceType": app.get("classification", ""), "sourceTitle": "",
            "sourceUrl": app.get("url", ""), "evidenceText": app.get("url", ""),
            "confidenceState": "VERIFIED" if app.get("classification") == "OFFICIAL_APPLICATION" else "PARTIALLY_VERIFIED"})
    return ok(app)


@app.get("/api/opportunities")
def list_opps(user_id: str = "demo-user", status: str = "", limit: int = 50):
    flt: dict = {"user_id": user_id} if user_id else {}
    if status:
        flt["status"] = status
    rows = col("opportunities").find(flt, limit=limit)
    for r in rows:
        m = col("matches").find_one({"opportunity_id": r["_id"]})
        if m:
            r["match"] = m.get("match")
    return ok(rows, count=len(rows))


@app.get("/api/opportunities/{oid}")
def get_opp(oid: str):
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    o["evidence"] = col("opportunity_evidence").find({"opportunity_id": oid}, limit=100)
    m = col("matches").find_one({"opportunity_id": oid})
    if m:
        o["match"] = m.get("match")
    return ok(o)


class InvestigateIn(BaseModel):
    user_id: str = "demo-user"


@app.post("/api/opportunities/{oid}/investigate")
def investigate(oid: str, body: InvestigateIn = InvestigateIn()):
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    task_id = o.get("task_id", uuid.uuid4().hex[:12])
    col("opportunities").update(oid, {"status": "INVESTIGATING"})
    inv = AG.investigator_agent(o, {"investigation_requirements": ["organization", "eligibility", "deadline"]}, task_id)
    col("opportunities").update(oid, {"status": "VERIFIED",
                                      "investigation": {k: v for k, v in inv.items() if k != "searches"}})
    return ok(inv)


@app.get("/api/opportunities/{oid}/evidence")
def evidence(oid: str):
    return ok(col("opportunity_evidence").find({"opportunity_id": oid}, limit=200))


@app.post("/api/opportunities/{oid}/verify")
def verify(oid: str):
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    v = AG.verifier_agent(o, o.get("task_id", uuid.uuid4().hex[:12]))
    col("opportunities").update(oid, {"verification": v})
    return ok(v)


@app.post("/api/opportunities/{oid}/match")
def match(oid: str, body: InvestigateIn = InvestigateIn()):
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    prof = col("profiles").find_one({"user_id": body.user_id}) or {"user_id": body.user_id}
    m = AG.match_agent(o, prof, o.get("task_id", uuid.uuid4().hex[:12]))
    col("opportunities").update(oid, {"status": "MATCHED"})
    return ok(m)


@app.get("/api/opportunities/{oid}/match")
def get_match(oid: str, user_id: str = "demo-user"):
    m = col("matches").find_one({"opportunity_id": oid, "user_id": user_id})
    if not m:
        raise err("no match yet — POST first", 404)
    return ok(m.get("match"))


# ---------- application ----------
@app.post("/api/opportunities/{oid}/prepare-application")
def prepare(oid: str, body: InvestigateIn = InvestigateIn()):
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    prof = col("profiles").find_one({"user_id": body.user_id}) or {"user_id": body.user_id}
    m = (col("matches").find_one({"opportunity_id": oid}) or {}).get("match") or AG.match_agent(o, prof, o.get("task_id", "t"))
    out = AG.application_agent(o, prof, m, o.get("task_id", uuid.uuid4().hex[:12]))
    col("opportunities").update(oid, {"status": "APPLICATION_READY"})
    return ok(out)


@app.get("/api/applications")
def list_apps(user_id: str = "demo-user"):
    return ok(col("applications").find({"user_id": user_id}, limit=100))


# ---------- AI resume builder (LLM only, zero SerpApi) ----------
RESUME_SCHEMA_HINT = ("{name,email,phone,location,links:{linkedin,github,website},"
                      "summary,experience:[{title,company,years,summary}],"
                      "education:[{school,degree,field,years}],skills:[],projects:[{title,summary}]}")


def _heuristic_questions(gaps: list, title: str) -> list[dict]:
    qs = []
    for i, g in enumerate(gaps[:4]):
        qs.append({"id": f"gap{i}", "question": f"Any experience with {g} — coursework, tutorial, or project? Tell me briefly, or say no.",
                   "options": ["Yes, project", "Coursework only", "No"], "why": f"Matters for {title}"})
    qs.append({"id": "proof", "question": "One achievement with a number on it (%, users, latency, rank)?",
               "options": [], "why": "Numbers carry resumes"})
    return qs


@app.post("/api/opportunities/{oid}/resume-questions")
def resume_questions(oid: str, body: dict = {}):
    user_id = body.get("user_id", "demo-user")
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    prof = col("profiles").find_one({"user_id": user_id}) or {"user_id": user_id}
    m = (col("matches").find_one({"opportunity_id": oid}) or {}).get("match") or {}
    gaps = (m.get("skill_match") or {}).get("gaps", []) or o.get("skills_hint", [])[:4]
    system = ("You are a resume strategist. Read the profile, the job and its skill gaps. "
              "Ask at most 5 sharp questions that decide what goes on the resume. "
              "Ask ONLY about gaps/unknowns that matter for THIS job. Never suggest inventing "
              "experience — phrase as 'do you have X? describe it or say no'. "
              "Return ONLY JSON: {questions:[{id,question,options[],why}]}.")
    user = (f"Profile: {json.dumps(prof, default=str)[:2500]}\nJob: {o.get('title')} at "
            f"{o.get('organization')} — {(o.get('description') or '')[:1200]}\nGaps: {gaps}")
    try:
        data = OC.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       response_format={"type": "json_object"}, max_tokens=800)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "{}")
        qs = OC.extract_json(content).get("questions", [])
        if not qs:
            raise ValueError("empty")
    except Exception:
        qs = _heuristic_questions(gaps, o.get("title", "this role"))
        return ok({"questions": qs, "mode": "heuristic"})
    AG.trace(o.get("task_id", "t"), "application", "resume questions ready",
             opportunity_id=oid, summary=f"{len(qs)} questions")
    return ok({"questions": qs[:5], "mode": "llm"})


@app.get("/api/profile/template")
def template_info(user_id: str = "demo-user"):
    from . import resume_template as RT

    path, blob = RT.load_upload(get_settings().DATA_DIR, user_id)
    if not blob:
        return ok({"has_template": False})
    ext = (path.rsplit(".", 1)[-1] if "." in path else "").lower()
    info: dict = {"has_template": True, "type": ext}
    try:
        if ext == "docx":
            info.update(RT.analyze_docx(blob))
    except Exception as e:
        info["analyze_error"] = str(e)[:200]
    return ok(info)


@app.post("/api/opportunities/{oid}/build-resume")
def build_resume(oid: str, body: dict = {}):
    from . import resume_template as RT

    user_id = body.get("user_id", "demo-user")
    answers = body.get("answers", []) or []
    keep_template = bool(body.get("keep_template"))
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    prof = col("profiles").find_one({"user_id": user_id}) or {"user_id": user_id}
    tpath, tblob = RT.load_upload(get_settings().DATA_DIR, user_id)
    ttype = (tpath.rsplit(".", 1)[-1].lower() if tpath and "." in tpath else "")
    sections: list[str] = []
    if ttype == "docx" and tblob:
        try:
            sections = RT.analyze_docx(tblob).get("sections", [])
        except Exception:
            sections = []
    system = ("You are an expert resume writer AND an ATS. Write the strongest truthful "
              f"resume for THIS job using ONLY the profile plus the candidate's answers. "
              "If an answer says 'no', leave that skill OUT — never invent proficiency, "
              "years, degrees or employers. "
              + (f"Rewrite section by section using EXACTLY these headings: {sections}. "
                 "Return ONLY JSON: {sections: {{HEADING: [paragraph texts]}}, "
                 "changes: [{section, change}]} — one line per real edit." if (keep_template and sections)
                 else f"Single column, standard headings. Return ONLY JSON matching: {RESUME_SCHEMA_HINT}"))
    user = (f"Profile: {json.dumps(prof, default=str)[:3000]}\nJob: {o.get('title')} at "
            f"{o.get('organization')} — {(o.get('description') or '')[:1200]}\n"
            f"Candidate answers: {json.dumps(answers, default=str)[:2000]}")
    resume, mode, changes, docx_ok = {}, "heuristic", [], False
    try:
        data = OC.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       response_format={"type": "json_object"}, max_tokens=2000)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "{}")
        parsed_llm = OC.extract_json(content)
        if keep_template and sections and parsed_llm.get("sections"):
            rebuilt = RT.rebuild_docx(tblob, parsed_llm["sections"])
            col("applications").upsert(
                {"opportunity_id": oid, "user_id": user_id},
                {"opportunity_id": oid, "user_id": user_id, "resume_docx": rebuilt.hex(),
                 "resume_sections": parsed_llm["sections"],
                 "resume_answers": answers, "resume_mode": "llm-template",
                 "task_id": o.get("task_id", "")})
            changes = parsed_llm.get("changes", [])[:12]
            docx_ok, mode = True, "llm-template"
            resume = {"name": prof.get("name", ""), "template_sections": sections}
        elif parsed_llm.get("name"):
            resume, mode = parsed_llm, "llm"
        else:
            raise ValueError("empty")
    except Exception:
        pass
    if not resume:
        yes = " ".join(a.get("answer", "") for a in answers if isinstance(a, dict))
        resume = {"name": prof.get("name", ""), "email": prof.get("email", ""),
                  "phone": prof.get("phone", ""), "location": prof.get("location", ""),
                  "links": prof.get("links", {}),
                  "summary": f"{o.get('title', '')} applicant. {yes[:200]}".strip(),
                  "experience": prof.get("experience", []),
                  "education": prof.get("education", []),
                  "skills": prof.get("skills", []),
                  "projects": prof.get("projects", [])}
    app = col("applications").upsert(
        {"opportunity_id": oid, "user_id": user_id},
        {"opportunity_id": oid, "user_id": user_id, **({} if docx_ok else {"resume": resume}),
         "resume_answers": answers, "resume_mode": mode,
         "task_id": o.get("task_id", "")})
    AG.trace(o.get("task_id", "t"), "application", f"resume built ({mode})",
             opportunity_id=oid, summary=resume.get("name", "")[:80])
    return ok({"resume": resume, "mode": mode, "changes": changes,
               "docx_available": docx_ok,
               "template": {"type": ttype, "sections": sections} if ttype else None,
               "application_id": app["_id"]})


@app.get("/api/applications/{aid}/resume.pdf")
def resume_pdf(aid: str):
    from fastapi.responses import Response

    from .resume_pdf import render_resume_pdf

    a = col("applications").find_one({"_id": aid})
    if not a or not a.get("resume"):
        raise err("no built resume on this application — build it first", 404)
    pdf = render_resume_pdf(a["resume"])
    name = (a["resume"].get("name") or "resume").replace(" ", "_")[:40]
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Pursuit_{name}.pdf"'})


@app.get("/api/applications/{aid}/resume.docx")
def resume_docx(aid: str):
    from fastapi.responses import Response

    a = col("applications").find_one({"_id": aid})
    if not a or not a.get("resume_docx"):
        raise err("no template rebuild on this application — build with 'keep my template' first", 404)
    blob = bytes.fromhex(a["resume_docx"])
    name = ((a.get("resume") or {}).get("name") or "resume").replace(" ", "_")[:40]
    return Response(content=blob,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="Pursuit_{name}_edited.docx"'})


@app.get("/api/applications/{aid}")
def get_app(aid: str):
    a = col("applications").find_one({"_id": aid})
    if not a:
        raise err("application not found", 404)
    return ok(a)


@app.patch("/api/applications/{aid}")
def patch_app(aid: str, body: dict):
    a = col("applications").update(aid, body)
    if not a:
        raise err("application not found", 404)
    return ok(a)


# ---------- outreach ----------
@app.post("/api/opportunities/{oid}/find-contact")
def find_contact(oid: str):
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    return ok(AG.find_contact(o, o.get("task_id", uuid.uuid4().hex[:12])))


@app.post("/api/opportunities/{oid}/generate-outreach")
def gen_outreach(oid: str, body: dict = {}):
    o = col("opportunities").find_one({"_id": oid})
    if not o:
        raise err("opportunity not found", 404)
    user_id = body.get("user_id", "demo-user")
    prof = col("profiles").find_one({"user_id": user_id}) or {"user_id": user_id}
    fc = AG.find_contact(o, o.get("task_id", uuid.uuid4().hex[:12]))
    if not fc.get("found"):
        return ok({**fc, "outreach": None}, note="No contact invented.")
    contact = fc["contact"]
    if body.get("contact_id"):
        c = col("contacts").find_one({"_id": body["contact_id"]})
        if c:
            contact = c
    out = AG.generate_outreach(o, prof, contact, o.get("task_id", uuid.uuid4().hex[:12]))
    col("opportunities").update(oid, {"status": "OUTREACH_READY"})
    return ok(out)


@app.get("/api/outreach/{ovid}")
def get_outreach(ovid: str):
    o = col("outreach").find_one({"_id": ovid})
    if not o:
        raise err("outreach not found", 404)
    return ok(o)


@app.post("/api/outreach/{ovid}/approve")
def approve_outreach(ovid: str, body: dict = {}):
    o = col("outreach").find_one({"_id": ovid})
    if not o:
        raise err("outreach not found", 404)
    edits = {k: body[k] for k in ("subject", "body") if k in body}
    if edits:
        col("outreach").update(ovid, edits)
    appr = col("approvals").find_one({"outreach_id": ovid, "status": "pending"})
    if appr:
        col("approvals").update(appr["_id"], {"status": "approved", "decided_at": time.time()})
    col("outreach").update(ovid, {"status": "approved"})
    col("opportunities").update(o.get("opportunity_id", ""), {"status": "AWAITING_APPROVAL"})
    return ok({"outreach_id": ovid, "status": "approved",
               "approval_id": (appr or {}).get("_id", "")})


@app.post("/api/outreach/{ovid}/draft")
def draft_email(ovid: str, body: dict = {}):
    o = col("outreach").find_one({"_id": ovid})
    if not o:
        raise err("outreach not found", 404)
    user_id = body.get("user_id", "demo-user")
    contact = col("contacts").find_one({"_id": o.get("contact_id", "")}) or {}
    to = body.get("to") or contact.get("name", "") or "recipient@example.com"
    return ok(gmail_mod.create_draft(user_id, to, o.get("subject", ""), o.get("body", "")))


@app.post("/api/outreach/{ovid}/send")
def send_email(ovid: str, body: dict = {}):
    o = col("outreach").find_one({"_id": ovid})
    if not o:
        raise err("outreach not found", 404)
    appr = col("approvals").find_one({"outreach_id": ovid, "status": "approved"})
    if not appr and not body.get("approval_id"):
        raise err("send blocked: explicit approval required first (POST approve)", 409)
    if body.get("approval_id"):
        a = col("approvals").find_one({"_id": body["approval_id"]})
        if not a or a.get("status") != "approved":
            raise err("send blocked: approval_id is not approved", 409)
    user_id = body.get("user_id", "demo-user")
    contact = col("contacts").find_one({"_id": o.get("contact_id", "")}) or {}
    to = body.get("to") or contact.get("name", "") or "recipient@example.com"
    res = gmail_mod.send_message(user_id, to, o.get("subject", ""), o.get("body", ""))
    if res.get("ok"):
        col("outreach").update(ovid, {"status": "sent", "message_id": res.get("message_id", ""),
                                      "sent_at": res.get("timestamp", ""),
                                      "last_contacted_at": time.time(), "response_received": False})
        col("opportunities").update(o.get("opportunity_id", ""), {"status": "OUTREACH_SENT"})
        AG.trace(o.get("task_id", "t"), "outreach", "email sent",
                 opportunity_id=o.get("opportunity_id", ""))
    return ok(res)


@app.get("/api/outreach/{ovid}/status")
def outreach_status(ovid: str):
    o = col("outreach").find_one({"_id": ovid})
    if not o:
        raise err("outreach not found", 404)
    return ok({k: o.get(k) for k in ("status", "message_id", "sent_at", "follow_up_count",
                                     "last_contacted_at", "response_received")})


@app.post("/api/outreach/{ovid}/followup")
def followup(ovid: str):
    o = col("outreach").find_one({"_id": ovid})
    if not o:
        raise err("outreach not found", 404)
    return ok(AG.prepare_followup(ovid, o.get("task_id", uuid.uuid4().hex[:12])))


@app.get("/api/approvals")
def approvals(status: str = "pending"):
    return ok(col("approvals").find({"status": status}, limit=100))


@app.post("/api/approvals/{aid}/decide")
def decide(aid: str, body: dict):
    decision = body.get("decision", "approved")
    if decision not in ("approved", "rejected", "cancelled"):
        raise err("decision must be approved|rejected|cancelled", 400)
    a = col("approvals").update(aid, {"status": decision, "decided_at": time.time()})
    if not a:
        raise err("approval not found", 404)
    return ok(a)


# ---------- monitoring ----------
@app.post("/api/opportunities/{oid}/watch")
def watch(oid: str, body: InvestigateIn = InvestigateIn()):
    out = AG.watch(oid, body.user_id, uuid.uuid4().hex[:12])
    if not out.get("ok"):
        raise err(out.get("error", "watch failed"), 404)
    col("opportunities").update(oid, {"status": "MONITORING"})
    return ok(out["job"])


@app.delete("/api/opportunities/{oid}/watch")
def unwatch(oid: str, user_id: str = "demo-user"):
    n = col("monitoring_jobs").delete({"opportunity_id": oid, "user_id": user_id})
    return ok({"removed": n})


@app.post("/api/opportunities/{oid}/check-now")
def check_now(oid: str, body: dict = {}):
    out = AG.check_watch(oid, body.get("user_id", "demo-user"),
                         uuid.uuid4().hex[:12], simulated=body.get("simulated"))
    if not out.get("ok"):
        raise err(out.get("error", "check failed"), 404)
    if out.get("changes"):
        col("opportunities").update(oid, {"status": "CHANGED"})
    return ok(out)


@app.get("/api/monitoring")
def monitoring(user_id: str = "demo-user"):
    return ok(col("monitoring_jobs").find({"user_id": user_id}, limit=100))


@app.get("/api/notifications")
def notifs(user_id: str = "demo-user"):
    return ok(col("notifications").find({"user_id": user_id}, limit=100))


# ---------- agent activity ----------
@app.get("/api/agent-runs/{tid}")
def runs(tid: str):
    return ok(col("agent_runs").find({"task_id": tid}, limit=500))


@app.get("/api/opportunities/{oid}/activity")
def opp_activity(oid: str):
    return ok(col("agent_runs").find({"opportunity_id": oid}, limit=500))


@app.get("/api/activity")
def activity(user_id: str = "", limit: int = 200):
    rows = col("agent_runs").find(limit=limit)
    return ok(rows, count=len(rows), db=backend_kind())


# ---------- integrations ----------
@app.get("/api/integrations")
def integrations():
    st = get_settings()
    g = gmail_mod.status()
    return ok({"gmail": g, "serpapi": {"configured": bool(st.SERPAPI_API_KEY),
                                       "budget": SC.remaining_budget()},
               "openrouter": {"configured": bool(st.OPENROUTER_API_KEY),
                              "model": st.OPENROUTER_MODEL}})


@app.get("/api/integrations/gmail/status")
def gmail_status(user_id: str = "demo-user"):
    return ok(gmail_mod.status(user_id))


@app.post("/api/integrations/gmail/connect")
def gmail_connect(body: dict = {}):
    return ok(gmail_mod.auth_url(body.get("user_id", "demo-user")))


@app.get("/api/integrations/gmail/callback")
def gmail_callback(code: str, state: str = "demo-user"):
    return ok(gmail_mod.oauth_callback(code, state))


# ---------- chat (ChatGPT-style console over the agent loop) ----------
class ChatIn(BaseModel):
    message: str
    user_id: str = "demo-user"
    history: list[dict] = []


SITE_KNOWLEDGE = """
You also know this website completely. Pages and tabs (console lives at /app):
- chat: this conversation. home: search bar, stats, updates, recent activity.
- jobs: every saved job with fit %, source, freshness and status; click one for details.
- details: the open job — about, fit breakdown, proof/evidence, outreach drafts, run log.
- activity: everything the app has done, newest first. approvals: inbox where the
  user approves emails before anything sends — nothing external ever happens first.
- watching: watched jobs + change alerts. profile: the candidate form with resume
  autofill, skills, preferences.
- Budget (SerpApi searches left) lives in the top bar. Gmail sends only after
  approval, and without Gmail OAuth the app makes drafts/`.eml` files instead —
  it never pretends something sent.
If the user asks to go somewhere, start your reply with [GO:tab] where tab is one
of chat, home, jobs, details, activity, approvals, watching, profile.
"""

NAV_TABS = {"chat": "chat", "home": "dashboard", "jobs": "feed", "details": "detail",
            "activity": "activity", "approvals": "approvals",
            "watching": "monitoring", "profile": "setup"}


def _go_tag(reply: str) -> tuple[str, str]:
    import re as _re
    m = _re.search(r"\[GO:(\w+)\]", reply or "")
    if not m:
        return reply or "", ""
    key = m.group(1).lower()
    tab = NAV_TABS.get(key) or next((v for k, v in NAV_TABS.items() if v == key), "")
    if not tab:
        return reply or "", ""
    return _re.sub(r"\[GO:\w+\]\s*", "", reply, count=1), tab


@app.post("/api/chat")
def chat_endpoint(body: ChatIn):
    msg = (body.message or "").strip()
    if not msg:
        raise err("empty message", 400)
    task_id = uuid.uuid4().hex[:12]
    profile = col("profiles").find_one({"user_id": body.user_id}) or {"user_id": body.user_id}
    opps = col("opportunities").find({"user_id": body.user_id}, limit=30)
    opp_ctx = [{"_id": o["_id"], "title": o.get("title"), "org": o.get("organization"),
                "status": o.get("status"), "source": o.get("source_type"),
                "fit": (o.get("match_summary") or {}).get("score")} for o in opps]
    hist = [{"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in (body.history or []) if isinstance(m, dict)][:10]
    AG.trace(task_id, "orchestrator", "chat", summary=msg[:200])
    if not get_settings().OPENROUTER_API_KEY:
        return ok(_chat_heuristic(msg, body.user_id, profile, opp_ctx, task_id))
    system = (
        "You are Pursuit, the assistant inside a job console. "
        f"Profile: {json.dumps(profile, default=str)[:1500]}. "
        f"Jobs already on file: {json.dumps(opp_ctx, default=str)[:2500]}. "
        "Speak plainly, no jargon. Use tools when the user asks to find, search, "
        "check, match, draft or watch jobs; otherwise answer from context. "
        "Never invent links, contacts, deadlines or application states. "
        "When searches run, say what you searched and what you found."
        + SITE_KNOWLEDGE)
    try:
        out = OC.agent_loop(system, msg, AG.build_executors(task_id, body.user_id),
                            context={"user_id": body.user_id, "task_id": task_id},
                            history=hist, max_iterations=3)
    except Exception as e:
        return ok(_chat_heuristic(msg, body.user_id, profile, opp_ctx, task_id,
                                  note=f"Assistant offline ({e}); local answer."))
    fresh = [o["_id"] for o in col("opportunities").find({"task_id": task_id}, limit=20)]
    reply, nav = _go_tag(out.get("final") or "Done — see the Jobs tab.")
    if fresh and not nav:
        nav = "feed"
    return ok({"reply": reply, "tool_calls": out.get("tool_calls", []), "task_id": task_id,
               "model": out.get("model", ""), "cards": fresh, "navigate": nav,
               "budget": SC.remaining_budget()})


def _chat_heuristic(msg: str, user_id: str, profile: dict, opp_ctx: list,
                    task_id: str, note: str = "") -> dict:
    low = msg.lower()

    def _wrap(reply: str, nav: str = "", cards: list | None = None,
              tools: list | None = None, extra: dict | None = None) -> dict:
        d = {"reply": (f"{note} " if note else "") + reply, "tool_calls": tools or [],
             "task_id": task_id, "model": "heuristic",
             "cards": cards if cards is not None else [o["_id"] for o in opp_ctx[:6]],
             "navigate": nav, "budget": SC.remaining_budget()}
        if extra:
            d.update(extra)
        return d

    # small talk — stay human, no tools
    if re.fullmatch(r"(hi|hey|hello|yo|namaste|good (morning|evening|afternoon))!?", low):
        name = (profile.get("name") or "").split()[0:1]
        hello = f"Hey{name and ' ' + name[0] or ''}! "
        if opp_ctx:
            return _wrap(hello + f"You've got {len(opp_ctx)} jobs on file. Want fresh ones, or should we review your fits?")
        return _wrap(hello + "Tell me what role you're hunting — I'll go find real postings.")
    if any(w in low for w in ("thank", "thanks", "shukriya", "great", "awesome", "nice")):
        return _wrap("Anytime. Ping me when you want fresh jobs, a fit check, or a draft written.")
    if "who are you" in low or "your name" in low:
        return _wrap("I'm Pursuit — I search jobs, check your fit, draft outreach, and watch deadlines. The Jobs tab holds everything I find.")
    if any(w in low for w in ("what can you do", "help", "how does this work", "features")):
        return _wrap("I can: find jobs (LinkedIn + job boards), check your fit, draft cold emails, watch jobs for changes, and walk you around — try 'take me to my approvals'. Just say the word.")

    # navigation — full website knowledge, zero cost
    nav_map = [("approv", "approvals"), ("watch", "monitoring"), ("profile", "setup"),
               ("job", "feed"), ("activit", "activity"), ("timeline", "activity"),
               ("home", "dashboard"), ("chat", "chat")]
    if any(w in low for w in ("take me", "open", "go to", "show me", "switch to", "bring me")):
        for key, tab in nav_map:
            if key in low:
                where = {"approvals": "Approvals", "monitoring": "Watching", "setup": "Profile",
                         "feed": "Jobs", "activity": "Activity", "dashboard": "Home"}.get(tab, tab)
                return _wrap(f"On it — opening {where}.", nav=tab)
        return _wrap("Where to? I can open Jobs, Approvals, Watching, Activity, Profile or Home.")
    if any(w in low for w in ("find", "search", "look for", "hunt", "get me", "show me", "any")) and \
       any(w in low for w in ("job", "intern", "role", "opening", "opportunit", "hiring")):
        try:
            m = AG.linkedin_mission(msg, user_id, max_results=8)
            fresh = m.get("opportunity_ids", [])
            n = len(fresh)
            reply = (f"I searched LinkedIn posts and job pages and saved {n} "
                     f"lead{'s' if n != 1 else ''} — opening them now. Most are early "
                     f"signals, so open one and hit Investigate before trusting it.")
            return _wrap(reply, nav="feed",
                         tools=[{"tool": "search_linkedin_posts", "status": "ok"}],
                         extra={"task_id": m.get("task_id", task_id), "cards": fresh})
        except Exception as e:
            return _wrap(f"Search failed: {e}. Try the Search button on Home.", cards=[])
    if not opp_ctx:
        reply = ("No jobs on file yet. Tell me what role you want — e.g. "
                 "'Find AI internships in India for me' — and I'll search.")
    else:
        tops = sorted([o for o in opp_ctx if o.get("fit") is not None],
                      key=lambda o: o.get("fit") or 0, reverse=True)[:3]
        if tops:
            reply = "On file right now: " + "; ".join(
                f"{o['title']} @ {o['org'] or 'unknown'} ({round((o['fit'] or 0) * 100)}% fit)" for o in tops) + \
                ". Open the Jobs tab for details, or ask me to find more."
        else:
            reply = (f"{len(opp_ctx)} jobs on file, none scored yet. Open one and hit "
                     f"'Check fit', or ask me to find more.")
    return _wrap(reply)


# ---------- agent tool-loop endpoint ----------
class ToolLoopIn(BaseModel):
    goal: str
    user_id: str = "demo-user"
    task_id: str = ""


@app.post("/api/agent/tool-loop")
def tool_loop(body: ToolLoopIn):
    task_id = body.task_id or uuid.uuid4().hex[:12]
    profile = col("profiles").find_one({"user_id": body.user_id}) or {"user_id": body.user_id}
    out = OC.agent_loop(
        system=("You are the Opportunity Intelligence orchestrator. Use tools to research. "
                "Be selective to save search budget. Return a concise summary."),
        user=f"Goal: {body.goal}\nProfile: {json.dumps(profile, default=str)[:2000]}",
        executors=AG.build_executors(task_id, body.user_id),
        context={"user_id": body.user_id})
    AG.trace(task_id, "orchestrator", "tool-loop finished",
             summary=json.dumps(out.get("tool_calls", []))[:500])
    return ok({**out, "task_id": task_id})


# ---------- integration smoke tests (sanitized, never expose keys) ----------
def _smoke_result(name: str, fn) -> dict:
    import time as _t
    t0 = _t.time()
    try:
        r = fn()
        ok_flag = bool((r.get("results") or r.get("result_count") or r.get("status") in ("Success", "Cached")))
        sample = (r.get("results") or [{}])[0]
        keys = sorted(list(r.keys()))
        return {"name": name, "ok": ok_flag or r.get("status") != "Error",
                "status": r.get("status"), "http_status": r.get("http_status", 200),
                "latency_ms": r.get("latency_ms", int((_t.time() - t0) * 1000)),
                "result_count": r.get("result_count", 0),
                "sample_keys": sorted(list(sample.keys()))[:8],
                "sample_title": str(sample.get("title", ""))[:120],
                "cache_hit": r.get("cache_hit", False),
                "error": r.get("error", "")[:300] if r.get("error") else ""}
    except Exception as e:
        return {"name": name, "ok": False, "error": str(e)[:300],
                "latency_ms": int((_t.time() - t0) * 1000)}


@app.get("/api/test/serpapi/google")
def t_google(q: str = "IIT Bombay AI research lab"):
    return ok(_smoke_result("google", lambda: SC.client.searchWeb(q, num=5)))


@app.get("/api/test/serpapi/jobs")
def t_jobs(q: str = "AI research intern India", location: str = "India"):
    return ok(_smoke_result("google_jobs", lambda: SC.client.searchJobs(q, location)))


@app.get("/api/test/serpapi/scholar")
def t_scholar(q: str = "transformer language models"):
    return ok(_smoke_result("google_scholar", lambda: SC.client.searchScholar(q)))


@app.get("/api/test/serpapi/news")
def t_news(q: str = "AI research India"):
    return ok(_smoke_result("google_news", lambda: SC.client.searchNews(q)))


@app.get("/api/test/serpapi/maps")
def t_maps(q: str = "IIT Bombay", location: str = "Mumbai"):
    return ok(_smoke_result("google_maps", lambda: SC.client.searchMaps(q, location)))


@app.get("/api/test/serpapi/linkedin-posts")
def t_li_posts(q: str = '"AI intern" India'):
    def fn():
        r = SC.client.searchLinkedinPosts(q)
        r["linkedin_urls"] = [x.get("link", "") for x in (r.get("results") or [])[:5]
                              if "linkedin.com" in (x.get("link", ""))]
        return r
    return ok(_smoke_result("linkedin_posts", fn))


@app.get("/api/test/serpapi/linkedin-jobs")
def t_li_jobs(q: str = '"AI intern" India'):
    def fn():
        r = SC.client.searchLinkedinJobs(q)
        r["linkedin_urls"] = [x.get("link", "") for x in (r.get("results") or [])[:5]
                              if "linkedin.com" in (x.get("link", ""))]
        return r
    return ok(_smoke_result("linkedin_jobs", fn))


@app.get("/api/test/openrouter")
def t_or():
    return ok(OC.minimal_ping())


@app.get("/api/test/openrouter/tools")
def t_or_tools():
    """Verify the model emits a real tool_call for search_jobs, execute it, feed back."""
    st = get_settings()
    if not st.OPENROUTER_API_KEY:
        return ok({"ok": False, "error": "OPENROUTER_API_KEY not configured"})
    try:
        data = OC.chat(
            [{"role": "system", "content": "You research opportunities. Use tools when asked."},
             {"role": "user", "content": "Find AI internships in India. Call search_jobs with query 'AI intern India'."}],
            tools=[t for t in AGENT_TOOLS if t["function"]["name"] == "search_jobs"],
            tool_choice="auto", max_tokens=400)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        tcs = msg.get("tool_calls") or []
        if not tcs:
            return ok({"ok": False, "error": "model returned no tool_calls",
                       "content": (msg.get("content") or "")[:300], "model": data.get("_model")})
        fn = tcs[0].get("function", {})
        import json as _j
        args = _j.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else {}
        tool_out = SC.client.searchJobs(args.get("query", "AI intern India"), args.get("location", "India"))
        follow = OC.chat(
            [{"role": "system", "content": "Summarize tool output as strict JSON {summary, count}."},
             {"role": "user", "content": f"Tool search_jobs returned {tool_out.get('result_count', 0)} results. Summarize."}],
            response_format={"type": "json_object"}, max_tokens=400)
        fmsg = (follow.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return ok({"ok": True, "model": data.get("_model"),
                   "tool_call": {"name": fn.get("name"), "args": args},
                   "tool_result_count": tool_out.get("result_count", 0),
                   "final": OC.extract_json(fmsg)})
    except Exception as e:
        return ok({"ok": False, "error": str(e)[:400]})


@app.get("/api/test/gmail/status")
def t_gmail(user_id: str = "demo-user"):
    return ok(gmail_mod.status(user_id))


@app.get("/api/test/all")
def t_all():
    st = get_settings()
    out: dict = {"serpapi_configured": bool(st.SERPAPI_API_KEY),
                 "openrouter_configured": bool(st.OPENROUTER_API_KEY)}
    if st.SERPAPI_API_KEY:
        out["google"] = _smoke_result("google", lambda: SC.client.searchWeb("IIT Bombay AI lab", num=3))
        out["jobs"] = _smoke_result("jobs", lambda: SC.client.searchJobs("AI intern India", "India"))
    if st.OPENROUTER_API_KEY:
        out["openrouter"] = OC.minimal_ping()
    out["gmail"] = gmail_mod.status()
    out["db"] = backend_kind()
    return ok(out)


# ---------- demo seed ----------
SEED_PROFILE = {
    "user_id": "demo-user", "name": "Demo Applicant",
    "email": "demo@example.com",
    "education": [{"raw": "B.Tech Computer Science, 2024-2028"}],
    "skills": ["python", "machine learning", "pytorch", "sql", "git", "nlp"],
    "experience": [], "projects": [{"title": "Sentiment classifier with transformers"}],
    "research": ["interested in NLP and LLMs"],
    "links": {}, "location": "India",
    "preferences": {"likes": ["research internships", "remote"], "dislikes": ["unpaid"]},
}

SEED_OPPS = [
    {"title": "AI Research Intern", "organization": "Demo University Lab",
     "location": "Bengaluru, India",
     "description": "Work on NLP and LLMs. Requires Python, PyTorch, machine learning. B.Tech students eligible.",
     "source_url": "https://example.com/ai-research-intern",
     "canonical_url": "example.com/ai-research-intern",
     "source_engine": "seed", "requirements": ["Python", "PyTorch", "B.Tech student"],
     "skills_hint": ["python", "pytorch", "machine learning"], "status": "DISCOVERED"},
    {"title": "Machine Learning Intern (Remote)", "organization": "Demo AI Startup",
     "location": "Remote, India",
     "description": "Build ML pipelines. Requires Python, SQL, Docker. CUDA a plus.",
     "source_url": "https://example.com/ml-intern",
     "canonical_url": "example.com/ml-intern",
     "source_engine": "seed", "requirements": ["Python", "SQL"],
     "skills_hint": ["python", "sql", "docker"], "status": "DISCOVERED"},
]


@app.post("/api/seed")
def seed():
    col("profiles").upsert({"user_id": "demo-user"}, SEED_PROFILE)
    ids = []
    for o in SEED_OPPS:
        ex = col("opportunities").find_one({"canonical_url": o["canonical_url"]})
        if ex:
            ids.append(ex["_id"])
        else:
            ids.append(col("opportunities").insert({**o, "user_id": "demo-user"})["_id"])
    return ok({"profile": "demo-user", "opportunities": ids})


@app.get("/")
def root():
    return {"service": "opportunity-intel", "docs": "/api/docs", "health": "/api/health"}

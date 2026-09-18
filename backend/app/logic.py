"""Deterministic logic: normalize, dedupe, match, skill gaps, change detection, resume parse."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse


def norm_url(u: str) -> str:
    if not u:
        return ""
    try:
        p = urlparse(u.strip().lower().split("?")[0].split("#")[0])
        host = p.netloc.replace("www.", "")
        path = p.path.rstrip("/")
        return f"{host}{path}"
    except Exception:
        return (u or "").strip().lower()


def norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def normalize_job(j: dict) -> dict:
    title = j.get("title", "")
    company = j.get("company_name") or j.get("company") or ""
    loc = j.get("location") or ", ".join(j.get("extensions", [])[:1]) if j.get("extensions") else j.get("location", "")
    link = j.get("link") or j.get("apply_link") or (j.get("apply_options") or [{}])[0].get("link", "") if j.get("apply_options") else j.get("link", "")
    desc = j.get("description") or j.get("snippet") or ""
    return {
        "title": title, "organization": company, "location": loc or "",
        "source_url": link or "", "canonical_url": norm_url(link or ""),
        "description": desc,
        "deadline": j.get("deadline", "") or "",
        "requirements": j.get("requirements") or extract_requirements(desc),
        "skills_hint": extract_skills(desc),
        "raw": {k: j.get(k) for k in ("title", "company_name", "location", "via", "extensions", "job_id", "link")},
    }


def normalize_web(r: dict) -> dict:
    return {
        "title": r.get("title", ""), "organization": "",
        "location": "", "source_url": r.get("link", ""),
        "canonical_url": norm_url(r.get("link", "")),
        "description": r.get("snippet", ""),
        "requirements": [], "skills_hint": extract_skills(r.get("snippet", "")),
        "raw": {"title": r.get("title"), "link": r.get("link")},
    }


SKILL_VOCAB = ["python", "pytorch", "tensorflow", "machine learning", "deep learning",
               "nlp", "computer vision", "cuda", "java", "c++", "sql", "react",
               "javascript", "typescript", "aws", "docker", "kubernetes", "git",
               "data analysis", "statistics", "llm", "transformers", "research",
               "matlab", "r ", "excel", "communication", "leadership"]


def extract_skills(text: str) -> list[str]:
    t = f" {(text or '').lower()} "
    return sorted({s.strip() for s in SKILL_VOCAB if s.strip() and s in t})


def extract_requirements(text: str) -> list[str]:
    reqs: list[str] = []
    for line in (text or "").splitlines():
        l = line.strip(" •-*")
        if re.match(r"(?i)^(require|must|eligib|qualif|you (have|need|are)|bachelor|master|phd|\d+\+?\s*years)", l) and len(l) > 8:
            reqs.append(line.strip()[:220])
    return reqs[:8]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def deduplicate_opportunities(items: list[dict]) -> tuple[list[dict], int]:
    """Dedupe on canonical URL, then fuzzy org+title+location. Returns (unique, removed)."""
    seen_url: set[str] = set()
    unique: list[dict] = []
    removed = 0
    for it in items:
        cu = it.get("canonical_url", "")
        if cu and cu in seen_url:
            removed += 1
            continue
        dup = False
        for u in unique:
            if (norm_text(u.get("organization")) == norm_text(it.get("organization"))
                    and similarity(u.get("title", ""), it.get("title", "")) > 0.82
                    and norm_text(u.get("location")) == norm_text(it.get("location"))):
                dup = True
                break
        if dup:
            removed += 1
            continue
        if cu:
            seen_url.add(cu)
        unique.append(it)
    return unique, removed


def compare_profile(profile: dict, opp: dict) -> dict:
    pskills = {s.lower() for s in (profile.get("skills") or [])}
    reqs: list[str] = opp.get("requirements") or []
    opp_skills = {s.lower() for s in (opp.get("skills_hint") or [])}
    needed = set()
    for r in reqs:
        needed.update(extract_skills(r))
    needed |= opp_skills
    matched = sorted(pskills & needed)
    gaps = sorted(needed - pskilled(pskills, needed))
    # eligibility
    prefs = profile.get("preferences") or {}
    loc_ok: list[str] = []
    ploc = norm_text(profile.get("location", ""))
    oloc = norm_text(opp.get("location", ""))
    loc_match = (not oloc) or (ploc and (ploc in oloc or oloc in ploc)) or "remote" in oloc or "india" in oloc
    eligibility_matched, eligibility_failed, eligibility_uncertain = [], [], []
    (eligibility_matched if loc_match else eligibility_uncertain).append("location")
    edu = profile.get("education") or []
    if edu:
        eligibility_matched.append("education-present")
    else:
        eligibility_uncertain.append("education")
    status = "likely_eligible" if not eligibility_failed and matched else ("needs_review" if gaps else "likely_eligible")
    if eligibility_failed:
        status = "likely_ineligible"
    score = round(len(matched) / max(1, len(needed)) * 0.7 + (0.3 if loc_match else 0.0), 3) if needed else 0.5
    research_alignment = []
    pres = " ".join(str(x) for x in (profile.get("research") or []) + (profile.get("projects") or [])).lower()
    odesc = f"{opp.get('title','')} {opp.get('description','')}".lower()
    for kw in ("ai", "ml", "machine learning", "research", "nlp", "vision", "llm"):
        if kw in pres and kw in odesc:
            research_alignment.append(kw)
    return {
        "eligibility": {"status": status, "matched": eligibility_matched,
                        "uncertain": eligibility_uncertain, "failed": eligibility_failed},
        "skill_match": {"matched": matched, "gaps": gaps},
        "preference_match": [{"preference": k, "match": True} for k in (prefs.keys() if isinstance(prefs, dict) else [])][:6],
        "research_alignment": research_alignment,
        "rationale": f"{len(matched)}/{len(needed) or 0} core skills match; "
                     f"{'location compatible' if loc_match else 'location uncertain'}; "
                     f"research overlap: {', '.join(research_alignment) or 'none stated'}.",
        "score": score,
    }


def pskilled(pskills: set[str], needed: set[str]) -> set[str]:
    out: set[str] = set()
    for n in needed:
        for p in pskills:
            if n == p or n in p or p in n:
                out.add(n)
                break
    return out


IMPORTANCE = {"deadline": "high", "status": "high", "requirements": "medium",
              "location": "medium", "title": "low", "description": "low"}


def compare_opportunity_state(old: dict, new: dict) -> list[dict]:
    """Deterministic change detection (never LLM-only)."""
    changes: list[dict] = []
    for field in ("deadline", "status", "requirements", "location", "title", "description"):
        o, n = old.get(field), new.get(field)
        if o != n:
            changes.append({"field": field, "old_value": o, "new_value": n,
                            "importance": IMPORTANCE.get(field, "low")})
    return changes


def parse_resume_text(text: str) -> dict:
    """Industry-style resume pipeline: segment sections, then extract per section.

    Mirrors how Workday/Sovren/Textkernel parsers work (headers -> blocks ->
    typed fields with date/degree/skill taxonomies), with a review-first
    contract: every field ships a confidence flag, the UI asks for review.
    """
    t = (text or "").replace("\r", "")
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", t)  # de-glue PDF artifacts: "EngineeringSep" -> "Engineering Sep"
    lines = [l.strip() for l in t.splitlines()]
    sections = split_sections(lines)
    contact = extract_contact(sections.get("header", []), t)
    experience = extract_experience(sections.get("experience", []))
    education = extract_education(sections.get("education", []), t)
    skills = extract_taxonomy_skills(sections.get("skills", []), sections)
    summary = " ".join(sections.get("summary", []))[:600]
    conf = {
        "name": "high" if contact["name_src"] == "line1" else "low",
        "email": "high" if contact["emails"] else "low",
        "phone": "high" if contact["phone"] else "low",
        "location": "high" if contact["location"] else "low",
        "experience": "high" if experience else ("low" if sections.get("experience") else "unknown"),
        "education": "high" if education else ("low" if sections.get("education") else "unknown"),
        "skills": "high" if skills else "low",
    }
    return {
        "name": contact["name"], "email": contact["emails"][0] if contact["emails"] else "",
        "phone": contact["phone"], "education": education, "skills": skills,
        "experience": experience, "projects": [], "research": [],
        "summary": summary, "links": contact["links"], "location": contact["location"],
        "raw_text": t[:8000],
        "parse_meta": {"sections_found": sorted(sections.keys()), "confidence": conf},
    }


SECTION_DEFS: list[tuple[str, list[str]]] = [
    ("experience", [r"professional experience", r"work experience", r"work history",
                    r"employment history", r"internships?", r"experience"]),
    ("education", [r"education(al background|al qualifications)?", r"academics?", r"education"]),
    ("skills", [r"(technical )?skills( and expertise| & expertise)?", r"core competencies",
                r"tech(nical)? stack", r"technologies", r"skills"]),
    ("projects", [r"(personal|academic|key) projects?", r"projects?"]),
    ("summary", [r"(professional|executive) summary", r"career objective", r"objective",
                 r"profile", r"about me", r"summary"]),
    ("certifications", [r"certifications?( & licenses)?", r"licenses", r"courses?"]),
]


def _is_header(line: str) -> str:
    s = re.sub(r"[^a-z &]", "", line.strip().lower()).strip()
    if not s or len(line.strip()) > 45:
        return ""
    for key, pats in SECTION_DEFS:
        for p in pats:
            if re.fullmatch(p, s):
                return key
    return ""


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    cur = "header"
    for ln in lines:
        if not ln.strip():
            continue
        h = _is_header(ln)
        if h:
            cur = h
            sections.setdefault(cur, [])
        else:
            sections.setdefault(cur, []).append(ln.strip())
    return sections


PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
URL_RE = re.compile(r"https?://[^\s)]+|(?:www\.)[^\s)]+|linkedin\.com[^\s)]*|github\.com[^\s)]*", re.I)

CITY_MAP = {
    "bengaluru": "Bengaluru, India", "bangalore": "Bengaluru, India",
    "mumbai": "Mumbai, India", "bombay": "Mumbai, India", "delhi": "Delhi NCR, India",
    "new delhi": "Delhi NCR, India", "gurgaon": "Delhi NCR, India", "gurugram": "Delhi NCR, India",
    "noida": "Delhi NCR, India", "hyderabad": "Hyderabad, India", "chennai": "Chennai, India",
    "pune": "Pune, India", "kolkata": "Kolkata, India", "ahmedabad": "Ahmedabad, India",
    "kochi": "Kochi, India", "jaipur": "Jaipur, India", "remote": "Remote",
    "new york": "New York, USA", "san francisco": "San Francisco, USA", "london": "London, UK",
    "singapore": "Singapore", "berlin": "Berlin, Germany", "toronto": "Toronto, Canada",
}


def extract_contact(header_lines: list[str], full_text: str) -> dict:
    emails = EMAIL_RE.findall(full_text or "")
    phones = [p.strip(" ()-.") for p in PHONE_RE.findall(full_text or "")]
    phone = next((p for p in phones if sum(c.isdigit() for c in p) >= 10), "")
    links: dict[str, str] = {}
    for m in URL_RE.findall(full_text or ""):
        u = m if m.startswith("http") else f"https://{m}"
        lu = u.lower()
        if "linkedin" in lu and "linkedin" not in links:
            links["linkedin"] = u
        elif "github" in lu and "github" not in links:
            links["github"] = u
        elif "website" not in links and not any(k in lu for k in ("linkedin", "github")):
            if re.search(r"\.(com|io|dev|me|in|org)(/|$)", lu):
                links["website"] = u
    # location: contact block first, then whole doc
    location, loc_src = "", ""
    for scope in ("\n".join(header_lines[:8]), full_text or ""):
        low = scope.lower()
        for city, label in CITY_MAP.items():
            if re.search(rf"\b{re.escape(city)}\b", low):
                location, loc_src = label, scope
                break
        if location:
            break
    # name: "Name:" hint > first clean title-case line (never email/phone/url/header)
    name, name_src = "", "fallback"
    m = re.search(r"(?im)^\s*name\s*:\s*(.+)$", full_text or "")
    if m and 2 <= len(m.group(1).split()) <= 5:
        name, name_src = m.group(1).strip()[:80], "hint"
    if not name:
        for ln in header_lines[:6]:
            s = ln.strip()
            if not s or "@" in s or URL_RE.search(s) or _is_header(s):
                continue
            if sum(c.isdigit() for c in s) > 3 or len(s) > 60:
                continue
            words = s.split()
            if 2 <= len(words) <= 4 and sum(1 for w in words if w[:1].isupper()) >= 2:
                name, name_src = s[:80], "line1"
                break
    return {"name": name, "name_src": name_src, "emails": emails, "phone": phone,
            "links": links, "location": location, "loc_src": loc_src}


MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
DATE_ATOM = rf"(?:{MONTH}\s+\d{{4}}|\d{{1,2}}[/-]\d{{2,4}}|(?:19|20)\d{{2}})"
RANGE_RE = re.compile(rf"(?P<s>{DATE_ATOM})\s*(?:–|—|-|–|to|till|through|until)\s*(?P<e>{DATE_ATOM}|present|current|now|till\s+date|ongoing)", re.I)


def _clean_bullet(ln: str) -> str:
    return re.sub(r"^[\s•\-\*▪▸>]+", "", ln).strip()


def extract_experience(lines: list[str]) -> list[dict]:
    """Split roles on date-range anchors (Sovren-style); attach bullets to roles."""
    if not lines:
        return []
    bounds = [i for i, ln in enumerate(lines) if RANGE_RE.search(ln)]
    chunks: list[list[str]] = []
    def _looks_header(s: str) -> bool:
        s = _clean_bullet(s)
        return bool(s) and len(s) < 120 and (" | " in s or " @ " in s or bool(re.search(r"\s+at\s+[A-Z]", s)))
    if not bounds:
        # fall back: split on title-like lines ("Title | Company" / "Title at Company")
        for ln in lines:
            s = _clean_bullet(ln)
            if _looks_header(s):
                chunks.append([ln])
            elif chunks:
                chunks[-1].append(ln)
            else:
                chunks.append([ln])
    else:
        # a date line belongs to the role it follows: only start a new chunk
        # when the current one already consumed a date range
        cur: list[str] = []
        for ln in lines:
            cur_dated = any(RANGE_RE.search(l) for l in cur)
            if cur and cur_dated and (RANGE_RE.search(ln) or _looks_header(ln)):
                chunks.append(cur)
                cur = []
            cur.append(ln)
        if cur:
            chunks.append(cur)
    roles = []
    for ch in chunks:
        ch = [l for l in ch if l.strip()]
        if not ch:
            continue
        header = [_clean_bullet(l) for l in ch if not l.strip().startswith(("•", "-", "*", "▪", "▸"))][:2]
        rng = next((RANGE_RE.search(l) for l in ch if RANGE_RE.search(l)), None)
        years = rng.group(0).strip() if rng else ""
        head = header[0] if header else ""
        head = RANGE_RE.sub("", head).strip(" |-–—")
        title, company = head, ""
        if " | " in head:
            title, company = [p.strip() for p in head.split("|", 1)]
        elif " @ " in head:
            title, company = [p.strip() for p in head.split("@", 1)]
        elif re.search(r"\s+at\s+", head, re.I) and len(head) < 140:
            title, company = [p.strip() for p in re.split(r"\s+at\s+", head, maxsplit=1, flags=re.I)]
        elif len(header) > 1 and len(header[1]) < 80 and not RANGE_RE.search(header[1]):
            company = header[1]
        company = company.split(",")[0].strip()[:80]
        bullets = [_clean_bullet(l) for l in ch if l.strip()[:1] in "•-*▪▸>" or (len(l) > 40 and l not in header)]
        summary = " ".join(bullets)[:500]
        if title or company:
            roles.append({"title": title[:100], "company": company, "years": years, "summary": summary})
    return roles[:8]


DEGREE_MAP = [
    (r"\bph\.?\s?d\b|\bdoctorate\b", "PhD"),
    (r"\bm\.?\s?tech\b|\bmaster of technology\b", "M.Tech"),
    (r"\bm\.?\s?s\b|\bmaster of science\b|\bmsc\b", "M.S."),
    (r"\bmba\b|\bmaster of business", "MBA"),
    (r"\bmasters?\b|\bm\.?\s?e\b", "Master's"),
    (r"\bb\.?\s?tech\b|\bbachelor of technology\b", "B.Tech"),
    (r"\bb\.?\s?e\b|\bbachelor of engineering\b|\bbe\b", "B.E."),
    (r"\bb\.?\s?sc\b|\bbachelor of science\b", "B.Sc"),
    (r"\bbachelor'?s\b|\bb\.?\s?a\b", "Bachelor's"),
    (r"\bdiploma\b", "Diploma"),
    (r"\b(xii|12th|higher secondary|hsc)\b", "XII"),
    (r"\b(x|10th|sslc|matric)", "X"),
]
INST_RE = re.compile(r"(university|institute|college|school|iit|nit|iiit|bits|vit|polytechnic)", re.I)


def extract_education(lines: list[str], full_text: str) -> list[dict]:
    src = lines or [l for l in (full_text or "").splitlines()
                    if INST_RE.search(l) or any(re.search(p, l, re.I) for p, _ in DEGREE_MAP)][:12]
    entries, cur = [], {"school": "", "degree": "", "field": "", "years": ""}
    def flush():
        if cur["school"] or cur["degree"]:
            entries.append({**cur})
        cur.update(school="", degree="", field="", years="")
    for ln in src:
        s = _clean_bullet(ln)
        if not s:
            continue
        deg = next((std for pat, std in DEGREE_MAP if re.search(pat, s, re.I)), "")
        yrs = ", ".join(m.group(0) for m in
                        list(RANGE_RE.finditer(s))[:1] or re.finditer(r"(?:19|20)\d{2}", s))[:40]
        if INST_RE.search(s) and (cur["school"] or cur["degree"]):
            flush()
        if INST_RE.search(s) and not cur["school"]:
            segs = [p.strip() for p in re.split(r",|\|| - | – |;", s) if p.strip()]
            inst = next((p for p in segs if INST_RE.search(p)), segs[-1] if segs else s)
            cur["school"] = RANGE_RE.sub("", inst).strip()[:100]
        if deg and not cur["degree"]:
            cur["degree"] = deg
            mf = re.search(rf"{deg.rsplit('.', 1)[0] if '.' in deg else deg}\s+(?:in|of)\s+([A-Za-z &+]+)", s, re.I)
            if mf:
                cur["field"] = mf.group(1).strip()[:60]
        if yrs and not cur["years"]:
            cur["years"] = yrs
        if not INST_RE.search(s) and not deg and not cur["school"] and len(s) < 90:
            cur["school"] = s[:100]
    flush()
    return entries[:5]


SKILL_TAXONOMY: dict[str, list[str]] = {
    "Python": ["python", "py"], "JavaScript": ["javascript", "js", "es6"],
    "TypeScript": ["typescript", "ts"], "Java": ["java"], "C++": ["c++", "cpp"],
    "C": [], "Go": ["go", "golang"], "Rust": ["rust"], "SQL": ["sql", "mysql", "postgres", "postgresql"],
    "React": ["react", "react.js", "reactjs"], "Angular": ["angular"], "Vue": ["vue", "vue.js"],
    "Node.js": ["node", "node.js", "nodejs"], "PyTorch": ["pytorch", "torch"],
    "TensorFlow": ["tensorflow", "tf"], "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"], "NLP": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision", "cv", "opencv"], "LLM": ["llm", "large language models", "genai", "generative ai"],
    "Transformers": ["transformers", "hugging face", "bert", "gpt"], "CUDA": ["cuda"],
    "Docker": ["docker"], "Kubernetes": ["kubernetes", "k8s"], "AWS": ["aws", "amazon web services"],
    "Git": ["git", "github", "gitlab"], "Linux": ["linux", "unix", "bash"],
    "Data Analysis": ["data analysis", "pandas", "numpy"], "Statistics": ["statistics", "a/b testing"],
    "Excel": ["excel"], "MATLAB": ["matlab"], "R": [r"\br\b"],
    "Communication": ["communication"], "Leadership": ["leadership", "led a team", "mentored"],
    "Research": ["research"], "Figma": ["figma"], "Django": ["django"], "Flask": ["flask"],
}
_ALIAS2CANON = {a.lower(): c for c, als in SKILL_TAXONOMY.items() for a in ([c] + als)}
_SPLIT_RE = re.compile(r"[,;•|\u2022\n/]+")


def extract_taxonomy_skills(skill_lines: list[str], sections: dict) -> list[str]:
    found: list[str] = []

    def scan(blob: str):
        low = f" {blob.lower()} "
        for alias, canon in _ALIAS2CANON.items():
            if not alias.strip() or len(alias.strip()) < 2:
                continue
            pat = alias if alias == r"\br\b" else re.escape(alias)
            if re.search(rf"(?<![a-z0-9+#]){pat}(?![a-z0-9+#])", low) and canon not in found:
                found.append(canon)

    # 1) dedicated skills section: split items, keep readable ones
    if skill_lines:
        for tok in _SPLIT_RE.split(" ".join(skill_lines)):
            t = tok.strip(" -–—:\t")
            if not (2 <= len(t) <= 30) or re.fullmatch(r"[\d\W]+", t):
                continue
            key = t.lower()
            if key in _ALIAS2CANON:
                canon = _ALIAS2CANON[key]
            elif len(t) >= 3 and len(t.split()) <= 3 and not re.fullmatch(r"[A-Z]{2}", t):
                canon = t  # custom skill, but never 2-letter acronym junk
            else:
                continue
            if canon and canon not in found:
                found.append(canon)
    # 2) whole-doc taxonomy sweep catches skills proven in bullets (Workday-style)
    scan(" ".join(sum(sections.values(), [])))
    return found[:40]


def why_shown(match: dict) -> list[str]:
    out = []
    m = match.get("skill_match", {}).get("matched", [])
    if m:
        out.append(f"{len(m)} core skills match ({', '.join(m[:4])})")
    if match.get("research_alignment"):
        out.append(f"research aligns: {', '.join(match['research_alignment'][:3])}")
    if "location" in match.get("eligibility", {}).get("matched", []):
        out.append("location compatible")
    if match.get("eligibility", {}).get("status") == "likely_eligible":
        out.append("eligibility likely met")
    return out or ["broad goal match — run Match for details"]

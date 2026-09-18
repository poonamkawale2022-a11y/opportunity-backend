"""LinkedIn signal discovery + link-quality layer (no LinkedIn API assumed).

All LinkedIn intake flows through SerpApi Google `site:` search. Posts are
treated as early signals, never canonical facts: cross-check before trust,
merge multi-source hits into ONE canonical opportunity, surface freshness
honestly, and never invent application URLs.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

# Domains that list hundreds of roles per page: deprioritize, never feature.
AGGREGATOR_DOMAINS = {
    "internshala.com", "indeed.com", "naukri.com", "glassdoor.com",
    "simplyhired.com", "ziprecruiter.com", "monster.com", "monsterindia.com",
    "timesjobs.com", "freshersworld.com", "letsintern.com", "twenty19.com",
    "ycombinator.com", "wellfound.com", "angel.co", "cutshort.io",
    "linkedin.com",  # listing/search pages; /posts/* and /jobs/view/* handled separately
}
LISTING_PATH_RES = [
    re.compile(r"/jobs/(search|collections|saved)", re.I),
    re.compile(r"/(jobs|internships?)([-_/]|$)", re.I),
    re.compile(r"/category/", re.I),
    re.compile(r"/blog/", re.I),
]
# Signals that a URL IS one specific role / application destination.
DIRECT_JOB_RES = [
    re.compile(r"linkedin\.com/jobs/view/", re.I),
    re.compile(r"/careers?/[^/]+/.+", re.I),
    re.compile(r"/jobs?/[^/]{3,}", re.I),
    re.compile(r"/apply", re.I),
    re.compile(r"(greenhouse\.io|lever\.co|ashbyhq\.com|workable\.com|breezy\.hr|workday|icims|taleo|myworkdayjobs)\.com", re.I),
]
OFFICIAL_RES = [
    re.compile(r"/careers?/", re.I), re.compile(r"/apply", re.I),
    re.compile(r"(greenhouse\.io|lever\.co|ashbyhq\.com|workable\.com|breezy\.hr|myworkdayjobs)\.com", re.I),
]
JOB_BOARD_DOMAINS = {
    "indeed.com", "naukri.com", "glassdoor.com", "simplyhired.com",
    "ziprecruiter.com", "monster.com", "monsterindia.com", "timesjobs.com",
    "freshersworld.com", "internshala.com", "cutshort.io", "wellfound.com",
}


def _host(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def classify_link(url: str) -> str:
    """OFFICIAL_APPLICATION | JOB_BOARD | LINKEDIN_JOB_PAGE | LINKEDIN_POST | UNKNOWN."""
    u = url or ""
    h = _host(u)
    if "linkedin.com/posts" in u or "/posts/" in u and "linkedin" in h:
        return "LINKEDIN_POST"
    if "linkedin.com/jobs/view" in u:
        return "LINKEDIN_JOB_PAGE"
    if any(p.search(u) for p in OFFICIAL_RES):
        return "OFFICIAL_APPLICATION"
    if h in JOB_BOARD_DOMAINS:
        return "JOB_BOARD"
    return "UNKNOWN"


def is_aggregator_page(url: str, title: str = "") -> bool:
    h = _host(url)
    if h in AGGREGATOR_DOMAINS and classify_link(url) not in ("LINKEDIN_POST", "LINKEDIN_JOB_PAGE"):
        # aggregator listing pages; a direct /jobs/view or /posts link is NOT one
        if any(p.search(url or "") for p in LISTING_PATH_RES):
            return True
        if h in AGGREGATOR_DOMAINS and not any(p.search(url or "") for p in DIRECT_JOB_RES):
            return True
    t = (title or "").lower()
    if re.search(r"\b\d{2,}\+?\s+(jobs|internships|openings|roles)\b", t):
        return True
    return False


def is_direct_opportunity(url: str, title: str = "") -> bool:
    if not url:
        return False
    if is_aggregator_page(url, title):
        return False
    return bool(any(p.search(url) for p in DIRECT_JOB_RES) or classify_link(url) in
                ("OFFICIAL_APPLICATION", "LINKEDIN_JOB_PAGE", "LINKEDIN_POST"))


URL_RE_ALL = re.compile(r"https?://[^\s)\"']+")


def extract_application_url(text: str, source_url: str = "") -> dict:
    """Pick the real application URL from visible text. Never invents one."""
    cands: list[str] = []
    for m in URL_RE_ALL.findall(text or ""):
        u = m.rstrip(".,;!)")
        if u and u != (source_url or "").rstrip("/"):
            cands.append(u)
    if source_url and classify_link(source_url) in ("OFFICIAL_APPLICATION", "LINKEDIN_JOB_PAGE"):
        cands.append(source_url)
    scored = []
    for u in dict.fromkeys(cands):  # dedupe, keep order
        cls = classify_link(u)
        score = {"OFFICIAL_APPLICATION": 3, "LINKEDIN_JOB_PAGE": 2,
                 "JOB_BOARD": 1, "LINKEDIN_POST": 0, "UNKNOWN": 0}[cls]
        scored.append((score, u, cls))
    scored.sort(reverse=True)
    if scored and scored[0][0] >= 1:
        return {"url": scored[0][1], "classification": scored[0][2], "found": True}
    if scored:
        return {"url": scored[0][1], "classification": scored[0][2],
                "found": False, "note": "Only a social/post link is visible — official application not found."}
    return {"found": False, "url": "", "classification": "UNKNOWN",
            "note": "Application link not found."}


def freshness(date_str: str = "", now: datetime | None = None) -> dict:
    """NEW / RECENT / AGING / STALE / UNKNOWN. Never invents timestamps."""
    now = now or datetime.now(timezone.utc)
    s = (date_str or "").strip()
    if not s:
        return {"label": "UNKNOWN", "detail": "DATE UNKNOWN"}
    low = s.lower()
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)s?\s*ago", low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = n / 24 if unit == "hour" else n / 1440 if unit == "minute" else n if unit == "day" else n * 7 if unit == "week" else n * 30
        detail = f"{n}{'m' if unit=='minute' else 'h' if unit=='hour' else 'd' if unit=='day' else 'w'} ago"
        label = "NEW" if days < 1 else "RECENT" if days <= 3 else "AGING" if days <= 14 else "STALE"
        return {"label": label, "detail": detail}
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            dt = datetime.strptime(s.split(",")[0].strip()[:20], fmt).replace(tzinfo=timezone.utc)
            days = (now - dt).days
            label = "NEW" if days < 1 else "RECENT" if days <= 3 else "AGING" if days <= 14 else "STALE"
            return {"label": label, "detail": s[:40]}
        except Exception:
            continue
    return {"label": "UNKNOWN", "detail": "DATE UNKNOWN"}


HIRING_CUES = ["hiring", "we're hiring", "we are hiring", "join our team", "join us",
               "opening", "openings", "apply now", "looking for", "seeking"]
POSTER_CUES = {
    "recruiter": ["recruiter", "talent", "hiring manager", "hr "],
    "founder": ["founder", "co-founder", "ceo", "cto"],
    "researcher": ["research", "professor", "phd", "lab ", "scientist"],
    "lab": [" lab", "laboratory"],
}


def classify_linkedin_signal(title: str = "", snippet: str = "") -> dict:
    blob = f"{title or ''} {snippet or ''}".lower()
    hiring = any(c in blob for c in HIRING_CUES)
    poster = next((k for k, cues in POSTER_CUES.items() if any(c in blob for c in cues)), "unknown")
    kind = "hiring_announcement" if hiring else "mention"
    return {"kind": kind, "poster": poster, "is_hiring": hiring,
            "early": hiring and poster in ("recruiter", "founder", "researcher", "lab", "unknown")}


def extract_linkedin_opportunity(result: dict, kind: str = "posts") -> dict:
    """Normalize one SerpApi Google result into a LinkedIn candidate.

    Only uses what Google actually exposes. Missing fields stay empty —
    the UI renders them as partial, never as facts.
    """
    url = result.get("link", "")
    title = result.get("title", "")
    snippet = result.get("snippet", "") or result.get("about_this_result", "") or ""
    date = result.get("date", "") or result.get("date_utc", "") or ""
    author = result.get("author", "") or ""
    org = ""
    m = re.search(r"(?:at|@|—|-|·|\|)\s*([A-Z][\w&., ]{2,60})$", title.strip())
    if m:
        org = m.group(1).strip()
    sig = classify_linkedin_signal(title, snippet)
    app = extract_application_url(f"{title} {snippet}", url)
    fresh = freshness(date)
    partial = not (org and app.get("found"))
    return {
        "title": title or "LinkedIn opportunity",
        "organization": org,
        "location": "",
        "description": snippet[:800],
        "source_url": url,
        "canonical_url": url.split("?")[0].lower().rstrip("/") if url else "",
        "source_engine": "google",
        "source_type": "linkedin_post" if kind == "posts" else "linkedin_job",
        "author": author,
        "posted_date": date,
        "freshness": fresh,
        "signal": sig,
        "application": app,
        "requirements": [],
        "skills_hint": [],
        "data_completeness": "partial" if partial else "full",
        "is_early_signal": sig["early"],
    }


def build_linkedin_queries(profile: dict, plan: dict, kind: str = "posts",
                           limit: int = 2) -> list[str]:
    """Dynamic site: queries from skills + role + location. Never hardcoded."""
    skills = " ".join((profile.get("skills") or [])[:2])
    otypes = " ".join((plan.get("opportunity_types") or ["internship"])[:2])
    domains = " ".join((plan.get("domains") or [])[:2])
    loc = (plan.get("locations") or [""])[0]
    role = f"{domains} {otypes}".strip() or "intern"
    base = f"{skills} {role}".strip()
    if kind == "posts":
        qs = [f'site:linkedin.com/posts "hiring" "{base}" {loc}'.strip(),
              f'site:linkedin.com/posts "{role}" {loc}'.strip()]
    else:
        qs = [f'site:linkedin.com/jobs/view "{base}" {loc}'.strip(),
              f'site:linkedin.com/jobs/view "{role}"'.strip()]
    return [q for q in qs if q][:max(1, limit)]


def find_canonical(existing: list[dict], cand: dict) -> dict | None:
    """ONE canonical opportunity across LinkedIn/Jobs/company sources."""
    from .logic import norm_text, similarity  # local import: same module, safe
    if cand.get("canonical_url"):
        for o in existing:
            if o.get("canonical_url") and o["canonical_url"] == cand["canonical_url"]:
                return o
    for o in existing:
        if (norm_text(o.get("organization")) == norm_text(cand.get("organization"))
                and cand.get("organization")
                and similarity(o.get("title", ""), cand.get("title", "")) > 0.78):
            return o
    return None

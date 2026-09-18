"""Unit tests: dedupe, matching, gaps, state compare, normalization. No network."""
from app import logic as L


def test_norm_url():
    assert L.norm_url("https://WWW.Example.com/a/?x=1#y") == "example.com/a"


def test_dedupe_url_and_fuzzy():
    a = {"title": "AI Intern", "organization": "Acme", "location": "India",
         "canonical_url": "acme.com/a", "description": ""}
    b = dict(a)
    c = {"title": "AI Intern", "organization": "Acme", "location": "India",
         "canonical_url": "other.com/x", "description": ""}
    u, removed = L.deduplicate_opportunities([a, b, c])
    assert len(u) == 1 and removed == 2


def test_normalize_job_requires_fields():
    n = L.normalize_job({"title": "T", "company_name": "C", "location": "L",
                         "description": "Needs Python and SQL"})
    assert n["title"] == "T" and "python" in n["skills_hint"]


def test_match_never_fabricates_unknown():
    m = L.compare_profile({"skills": [], "preferences": {}, "location": "",
                           "education": [], "research": [], "projects": []},
                          {"requirements": ["PhD required"], "skills_hint": ["cuda"],
                           "location": "", "title": "", "description": ""})
    assert m["eligibility"]["status"] in ("likely_eligible", "needs_review")
    assert "cuda" in m["skill_match"]["gaps"]
    assert "education" in m["eligibility"]["uncertain"]


def test_skill_gaps():
    m = L.compare_profile({"skills": ["Python", "SQL"], "preferences": {},
                           "location": "India", "education": [{"raw": "B.Tech"}],
                           "research": [], "projects": []},
                          {"requirements": [], "skills_hint": ["python", "cuda"],
                           "location": "India", "title": "ML", "description": ""})
    assert "python" in m["skill_match"]["matched"]
    assert "cuda" in m["skill_match"]["gaps"]


def test_change_detection_deterministic():
    old = {"deadline": "2026-10-15", "status": "open", "location": "X",
           "title": "T", "requirements": ["a"], "description": "d"}
    new = dict(old, deadline="2026-10-25")
    ch = L.compare_opportunity_state(old, new)
    assert len(ch) == 1 and ch[0]["field"] == "deadline"
    assert ch[0]["importance"] == "high"
    assert L.compare_opportunity_state(old, dict(old)) == []


def test_resume_parse():
    p = L.parse_resume_text("Jane Doe\nB.Tech CSE, ABC University\nPython PyTorch SQL\nme@x.com")
    assert p["email"] == "me@x.com"
    assert "Python" in p["skills"] or "python" in [s.lower() for s in p["skills"]]
    assert p["education"]


def test_section_segmentation():
    t = "John Smith\njohn@x.com\nEXPERIENCE\nML Intern | Acme, Bengaluru\nJan 2024 - Jun 2024\n- Built things\nEDUCATION\nB.Tech, IIT Bombay, 2022 - 2026\nSKILLS\nPython, SQL"
    p = L.parse_resume_text(t)
    assert "experience" in p["parse_meta"]["sections_found"]
    assert p["experience"] and p["experience"][0]["title"] == "ML Intern"
    assert p["experience"][0]["company"] == "Acme"
    assert "2024" in p["experience"][0]["years"]
    assert p["education"] and p["education"][0]["degree"] == "B.Tech"
    assert "IIT Bombay" in p["education"][0]["school"]


def test_skill_aliases_and_phone():
    p = L.parse_resume_text("A B\nSKILLS\nJS, k8s, golang\n+91 98765 43210")
    assert "JavaScript" in p["skills"]
    assert "Kubernetes" in p["skills"]
    assert "Go" in p["skills"]
    assert p["phone"] == "+91 98765 43210"


def test_present_date_role():
    p = L.parse_resume_text("N\nEXPERIENCE\nSDE at Foo | Mar 2023 - Present\n- x")
    assert p["experience"] and "Present" in p["experience"][0]["years"]
    assert p["experience"][0]["company"] == "Foo"


def test_link_classification():
    from app import linkedin as LI

    assert LI.classify_link("https://www.linkedin.com/posts/abc_123") == "LINKEDIN_POST"
    assert LI.classify_link("https://www.linkedin.com/jobs/view/123") == "LINKEDIN_JOB_PAGE"
    assert LI.classify_link("https://careers.acme.com/apply/123") == "OFFICIAL_APPLICATION"
    assert LI.classify_link("https://www.indeed.com/viewjob?jk=1") == "JOB_BOARD"
    assert LI.classify_link("https://example.com/x") == "UNKNOWN"


def test_aggregator_filter_prefers_direct_links():
    from app import linkedin as LI

    assert LI.is_aggregator_page("https://www.internshala.com/internships artificial", "255 Artificial Intelligence (AI) Internships")
    assert LI.is_aggregator_page("https://www.linkedin.com/jobs/search/?x=1", "Jobs")
    assert not LI.is_aggregator_page("https://www.linkedin.com/jobs/view/123", "AI Intern")
    assert not LI.is_aggregator_page("https://careers.acme.com/jobs/ai-intern-123", "AI Intern")
    assert LI.is_direct_opportunity("https://careers.acme.com/jobs/ai-intern-123", "AI Intern")
    assert not LI.is_direct_opportunity("https://www.internshala.com/internships/", "255 Internships")


def test_application_url_never_invented():
    from app import linkedin as LI

    r = LI.extract_application_url("Apply here https://careers.acme.com/apply/9 and https://indeed.com/x",
                                   "https://www.linkedin.com/posts/1")
    assert r["found"] and r["url"] == "https://careers.acme.com/apply/9"
    r2 = LI.extract_application_url("Great post, no link", "https://www.linkedin.com/posts/1")
    assert r2["found"] is False and "not found" in r2["note"]


def test_freshness_honest():
    from app import linkedin as LI

    assert LI.freshness("2 hours ago")["label"] == "NEW"
    assert LI.freshness("5 days ago")["label"] == "AGING"
    assert LI.freshness("") == {"label": "UNKNOWN", "detail": "DATE UNKNOWN"}
    assert LI.freshness("nonsense")["label"] == "UNKNOWN"


def test_linkedin_extract_partial_and_queries():
    from app import linkedin as LI

    o = LI.extract_linkedin_opportunity({"title": "We're hiring AI interns", "link": "https://www.linkedin.com/posts/1",
                                         "snippet": "Join XYZ Labs, apply now", "date": "3 hours ago"}, "posts")
    assert o["source_type"] == "linkedin_post"
    assert o["data_completeness"] == "partial"  # org unknown, never invented
    assert o["freshness"]["label"] == "NEW"
    assert o["is_early_signal"] is True
    qs = LI.build_linkedin_queries({"skills": ["Python"]},
                                   {"opportunity_types": ["internship"], "locations": ["India"]}, "posts")
    assert qs and all("site:linkedin.com/posts" in q for q in qs) and any("India" in q for q in qs)


def test_canonical_merge():
    from app import linkedin as LI

    a = {"_id": "1", "title": "AI Research Intern", "organization": "XYZ Labs",
         "canonical_url": "xyz.com/jobs/1"}
    b = {"title": "AI Research Intern", "organization": "XYZ Labs", "canonical_url": "other.com/x"}
    assert LI.find_canonical([a], b) is a
    c = {"title": "Cook", "organization": "Elsewhere", "canonical_url": "z.com"}
    assert LI.find_canonical([a], c) is None

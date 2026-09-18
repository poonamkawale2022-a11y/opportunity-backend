"""Pydantic schemas, lifecycle state machine, typed tool definitions."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class OppStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    EARLY_SIGNAL = "EARLY_SIGNAL"
    INVESTIGATING = "INVESTIGATING"
    VERIFIED = "VERIFIED"
    MATCHED = "MATCHED"
    SHORTLISTED = "SHORTLISTED"
    PREPARING = "PREPARING"
    APPLICATION_READY = "APPLICATION_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPLIED = "APPLIED"
    OUTREACH_READY = "OUTREACH_READY"
    OUTREACH_SENT = "OUTREACH_SENT"
    WAITING = "WAITING"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    MONITORING = "MONITORING"
    CHANGED = "CHANGED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    OFFER = "OFFER"


ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "DISCOVERED": ["INVESTIGATING", "EARLY_SIGNAL", "CLOSED"],
    "EARLY_SIGNAL": ["INVESTIGATING", "VERIFIED", "CLOSED"],
    "INVESTIGATING": ["VERIFIED", "DISCOVERED", "CLOSED"],
    "VERIFIED": ["MATCHED", "INVESTIGATING", "CLOSED"],
    "MATCHED": ["SHORTLISTED", "VERIFIED"],
    "SHORTLISTED": ["PREPARING", "MATCHED"],
    "PREPARING": ["APPLICATION_READY", "OUTREACH_READY", "SHORTLISTED"],
    "APPLICATION_READY": ["AWAITING_APPROVAL", "APPLIED", "PREPARING"],
    "AWAITING_APPROVAL": ["APPLIED", "OUTREACH_SENT", "PREPARING", "APPLICATION_READY"],
    "APPLIED": ["WAITING", "OFFER", "REJECTED"],
    "OUTREACH_READY": ["AWAITING_APPROVAL", "PREPARING"],
    "OUTREACH_SENT": ["WAITING", "FOLLOW_UP_DUE"],
    "WAITING": ["FOLLOW_UP_DUE", "OFFER", "REJECTED"],
    "FOLLOW_UP_DUE": ["AWAITING_APPROVAL", "OUTREACH_SENT", "WAITING"],
    "MONITORING": ["CHANGED", "CLOSED"],
    "CHANGED": ["INVESTIGATING", "VERIFIED", "MONITORING"],
    "CLOSED": [],
    "REJECTED": [],
    "OFFER": [],
}


def can_transition(frm: str, to: str) -> bool:
    return to in ALLOWED_TRANSITIONS.get(frm, [])


def set_status(opp: dict, to: str) -> dict:
    frm = opp.get("status", "DISCOVERED")
    if frm != to and not can_transition(frm, to):
        # allow forward jumps used by orchestrator: DISCOVERED->VERIFIED etc.
        pass  # state machine is advisory; timeline records every change
    opp["status"] = to
    opp.setdefault("status_history", []).append({"from": frm, "to": to})
    return opp


ConfidenceState = Literal["VERIFIED", "PARTIALLY_VERIFIED", "CONFLICTING", "UNVERIFIED", "UNKNOWN"]


class Evidence(BaseModel):
    claim: str = ""
    sourceType: str = ""
    sourceTitle: str = ""
    sourceUrl: str = ""
    evidenceText: str = ""
    confidenceState: str = "UNVERIFIED"


class PlannerOutput(BaseModel):
    opportunity_types: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    search_verticals: list[str] = Field(default_factory=list)
    investigation_requirements: list[str] = Field(default_factory=list)
    monitoring_candidate: bool = True


class MatchOutput(BaseModel):
    eligibility: dict = Field(default_factory=dict)
    skill_match: dict = Field(default_factory=dict)
    preference_match: list = Field(default_factory=list)
    research_alignment: list = Field(default_factory=list)
    rationale: str = ""
    score: float = 0.0


class ProfileIn(BaseModel):
    user_id: str = "demo-user"
    name: str = ""
    email: str = ""
    education: list = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list = Field(default_factory=list)
    projects: list = Field(default_factory=list)
    research: list = Field(default_factory=list)
    links: dict = Field(default_factory=dict)
    location: str = ""
    preferences: dict = Field(default_factory=dict)
    raw_text: str = ""


class DiscoverIn(BaseModel):
    user_goal: str
    user_id: str = "demo-user"
    max_results: int = 20
    force_fresh: bool = False


# ---- OpenRouter tool definitions (real tool calling) ----
AGENT_TOOLS: list[dict] = [
    {"type": "function", "function": {"name": "search_web", "description": "General web search via SerpApi Google engine (company pages, opportunity pages).", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "location": {"type": "string"}, "num": {"type": "integer"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_jobs", "description": "Jobs/internships discovery via SerpApi Google Jobs engine.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "location": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_scholar", "description": "Research/lab/researcher discovery via SerpApi Google Scholar.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_news", "description": "Current developments via SerpApi Google News.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_maps", "description": "Organization/location context via SerpApi Google Maps.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "location": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_linkedin_posts", "description": "Public LinkedIn hiring posts via SerpApi Google Search site: query. Snippets only, never private data.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "location": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_linkedin_jobs", "description": "Public LinkedIn job pages via SerpApi Google Search site: query.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "location": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "extract_application_url", "description": "Find the real application URL for an opportunity (official > board > unknown). Never invents links.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "verify_linkedin_opportunity", "description": "Cross-check a LinkedIn-discovered opportunity against jobs/company sources.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "get_opportunity", "description": "Fetch a stored opportunity by id.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "investigate_opportunity", "description": "Run second-hop investigation on an opportunity.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "verify_claim", "description": "Cross-check a claim (deadline, eligibility, location...) against evidence.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}, "claim": {"type": "string"}, "field": {"type": "string"}}, "required": ["opportunity_id", "claim"]}}},
    {"type": "function", "function": {"name": "match_profile", "description": "Match stored user profile against an opportunity.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "generate_application", "description": "Prepare application materials for an opportunity.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "find_relevant_contact", "description": "Find a relevant public professional contact for an opportunity.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "generate_outreach", "description": "Generate a personalized outreach draft.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}, "contact_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "request_human_approval", "description": "Pause and request human approval before an irreversible action.", "parameters": {"type": "object", "properties": {"action_type": {"type": "string"}, "summary": {"type": "string"}, "payload": {"type": "object"}}, "required": ["action_type", "summary"]}}},
    {"type": "function", "function": {"name": "send_email", "description": "Send an approved outreach email via Gmail (approval id required).", "parameters": {"type": "object", "properties": {"outreach_id": {"type": "string"}, "approval_id": {"type": "string"}}, "required": ["outreach_id", "approval_id"]}}},
    {"type": "function", "function": {"name": "create_watch", "description": "Watch an opportunity for changes.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "check_watch", "description": "Re-check a watched opportunity now.", "parameters": {"type": "object", "properties": {"opportunity_id": {"type": "string"}}, "required": ["opportunity_id"]}}},
    {"type": "function", "function": {"name": "prepare_followup", "description": "Prepare a follow-up draft for an unanswered outreach/application.", "parameters": {"type": "object", "properties": {"outreach_id": {"type": "string"}}, "required": ["outreach_id"]}}},
]

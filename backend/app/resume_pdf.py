"""ATS-clean resume PDF renderer (single column, standard headings).

ReportLab Platypus, Helvetica only — parses cleanly on every ATS because it
IS what the parsers expect: one column, plain text, standard sections.
"""
from __future__ import annotations

from io import BytesIO

INK = (0x16 / 255, 0x15 / 255, 0x0F / 255)
MUTED = (0x5C / 255, 0x57 / 255, 0x4A / 255)
SIGNAL = (0xFF / 255, 0x4D / 255, 0x00)
RULE = (0xD8 / 255, 0xD4 / 255, 0xCA / 255)


def render_resume_pdf(res: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"Resume - {res.get('name', '')}")
    name_s = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=19,
                            leading=22, textColor=INK, alignment=1)
    contact_s = ParagraphStyle("contact", fontName="Helvetica", fontSize=8.5,
                               leading=11, textColor=MUTED, alignment=1)
    h_s = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10.5,
                         leading=14, textColor=INK, spaceBefore=10, spaceAfter=3)
    b_s = ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
    bi_s = ParagraphStyle("bi", parent=b_s, leftIndent=12, bulletIndent=4, spaceBefore=1)

    story = []
    story.append(Paragraph(_esc(res.get("name", "Candidate")), name_s))
    contact = "  |  ".join([p for p in [
        res.get("email", ""), res.get("phone", ""), res.get("location", ""),
        res.get("links", {}).get("linkedin", ""), res.get("links", {}).get("github", "")] if p])
    if contact:
        story.append(Paragraph(_esc(contact), contact_s))

    def section(title: str):
        story.append(HRFlowable(width="100%", thickness=0.7, color=RULE, spaceAfter=2))
        story.append(Paragraph(title.upper(), h_s))

    if res.get("summary"):
        section("Summary")
        story.append(Paragraph(_esc(res["summary"]), b_s))
    if res.get("experience"):
        section("Experience")
        for e in res["experience"]:
            head = f"<b>{_esc(e.get('title', ''))}</b>"
            if e.get("company"):
                head += f" — {_esc(e['company'])}"
            if e.get("years"):
                head += f" <font color='#5C574A'>{_esc(e['years'])}</font>"
            story.append(Paragraph(head, b_s))
            for line in _bullets(e.get("summary", "")):
                story.append(Paragraph(f"•  {_esc(line)}", bi_s,
                                       bulletText="•"))
    if res.get("education"):
        section("Education")
        for e in res["education"]:
            line = " — ".join([p for p in [e.get("degree", ""), e.get("field", ""),
                                           e.get("school", ""), e.get("years", "")] if p])
            story.append(Paragraph(_esc(line), b_s))
    if res.get("skills"):
        section("Skills")
        story.append(Paragraph(_esc(", ".join(res["skills"])), b_s))
    if res.get("projects"):
        section("Projects")
        for p in res["projects"]:
            if isinstance(p, dict):
                story.append(Paragraph(f"<b>{_esc(p.get('title', ''))}</b> — {_esc(p.get('summary', ''))}", b_s))
            else:
                story.append(Paragraph(_esc(str(p)), b_s))
    doc.build(story)
    return buf.getvalue()


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bullets(summary: str) -> list[str]:
    import re as _re
    parts = _re.split(r"[•\n;]+", summary or "")
    out = [p.strip(" -–—") for p in parts if p.strip()]
    return out[:8] or ([summary.strip()] if summary.strip() else [])

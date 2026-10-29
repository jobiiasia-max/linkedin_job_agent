"""Step 5: write a strong, TRUTHFUL, ATS-friendly CV + cover letter (PDF) for each job.

How it works for every selected job:
  1. ANALYSE  - Groq reads the job post and lists the must-have / nice-to-have skills.
  2. GAP CHECK (plain Python, no AI) - each requirement is checked against your real CV
     text. Supported ones are woven into the CV in the job's exact wording (this is what
     recruiter software scans for). Unsupported ones are listed as "missing" and forbidden.
  3. WRITE    - Groq writes a one-page CV (headline, summary, skills, experience) and a short
     cover letter, using only your real facts.
  4. TRUTH CHECK (plain Python) - removes any skill, bullet, sentence, company or school
     that is not backed by your CV, so an AI slip can never reach a recruiter.

Real experience missing from your CV? Put it in extra_experience.txt (same folder).
Everything in that file is treated as true.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from langchain_groq import ChatGroq
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph,
                                SimpleDocTemplate, Spacer)

import config
from cv_reader import find_cv_files, read_cv_text
from matcher import _has, skill_hit
from utils import log

_cv_texts = {}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _load_cv_texts():
    if not _cv_texts:
        for f in find_cv_files(config.CV_FOLDER):
            try:
                _cv_texts[f.name] = read_cv_text(str(f))
            except ValueError:
                pass
    if not _cv_texts:
        raise FileNotFoundError("No readable CV PDF found.")
    return _cv_texts


def pick_base_cv(job):
    texts = _load_cv_texts()
    if config.BASE_CV in texts:
        return texts[config.BASE_CV]
    wanted = job.get("matched") or []
    return max(texts.values(), key=lambda t: sum(skill_hit(s, t.lower()) for s in wanted))


def _extra_facts():
    p = Path(config.CV_FOLDER) / "extra_experience.txt"
    return p.read_text(encoding="utf-8", errors="ignore").strip() if p.exists() else ""


def _invoke(prompt, retries=3):
    llm = ChatGroq(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), temperature=0.2)
    for attempt in range(retries):
        try:
            return llm.invoke(prompt).content
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(20 * (attempt + 1))   # Groq rate limit: wait and retry


def _json(reply):
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        raise ValueError("model did not return JSON")
    return json.loads(m.group(0))


# ----------------------------------------------------------------------------
# 1. ANALYSE the job
# ----------------------------------------------------------------------------
ANALYSE_PROMPT = """Read this job post. Return ONLY JSON in this shape:
{"must_have": ["up to 10 REQUIRED skills/tools/technologies, 1-3 words each, written exactly as the post writes them"],
 "nice_to_have": ["up to 6 optional skills/tools, same style"],
 "role_focus": "one short phrase describing what the role is about"}

JOB TITLE: <<TITLE>>
JOB POST:
<<DESC>>"""


def analyse_job(job):
    prompt = (ANALYSE_PROMPT.replace("<<TITLE>>", job["title"])
              .replace("<<DESC>>", job.get("desc_text", "")[:3500]))
    data = _json(_invoke(prompt))
    clean = lambda xs: [x.strip() for x in xs if isinstance(x, str) and x.strip()]
    return clean(data.get("must_have", [])), clean(data.get("nice_to_have", [])), \
        str(data.get("role_focus", ""))


# ----------------------------------------------------------------------------
# 2. GAP CHECK (no AI): what does the real CV support?
# ----------------------------------------------------------------------------
def gap_check(source_lower, must, nice):
    supported = [k for k in must + nice if skill_hit(k.lower(), source_lower)]
    missing_must = [k for k in must if k not in supported]
    missing_nice = [k for k in nice if k not in supported]
    must_ok = len([k for k in must if k in supported])
    coverage = int(round(must_ok / len(must) * 100)) if must else 0
    return supported, missing_must + missing_nice, coverage


# ----------------------------------------------------------------------------
# 3. WRITE the CV and cover letter
# ----------------------------------------------------------------------------
WRITE_PROMPT = """You are an expert CV writer whose CVs get candidates shortlisted. Rewrite the
candidate's CV for ONE job and write a short cover letter.

TRUTH RULES (never break these):
- Use ONLY facts from the CANDIDATE CV or the CONFIRMED EXTRA FACTS below.
- NEVER invent skills, tools, certifications, employers, degrees, titles, dates, numbers
  or achievements. Do not inflate years of experience.
- The candidate does NOT have these, so never mention them anywhere: <<MISSING>>

HOW TO MAKE IT STRONG:
- headline: the candidate's real most recent job title plus 2-3 real strengths that fit the
  job, e.g. "Automation Developer | Python | RAG".
- summary: 2-3 sentences. Lead with the role and the candidate's strongest REAL match to
  this job (<<FOCUS>>). Work in these supported keywords naturally: <<SUPPORTED>>.
- skills: put these supported keywords FIRST, written exactly as the job writes them:
  <<SUPPORTED>>. Then the candidate's other real skills most relevant to the job.
  Maximum 18 skills.
- experience: keep every real job, newest first. 3-5 bullets each, most relevant first.
  Start every bullet with a strong action verb. Keep numbers/results already in the CV.
  Re-word a bullet with the job's vocabulary ONLY if the bullet is really about that thing.
- Cut irrelevant detail so it fits ONE page.
- cover_letter: 120-170 words, 3 short paragraphs separated by a blank line. Mention the
  company and role, 2 real strengths relevant to the job, and a polite closing. No
  greeting or signature lines, and no claims that are not in the CV.

Return ONLY JSON in exactly this shape:
{"name": "", "headline": "", "contact": "email | phone | city", "summary": "", "skills": [""],
 "experience": [{"title": "", "company": "", "dates": "", "bullets": [""]}],
 "education": [{"degree": "", "school": "", "dates": ""}],
 "other": [{"heading": "", "items": [""]}],
 "cover_letter": ""}

JOB TITLE: <<TITLE>>
COMPANY: <<COMPANY>>
JOB POST:
<<DESC>>

CONFIRMED EXTRA FACTS (from the candidate, true):
<<EXTRA>>

CANDIDATE CV:
<<CV>>"""


def write_cv(cv_text, job, supported, missing, focus):
    prompt = (WRITE_PROMPT
              .replace("<<MISSING>>", ", ".join(missing) or "(none)")
              .replace("<<FOCUS>>", focus or "the role")
              .replace("<<SUPPORTED>>", ", ".join(supported) or "(none)")
              .replace("<<TITLE>>", job["title"]).replace("<<COMPANY>>", job["company"])
              .replace("<<DESC>>", job.get("desc_text", "")[:3000])
              .replace("<<EXTRA>>", _extra_facts() or "(none)")
              .replace("<<CV>>", cv_text[:8000]))
    return _json(_invoke(prompt))


# ----------------------------------------------------------------------------
# 4. TRUTH CHECK (no AI): strip anything the real CV does not back up
# ----------------------------------------------------------------------------
def _mentions(text, forbidden):
    t = text.lower()
    return any(_has(f.lower(), t) for f in forbidden)


def _drop_sentences(text, forbidden):
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    return " ".join(p for p in parts if not _mentions(p, forbidden)).strip()


def enforce_truth(data, source_lower, missing):
    removed = []

    kept = []
    for s in data.get("skills", []) or []:
        if isinstance(s, str) and skill_hit(s.lower(), source_lower) and not _mentions(s, missing):
            kept.append(s)
        else:
            removed.append(f"skill:{s}")
    data["skills"] = kept[:18]

    def known(name):   # does any real word of this name appear in the source?
        return any(w in source_lower for w in re.findall(r"[a-z0-9]{3,}", (name or "").lower()))

    exp = []
    for e in data.get("experience", []) or []:
        if not known(e.get("company")):
            removed.append(f"company:{e.get('company')}")
            continue
        bullets = []
        for b in e.get("bullets", []) or []:
            if _mentions(b, missing):
                removed.append(f"bullet:{b[:40]}")
            else:
                bullets.append(b)
        e["bullets"] = bullets
        exp.append(e)
    data["experience"] = exp

    edu = []
    for ed in data.get("education", []) or []:
        if known(ed.get("school")) or known(ed.get("degree")):
            edu.append(ed)
        else:
            removed.append(f"education:{ed.get('school')}")
    data["education"] = edu

    data["summary"] = _drop_sentences(data.get("summary", ""), missing)
    data["cover_letter"] = _drop_sentences(data.get("cover_letter", ""), missing) \
        if "\n\n" not in (data.get("cover_letter") or "") else "\n\n".join(
            _drop_sentences(p, missing) for p in data["cover_letter"].split("\n\n"))
    if _mentions(data.get("headline", ""), missing):
        data["headline"] = ""
        removed.append("headline")
    return data, removed


# ----------------------------------------------------------------------------
# PDF output (single column, plain fonts = easy for recruiter software to read)
# ----------------------------------------------------------------------------
def _styles():
    base = dict(fontName="Helvetica", fontSize=10, leading=13)
    return {
        "name": ParagraphStyle("n", fontName="Helvetica-Bold", fontSize=20, leading=24),
        "headline": ParagraphStyle("hl", fontName="Helvetica-Bold", fontSize=11, leading=14,
                                   textColor=colors.HexColor("#1f3a5f")),
        "contact": ParagraphStyle("c", textColor=colors.HexColor("#444444"), **base),
        "head": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11, leading=14,
                               spaceBefore=8, textColor=colors.HexColor("#1f3a5f")),
        "body": ParagraphStyle("b", **base),
        "role": ParagraphStyle("r", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=4),
        "letter": ParagraphStyle("l", fontName="Helvetica", fontSize=11, leading=16, spaceAfter=8),
    }


def _P(text, style):
    return Paragraph(escape(str(text or "")), style)


def render_pdf(data, path):
    st = _styles()

    def heading(text):
        return [_P(text.upper(), st["head"]),
                HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1f3a5f"))]

    def bullets(items):
        return ListFlowable([ListItem(_P(i, st["body"]), leftIndent=10) for i in items if i],
                            bulletType="bullet", start="•", leftIndent=12)

    s = [_P(data.get("name"), st["name"])]
    if data.get("headline"):
        s.append(_P(data["headline"], st["headline"]))
    s += [_P(data.get("contact"), st["contact"]), Spacer(1, 4)]
    if data.get("summary"):
        s += heading("Summary") + [_P(data["summary"], st["body"])]
    if data.get("skills"):
        s += heading("Skills") + [_P(", ".join(data["skills"]), st["body"])]
    if data.get("experience"):
        s += heading("Experience")
        for e in data["experience"]:
            s.append(_P(f"{e.get('title', '')} - {e.get('company', '')}   ({e.get('dates', '')})",
                        st["role"]))
            s.append(bullets(e.get("bullets", [])))
    if data.get("education"):
        s += heading("Education")
        for ed in data["education"]:
            s.append(_P(f"{ed.get('degree', '')} - {ed.get('school', '')}   "
                        f"({ed.get('dates', '')})", st["body"]))
    for sec in data.get("other", []) or []:
        if sec.get("items"):
            s += heading(sec.get("heading", "Other")) + [bullets(sec["items"])]

    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=15 * mm, bottomMargin=15 * mm).build(s)


def render_letter(data, job, path):
    st = _styles()
    paras = [p.strip() for p in (data.get("cover_letter") or "").split("\n\n") if p.strip()]
    if not paras:
        return False
    s = [_P(data.get("name"), st["name"]), _P(data.get("contact"), st["contact"]),
         Spacer(1, 10), _P(datetime.now().strftime("%d %B %Y"), st["body"]), Spacer(1, 10),
         _P(f"Dear Hiring Team at {job['company']},", st["letter"])]
    s += [_P(p, st["letter"]) for p in paras]
    s += [_P("Sincerely,", st["letter"]), _P(data.get("name"), st["body"])]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                      topMargin=20 * mm, bottomMargin=20 * mm).build(s)
    return True


# ----------------------------------------------------------------------------
# Main entry: called by main.py
# ----------------------------------------------------------------------------
def tailor_one(job):
    cv_text = pick_base_cv(job)
    source_lower = (cv_text + "\n" + _extra_facts()).lower()

    must, nice, focus = analyse_job(job)
    supported, missing, coverage = gap_check(source_lower, must, nice)
    data = write_cv(cv_text, job, supported, missing, focus)
    data, removed = enforce_truth(data, source_lower, missing)

    job["missing_skills"] = missing[:10]
    job["cv_keywords"] = supported[:10]
    job["ats_coverage"] = coverage
    return data, removed


def generate_tailored_cvs(jobs):
    """Adds pdf_path, cover_path, missing_skills, cv_keywords, ats_coverage to each top job."""
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    top = jobs[:config.TAILOR_TOP_N]
    log(f"CV writer: making {len(top)} tailored CVs + cover letters (truthful, nothing invented)...")
    stamp = datetime.now().strftime("%Y%m%d")
    for i, job in enumerate(top, 1):
        try:
            data, removed = tailor_one(job)
            label = re.sub(r"[^A-Za-z0-9]+", "_", f"{job['company']}_{job['title']}")[:50]
            cv_path = config.OUTPUT_DIR / f"{stamp}_{i:02d}_{label}_CV.pdf"
            render_pdf(data, cv_path)
            job["pdf_path"] = str(cv_path)
            letter_path = config.OUTPUT_DIR / f"{stamp}_{i:02d}_{label}_CoverLetter.pdf"
            if render_letter(data, job, letter_path):
                job["cover_path"] = str(letter_path)
            note = f" (truth check removed {len(removed)} unsupported item(s))" if removed else ""
            log(f"  {i}/{len(top)} ready: keyword coverage {job['ats_coverage']}%{note}")
        except Exception as e:
            log(f"  {i}/{len(top)} CV failed for '{job['title']}': {e}")
        time.sleep(3)

"""Step 4: emails through the Resend API (resend.com).
Email 1 = the job list.  Email 2 = tailored CVs attached, ready for you to apply."""
import base64
import sys
from pathlib import Path

import requests

import config
from utils import log

RESEND_URL = "https://api.resend.com/emails"


def send_email(subject, text_body, html_body, attachments=None):
    if not config.RESEND_API_KEY:
        sys.exit("Set RESEND_API_KEY in .env first.")
    if not config.EMAIL_TO:
        sys.exit("Set EMAIL_TO in .env first (the address that receives the jobs).")
    payload = {
        "from": config.EMAIL_FROM,
        "to": [x.strip() for x in config.EMAIL_TO.split(",") if x.strip()],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    if attachments:
        payload["attachments"] = attachments
    headers = {
        "Authorization": f"Bearer {config.RESEND_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "job-agent/1.0",
    }
    try:
        r = requests.post(RESEND_URL, json=payload, headers=headers, timeout=60)
    except requests.RequestException as e:
        sys.exit(f"Could not reach Resend ({type(e).__name__}). Check your internet.")
    if r.status_code >= 400:
        sys.exit(f"Resend error {r.status_code}: {r.text}\n"
                 "Common causes: wrong API key; or using onboarding@resend.dev while "
                 "EMAIL_TO {config.EMAIL_TO}is not the email you signed up to Resend with; or EMAIL_FROM{config.EMAIL_FROM} "
                 "uses a domain you have not verified in Resend.")
    return r.json()


def _line(j):
    kind = j.get("mode", "")
    src = j.get("source", "LinkedIn")
    why = ", ".join(j["matched"][:8]) or "title match"
    return kind, src, why


def send_matches(good_jobs):
    """ONE email: every selected job with its apply link, plus the tailored CVs attached."""
    if not good_jobs:
        return
    attachments, lines, rows = [], [], []
    note = ("Apply links, tailored CVs and cover letters for your selected jobs. I have NOT applied for you: "
            "open each link, check the CV, and press Apply. Skills listed as 'not on your CV' "
            "were left out on purpose. Add them yourself only if you genuinely have them.")
    for n, j in enumerate(good_jobs, 1):
        kind, src, why = _line(j)
        pdf = Path(j["pdf_path"]) if j.get("pdf_path") else None
        if pdf and pdf.exists():
            names = [pdf.name]
            for p in [pdf, Path(j["cover_path"]) if j.get("cover_path") else None]:
                if p and p.exists():
                    attachments.append({"filename": p.name,
                                        "content": base64.b64encode(p.read_bytes()).decode()})
                    if p is not pdf:
                        names.append(p.name)
            cv = "Attached: " + ", ".join(names)
            missing = ", ".join(j.get("missing_skills", [])) or "none found"
            gap = (f"CV keyword coverage: {j.get('ats_coverage', 0)}% of the job's must-haves | "
                   f"Not on your CV (job asks for these): {missing}")
        else:
            cv, gap = "CV: not generated for this job", ""
        lines.append(f"{n}. {j['title']} at {j['company']}\n{kind} | {j['location']} | "
                     f"via {src} | Match {j['score']}%\nMatches: {why}\n"
                     f"Apply: {j['url']}\n{cv}\n{gap}\n")
        rows.append(f"<p>{n}. <b><a href='{j['url']}'>{j['title']}</a></b> at {j['company']}<br>"
                    f"{kind} | {j['location']} | via {src} | Match {j['score']}%<br>"
                    f"<small>Matches: {why}<br>{cv}<br>{gap}</small></p>")
    send_email(f"{len(good_jobs)} job(s) with apply links and tailored CVs",
               note + "\n\n" + "\n".join(lines),
               f"<html><body><p>{note}</p>" + "".join(rows) + "</body></html>",
               attachments or None)
    log(f"Emailer: ONE email sent with {len(good_jobs)} jobs and "
        f"{len(attachments)} CVs attached to {config.EMAIL_TO}")

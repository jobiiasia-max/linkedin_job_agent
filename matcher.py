"""Step 3: apply the location rules and score jobs against your skills.

Rules:
  - Lahore search  : remote, on-site and hybrid are all allowed
                     (a job outside Lahore is kept only if it is remote)
  - Worldwide etc. : REMOTE ONLY (hybrid and on-site jobs are rejected)
"""
import random
import re
import time

import config
from linkedin_search import fetch_description
from utils import log

HYBRID = re.compile(r"\bhybrid\b", re.I)
ONSITE = re.compile(r"\bon[- ]?site\b|\bin[- ]office\b|\bin[- ]person\b", re.I)
REMOTE = re.compile(r"\bremote\b", re.I)


def _has(skill, text):
    return re.search(r"(?<![\w+#])" + re.escape(skill) + r"(?![\w+#])", text) is not None


def skill_hit(skill, text):
    """True if the skill phrase is present, or (for 2-word skills) both words are present."""
    if _has(skill, text):
        return True
    words = skill.split()
    return len(words) > 1 and all(_has(w, text) for w in words)


def work_mode(job, description):
    text = f"{job['title']} {job['location']} {description}"
    if HYBRID.search(text):
        return "Hybrid"
    if REMOTE.search(text):
        return "Remote"
    if ONSITE.search(text):
        return "On-site"
    return "Lahore (type not stated)" if job["work_type"] == "lahore" else "Remote"


def fits_rules(job, description):
    head = f"{job['title']} {job['location']}"
    text = f"{head} {description}"
    if job["work_type"] == "remote":           # worldwide: remote only
        if HYBRID.search(head) or ONSITE.search(head):
            return False, "hybrid/on-site in title or location"
        if HYBRID.search(description):
            return False, "description says hybrid"
        if ONSITE.search(description) and not REMOTE.search(text):
            return False, "on-site job, not remote"
    else:                                       # Lahore: anything, if it is really Lahore
        if "lahore" not in job["location"].lower():
            if not REMOTE.search(text) or HYBRID.search(text):
                return False, "not in Lahore and not remote"
    return True, ""


def score_job(job, skills, description):
    text = f"{job['title']} {description}".lower()
    matched = [s for s in skills if skill_hit(s, text)]
    score = min(80, int(len(matched) / max(1, min(len(skills), 8)) * 80))
    if any(skill_hit(s, job["title"].lower()) for s in skills):
        score += 20
    return min(score, 100), matched


def match_jobs(jobs, skills, seen):
    fresh = [j for j in jobs if j["id"] not in seen]
    # cap only the jobs that need an extra LinkedIn page request
    linkedin = [j for j in fresh if not j.get("description")][:config.MAX_DETAIL_FETCH]
    boards = [j for j in fresh if j.get("description")]
    new_jobs = linkedin + boards
    log(f"Matcher: checking {len(new_jobs)} new jobs")
    keep = []
    for job in new_jobs:
        desc = job.get("description")
        if not desc:
            desc = fetch_description(job["id"])
            time.sleep(random.uniform(3, 6))
        if not desc:
            log(f"  SKIPPED (could not read job page, will retry next run): {job['title']}")
            continue
        seen[job["id"]] = job["title"]

        ok, why = fits_rules(job, desc)
        if not ok:
            log(f"  REJECTED [{why}] {job['title']} | {job['company']} | {job['location']}")
            continue

        job["mode"] = work_mode(job, desc)
        job["score"], job["matched"] = score_job(job, skills, desc)
        job["is_match"] = job["score"] >= config.MIN_SCORE
        job["desc_text"] = desc
        tag = "MATCH" if job["is_match"] else "low  "
        log(f"  {tag} {job['score']:>3}% | {job['mode']} | {job['title']} | "
            f"{job['company']} | {job['location']}")
        # job boards are not filtered by keyword, so keep only real matches from them
        from_board = bool(job.get("source"))
        if job["is_match"] or (config.EMAIL_ALL_JOBS and not from_board):
            keep.append(job)
    keep.sort(key=lambda j: j["score"], reverse=True)
    log(f"Matcher: {len(keep)} jobs will be emailed (out of {len(new_jobs)} new jobs)")
    return keep

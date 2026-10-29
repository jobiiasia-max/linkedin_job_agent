"""Step 2: search LinkedIn. Lahore = remote, on-site or hybrid. Everywhere else = remote only."""
import random
import time

import requests
from bs4 import BeautifulSoup

import config
from utils import log

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
})


class RateLimited(Exception):
    pass


def http_get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                raise RateLimited()
            return r
        except (requests.Timeout, requests.ConnectionError, RateLimited) as e:
            if attempt == retries - 1:
                raise
            wait = 30 * (attempt + 1)
            kind = "rate-limited" if isinstance(e, RateLimited) else "timed out"
            log(f"Searcher: {kind}, waiting {wait}s then retrying...")
            time.sleep(wait)


def search_linkedin(keyword, location, work_type, use_geo=True):
    """work_type: 'lahore' (any type) or 'remote' (f_WT=2)."""
    params = {
        "keywords": keyword,
        "location": location,
        "f_TPR": f"r{config.POSTED_WITHIN_HOURS * 3600}",
        "start": 0,
    }
    if use_geo and location.lower() == "worldwide":
        params["geoId"] = "92000000"   # LinkedIn's "Worldwide" region (any country)
    if work_type == "remote":
        params["f_WT"] = "2"   # remote only. Lahore searches have no filter (remote, on-site, hybrid)
    try:
        r = http_get(SEARCH_URL, params=params)
        r.raise_for_status()
    except RateLimited:
        raise
    except requests.RequestException as e:
        log(f"Searcher: failed for '{keyword}' in {location}: {type(e).__name__}")
        return []

    jobs = []
    if len(r.text.strip()) < 200:
        log(f"Searcher: LinkedIn returned an empty page for '{keyword}' in {location}")
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.select("li"):
        base = card.select_one("div.base-card")
        link = card.select_one("a.base-card__full-link")
        title = card.select_one(".base-search-card__title")
        if not (base and link and title):
            continue
        job_id = base.get("data-entity-urn", "").split(":")[-1]
        if not job_id:
            continue
        company = card.select_one(".base-search-card__subtitle")
        loc = card.select_one(".job-search-card__location")
        jobs.append({
            "id": job_id,
            "title": title.get_text(strip=True),
            "company": company.get_text(strip=True) if company else "",
            "location": loc.get_text(strip=True) if loc else location,
            "url": link.get("href", "").split("?")[0],
            "work_type": work_type,
        })
    return jobs


def search_all(skills):
    """Search every keyword in Lahore (on-site) and in the remote locations."""
    keywords = skills[:config.MAX_SEARCH_KEYWORDS]
    plan = [(k, loc, "lahore") for k in keywords for loc in config.ONSITE_LOCATIONS]
    plan += [(k, loc, "remote") for k in keywords for loc in config.REMOTE_LOCATIONS]

    found, blocked_in_a_row = {}, 0
    for i, (kw, loc, kind) in enumerate(plan, 1):
        log(f"Searcher: {i}/{len(plan)} '{kw}' | {loc} | {kind}")
        try:
            jobs = search_linkedin(kw, loc, kind)
            if kind == "remote" and not jobs and loc.lower() == "worldwide":
                log("Searcher: Worldwide gave 0 jobs, retrying without region id...")
                time.sleep(random.uniform(6, 12))
                jobs = search_linkedin(kw, loc, kind, use_geo=False)
            if kind == "remote" and not jobs and loc.lower() == "worldwide":
                log("Searcher: still 0, trying fallback regions (remote only)...")
                for fb in config.REMOTE_FALLBACK:
                    time.sleep(random.uniform(6, 12))
                    jobs += search_linkedin(kw, fb, kind)
            blocked_in_a_row = 0
        except RateLimited:
            blocked_in_a_row += 1
            log("Searcher: LinkedIn is blocking us right now.")
            if blocked_in_a_row >= 2:
                log("Searcher: stopping early. Will try again next run.")
                break
            continue
        log(f"Searcher:    -> {len(jobs)} jobs returned")
        for job in jobs:
            where = job["location"].lower()
            if kind == "lahore" and not ("lahore" in where or "pakistan" in where):
                continue
            found.setdefault(job["id"], job)
        time.sleep(random.uniform(6, 12))
    log(f"Searcher: {len(found)} unique jobs found")
    return list(found.values())


def fetch_description(job_id):
    try:
        r = http_get(DETAIL_URL.format(id=job_id), retries=1)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        el = soup.select_one(".show-more-less-html__markup") or soup
        return el.get_text(" ", strip=True)
    except (requests.RequestException, RateLimited):
        return ""

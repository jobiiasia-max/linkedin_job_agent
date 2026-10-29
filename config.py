"""All settings live here. Values come from the .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _list(name, default, sep=","):
    return [x.strip() for x in os.getenv(name, default).split(sep) if x.strip()]


# CVs (PDFs) are read from the same folder as this code, unless CV_FOLDER is set
CV_FOLDER = os.getenv("CV_FOLDER") or str(Path(__file__).resolve().parent)
BLOCKED_SKILLS = _list("BLOCKED_SKILLS", "")   # words to ignore, e.g. huawei,islamabad
EXTRA_SKILLS = _list("EXTRA_SKILLS", "")       # skills to always add

# Locations. Lahore searches return remote, on-site and hybrid jobs
ONSITE_LOCATIONS = _list("ONSITE_LOCATIONS", "Lahore, Pakistan|Lahore, Punjab, Pakistan", "|")
# Remote jobs: no specific region. One worldwide search per keyword.
REMOTE_LOCATIONS = ["Worldwide"]
# Used ONLY if the Worldwide search returns nothing (LinkedIn needs some location)
REMOTE_FALLBACK = ["United States", "United Kingdom", "Canada", "Germany", "Netherlands",
                   "Australia", "United Arab Emirates", "Singapore"]

# Search behaviour
MAX_SEARCH_KEYWORDS = int(os.getenv("MAX_SEARCH_KEYWORDS", "3"))
MAX_DETAIL_FETCH = int(os.getenv("MAX_DETAIL_FETCH", "30"))
POSTED_WITHIN_HOURS = int(os.getenv("POSTED_WITHIN_HOURS", "24"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "25"))
# true = email every job that passes the location rules (sorted by score)
EMAIL_ALL_JOBS = os.getenv("EMAIL_ALL_JOBS", "true").lower() in ("1", "true", "yes")
CHECK_EVERY_HOURS = float(os.getenv("CHECK_EVERY_HOURS", "3"))

# Email (Resend: resend.com)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Job Agent <onboarding@resend.dev>")
EMAIL_TO = os.getenv("EMAIL_TO", "")

# Tailored CVs (one PDF per selected job)
TAILOR_CVS = os.getenv("TAILOR_CVS", "true").lower() in ("1", "true", "yes")
TAILOR_TOP_N = int(os.getenv("TAILOR_TOP_N", "16"))     # how many jobs get a tailored CV
BASE_CV = os.getenv("BASE_CV", "")                       # e.g. my_cv.pdf (empty = best match)
OUTPUT_DIR = Path(__file__).resolve().parent / "tailored_cvs"

SEEN_FILE = str(Path(__file__).resolve().parent / "seen_jobs.json")

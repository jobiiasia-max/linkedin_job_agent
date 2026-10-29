# Job Agent

Reads all CV PDFs in the same folder as the code, asks Groq for the strongest skills, searches LinkedIn,
and emails matching jobs. On-site jobs: Lahore only. Remote jobs: anywhere in the world.

## Folder structure
job-agent/
  main.py              runs everything
  cv_reader.py         reads CV PDFs, extracts skills with Groq
  linkedin_search.py   searches LinkedIn
  matcher.py           scores jobs against your skills
  emailer.py           sends the email
  config.py            settings from .env
  utils.py             small helpers
  your CV PDFs         put them in this same folder
  requirements.txt, .env.example, .gitignore

## Setup
1. pip install -r requirements.txt
2. Copy .env.example to .env and fill it in
3. Put your CV PDFs in the same folder as main.py

## Run
python main.py --show-skills   # check the skills found in your CVs
python test_email.py           # check email works (Resend)
python main.py --dry-run       # search and print matches, no email
python main.py                 # run once and email matches
python main.py --loop          # repeat every few hours

## Notes
- If a wrong word appears as a skill, add it to BLOCKED_SKILLS in .env.
- LinkedIn may rate-limit automated searches. Keep CHECK_EVERY_HOURS at 3 or more.

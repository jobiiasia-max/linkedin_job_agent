import os
from langchain_groq import ChatGroq

def check_model(model: str) -> bool:
    try:
        ChatGroq(model=model, max_tokens=1).invoke("hi")
        print(f"✅ {model}: allowed")
        return True
    except Exception as e:
        msg = str(e)
        if "404" in msg or "model_not_found" in msg:
            print(f"❌ {model}: not available to you")
        elif "429" in msg:
            print(f"⚠️ {model}: allowed, but rate limited right now")
        else:
            print(f"❓ {model}: {msg[:150]}")
        return False

for m in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
    check_model(m)



# """Job agent. Run:  python main.py --help"""
# import argparse
# import time

# import config
# from cv_reader import extract_skills_from_folder
# from cv_tailor import generate_tailored_cvs
# from emailer import send_email, send_matches
# from linkedin_search import search_all
# from matcher import match_jobs
# from utils import load_seen, log, save_seen


# def get_skills():
#     log(f"CV reader: reading PDFs in {config.CV_FOLDER}")
#     skills = extract_skills_from_folder(
#         config.CV_FOLDER, blocked=['python','automation developer', 'rpa engineer', 'c#', '.net core', 'selenium'], extra=config.EXTRA_SKILLS)
#     log(f"CV reader: final skills = {skills}")
#     return skills


# def run_once(dry_run=False):
#     seen = load_seen(config.SEEN_FILE)
#     skills = get_skills()
#     jobs = search_all(skills)
#     good = match_jobs(jobs, skills, seen)
#     if dry_run:
#         for j in good:
#             print(f"- [{j['score']}%] {j['title']} | {j['company']} | "
#                   f"{j['mode']} | {j['location']}\n  {j['url']}")
#         if config.TAILOR_CVS and good:
#             generate_tailored_cvs(good)   # PDFs are saved in tailored_cvs/ only
#         log("Dry run: no email sent, seen list not saved.")
#         return
#     if config.TAILOR_CVS and good:
#         generate_tailored_cvs(good)       # tailored PDFs, one per selected job
#     send_matches(good)                    # ONE email: jobs + apply links + CVs attached
#     save_seen(config.SEEN_FILE, seen)


# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--show-skills", action="store_true", help="only show skills found in CVs")
#     ap.add_argument("--test-email", action="store_true", help="send a test email")
#     ap.add_argument("--dry-run", action="store_true", help="print matches, send nothing")
#     ap.add_argument("--loop", action="store_true", help="repeat every CHECK_EVERY_HOURS")
#     args = ap.parse_args()

#     if args.show_skills:
#         get_skills()
#         return
#     if args.test_email:
#         send_email("Job agent test", "Your email settings work.", "<p>Your email settings work.</p>")
#         log("Test email sent.")
#         return
#     if not args.loop:
#         run_once(args.dry_run)
#         return

#     log(f"Loop mode: every {config.CHECK_EVERY_HOURS} hours. Ctrl+C to stop.")
#     while True:
#         try:
#             run_once(args.dry_run)
#         except Exception as e:
#             log(f"Run failed: {e}")
#         time.sleep(config.CHECK_EVERY_HOURS * 3600)


# if __name__ == "__main__":
#     main()

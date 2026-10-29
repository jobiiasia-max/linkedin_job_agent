"""Step 1: read the CV PDF and let the Groq LLM pull out job-search keywords."""
import json
import os
import re
from pathlib import Path

from langchain_groq import ChatGroq
from pypdf import PdfReader


def read_cv_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise ValueError("Could not read any text from the CV. Is it a scanned image PDF?")
    return text


def extract_skills(cv_text: str) -> list[str]:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
    )
    prompt = (
        "You are a recruiter. Read this CV and list the 6 strongest skills or job titles "
        "this person could search for on a job board.\n"
        "Rules: each item must be 1-2 words (e.g. 'python', 'rag', 'langchain', 'data engineer'). "
        "Reply with ONLY a JSON list of strings, nothing else.\n\n"
        f"CV:\n{cv_text[:6000]}"
    )
    reply = llm.invoke(prompt).content
    match = re.search(r"\[.*\]", reply, re.S)
    if not match:
        raise ValueError(f"LLM did not return a JSON list: {reply}")
    skills = json.loads(match.group(0))
    return [s.strip().lower() for s in skills if isinstance(s, str) and s.strip()]


# ---------------------------------------------------------------------------
# Added: read ALL PDFs in a folder and merge their skills into one list.
# (The three functions above are your original code, unchanged.)
# ---------------------------------------------------------------------------
def find_cv_files(folder: str = ".") -> list[Path]:
    return sorted(Path(folder).glob("*.pdf"))


def extract_skills_from_folder(folder: str = ".", blocked=(), extra=()) -> list[str]:
    """Run extract_skills on every PDF, merge, remove duplicates and unwanted words."""
    files = find_cv_files(folder)
    if not files:
        raise FileNotFoundError(f"No PDF files found in '{folder}'. Put your CV PDFs in the same folder as the code.")

    per_cv = []
    for f in files:
        skills = extract_skills(read_cv_text(str(f)))
        print(f"  {f.name}: {skills}")
        per_cv.append(skills)

    blocked = {b.lower() for b in blocked}
    print(f"blocked{f.blocked}")
    merged, seen = [], set()
    # round-robin so the strongest skill of every CV comes first
    for i in range(max(len(s) for s in per_cv)):
        for skills in per_cv:
            if i < len(skills):
                skill = skills[i]
                if skill not in seen and skill.lower not in blocked:
                    seen.add(skill)
                    merged.append(skill)
    for skill in extra:
        if skill.lower() not in seen:
            merged.append(skill.lower())
    print(f"final skills are {f.merged}")
    return merged

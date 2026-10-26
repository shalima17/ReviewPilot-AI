# ReviewPilot AI — Internship Review Automation

A beginner-friendly MVP that helps reviewers manage internship task assignments, explain requirements, review submissions with AI assistance, generate feedback emails, schedule the next review, and track repeated review rounds.

## Features

- Create a candidate profile and assign a task.
- Generate a simple task explanation using Gemini (optional).
- Upload TXT, Markdown, PDF, DOCX, Python, JavaScript, HTML, CSS, or JSON submissions.
- Compare a submission with the task and requirement text using Gemini (optional).
- Produce a structured feedback report covering missing/incomplete modules, visible risks, recommended changes/additions, and a next-review checklist.
- Generate task and feedback email drafts.
- Optionally send emails via SMTP.
- Save candidates and review rounds in a local SQLite database.
- Mark the review process complete.

## Tech stack

- Python
- Streamlit
- Google Gemini API (optional)
- SQLite
- pypdf and python-docx for document text extraction
- SMTP for optional email delivery

## Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Install dependencies and start the app:

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

## Enable Gemini AI (optional)

Create an API key in Google AI Studio, then set the environment variable before starting the app.

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="your_key_here"
streamlit run app.py
```

macOS/Linux:

```bash
export GEMINI_API_KEY="your_key_here"
streamlit run app.py
```

If the key is not set or the API call fails, the app switches to a clearly labelled demo/manual-review template. Do not claim this fallback is AI analysis.

## Enable email sending (optional)

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` as environment variables. For Gmail, use an App Password where supported; never commit credentials to GitHub. Without SMTP configuration, the app only generates email drafts.

## Demo workflow

1. Open **Assign & Explain**.
2. Enter a sample candidate, task description, requirements, and review schedule.
3. Generate the task explanation and inspect the email draft.
4. Open **Review Submission** and select the candidate.
5. Upload or paste a sample submission.
6. Generate the feedback report and next-review email draft.
7. Save feedback to history and check **Candidate History**.
8. Repeat with an updated submission, or mark the process complete.

## Important limitations

- This is a local MVP, not a production deployment.
- Review output depends on the quality of the supplied task, requirements, and submission text.
- The application does not execute or test submitted code. AI findings must be checked by a human reviewer.
- PDF extraction works only when the PDF contains extractable text; scanned PDFs need OCR, which is not included.
- Email delivery and Gemini analysis require external credentials and network access.
- SQLite stores data locally in `reviews.db`; that file is excluded from Git.
- For real candidate data, add authentication, authorization, privacy controls, audit logs, secure hosting, and data-retention rules before production use.

## GitHub upload

1. Create a new **public** repository, e.g. `ai-internship-review-automation`.
2. Do not upload `.env`, API keys, passwords, or `reviews.db`.
3. Upload `app.py`, `requirements.txt`, `.env.example`, `.gitignore`, and `README.md`.
4. Add a screenshot of the running app if time permits.

## Suggested interview explanation

"I built ReviewPilot AI, a Streamlit application for internship task-review automation. It stores candidate tasks and review rounds in SQLite, uses Gemini optionally to explain tasks and compare submissions against requirements, generates structured feedback and follow-up email drafts, and supports SMTP delivery when configured. I also included a demo fallback so the workflow can be explored without API credentials. The reviewer remains responsible for verifying the feedback; the app does not execute submitted code or make automatic pass/fail decisions."

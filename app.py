import os
import sqlite3
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta 
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "reviews.db"

st.set_page_config(page_title="ReviewPilot AI", page_icon="🧭", layout="wide")

# ---------- Storage ----------
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        task_title TEXT NOT NULL,
        task_description TEXT NOT NULL,
        requirements TEXT NOT NULL,
        review_date TEXT,
        review_time TEXT,
        meeting_link TEXT,
        status TEXT NOT NULL DEFAULT 'Task assigned',
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        review_number INTEGER NOT NULL,
        submission_name TEXT,
        submission_text TEXT NOT NULL,
        feedback TEXT NOT NULL,
        next_review_date TEXT,
        next_review_time TEXT,
        next_meeting_link TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(candidate_id) REFERENCES candidates(id)
    )""")
    conn.commit()
    return conn

conn = get_connection()

# ---------- Document parsing ----------
def extract_text(uploaded_file):
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    if name.endswith(".txt") or name.endswith(".md") or name.endswith(".py") or name.endswith(".js") or name.endswith(".html") or name.endswith(".css") or name.endswith(".json"):
        return raw.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            return f"[Could not read PDF text: {exc}. Try uploading a TXT or DOCX file.]"
    if name.endswith(".docx"):
        try:
            from docx import Document
            import io
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:
            return f"[Could not read DOCX text: {exc}. Try uploading a TXT file.]"
    return "[Unsupported file type. Please use TXT, MD, PDF, DOCX, PY, JS, HTML, CSS, or JSON.]"

# ---------- AI and fallback ----------
def ask_ai(prompt):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, "Demo mode: GEMINI_API_KEY is not configured."
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return (response.text or "No text returned by the AI model."), "AI mode: Gemini API"
    except Exception as exc:
        return None, f"AI request failed; using demo output instead. Details: {exc}"

def task_explanation(task_title, task_description, requirements):
    prompt = f"""You are a friendly internship mentor. Explain this task to a beginner intern in simple English.
Return: (1) purpose, (2) step-by-step plan, (3) expected deliverables, (4) acceptance checklist, (5) questions to clarify.
Task title: {task_title}\nTask description: {task_description}\nRequirements: {requirements}"""
    result, mode = ask_ai(prompt)
    if result:
        return result, mode
    return (f"## Task purpose\n{task_description}\n\n## Suggested steps\n1. Read the requirements carefully.\n2. Break the task into small modules.\n3. Build each module and test it.\n4. Compare the result against every requirement.\n5. Submit the source code and a short README.\n\n## Expected deliverables\n- Working project\n- Source code and setup instructions\n- Evidence of testing\n\n## Acceptance checklist\n- [ ] All listed requirements are addressed\n- [ ] Main workflow works\n- [ ] Errors and edge cases are handled\n- [ ] README explains how to run the project\n\n## Clarify with reviewer\n- What format should the submission use?\n- Are there required libraries or constraints?\n- What are the evaluation criteria?", mode)

def review_submission(task_title, task_description, requirements, submission_text, review_number):
    prompt = f"""Act as a constructive technical reviewer for an internship student's submission. Do not invent evidence. Compare the submission with the task and requirements. Clearly separate confirmed observations from items that need manual verification. Do not claim code was executed.
Return these headings: Overall summary; Requirement-by-requirement comparison; Missing or incomplete modules; Bugs or risks visible from the submission; Recommended changes; Recommended additions; Questions for the candidate; Suggested next-review checklist.
Review round: {review_number}\nTask title: {task_title}\nTask description: {task_description}\nRequirements: {requirements}\nCandidate submission:\n{submission_text[:25000]}"""
    result, mode = ask_ai(prompt)
    if result:
        return result, mode
    req_lines = [x.strip(" -*\t") for x in requirements.splitlines() if x.strip()]
    checklist = "\n".join(f"- [ ] Verify requirement: {line}" for line in req_lines[:12]) or "- [ ] Confirm the expected features with the reviewer"
    return (f"## Overall summary\nThis is a demo review, not an AI-generated technical verdict. Configure GEMINI_API_KEY to enable AI analysis.\n\n## Requirement-by-requirement comparison\nThe current demo cannot reliably judge whether each requirement is implemented. Use the checklist below during manual review.\n\n## Missing or incomplete modules\n- Compare each required module with the submitted files.\n- Check whether all user flows are implemented.\n\n## Bugs or risks visible from the submission\n- The submission has not been executed or tested by this application.\n- Validate error handling, input validation, and edge cases manually.\n\n## Recommended changes\n- Map each requirement to a specific file or function.\n- Add clear setup and run instructions.\n\n## Recommended additions\n- Add tests and screenshots where useful.\n- Document assumptions and known limitations.\n\n## Questions for the candidate\n- Which requirements are complete, and how were they tested?\n- Are there any known limitations?\n\n## Suggested next-review checklist\n{checklist}", "Demo mode: manual-review template")

# ---------- Email helpers ----------
def make_email(subject, body, recipient):
    return f"To: {recipient}\nSubject: {subject}\n\n{body}"

def send_email(recipient, subject, body):
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM", username).strip()
    if not all([host, username, password, sender]):
        return False, "Email is not configured. Review the generated draft and configure SMTP settings to send real email."
    try:
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)
        return True, "Email sent successfully."
    except Exception as exc:
        return False, f"Email send failed: {exc}"

# ---------- UI ----------
st.markdown("# 🧭 ReviewPilot AI")
st.caption("AI-assisted task explanation, internship submission review, feedback, and review-cycle tracking.")

with st.sidebar:
    st.markdown("### System status")
    st.write("**AI:** " + ("Gemini API key detected" if os.getenv("GEMINI_API_KEY") else "Demo mode (add GEMINI_API_KEY)"))
    st.write("**Email:** " + ("SMTP configured" if all(os.getenv(k) for k in ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD"]) else "Draft-only mode (configure SMTP)"))
    st.info("Demo mode keeps the workflow usable, but its review output is a checklist—not a real AI judgment.")
    st.markdown("### Workflow")
    st.write("1. Assign task\n2. Explain requirements\n3. Schedule review\n4. Review submission\n5. Send feedback\n6. Repeat until complete")

tab_assign, tab_review, tab_history = st.tabs(["📝 Assign & Explain", "🔍 Review Submission", "📚 Candidate History"])

with tab_assign:
    st.subheader("Create an internship task")
    with st.form("assign_form"):
        c1, c2 = st.columns(2)
        with c1:
            candidate_name = st.text_input("Candidate name *")
            candidate_email = st.text_input("Candidate email *")
            task_title = st.text_input("Task title *", placeholder="AI Review Automation")
        with c2:
            review_date = st.date_input("First review date")
            review_time = st.time_input("First review time")
            meeting_link = st.text_input("Meeting link", placeholder="https://meet.google.com/...")
        task_description = st.text_area("Task description *", height=120, placeholder="Explain what the intern needs to build...")
        requirements = st.text_area("Requirement document text *", height=150, placeholder="Paste the acceptance criteria, required modules, and constraints...")
        submitted = st.form_submit_button("Save task and generate explanation", type="primary")
    if submitted:
        if not all([candidate_name.strip(), candidate_email.strip(), task_title.strip(), task_description.strip(), requirements.strip()]):
            st.error("Please fill in all required fields marked with *.")
        else:
            cur = conn.execute("INSERT INTO candidates(name,email,task_title,task_description,requirements,review_date,review_time,meeting_link,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (candidate_name.strip(), candidate_email.strip(), task_title.strip(), task_description.strip(), requirements.strip(), str(review_date), str(review_time), meeting_link.strip(), "Task assigned", datetime.now().isoformat(timespec="seconds")))
            conn.commit()
            candidate_id = cur.lastrowid
            explanation, mode = task_explanation(task_title, task_description, requirements)
            st.session_state[f"explanation_{candidate_id}"] = explanation
            st.session_state[f"explanation_mode_{candidate_id}"] = mode
            st.session_state["last_candidate_id"] = candidate_id
            st.success(f"Task saved for {candidate_name}. Candidate ID: {candidate_id}")
    last_id = st.session_state.get("last_candidate_id")
    if last_id:
        row = conn.execute("SELECT * FROM candidates WHERE id=?", (last_id,)).fetchone()
        if row:
            st.markdown("#### AI task explanation")
            st.caption(st.session_state.get(f"explanation_mode_{last_id}", ""))
            explanation = st.session_state.get(f"explanation_{last_id}", "")
            st.markdown(explanation)
            body = f"Hi {row['name']},\n\nYour internship task '{row['task_title']}' has been assigned.\n\nTask overview:\n{row['task_description']}\n\nTask explanation:\n{explanation}\n\nFirst review: {row['review_date']} at {row['review_time']}\nMeeting link: {row['meeting_link'] or 'To be shared by the reviewer'}\n\nPlease prepare your submission before the review.\n\nRegards,\nInternship Review Team"
            st.markdown("#### Candidate email draft")
            st.code(make_email(f"Task assigned: {row['task_title']}", body, row['email']), language="text")
            if st.button("Send task email (requires SMTP setup)", key=f"send_task_{last_id}"):
                ok, msg = send_email(row['email'], f"Task assigned: {row['task_title']}", body)
                (st.success if ok else st.warning)(msg)

with tab_review:
    st.subheader("Review a candidate submission")
    candidates = conn.execute("SELECT id,name,task_title,email,status FROM candidates ORDER BY id DESC").fetchall()
    if not candidates:
        st.info("Create a candidate and task in the Assign & Explain tab first.")
    else:
        options = {f"#{r['id']} · {r['name']} — {r['task_title']} ({r['status']})": r['id'] for r in candidates}
        selected_label = st.selectbox("Choose candidate", list(options.keys()))
        selected_id = options[selected_label]
        candidate = conn.execute("SELECT * FROM candidates WHERE id=?", (selected_id,)).fetchone()
        prior_count = conn.execute("SELECT COUNT(*) AS n FROM reviews WHERE candidate_id=?", (selected_id,)).fetchone()["n"]
        st.write(f"**Review round:** {prior_count + 1} · **Candidate email:** {candidate['email']}")
        st.write("Upload a document or paste the submission below. Code files and plain text work best for a fast demo.")
        upload = st.file_uploader("Upload submission", type=["txt", "md", "pdf", "docx", "py", "js", "html", "css", "json"], key=f"upload_{selected_id}_{prior_count}")
        submission_text = st.text_area("Or paste submission / project notes", height=180, key=f"submission_{selected_id}_{prior_count}", placeholder="Paste source code, README, feature notes, or implementation details...")
        extracted = extract_text(upload) if upload else ""
        if upload and extracted:
            with st.expander("Preview extracted document text"):
                st.text(extracted[:6000])
        
        c1, c2, c3 = st.columns(3)

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        default_time = datetime.strptime("10:00", "%H:%M").time()

        with c1:
            next_date = st.date_input(
                "Next review date",
                value=tomorrow,
                min_value=today,
                key=f"next_date_{selected_id}_{prior_count}"
            )

        with c2:
            next_time = st.time_input(
                "Next review time",
                value=default_time,
                key=f"next_time_{selected_id}_{prior_count}"
            )

        with c3:
            next_link = st.text_input(
                "Next meeting link",
                value=candidate["meeting_link"] or "",
                key=f"next_link_{selected_id}_{prior_count}"
            )

        schedule_valid = datetime.combine(next_date, next_time) > datetime.now()

        if not schedule_valid:
            st.error(
                "The next review must be scheduled in the future. "
                "Please select a later date or time."
            )

        final_submission = submission_text.strip() or extracted.strip()
        if st.button("Analyze submission and generate feedback", type="primary", key=f"analyze_{selected_id}_{prior_count}"):
            if not final_submission:
                st.error("Upload a submission or paste its contents first.")
            else:
                with st.spinner("Comparing submission with task requirements..."):
                    feedback, mode = review_submission(candidate["task_title"], candidate["task_description"], candidate["requirements"], final_submission, prior_count + 1)
                st.session_state[f"feedback_{selected_id}_{prior_count}"] = feedback
                st.session_state[f"feedback_mode_{selected_id}_{prior_count}"] = mode
                st.session_state[f"submission_used_{selected_id}_{prior_count}"] = final_submission
                st.session_state[f"submission_name_{selected_id}_{prior_count}"] = upload.name if upload else "Pasted text"
        feedback_key = f"feedback_{selected_id}_{prior_count}"
        if feedback_key in st.session_state:
            feedback = st.session_state[feedback_key]
            st.markdown("### Review feedback")
            st.caption(st.session_state.get(f"feedback_mode_{selected_id}_{prior_count}", ""))
            st.markdown(feedback)
            feedback_body = f"Hi {candidate['name']},\n\nThank you for submitting your work for review round {prior_count + 1}.\n\nFeedback:\n{feedback}\n\nNext review: {next_date} at {next_time}\nMeeting link: {next_link or 'To be shared by the reviewer'}\n\nPlease address the feedback and bring your updated submission to the next review.\n\nRegards,\nInternship Review Team"
            st.markdown("### Feedback email draft")
            st.code(make_email(f"Review {prior_count + 1} feedback: {candidate['task_title']}", feedback_body, candidate['email']), language="text")
            b1, b2 = st.columns(2)
            
            with b1:
                if st.button(
                    "Save feedback to review history",
                    key=f"save_review_{selected_id}_{prior_count}"
                ):
                    if not schedule_valid:
                        st.error(
                            "Cannot save: please choose a future review date and time."
                        )
                    else:
                        conn.execute(
                            """INSERT INTO reviews(
                                candidate_id, review_number, submission_name,
                                submission_text, feedback, next_review_date,
                                next_review_time, next_meeting_link, created_at
                            ) VALUES(?,?,?,?,?,?,?,?,?)""",
                            (
                                selected_id,
                                prior_count + 1,
                                st.session_state.get(
                                    f"submission_name_{selected_id}_{prior_count}",
                                    "Pasted text"
                                ),
                                st.session_state.get(
                                    f"submission_used_{selected_id}_{prior_count}",
                                    final_submission
                                ),
                                feedback,
                                str(next_date),
                                str(next_time),
                                next_link,
                                datetime.now().isoformat(timespec="seconds")
                            )
                        )

                        conn.execute(
                            """UPDATE candidates
                            SET review_date=?, review_time=?, meeting_link=?, status=?
                            WHERE id=?""",
                            (
                                str(next_date),
                                str(next_time),
                                next_link,
                                "Feedback sent / next review scheduled",
                                selected_id
                            )
                        )

                        conn.commit()
                        st.success(
                            "Feedback saved. The next review is scheduled for the future."
                        )

            with b2:
                if st.button("Send feedback email (requires SMTP setup)", key=f"send_feedback_{selected_id}_{prior_count}"):
                    ok, msg = send_email(candidate['email'], f"Review {prior_count + 1} feedback: {candidate['task_title']}", feedback_body)
                    (st.success if ok else st.warning)(msg)
            st.download_button("Download feedback as TXT", data=feedback_body, file_name=f"candidate_{selected_id}_review_{prior_count + 1}_feedback.txt", mime="text/plain")
        st.divider()
        st.markdown("#### Mark process complete")
        if st.button("Mark candidate review process complete", key=f"complete_{selected_id}"):
            conn.execute("UPDATE candidates SET status='Completed' WHERE id=?", (selected_id,))
            conn.commit()
            st.success("Candidate marked as completed. Refresh the page to see the updated status.")

with tab_history:
    st.subheader("Candidate and review history")
    all_candidates = conn.execute("SELECT * FROM candidates ORDER BY id DESC").fetchall()
    if not all_candidates:
        st.info("No candidates yet. Add one in Assign & Explain.")
    else:
        for cand in all_candidates:
            with st.expander(f"#{cand['id']} · {cand['name']} — {cand['task_title']} | {cand['status']}"):
                st.write(f"**Email:** {cand['email']}")
                st.write(f"**Current review schedule:** {cand['review_date']} at {cand['review_time']}")
                st.write(f"**Meeting link:** {cand['meeting_link'] or 'Not provided'}")
                st.write("**Task description:**")
                st.write(cand['task_description'])
                reviews = conn.execute("SELECT * FROM reviews WHERE candidate_id=? ORDER BY review_number", (cand['id'],)).fetchall()
                if not reviews:
                    st.caption("No saved reviews yet.")
                for rev in reviews:
                    st.markdown(f"**Review round {rev['review_number']} · {rev['created_at']}**")
                    st.write(f"Submission: {rev['submission_name'] or 'Pasted text'}")
                    st.write(f"Next review: {rev['next_review_date']} at {rev['next_review_time']}")
                    st.markdown(rev['feedback'])
                    st.divider()

st.divider()
st.caption("ReviewPilot AI is an assistant, not an automatic pass/fail decision-maker. Reviewers should verify findings before sending feedback.")

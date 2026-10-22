# ❓ FAQ & Troubleshooting Guide

Common questions, root causes, and solutions for deploying, configuring, and using **EasyExam**.

<p align="center"><a href="FAQ.md">English</a> · <a href="FAQ.zh-CN.md">简体中文</a></p>

---

## 🚀 Deployment & Runtime

### Q1: Failed to install FPK package or start service on fnOS (Feiniu NAS)?
* **Diagnosis**:
  1. Port conflict: Default ports are `8080`/`3000` (frontend) and `8000` (backend). Adjust them in your environment variables or compose manifest if occupied.
  2. Data permissions: Ensure the mounted volume directory (e.g., `/vol1/1000/docker/easy-exam/data`) has read/write permissions for the application user.
* **Resolution**:
  - Refer to `docs/FNOS_FPK_GUIDE.md` for lifecycle hooks and compose configuration details.

### Q2: `UnicodeDecodeError: 'gbk' codec can't decode...` on Windows?
* **Diagnosis**: Windows console defaults to GBK encoding.
* **Resolution**: Set UTF-8 encoding in PowerShell before running scripts: `$OutputEncoding = [System.Text.UTF8Encoding]::new()`. Python files enforce `encoding="utf-8"`.

---

## 📚 Question Banks & Practice

### Q3: PDF parsing misses questions or formats incorrectly?
* **Diagnosis**: Inconsistent layouts, two-column formats, or pure scanned image PDFs.
* **Resolution**:
  1. Prefer searchable text-based PDFs over image scans (scanned files must be OCR processed first).
  2. Standard questions should have prefixes like `1.` or `2.` and options like `A.` or `B.` on separate lines.
  3. Failed import batches are recorded in an audit preview; transactions are atomic and never leave half-imported dirty state.

### Q4: What is FSRS and how should I select Again / Hard / Good / Easy?
* **Explanation**: FSRS (Free Spaced Repetition Scheduler) is a modern memory algorithm superior to legacy SM-2:
  - **Again**: Complete lapse or incorrect answer; schedules immediate review.
  - **Hard**: Correct but recalled with significant difficulty.
  - **Good**: Normal correct recall; standard interval growth.
  - **Easy**: Mastered; substantially extends review intervals.
* **Note**: System captures memory snapshot prior to rating to prevent double-scheduling re-entrancy.

### Q5: Why can't I edit a question while an exam is running? Is that the same as a multiple-choice save failure?
* **No, they are different**: the first means "temporarily locked, try again later"; the second means "the question content is invalid and must be corrected".

**1. Active-exam lock (HTTP 403 / error code `EXAM_ACTIVE_PROTECTED`)**
* **When it triggers**: any user has an unfinished mock-exam session on that bank and the session drew the question you are trying to change. There is no administrator bypass — a bank administrator is rejected exactly the same way.
* **What you will see**: the bank management page shows a "Cannot edit during active exam" read-only banner and Edit turns into a read-only View. The server refuses to save a new version for questions actually drawn by that exam, and batch imports using the `merge` strategy against those questions also return 403.
* **What to do next**: ask the person sitting the exam to submit it, or have them choose "Abandon Session" in the "In-Progress Sessions" list on the home page, then reload the management page and retry the edit. A timed exam stops blocking writes to those questions once the time limit plus a roughly 60-second grace period has passed, but the read-only banner only clears after the session is submitted or abandoned.

**2. Multiple-choice content validation failure (HTTP 400 / error code `HTTP_400`)**
* Unrelated to exams; retrying will not help, the content must be fixed first. Current constraints:
  1. At least 2 options, and at least 2 of them must carry a key (options without a key are accepted);
  2. Option keys must be unique;
  3. At least 2 distinct correct answers;
  4. Answers must be existing option keys (option text is also accepted and converted to its key). Separate multiple answers with commas, semicolons or spaces, or write them together (e.g. `AB`).

---

## 🤖 AI Tutor & Localization

### Q6: How to configure local Ollama or cloud LLMs?
* **Configuration**: In system settings or `.env`:
  - `AI_API_BASE`: e.g., `http://localhost:11434/v1` (Ollama) or `https://api.deepseek.com/v1`
  - `AI_API_KEY`: Model provider API key
  - `AI_MODEL_NAME`: e.g., `deepseek-chat` or `qwen2.5:7b`
* **Offline Resilience**: If AI services are unreachable or unconfigured, core offline practice and official explanations remain 100% operational.

### Q7: How to switch interface language and dark mode?
* **Action**: Click the language toggle (`中/EN`) or theme toggle (`Light/Dark`) in the top navigation bar.
* **Zero Flash**: Stored in local storage and applied directly to `document.documentElement` before hydration, preventing white flash on dark mode reload.

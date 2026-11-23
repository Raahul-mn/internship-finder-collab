# Contributing Guidelines

Welcome to **InternShip Finder**. To keep our 3-member collaborative workflow clean, conflict-free, and easy to audit, every teammate must follow these repository rules.

---

## 1. Branching Strategy

- **`main`** is the protected integration branch. Never push feature commits directly to `main`.
- Always create and push work to your assigned feature branch split from `main`:
  - **Member 1 (API & Core):** `feature/api-integration`
  - **Member 2 (Frontend & UI):** `feature/frontend-ui`
  - **Member 3 (Backend & Database):** `feature/backend-database`

---

## 2. Module Ownership (Zero-Conflict Rule)

Modify and stage **only** the files assigned to your role so all three branches merge into `main` without conflicts:

- **Member 1 (`feature/api-integration`):**
  - `app.py`
  - `resume_parser.py`
  - `gemini_service.py`
  - `tests/test_internships.py`
  - Root documentation (`README.md`, `CONTRIBUTING.md`)
- **Member 2 (`feature/frontend-ui`):**
  - `static/` assets (CSS and media)
  - `templates/` (all 13 Jinja2 HTML views)
- **Member 3 (`feature/backend-database`):**
  - `database.py`
  - `validators.py`
  - `internship_listings.py`
  - `tests/test_bookmarks.py`

---

## 3. Commit Standards & Limits

- **Commit Cap:** Bundle each day's assigned modules into **1 atomic commit per day** (maximum **4 commits per member** across the cycle).
- **Conventional Commit Prefixes:**
  - `feat:` — New features or modules
  - `fix:` — Bug fixes, encoding corrections, or configuration updates
  - `test:` — Automated `pytest` test cases
  - `docs:` — Documentation updates (`README.md`, `CONTRIBUTING.md`)
  - `chore:` — Initial repository setup and tooling
- **Excluded Files:** Never stage or commit `.env`, `venv/`, `__pycache__/`, `.pytest_cache/`, or local SQLite database files (`instance/*.db`).

---

## 4. Testing & Pull Request Workflow

1. **Verify Locally Before Opening a PR:**
   - Run `pytest -v` in your activated virtual environment and confirm all tests pass.
   - Confirm `requirements.txt` remains UTF-8 encoded without Windows-specific packages (`pywin32`).
2. **Open a Pull Request on Day 3:**
   - Target **`base: main`** from your feature branch (`compare: feature/<your-branch>`).
   - Provide a clear summary of the modules added across your commits.
3. **Peer Review & Merge:**
   - Request a review from a teammate—do not merge your own Pull Request.
   - Leave feature branches intact after merging into `main` so the repository's **Insights → Network** graph preserves the full branching tree.
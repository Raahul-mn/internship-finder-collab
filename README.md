# InternShip Finder

AI-powered internship matching platform built with **Python**, **Flask**, **SQLite**, and the **Google Gemini API**. InternShip Finder analyzes a student's academic background, technical skills, completed projects, uploaded resume text, and location/stipend preferences to generate calibrated internship recommendations across Tier 1 global tech firms, Tier 2 product unicorns, and Tier 3 startups.

**Live Demo:** [https://internship-finder-demo.onrender.com](https://internship-finder-demo.onrender.com)

---

## Key Features

- **Core Routing & Role-Based Authentication (`app.py`):** Secure session management with separate registration, login, and protected dashboards for **Students** and **Administrators**.
- **Automated Resume Parsing (`resume_parser.py`):** Extracts structured skills, project highlights, and academic details from uploaded student resumes to enrich profile matching.
- **Gemini 2.5 Flash AI Matchmaker (`gemini_service.py`):** Evaluates candidate readiness against real-world hiring criteria, returning calibrated match scores, company tier classifications, actionable skill-gap feedback, and an automatic rule-based fallback if API quotas are reached.
- **Comprehensive Student Profiling:** Tracks college/university, CGPA or percentage, degree and branch, course duration, current/target semesters, skills, projects, preferred city, and expected stipend.
- **Internship Catalog & Duplicate-Safe Bookmarks:** Allows students to browse curated listings, inspect role requirements, and bookmark target opportunities.
- **Admin Management Portal:** Enables administrators to create, update, and manage internship listings across the platform.

---

## Tech Stack

- **Backend:** Python 3, Flask, Gunicorn
- **Database:** SQLite3
- **AI Engine:** Google Gemini API (`gemini-2.5-flash` via `google-genai`)
- **Frontend:** HTML5, CSS3, Jinja2 Templates
- **Testing:** `pytest`

---

## Project Structure

```text
internship-finder-collab/
├── app.py                     # Main Flask application, routes, and session handling
├── gemini_service.py          # Gemini 2.5 Flash AI matching engine & smart fallback
├── resume_parser.py           # Resume text extraction and skill parsing module
├── database.py                # SQLite schema initialization and query helpers
├── validators.py              # Form input and academic metric validation
├── internship_listings.py     # Curated internship dataset and tier metadata
├── requirements.txt           # Production Python dependencies (UTF-8)
├── .env.example               # Environment variable template
├── README.md                  # Project documentation
├── CONTRIBUTING.md            # Team branching and commit workflow rules
├── static/                    # CSS stylesheets and frontend assets
├── templates/                 # Jinja2 HTML templates (student, admin, auth views)
└── tests/                     # Automated pytest test suites
    ├── test_internships.py    # Core routing, profile, and AI recommendation tests
    └── test_bookmarks.py      # Bookmarking and database persistence tests
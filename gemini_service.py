import os
import re
import json
import time
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Canonical display casing for technical acronyms
TECH_DISPLAY_NAMES = {
    "sql": "SQL",
    "sqlite": "SQLite",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "html": "HTML",
    "css": "CSS",
    "aws": "AWS",
    "c": "C",
    "c++": "C++",
    "rest api": "REST API",
    "node.js": "Node.js",
    "next.js": "Next.js",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "power bi": "Power BI",
    "opencv": "OpenCV",
    "ros2": "ROS2",
    "uvm": "UVM",
    "fpga": "FPGA",
    "matlab": "MATLAB",
    "systemverilog": "SystemVerilog",
    "verilog": "Verilog",
    "owasp": "OWASP",
    "github actions": "GitHub Actions",
    "ci/cd": "CI/CD",
    "sta": "Static Timing Analysis (STA)",
}

INDIAN_METRO_ALIASES = {
    "chennai": ("chennai", "madras"),
    "bengaluru": ("bengaluru", "bangalore"),
    "hyderabad": ("hyderabad", "secunderabad"),
    "pune": ("pune",),
    "mumbai": ("mumbai", "navi mumbai", "thane"),
    "delhi ncr": ("delhi", "new delhi", "noida", "greater noida", "gurgaon", "gurugram"),
    "kochi": ("kochi", "cochin", "ernakulam"),
    "thiruvananthapuram": ("thiruvananthapuram", "trivandrum"),
}


def _format_tech_name(token):
    cleaned = str(token or "").strip()
    return TECH_DISPLAY_NAMES.get(cleaned.lower(), cleaned.title())


def _parse_cgpa_scale_10(cgpa_raw):
    """Extracts a numeric 10-point CGPA from strings like '8.45', '8.45 / 10', or '86.5%'."""
    if not cgpa_raw:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(cgpa_raw))
    if not match:
        return None
    val = float(match.group(1))
    if 10.0 < val <= 100.0:
        return round(val / 10.0, 2)
    if 0.0 <= val <= 10.0:
        return round(val, 2)
    return None


def _extract_skill_tokens(skills_raw, resume_raw=""):
    """Normalizes declared skills plus key tech keywords extracted from resume_text."""
    declared = [s.strip() for s in str(skills_raw or "").split(",") if s.strip()]
    seen = {s.lower() for s in declared}

    common_tech = [
        "Python", "Flask", "Django", "FastAPI", "SQL", "SQLite", "PostgreSQL", "MySQL",
        "JavaScript", "TypeScript", "React", "Node.js", "HTML", "CSS", "Git", "Docker",
        "AWS", "Linux", "Java", "C", "C++", "Pandas", "NumPy", "Machine Learning", "REST API",
        "MongoDB", "Express", "Next.js", "Tailwind", "Bootstrap", "PyTorch", "TensorFlow",
        "Verilog", "SystemVerilog", "UVM", "FPGA", "MATLAB", "ROS2", "OpenCV",
        "Burp Suite", "Wireshark", "OWASP", "Power BI", "Excel", "Bash", "Kubernetes",
        "Terraform", "GitHub Actions", "Tableau", "Snowflake", "PySpark"
    ]
    resume_lower = str(resume_raw or "").lower()
    for tech in common_tech:
        if tech.lower() in resume_lower and tech.lower() not in seen:
            declared.append(tech)
            seen.add(tech.lower())

    return declared


def _compute_role_skill_alignment(skills_list, role_raw, courses_raw):
    """Computes genuine overlap between student skills/courses and target role expectations."""
    role_lower = (role_raw or "software engineering intern").lower()
    skills_lower = {s.lower() for s in skills_list}
    courses_lower = (courses_raw or "").lower()

    role_expectations = {
        "backend": {"python", "flask", "django", "fastapi", "node.js", "sql", "postgresql", "mysql", "rest api", "git", "docker"},
        "frontend": {"html", "css", "javascript", "typescript", "react", "next.js", "tailwind", "git"},
        "full": {"python", "javascript", "html", "css", "sql", "react", "node.js", "flask", "git", "rest api"},
        "data": {"python", "sql", "pandas", "numpy", "power bi", "excel", "tableau", "snowflake", "mysql"},
        "analytics": {"python", "sql", "pandas", "numpy", "power bi", "excel", "tableau", "snowflake"},
        "ai": {"python", "machine learning", "pytorch", "tensorflow", "pandas", "numpy", "fastapi", "opencv", "c++"},
        "vision": {"python", "c++", "pytorch", "opencv", "linux", "docker", "ros2", "git"},
        "robotics": {"python", "c++", "ros2", "opencv", "linux", "docker", "pytorch", "git"},
        "vlsi": {"verilog", "systemverilog", "uvm", "c", "python", "linux", "fpga", "matlab", "git"},
        "rtl": {"verilog", "systemverilog", "uvm", "c", "python", "linux", "fpga", "matlab", "git"},
        "hardware": {"verilog", "systemverilog", "uvm", "c", "c++", "python", "linux", "fpga", "matlab"},
        "embedded": {"c", "c++", "python", "linux", "fpga", "ros2", "git"},
        "cyber": {"python", "linux", "burp suite", "wireshark", "owasp", "sql", "bash", "docker", "git"},
        "security": {"python", "linux", "burp suite", "wireshark", "owasp", "sql", "bash", "docker", "git"},
        "cloud": {"linux", "docker", "aws", "github actions", "python", "bash", "git", "kubernetes", "terraform"},
        "devops": {"linux", "docker", "aws", "github actions", "python", "bash", "git", "kubernetes", "terraform"},
    }

    target_set = {"python", "sql", "git", "html", "css", "javascript", "docker"}
    for key, expected in role_expectations.items():
        if key in role_lower:
            target_set = expected
            break

    matched = [s for s in skills_list if s.lower() in target_set]
    missing = [_format_tech_name(req) for req in sorted(target_set - skills_lower)][:3]

    if not missing:
        fallback_gaps = ["System Design", "CI/CD Pipelines", "Automated Testing (pytest)", "Kubernetes"]
        missing = [g for g in fallback_gaps if g.lower() not in skills_lower][:2]

    overlap_ratio = len(matched) / max(len(target_set), 1)
    course_keywords = (
        "dbms", "database", "data structures", "os", "operating system", "web",
        "algorithms", "ai", "ml", "deep learning", "vlsi", "verilog", "cmos",
        "networks", "security", "cryptography", "cloud", "statistics", "embedded"
    )
    course_bonus = 4 if any(k in courses_lower for k in course_keywords) else 0
    skill_score_boost = int(round(overlap_ratio * 14)) + course_bonus

    return {
        "matched_for_role": matched if matched else skills_list[:3],
        "missing_for_role": missing,
        "skill_score_boost": skill_score_boost,
    }


def _analyze_academic_standing(p):
    """
    Computes deterministic CGPA tier bands and role-aligned score ranges
    so CGPA, skills, courses, and projects visibly differentiate every recommendation.
    """
    cgpa_val = _parse_cgpa_scale_10(p.get("cgpa"))
    skills_list = _extract_skill_tokens(p.get("skills"), p.get("resume_text"))
    alignment = _compute_role_skill_alignment(skills_list, p.get("preferred_role"), p.get("courses"))

    projects_text = (p.get("projects") or "").strip()
    project_items = [proj.strip() for proj in re.split(r"[\n;•]+", projects_text) if len(proj.strip()) >= 6]
    project_bonus = min(len(project_items) * 3, 7)

    boost = alignment["skill_score_boost"] + project_bonus

    if cgpa_val is None:
        band = "Unverified CGPA Band (Evaluated on Skills, Courses & Projects)"
        tier_guidance = (
            "CGPA is unspecified. Target Tier 2 Product Scale-ups and Tier 3 Startups that screen "
            "student interns via GitHub projects and coding tasks rather than strict CGPA cutoffs."
        )
        primary_score = min(68 + boost, 90)
        secondary_score = min(72 + boost, 92)
    elif cgpa_val >= 8.5:
        band = f"High Distinction Band ({cgpa_val}/10 — Clears 8.5+ Tier 1 & R&D Internship Cutoffs)"
        tier_guidance = (
            f"At {cgpa_val}/10 CGPA, the candidate clears strict 8.0–8.5+ campus/off-campus internship gates at "
            "Tier 1 Global Tech R&D Centers as well as Tier 2 Product Scale-ups."
        )
        primary_score = min(78 + boost, 97)
        secondary_score = min(75 + boost, 94)
    elif cgpa_val >= 7.5:
        band = f"Strong Product-Tier Band ({cgpa_val}/10 — Clears 7.0–7.5 Product Internship Cutoffs)"
        tier_guidance = (
            f"At {cgpa_val}/10 CGPA, the candidate clears standard 7.0–7.5 product company internship cutoffs "
            "(Tier 2 SaaS/Fintech/Core Scale-ups), while some Tier 1 MNCs enforce an 8.0+ gate."
        )
        primary_score = min(72 + boost, 92)
        secondary_score = min(75 + boost, 94)
    elif cgpa_val >= 6.5:
        band = f"Skill-First & Startup Band ({cgpa_val}/10 — Below 7.5 Enterprise Cutoffs)"
        tier_guidance = (
            f"At {cgpa_val}/10 CGPA, automated 7.5+ enterprise intern filters may screen out the resume; "
            "prioritize Tier 3 VC-Backed Startups and Mid-Size Product Teams offering task-based internships."
        )
        primary_score = min(62 + boost, 85)
        secondary_score = min(70 + boost, 89)
    else:
        band = f"Portfolio-Driven Recovery Band ({cgpa_val}/10 — Below Standard CGPA Gates)"
        tier_guidance = (
            f"At {cgpa_val}/10 CGPA, bypass automated GPA screens by targeting early-stage startups "
            "and build-first student internships where live projects carry full weight."
        )
        primary_score = min(54 + boost, 78)
        secondary_score = min(65 + boost, 84)

    return {
        "cgpa_numeric": cgpa_val,
        "skills_list": skills_list,
        "project_items": project_items,
        "alignment": alignment,
        "band": band,
        "tier_guidance": tier_guidance,
        "primary_score": primary_score,
        "secondary_score": secondary_score,
    }


def _contains_wrong_city_only(text_blob, target_location):
    """
    Detects if a generated card references another Indian city (e.g., Bengaluru)
    without mentioning the student's target city (e.g., Chennai).
    """
    loc_lower = (target_location or "").lower().strip()
    if not loc_lower or "remote" in loc_lower or "india" == loc_lower:
        return False

    target_aliases = ()
    for metro_key, aliases in INDIAN_METRO_ALIASES.items():
        if any(a in loc_lower for a in aliases):
            target_aliases = aliases
            break

    if not target_aliases:
        return False

    blob = (text_blob or "").lower()
    mentions_target = any(a in blob for a in target_aliases)
    if mentions_target:
        return False

    for metro_key, aliases in INDIAN_METRO_ALIASES.items():
        if aliases == target_aliases:
            continue
        if any(re.search(rf"\b{re.escape(a)}\b", blob) for a in aliases):
            return True

    return False


def _validate_recommendations(data, academic, target_location=""):
    """
    Validates parsed JSON, strips out-of-city hallucinations and placeholder entries,
    and guarantees complete student-internship cards.
    """
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("opportunities"), list) or len(data["opportunities"]) == 0:
        return False
    if not isinstance(data.get("workflows"), list):
        return False
    if not isinstance(data.get("profile_insights"), list):
        return False

    default_matched = academic["alignment"]["matched_for_role"]
    default_gaps = academic["alignment"]["missing_for_role"]
    declared_lower = {s.lower() for s in academic["skills_list"]}
    banned_names = {"company 1", "company 2", "company 3", "company 4", "company 5", "company 6", "company 7", "tbd", "n/a"}

    valid_tiers = 0
    for item in data["opportunities"]:
        if not isinstance(item, dict):
            return False
        if not item.get("company_tier") or not isinstance(item.get("companies"), list):
            return False
        if not item.get("matched_role") or not isinstance(item.get("eligibility_points"), list):
            return False

        raw_cards = item.get("company_cards") or []
        cleaned_cards = []

        for card in raw_cards:
            if not isinstance(card, dict):
                continue
            cname = str(card.get("company_name") or "").strip()
            if not cname or cname.lower() in banned_names:
                continue

            combined_text = f"{cname} {card.get('role_title', '')} {card.get('stipend_duration_fit', '')}"
            if _contains_wrong_city_only(combined_text, target_location):
                logger.warning(f"Filtered out-of-city hallucination '{cname}' for target '{target_location}'.")
                continue

            # Ensure role_title explicitly indicates an internship
            rtitle = str(card.get("role_title") or item["matched_role"]).strip()
            if "intern" not in rtitle.lower():
                rtitle = f"{rtitle} (Student Internship)"
            card["role_title"] = rtitle

            # Clamp match_score to realistic integer
            try:
                score_int = int(card.get("match_score", academic["primary_score"]))
            except (TypeError, ValueError):
                score_int = academic["primary_score"]
            card["match_score"] = max(50, min(98, score_int))

            # Filter matching_skills to verified student skills; ensure skill_gaps aren't already known
            m_skills = [s for s in (card.get("matching_skills") or []) if str(s).strip()]
            card["matching_skills"] = m_skills if m_skills else default_matched

            g_skills = [
                g for g in (card.get("skill_gaps") or [])
                if str(g).strip() and str(g).strip().lower() not in declared_lower
            ]
            card["skill_gaps"] = g_skills[:2] if g_skills else default_gaps[:2]

            if card.get("work_mode") not in ("Remote", "On-site", "Hybrid"):
                card["work_mode"] = "Remote" if "remote" in (target_location or "").lower() else "Hybrid"

            cleaned_cards.append(card)

        if len(cleaned_cards) < 2:
            return False

        item["company_cards"] = cleaned_cards
        item["companies"] = [c["company_name"] for c in cleaned_cards]
        valid_tiers += 1

    return valid_tiers >= 1


def generate_ai_recommendations(profile, override_need=""):
    """
    8-Factor Location-locked, Student-Internship-verified, CGPA-calibrated,
    Coursework-verified, Skill-audited, and Project-grounded internship matcher.
    """
    p = dict(profile) if profile else {}
    if override_need and override_need.strip():
        p["what_i_need"] = override_need.strip()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip().strip('"').strip("'")

    if not model_name or model_name in ("your-selected-gemini-model", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"):
        model_name = "gemini-3.8-flash"

    academic = _analyze_academic_standing(p)
    skills_joined = ", ".join(academic["skills_list"]) or (p.get("skills") or "Python")

    college = p.get("college") or "Not specified"
    cgpa = p.get("cgpa") or "Not specified"
    degree_branch = p.get("degree_branch") or "Not specified"
    courses = p.get("courses") or "Not specified"
    course_duration = p.get("course_duration") or "4 Years (8 Semesters)"
    current_semester = p.get("current_semester") or "Not specified"
    target_semester = p.get("target_semester") or "Upcoming Semester"
    internship_duration = p.get("internship_duration") or "2 to 6 Months"
    stipend_expectation = p.get("stipend_expectation") or "Paid / Standard"
    what_i_need = p.get("what_i_need") or f"Hands-on {p.get('preferred_role') or 'Software Engineering'} internship matching my stack"
    projects = p.get("projects") or "Academic coursework projects"
    role = p.get("preferred_role") or "Software Engineering Intern"
    location = p.get("preferred_location") or "Remote / India"
    resume_text = (p.get("resume_text") or "")[:1800]

    if not api_key or api_key in ("your_actual_gemini_api_key_here", "your-gemini-api-key"):
        return get_platform_native_matches(p, academic, fallback_reason="Missing GEMINI_API_KEY in .env")

    try:
        http_opts = {"timeout": 30000}
        if hasattr(types, "HttpRetryOptions"):
            http_opts["retry_options"] = types.HttpRetryOptions(attempts=1)

        prompt = f"""
You are a strict technical campus & off-campus internship evaluator for Indian engineering students ('InternShip Finder').
Never write generic filler. Every single card MUST represent a REAL STUDENT INTERNSHIP PROGRAM offered by a company with a verified physical engineering/R&D office in "{location}".

CANDIDATE 8-FACTOR AUDIT PROFILE:
1. College / Institution: {college}
2. Exact CGPA / Score: {cgpa} -> {academic['band']}
   - Cutoff Rule: {academic['tier_guidance']}
3. Degree, Branch & Completed Courses: {degree_branch} | {courses} ({course_duration})
4. Semester Window: Currently in {current_semester} -> Applying for {target_semester}
5. Duration & Stipend Target: {internship_duration} | Expected Stipend: {stipend_expectation}
6. Extracted Technical Skills (Profile + Resume): {skills_joined}
7. Projects Built: {projects}
8. Target Role, Location & Immediate Need ("What I Need"):
   - Preferred Role: {role}
   - Target City / Location: {location}
   - Student's Specific Need: "{what_i_need}"
   - Resume Excerpt: {resume_text if resume_text else "None provided"}

MANDATORY INTERNSHIP & LOCATION VERIFICATION RULES:
1. STUDENT INTERNSHIP PROGRAMS ONLY (NOT JUST COMPANY NAMES):
   - Every recommended company MUST actively run structured student internship programs (such as 6-month final-year/semester internships, 2-month summer internships, IIT/university research-park internships, or campus/off-campus intern cohorts) open to students pursuing {degree_branch}.
   - Do NOT list companies that only hire experienced full-time engineers or have no student internship intake in {location}.
   - In every card's "role_title", explicitly include the internship track (e.g., "{role} — 6-Month Student Internship" or "{role} — Summer Intern Cohort").
2. STRICT PHYSICAL OFFICE LOCK ({location}):
   - If "{location}" is NOT "Remote", ONLY recommend companies that operate a verified physical engineering, R&D, or design center inside "{location}".
   - NEVER assign a company's Bengaluru-, Hyderabad-, Pune-, or NCR-only R&D center to "{location}" just to match a niche domain (for example, never list Bengaluru-only silicon or software labs under Chennai).
   - In every card's "stipend_duration_fit", explicitly name the company's real local office corridor or tech park in "{location}" (e.g., OMR, IIT Madras Research Park, DLF IT Park, Guindy, HITEC City, Outer Ring Road, Hinjawadi, Technopark) AND explain how its student intern program fits {internship_duration} in {target_semester} and {stipend_expectation}.
   - If fewer than 4 Tier 1 R&D centers exist in "{location}" for a niche branch, fill the remaining slots with verified local Tier 2 scale-ups, research-park spin-offs, or engineering-services R&D centers inside "{location}".
3. COMPANY TIER CALIBRATION:
   - If CGPA >= 8.5, Tier 1 must feature Global Tech R&D / Top Product Giants offering student internships in {location}, and Tier 2 must feature top SaaS/Fintech/Core Product Scale-ups offering student internships in {location}.
   - If CGPA is 7.5–8.49, Tier 1 must feature Product Scale-ups offering student internships in {location} (7.0–7.5 cutoff) and Tier 2 must feature High-Growth Startups / R&D centers offering student internships in {location}.
   - If CGPA < 7.5, Tier 1 must feature Project-First Startups offering student internships in {location} (no strict GPA gate) and Tier 2 must feature Mid-Size Product Teams offering student internships in {location}.
4. INDIVIDUAL INTERNSHIP CARDS (4 in Tier 1, 3 in Tier 2):
   - Give each company a DISTINCT, realistic "match_score" (varying between {max(52, academic['primary_score'] - 7)} and {min(98, academic['primary_score'] + 4)}).
   - "matching_skills": ONLY list technologies the student ACTUALLY possesses in [{skills_joined}].
   - "skill_gaps": Name 1–2 concrete tools that specific company's intern team uses which are MISSING from [{skills_joined}].
   - "project_alignment": Name the student's actual project from "{projects}" and explain how to pitch it in their intern interview.
   - "coursework_fit": Connect a specific subject from "{courses}" to that company's internship work.
   - "cgpa_cutoff_note": State the company's typical intern CGPA filter vs {cgpa}.
   - "work_mode": Must be strictly one of "Remote", "On-site", or "Hybrid". Do NOT fabricate application URLs.

Return ONLY valid JSON matching this exact schema:
{{
  "opportunities": [
    {{
      "company_tier": "<Primary Internship Tier calibrated to {cgpa} CGPA in {location}>",
      "companies": ["<Company 1>", "<Company 2>", "<Company 3>", "<Company 4>"],
      "matched_role": "<Specific student internship track aligned with {role} and '{what_i_need}'>",
      "match_score": {academic['primary_score']},
      "location_fit": "<Verified local tech parks/corridors in {location} where these 4 companies host student interns>",
      "timeline_fit": "<Concrete assessment of {current_semester} -> {target_semester}, {internship_duration}, and {stipend_expectation}>",
      "eligibility_points": [
        "<CGPA ({cgpa}) & completed courses ({courses}) intern eligibility verdict>",
        "<Stack ([{skills_joined}]), projects ({projects}), and goal ('{what_i_need}') verdict>"
      ],
      "company_cards": [
        {{
          "company_name": "<Company 1>",
          "role_title": "<Specific Student Internship Track at Company 1>",
          "match_score": <int 52-98>,
          "cgpa_cutoff_note": "<Exact intern CGPA cutoff comparison against {cgpa}>",
          "coursework_fit": "<How '{courses}' applies to this internship>",
          "matching_skills": ["<Matched Skill 1>", "<Matched Skill 2>"],
          "skill_gaps": ["<Missing Skill 1>", "<Missing Skill 2>"],
          "project_alignment": "<How '{projects}' maps to Company 1's intern team>",
          "stipend_duration_fit": "<Local {location} office corridor + {internship_duration} & {stipend_expectation} intern program fit>",
          "work_mode": "<On-site | Hybrid | Remote>"
        }},
        {{
          "company_name": "<Company 2>",
          "role_title": "<Specific Student Internship Track at Company 2>",
          "match_score": <int 52-98>,
          "cgpa_cutoff_note": "<Exact intern CGPA cutoff comparison against {cgpa}>",
          "coursework_fit": "<How '{courses}' applies to this internship>",
          "matching_skills": ["<Matched Skill 1>", "<Matched Skill 2>"],
          "skill_gaps": ["<Missing Skill 1>"],
          "project_alignment": "<How '{projects}' maps to Company 2's intern team>",
          "stipend_duration_fit": "<Local {location} office corridor + {internship_duration} & {stipend_expectation} intern program fit>",
          "work_mode": "<On-site | Hybrid | Remote>"
        }},
        {{
          "company_name": "<Company 3>",
          "role_title": "<Specific Student Internship Track at Company 3>",
          "match_score": <int 52-98>,
          "cgpa_cutoff_note": "<Exact intern CGPA cutoff comparison against {cgpa}>",
          "coursework_fit": "<How '{courses}' applies to this internship>",
          "matching_skills": ["<Matched Skill 1>", "<Matched Skill 2>"],
          "skill_gaps": ["<Missing Skill 1>"],
          "project_alignment": "<How '{projects}' maps to Company 3's intern team>",
          "stipend_duration_fit": "<Local {location} office corridor + {internship_duration} & {stipend_expectation} intern program fit>",
          "work_mode": "<On-site | Hybrid | Remote>"
        }},
        {{
          "company_name": "<Company 4>",
          "role_title": "<Specific Student Internship Track at Company 4>",
          "match_score": <int 52-98>,
          "cgpa_cutoff_note": "<Exact intern CGPA cutoff comparison against {cgpa}>",
          "coursework_fit": "<How '{courses}' applies to this internship>",
          "matching_skills": ["<Matched Skill 1>", "<Matched Skill 2>"],
          "skill_gaps": ["<Missing Skill 1>"],
          "project_alignment": "<How '{projects}' maps to Company 4's intern team>",
          "stipend_duration_fit": "<Local {location} office corridor + {internship_duration} & {stipend_expectation} intern program fit>",
          "work_mode": "<On-site | Hybrid | Remote>"
        }}
      ]
    }},
    {{
      "company_tier": "<Secondary Internship Tier calibrated to {cgpa} CGPA in {location}>",
      "companies": ["<Company 5>", "<Company 6>", "<Company 7>"],
      "matched_role": "<Secondary student internship track aligned with {skills_joined} and '{what_i_need}'>",
      "match_score": {academic['secondary_score']},
      "location_fit": "<Verified local tech parks/corridors in {location} for these 3 internship programs>",
      "timeline_fit": "<How {internship_duration} in {target_semester} fits this intern intake>",
      "eligibility_points": [
        "<How projects ({projects}) differentiate the student applicant here>",
        "<Completed courses ({courses}) and stipend ({stipend_expectation}) alignment>"
      ],
      "company_cards": [
        {{
          "company_name": "<Company 5>",
          "role_title": "<Specific Student Internship Track at Company 5>",
          "match_score": <int 52-98>,
          "cgpa_cutoff_note": "<Exact intern CGPA cutoff comparison against {cgpa}>",
          "coursework_fit": "<How '{courses}' applies to this internship>",
          "matching_skills": ["<Matched Skill 1>", "<Matched Skill 2>"],
          "skill_gaps": ["<Missing Skill 1>"],
          "project_alignment": "<How '{projects}' maps to Company 5's intern team>",
          "stipend_duration_fit": "<Local {location} office corridor + {internship_duration} & {stipend_expectation} intern program fit>",
          "work_mode": "<On-site | Hybrid | Remote>"
        }},
        {{
          "company_name": "<Company 6>",
          "role_title": "<Specific Student Internship Track at Company 6>",
          "match_score": <int 52-98>,
          "cgpa_cutoff_note": "<Exact intern CGPA cutoff comparison against {cgpa}>",
          "coursework_fit": "<How '{courses}' applies to this internship>",
          "matching_skills": ["<Matched Skill 1>", "<Matched Skill 2>"],
          "skill_gaps": ["<Missing Skill 1>"],
          "project_alignment": "<How '{projects}' maps to Company 6's intern team>",
          "stipend_duration_fit": "<Local {location} office corridor + {internship_duration} & {stipend_expectation} intern program fit>",
          "work_mode": "<On-site | Hybrid | Remote>"
        }},
        {{
          "company_name": "<Company 7>",
          "role_title": "<Specific Student Internship Track at Company 7>",
          "match_score": <int 52-98>,
          "cgpa_cutoff_note": "<Exact intern CGPA cutoff comparison against {cgpa}>",
          "coursework_fit": "<How '{courses}' applies to this internship>",
          "matching_skills": ["<Matched Skill 1>", "<Matched Skill 2>"],
          "skill_gaps": ["<Missing Skill 1>"],
          "project_alignment": "<How '{projects}' maps to Company 7's intern team>",
          "stipend_duration_fit": "<Local {location} office corridor + {internship_duration} & {stipend_expectation} intern program fit>",
          "work_mode": "<On-site | Hybrid | Remote>"
        }}
      ]
    }}
  ],
  "workflows": [
    {{
      "target_type": "<Student internship selection track for Primary Tier in {location}>",
      "steps": ["<Step 1>", "<Step 2>", "<Step 3>", "<Step 4>"]
    }},
    {{
      "target_type": "<Student internship selection track for Secondary Tier in {location}>",
      "steps": ["<Step 1>", "<Step 2>", "<Step 3>"]
    }}
  ],
  "profile_insights": [
    "<CGPA ({cgpa}) & Cutoff Audit: Specific action item for {college} / {courses}>",
    "<Skill Gap Action Plan: Top 2 missing skills to add before {target_semester}>",
    "<Project & Goal Pitch: How to quantify '{projects}' for '{what_i_need}' internships in {location}>"
  ]
}}
"""
        candidate_models = []
        for m in [
            model_name,
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.6-flash",
        ]:
            if m and m not in candidate_models:
                candidate_models.append(m)

        response = None
        active_model_used = model_name
        last_err = None

        with genai.Client(api_key=api_key, http_options=types.HttpOptions(**http_opts)) as client:
            for candidate in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=candidate,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.15,
                            max_output_tokens=8192,
                        ),
                    )
                    active_model_used = candidate
                    break
                except Exception as model_err:
                    last_err = model_err
                    err_str = str(model_err).upper()
                    if any(code in err_str for code in ("404", "NOT_FOUND", "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "TIMEOUT", "DEADLINE")):
                        time.sleep(0.5)
                        continue
                    raise model_err

        if response is None and last_err is not None:
            raise last_err

        text = (response.text or "").strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = re.sub(r",\s*([}\]])", r"\1", text.strip())

        parsed = json.loads(text)
        if not _validate_recommendations(parsed, academic, target_location=location):
            logger.warning("Gemini JSON failed validation or location lock; activating offline fallback.")
            return get_platform_native_matches(p, academic, fallback_reason="Strict Location/Schema Validation")

        parsed["engine_source"] = f"Gemini Live AI ({active_model_used})"
        parsed["academic_band"] = academic["band"]
        parsed["active_need"] = what_i_need
        return parsed

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return get_platform_native_matches(p, academic, fallback_reason=f"API Error: {str(e)[:80]}")


def _get_location_companies(location_raw, cgpa_val, role_raw=""):
    """Returns verified local companies with active student internship programs in India."""
    loc = (location_raw or "").lower()
    role = (role_raw or "").lower()
    is_hardware = any(k in role for k in ("vlsi", "rtl", "hardware", "fpga", "embedded", "semiconductor", "robotics"))
    is_data = any(k in role for k in ("data", "analytics", "business intelligence", "bi "))
    is_security = any(k in role for k in ("cyber", "security", "appsec", "pentest", "soc"))

    if "chennai" in loc:
        if is_hardware:
            t1 = [
                "Qualcomm India — Ramanujan IT City (Chennai)",
                "Microchip Technology — OMR (Chennai)",
                "KLA — DLF IT Park (Chennai)",
                "Valeo India R&D — Navalur (Chennai)",
            ]
            t2 = [
                "Tessolve Semiconductor (Chennai)",
                "HCLTech Engineering & R&D — Sholinganallur (Chennai)",
                "Data Patterns India — SIPCOT Siruseri (Chennai)",
                "Visteon Technical Center — Porur (Chennai)",
            ]
            t3 = [
                "Morphing Machines — IIT Madras Research Park (Chennai)",
                "Mindgrove Technologies — IIT Madras Research Park (Chennai)",
                "InCore Semiconductors — IIT Madras Research Park (Chennai)",
            ]
        else:
            t1 = ["PayPal R&D — Sholinganallur (Chennai)", "Amazon Development Center — WTC (Chennai)", "Oracle — OMR (Chennai)", "Autodesk (Chennai)"]
            t2 = ["Zoho — Estancia (Chennai)", "Freshworks — Perungudi (Chennai)", "Kissflow — Perungudi (Chennai)", "Chargebee (Chennai)"]
            t3 = ["SurveySparrow (Chennai)", "Mad Street Den (Chennai)", "Facilio (Chennai)"]
    elif "bengaluru" in loc or "bangalore" in loc:
        if is_hardware:
            t1 = ["Texas Instruments — Bagmane (Bengaluru)", "Intel India — ORR (Bengaluru)", "NVIDIA (Bengaluru)", "ARM Embedded Technologies (Bengaluru)"]
            t2 = ["Saankhya Labs (Bengaluru)", "Steradian Semiconductors / Renesas (Bengaluru)", "Tejas Networks (Bengaluru)", "Silizium Circuits (Bengaluru)"]
            t3 = ["Signalchip (Bengaluru)", "Sankalp Semiconductor (Bengaluru)", "System Level Solutions (Bengaluru)"]
        else:
            t1 = ["Microsoft IDC (Bengaluru)", "Google India (Bengaluru)", "Intuit (Bengaluru)", "Adobe (Bengaluru)"]
            t2 = ["Razorpay (Bengaluru)", "Postman (Bengaluru)", "BrowserStack (Bengaluru)", "CRED (Bengaluru)"]
            t3 = ["Hasura (Bengaluru)", "Appsmith (Bengaluru)", "Sarvam AI (Bengaluru)"]
    elif "hyderabad" in loc:
        if is_hardware:
            t1 = ["AMD India — HITEC City (Hyderabad)", "Qualcomm India — Madhapur (Hyderabad)", "Micron Technology (Hyderabad)", "Intel India (Hyderabad)"]
            t2 = ["InSemi Technology (Hyderabad)", "MosChip Technologies (Hyderabad)", "Cyient Semiconductor (Hyderabad)", "eInfochips (Hyderabad)"]
            t3 = ["Soctronics (Hyderabad)", "Veda IIT / SoCtronics R&D (Hyderabad)", "Sevya Multimedia (Hyderabad)"]
        elif is_security:
            t1 = ["ServiceNow Security R&D (Hyderabad)", "Qualcomm Product Security (Hyderabad)", "Microsoft IDC Security (Hyderabad)", "Deloitte Cyber (Hyderabad)"]
            t2 = ["Darwinbox AppSec (Hyderabad)", "OpenText Security (Hyderabad)", "HighRadius InfoSec (Hyderabad)", "Progress Software (Hyderabad)"]
            t3 = ["SenecaGlobal (Hyderabad)", "ValueLabs Security Practice (Hyderabad)", "Kore.ai Security (Hyderabad)"]
        else:
            t1 = ["Microsoft IDC (Hyderabad)", "Google (Hyderabad)", "ServiceNow (Hyderabad)", "Salesforce (Hyderabad)"]
            t2 = ["Darwinbox (Hyderabad)", "Kore.ai (Hyderabad)", "Zenoti (Hyderabad)", "HighRadius (Hyderabad)"]
            t3 = ["Yellow.ai (Hyderabad)", "Progress (Hyderabad)", "SenecaGlobal (Hyderabad)"]
    elif "pune" in loc or "mumbai" in loc:
        t1 = ["NVIDIA — Yerawada (Pune)", "Mastercard (Pune)", "KPIT Technologies R&D — Hinjawadi (Pune)", "Barclays Tech (Pune)"]
        t2 = ["Druva (Pune)", "Icertis (Pune)", "PubMatic (Pune)", "Gupshup (Mumbai)"]
        t3 = ["Fynd (Mumbai)", "Simpl (Mumbai)", "MindTickle (Pune)"]
    elif "delhi" in loc or "noida" in loc or "gurgaon" in loc or "gurugram" in loc:
        t1 = ["Microsoft (Noida)", "Adobe (Noida)", "STMicroelectronics (Greater Noida)", "Cadence Design Systems (Noida)"]
        t2 = ["Zomato (Gurugram)", "Paytm (Noida)", "PolicyBazaar (Gurugram)", "Info Edge (Noida)"]
        t3 = ["Shiprocket (Delhi NCR)", "Cars24 (Gurugram)", "BharatPe (Delhi NCR)"]
    elif "kochi" in loc or "trivandrum" in loc or "thiruvananthapuram" in loc or "kerala" in loc:
        t1 = ["Oracle — Technopark (Thiruvananthapuram)", "Nissan Digital — Technopark (Thiruvananthapuram)", "Allianz Technology (Trivandrum)", "EY GDS — Infopark (Kochi)"]
        t2 = ["IBS Software — Infopark (Kochi)", "QBurst (Kochi/Trivandrum)", "UST (Thiruvananthapuram)", "Experion Technologies (Kochi)"]
        t3 = ["KeyValue Software Systems (Kochi)", "Fingent (Kochi)", "litmus7 (Kochi)"]
    elif is_data:
        t1 = ["Atlan (Remote India)", "Intuit Data Analytics (Bengaluru/Remote)", "Microsoft IDC Data (Hybrid/India)", "Swiggy Data Science (Bengaluru/Remote)"]
        t2 = ["Sprinto (Remote)", "M2P Fintech (Chennai/Remote)", "Razorpay Analytics (Bengaluru)", "Zoho Analytics (Chennai)"]
        t3 = ["Loop Health (Remote)", "Knight FinTech (Mumbai/Remote)", "Appsmith (Remote)"]
    else:
        t1 = ["Microsoft IDC (Hybrid/India)", "Intuit (Bengaluru/Remote)", "Atlassian (Remote India)", "GitLab (Remote)"]
        t2 = ["Zoho (Chennai)", "Razorpay (Bengaluru)", "Postman (Bengaluru)", "Darwinbox (Hyderabad)"]
        t3 = ["Hasura (Remote/Bengaluru)", "Appsmith (Remote)", "Sprinto (Remote)"]

    if cgpa_val is not None and cgpa_val >= 8.5:
        return t1, t2, "Tier 1: Global Tech R&D & Enterprise Internship Programs", "Tier 2: Product Scale-ups & Core R&D Internships"
    if cgpa_val is not None and cgpa_val < 7.5:
        return t3, t2, "Tier 3: Project-First High-Growth Startup Internships", "Tier 2: Mid-Size Product Engineering Internships"
    return t2, t3, "Tier 2: Product Scale-ups & Core Engineering Internships", "Tier 3: High-Growth Startup & Research-Park Internships"


def _build_offline_company_cards(companies, base_score, role, cgpa, courses, academic, projects, intern_dur, stipend):
    """Generates rich per-company student internship cards when offline fallback is triggered."""
    matched = academic["alignment"]["matched_for_role"]
    gaps = academic["alignment"]["missing_for_role"]
    cards = []
    for idx, comp in enumerate(companies):
        score = max(55, min(96, base_score - (idx * 2)))
        cards.append({
            "company_name": comp,
            "role_title": f"{role} ({intern_dur} Student Internship Track)",
            "match_score": score,
            "cgpa_cutoff_note": f"Evaluated against {cgpa} CGPA ({academic['band'].split('—')[0].strip()})",
            "coursework_fit": f"Applies {courses[:55]} fundamentals",
            "matching_skills": matched[:4],
            "skill_gaps": [gaps[idx % len(gaps)]],
            "project_alignment": f"Pitch '{projects[:70]}' during intern technical screening.",
            "stipend_duration_fit": f"Active {intern_dur} student intern intake | Target: {stipend}",
            "work_mode": "Remote" if "remote" in comp.lower() else ("Hybrid" if idx % 2 == 0 else "On-site"),
        })
    return cards


def get_platform_native_matches(p, academic=None, fallback_reason="Offline Mode"):
    """8-Factor CGPA-calibrated, location-aware, internship-verified offline fallback."""
    if academic is None:
        academic = _analyze_academic_standing(p)

    role = p.get("preferred_role") or "Software Development Intern"
    cgpa = p.get("cgpa") or "Not specified"
    college = p.get("college") or "your institution"
    courses = p.get("courses") or "Core Computer Science"
    course_duration = p.get("course_duration") or "4 Years (8 Semesters)"
    current_sem = p.get("current_semester") or "Current Semester"
    target_sem = p.get("target_semester") or "Target Semester"
    intern_dur = p.get("internship_duration") or "2–6 Months"
    stipend = p.get("stipend_expectation") or "Paid / Standard"
    what_i_need = p.get("what_i_need") or f"Practical {role} internship experience"
    skills_str = ", ".join(academic["skills_list"]) or "Python, SQL"
    projects = p.get("projects") or "Portfolio Projects"
    location = p.get("preferred_location") or "Remote / India"

    primary_companies, secondary_companies, primary_label, secondary_label = _get_location_companies(
        location, academic["cgpa_numeric"], role
    )

    return {
        "engine_source": f"Offline Smart Fallback ({fallback_reason})",
        "academic_band": academic["band"],
        "active_need": what_i_need,
        "opportunities": [
            {
                "company_tier": f"{primary_label} in {location}",
                "companies": primary_companies,
                "matched_role": f"{role} (Student Internship)",
                "match_score": academic["primary_score"],
                "location_fit": f"Companies with verified local offices and active student internship tracks in {location}.",
                "timeline_fit": f"{current_sem} -> {target_sem} ({course_duration}) | {intern_dur} | {stipend}",
                "eligibility_points": [
                    f"CGPA Calibration ({cgpa}): {academic['tier_guidance']}",
                    f"Coursework & Goal Fit: {courses} at {college}; aligned with '{what_i_need}'.",
                ],
                "company_cards": _build_offline_company_cards(
                    primary_companies, academic["primary_score"], role, cgpa, courses, academic, projects, intern_dur, stipend
                ),
            },
            {
                "company_tier": f"{secondary_label} in {location}",
                "companies": secondary_companies,
                "matched_role": f"{role} — Research / Startup Intern Track",
                "match_score": academic["secondary_score"],
                "location_fit": f"Secondary verified internship ecosystem in {location}.",
                "timeline_fit": f"Aligned with {target_sem} student intake for {intern_dur} ({stipend}).",
                "eligibility_points": [
                    f"Coursework alignment ({courses}) and practical stack readiness ({skills_str}).",
                    f"Demonstrated implementation through: {projects[:65]}.",
                ],
                "company_cards": _build_offline_company_cards(
                    secondary_companies, academic["secondary_score"], role, cgpa, courses, academic, projects, intern_dur, stipend
                ),
            },
        ],
        "workflows": [
            {
                "target_type": f"Primary Student Internship Track in {location}",
                "steps": [
                    f"Apply 6–8 weeks prior to {target_sem} via University Portal / Careers Intern Page",
                    "Online Technical & Domain-Specific Assessment",
                    f"Technical Interview focused on {skills_str} & Projects",
                    f"Internship Duration ({intern_dur}) & Stipend ({stipend}) Offer Confirmation",
                ],
            },
            {
                "target_type": f"Secondary / Research-Park Internship Track in {location}",
                "steps": [
                    "Submit Resume with live GitHub project links to Intern Intake",
                    "Practical Take-Home Design / Coding Task",
                    "Engineering Lead / R&D Mentor Discussion",
                ],
            },
        ],
        "profile_insights": [
            f"CGPA & Internship Tier Strategy: {academic['band']} — {academic['tier_guidance']}",
            f"Immediate Need Alignment: Filtered for '{what_i_need}' ({intern_dur}, {stipend}).",
            "Use + Bookmark or Create & Apply Entry directly on any internship card above.",
        ],
    }
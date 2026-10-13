"""Category scores computed in code from the facts a scoring call extracts.

Each function implements one scoring rule from the cv-rubric skill and returns
(score, rationale). Scores are integers clamped to 0-100.
"""

import re

SECTIONS = {
    "summary": r"(professional\s+)?(summary|profile)",
    "experience": r"(work\s+|professional\s+)?(experience|employment(\s+history)?|work\s+history)",
    "skills": r"(technical\s+|key\s+)?skills",
    "education": r"education(\s+and\s+certifications)?",
}
YEAR = re.compile(r"\b(19|20)\d{2}\b")
LONG_BULLET_CHARS = 250


def round_half_up(value):
    """Round a non-negative number to the nearest integer, halves up."""
    return int(value + 0.5)


def deduct(deductions, perfect):
    """Apply (points, reason) deductions to 100 and explain them."""
    if not deductions:
        return 100, perfect
    score = max(0, 100 - sum(points for points, _ in deductions))
    return score, "Deducted for " + ", ".join(reason for _, reason in deductions) + "."


def skills_score(keywords, matched_terms):
    """Weighted share of JD keywords found in the CV; required count 2, preferred 1."""
    if not keywords:
        return 100, "The JD names no specific skills."
    points = {"required": 2, "preferred": 1}
    found = [k for k in keywords if k.term in matched_terms]
    required = [k for k in keywords if k.importance == "required"]
    required_found = [k for k in found if k.importance == "required"]
    score = round_half_up(100 * sum(points[k.importance] for k in found) / sum(points[k.importance] for k in keywords))
    return score, f"{len(found)} of {len(keywords)} JD keywords found, {len(required_found)} of {len(required)} required."


def experience_score(experience):
    """100 minus fixed deductions for years, seniority, domain and other unmet requirements."""
    deductions = []
    if experience.years_required:
        short = max(0.0, experience.years_required - (experience.years_relevant or 0))
        if short:
            unit = "year" if short == 1 else "years"
            deductions.append((min(40, round_half_up(10 * short)), f"{short:g} {unit} short of {experience.years_required:g}"))
    seniority = {"one_level_below": 10, "two_or_more_below": 25}.get(experience.seniority)
    if seniority:
        deductions.append((seniority, "seniority " + experience.seniority.replace("_", " ")))
    domain = {"adjacent": 10, "different": 25}.get(experience.domain)
    if domain:
        deductions.append((domain, f"{experience.domain} domain"))
    if experience.unmet_requirements:
        deductions.append((min(30, 10 * len(experience.unmet_requirements)), "not shown: " + "; ".join(experience.unmet_requirements)))
    return deduct(deductions, "Meets the experience the JD asks for.")


def achievements_score(bullets):
    """Share of experience bullets that state a measurable outcome."""
    if not bullets:
        return 0, "No experience bullets found."
    with_outcome = sum(1 for b in bullets if b.has_outcome)
    return (
        round_half_up(100 * with_outcome / len(bullets)),
        f"{with_outcome} of {len(bullets)} experience bullets state a measurable outcome.",
    )


def education_score(items):
    """100 minus 15 per unmet preferred item, capped at 40 when a required item is unmet."""
    unmet_required = [i.requirement for i in items if i.importance == "required" and not i.met]
    unmet_preferred = [i.requirement for i in items if i.importance == "preferred" and not i.met]
    if not unmet_required and not unmet_preferred:
        return 100, "Meets every education requirement." if items else "The JD sets no education requirements."
    score = max(0, 100 - 15 * len(unmet_preferred))
    if unmet_required:
        score = min(score, 40)
    return score, "Not met: " + "; ".join(unmet_required + unmet_preferred) + "."


def has_section(cv_text, pattern):
    """True when a line of the CV is just this section heading."""
    return re.search(rf"^[#\s]*{pattern}\s*:?\s*$", cv_text, re.I | re.M) is not None


def structure_score(cv_text, bullets):
    """100 minus deductions for missing sections, undated roles and long bullets."""
    deductions = []
    missing = [name for name, pattern in SECTIONS.items() if not has_section(cv_text, pattern)]
    if missing:
        deductions.append((15 * len(missing), "missing " + ", ".join(missing)))
    if not YEAR.search(cv_text):
        deductions.append((20, "no dated roles"))
    long_bullets = sum(1 for b in bullets if len(b.text) > LONG_BULLET_CHARS)
    if long_bullets:
        deductions.append((min(20, 5 * long_bullets), f"{long_bullets} overlong bullets"))
    return deduct(deductions, "Standard sections, dated roles and concise bullets.")

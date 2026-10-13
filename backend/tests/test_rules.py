"""Unit tests for the category rules computed in code."""

from app import rules
from app.scoring import Bullet, EducationItem, Experience, Keyword

CV = "# Linh\n\n## Summary\nx\n\n## Experience\nRole (2020 - 2022)\n\n## Skills\nx\n\n## Education\nx"


def experience(**changes):
    base = dict(years_required=None, years_relevant=None, seniority="meets", domain="same", unmet_requirements=[])
    return Experience(**{**base, **changes})


def test_skills_counts_required_twice():
    keywords = [Keyword(term="A", importance="required"), Keyword(term="B", importance="preferred")]
    assert rules.skills_score(keywords, {"A"})[0] == 67
    assert rules.skills_score(keywords, {"B"})[0] == 33
    assert rules.skills_score([], set())[0] == 100


def test_experience_deductions():
    assert rules.experience_score(experience())[0] == 100
    assert rules.experience_score(experience(years_required=5, years_relevant=4))[0] == 90
    assert rules.experience_score(experience(years_required=10, years_relevant=None))[0] == 60
    assert rules.experience_score(experience(seniority="two_or_more_below", domain="adjacent"))[0] == 65
    assert rules.experience_score(experience(unmet_requirements=["a", "b", "c", "d"]))[0] == 70


def test_experience_never_drops_below_zero():
    worst = experience(years_required=9, years_relevant=0, seniority="two_or_more_below", domain="different", unmet_requirements=["a", "b", "c"])
    assert rules.experience_score(worst)[0] == 0


def test_achievements_share_of_bullets_with_outcome():
    bullets = [Bullet(text="a", has_outcome=True), Bullet(text="b", has_outcome=False), Bullet(text="c", has_outcome=False)]
    assert rules.achievements_score(bullets) == (33, "1 of 3 experience bullets state a measurable outcome.")
    assert rules.achievements_score([])[0] == 0


def test_education_caps_at_40_when_required_missing():
    def item(importance, met):
        return EducationItem(requirement=f"{importance} {met}", importance=importance, met=met)

    assert rules.education_score([])[0] == 100
    assert rules.education_score([item("required", True), item("preferred", False)])[0] == 85
    assert rules.education_score([item("required", False)])[0] == 40
    assert rules.education_score([item("required", False)] + [item("preferred", False)] * 5)[0] == 25


def test_structure_full_marks_for_standard_cv():
    assert rules.structure_score(CV, [])[0] == 100


def test_structure_recognises_heading_variants():
    cv = "PROFESSIONAL SUMMARY\nx\nWork Experience:\nRole 2021\nTechnical Skills\nx\nEducation and Certifications\nx"
    assert rules.structure_score(cv, [])[0] == 100


def test_structure_ignores_section_words_inside_sentences():
    cv = "I have experience with skills and education. 2020"
    assert rules.structure_score(cv, [])[0] == 40


def test_structure_deducts_for_missing_year_and_long_bullets():
    no_year = CV.replace("2020 - 2022", "recently")
    long = [Bullet(text="x" * 251, has_outcome=True)] * 5
    assert rules.structure_score(no_year, long)[0] == 60

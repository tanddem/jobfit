"""Integration tests: every fixture case is complete and agrees with the rubric."""

import re

import pytest

from conftest import FIXTURES, load_json

INDEX = load_json(FIXTURES / "index.json")
SEVERITIES = {"high", "medium", "low"}


@pytest.fixture(params=INDEX["cases"], ids=lambda c: c["id"])
def case(request):
    """One indexed case with its CV, JD and expected result loaded."""
    folder = FIXTURES / request.param["id"]
    return {
        **request.param,
        "cv": (folder / "cv.md").read_text(encoding="utf-8"),
        "jd": (folder / "jd.md").read_text(encoding="utf-8"),
        "expected": load_json(folder / "expected.json"),
    }


def contains_term(text, term):
    """True when term appears in text as a whole word or phrase, ignoring case."""
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I) is not None


def test_index_matches_case_folders():
    folders = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())
    assert sorted(c["id"] for c in INDEX["cases"]) == folders


def test_index_has_one_case_per_band(rubric):
    assert sorted(c["band"] for c in INDEX["cases"]) == sorted(rubric["bands"])


def test_overall_range_sits_inside_the_indexed_band(case, rubric):
    expected = case["expected"]
    assert expected["band"] == case["band"]
    band = rubric["bands"][case["band"]]
    overall = expected["overall_score"]
    assert band["min"] <= overall["min"] <= overall["max"] <= band["max"]


def test_category_ranges_cover_every_rubric_category(case, rubric):
    ranges = case["expected"]["categories"]
    assert set(ranges) == {c["id"] for c in rubric["categories"]}
    for cid, r in ranges.items():
        assert 0 <= r["min"] <= r["max"] <= 100, cid


def test_weighted_category_ranges_land_inside_overall_range(case, rubric):
    """Any category scores inside their ranges must give an overall inside its range."""
    weights = {c["id"]: c["weight"] for c in rubric["categories"]}
    ranges = case["expected"]["categories"]

    def weighted(bound):
        return sum(weights[cid] * r[bound] for cid, r in ranges.items()) / 100

    overall = case["expected"]["overall_score"]
    assert overall["min"] <= weighted("min")
    assert weighted("max") <= overall["max"]


def test_matched_keywords_appear_in_cv_and_jd(case):
    for keyword in case["expected"]["matched_keywords"]:
        assert contains_term(case["cv"], keyword), f"{keyword} not in CV"
        assert contains_term(case["jd"], keyword), f"{keyword} not in JD"


def test_missing_keywords_appear_in_jd_but_not_cv(case):
    for keyword in case["expected"]["missing_keywords"]:
        assert contains_term(case["jd"], keyword), f"{keyword} not in JD"
        assert not contains_term(case["cv"], keyword), f"{keyword} found in CV"


def test_required_gaps_are_well_formed(case, rubric):
    gaps = case["expected"]["required_gaps"]
    categories = {c["id"] for c in rubric["categories"]}
    assert gaps, "every case must require at least one gap"
    for gap in gaps:
        assert gap["category"] in categories
        assert gap["severity"] in SEVERITIES
        assert gap["requirement"].strip()


def test_contains_term_respects_word_boundaries():
    assert contains_term("Strong SQL skills", "sql")
    assert contains_term("Built CI/CD pipelines", "CI/CD")
    assert not contains_term("PostgreSQL only", "SQL")
    assert not contains_term("It sparked interest", "Spark")

"""Unit tests for the shape of rubric.json and its agreement with the cv-rubric skill."""

import re

from conftest import ROOT

SKILL_TEXT = (ROOT / ".claude" / "skills" / "cv-rubric" / "SKILL.md").read_text(encoding="utf-8")

# "| `skills_keywords` | Skills and keywords | 35 | ..." in the categories table.
CATEGORY_ROW = re.compile(r"^\| `(\w+)` \| ([^|]+?) \| (\d+) \|", re.M)
# "| strong | 75-100 | Strong |" in the bands table.
BAND_ROW = re.compile(r"^\| (\w+) \| (\d+)-(\d+) \|", re.M)


def test_has_five_categories_with_unique_ids(rubric):
    ids = [c["id"] for c in rubric["categories"]]
    assert len(ids) == 5
    assert len(set(ids)) == 5


def test_weights_are_positive_and_sum_to_100(rubric):
    weights = [c["weight"] for c in rubric["categories"]]
    assert all(isinstance(w, int) and w > 0 for w in weights)
    assert sum(weights) == 100


def test_every_category_has_criteria(rubric):
    for category in rubric["categories"]:
        for field in ("name", "measures", "scoring"):
            assert category[field].strip(), f"{category['id']} has empty {field}"


def test_bands_cover_0_to_100_without_overlap(rubric):
    bands = sorted(rubric["bands"].values(), key=lambda b: b["min"])
    assert bands[0]["min"] == 0
    assert bands[-1]["max"] == 100
    for lower, upper in zip(bands, bands[1:]):
        assert upper["min"] == lower["max"] + 1


def test_categories_match_skill(rubric):
    in_skill = {cid: (name, int(w)) for cid, name, w in CATEGORY_ROW.findall(SKILL_TEXT)}
    assert in_skill, "categories table not found in SKILL.md"
    assert in_skill == {c["id"]: (c["name"], c["weight"]) for c in rubric["categories"]}


def test_bands_match_skill(rubric):
    in_skill = {name: {"min": int(lo), "max": int(hi)} for name, lo, hi in BAND_ROW.findall(SKILL_TEXT)}
    assert in_skill, "bands table not found in SKILL.md"
    assert in_skill == rubric["bands"]

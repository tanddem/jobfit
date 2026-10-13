"""Unit tests for scoring: schema, arithmetic, matching, highlights, retry and cache."""

import json

import httpx2
import pytest

from app.db import connect, init_db
from app.scoring import (
    CATEGORY_IDS,
    MAX_OUTPUT_TOKENS,
    SCORER_FILES,
    SYSTEM_PROMPT,
    ModelOutput,
    ScoringError,
    band_for,
    build_result,
    find_span,
    request_scores,
    response_schema,
    score,
)
from conftest import StubModel, model_reply

CV = "Linh Tran\nBuilt APIs in Python and FastAPI.\nRan Meta Ads campaigns for new\n  product launches"


def output(keywords=(), bullets=(), gaps=(), education=(), **experience):
    """A valid ModelOutput; keywords are (term, importance) pairs, bullets (text, has_outcome)."""
    return ModelOutput.model_validate(
        {
            "jd_keywords": [{"term": t, "importance": i} for t, i in keywords],
            "experience": {
                "years_required": None,
                "years_relevant": None,
                "seniority": "meets",
                "domain": "same",
                "unmet_requirements": [],
                **experience,
            },
            "bullets": [{"text": t, "has_outcome": o} for t, o in bullets],
            "education": list(education),
            "gaps": list(gaps),
        }
    ).check_rubric()


def gap(severity="medium", evidence=None, category="skills_keywords"):
    return {"category": category, "severity": severity, "requirement": "req", "evidence": evidence}


def test_schema_asks_for_facts_never_scores():
    schema = response_schema()
    assert schema["required"] == ["jd_keywords", "experience", "bullets", "education", "gaps"]
    assert schema["properties"]["gaps"]["items"]["properties"]["category"]["enum"] == CATEGORY_IDS
    assert "score" not in json.dumps(schema)


def test_system_prompt_is_the_skill_without_frontmatter():
    assert SYSTEM_PROMPT.startswith("# cv-rubric")
    assert "Rewrite rules" in SYSTEM_PROMPT


def test_overall_is_weighted_and_rounds_half_up():
    # skills 0, experience 100, achievements 50, education 100, structure 25 (no sections, no year, 1 long bullet)
    bullets = [("x" * 300, True), ("y", False)]
    result = build_result(output(keywords=[("Kafka", "required")], bullets=bullets), "no headings here", "m")
    assert [c.score for c in result.categories] == [0, 100, 50, 100, 15]
    # 35*0 + 25*100 + 20*50 + 10*100 + 10*15 = 4650 -> 46.5 -> 47 (half up, not to even)
    assert result.overall == 47


def test_band_boundaries():
    assert [band_for(n) for n in (0, 49, 50, 74, 75, 100)] == ["weak", "weak", "partial", "partial", "strong", "strong"]


def test_keywords_are_split_by_whole_word_match_in_code():
    keywords = [("Python", "required"), ("SQL", "required"), ("fastapi", "preferred"), ("python", "preferred"), (" ", "required")]
    result = build_result(output(keywords=keywords), CV, "m")
    assert result.matched_keywords == ["Python", "fastapi"]
    assert result.missing_keywords == ["SQL"]


def test_evidence_is_located_across_line_breaks():
    assert find_span(CV, "Ran Meta Ads campaigns for new product launches") == (
        CV.index("Ran"),
        len(CV),
    )
    assert find_span(CV, "Something the CV never says") is None
    assert find_span(CV, None) is None


def test_highlights_by_tone_without_overlap():
    result = build_result(
        output(
            keywords=[("Python", "required"), ("Meta Ads", "required")],
            gaps=[gap("medium", "Ran Meta Ads campaigns for new product launches"), gap("high", "Linh Tran")],
        ),
        CV,
        "m",
    )
    tones = [(CV[h.start : h.end], h.tone) for h in result.highlights]
    assert tones == [
        ("Linh Tran", "weak"),
        ("Python", "strong"),
        ("Ran Meta Ads campaigns for new\n  product launches", "partial"),
    ]


def test_gap_without_findable_evidence_has_no_span():
    result = build_result(output(gaps=[gap("high"), gap("medium", "made up text")]), CV, "m")
    assert [g.span for g in result.gaps] == [None, None]
    assert result.highlights == []


def test_rejects_gap_with_unknown_category():
    with pytest.raises(ValueError):
        output(gaps=[gap(category="charisma")])


def test_request_sends_skill_schema_and_deterministic_settings():
    stub = StubModel(model_reply(output().model_dump()))
    request_scores("cv", "jd", api_key="k", model="m", call=stub)
    payload = stub.payloads[0]
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == MAX_OUTPUT_TOKENS
    assert payload["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["provider"] == {"require_parameters": True}


def test_retries_once_then_succeeds():
    stub = StubModel({"choices": [{"message": {"content": "not json"}}]}, model_reply(output().model_dump()))
    assert request_scores("cv", "jd", api_key="k", model="m", call=stub).experience.seniority == "meets"
    assert len(stub.payloads) == 2


def test_gives_up_after_second_failure():
    stub = StubModel(httpx2.ConnectError("down"))
    with pytest.raises(ScoringError):
        request_scores("cv", "jd", api_key="k", model="m", call=stub)
    assert len(stub.payloads) == 2


def test_missing_key_fails_without_calling_the_model():
    stub = StubModel(model_reply(output().model_dump()))
    with pytest.raises(ScoringError):
        request_scores("cv", "jd", api_key="", model="m", call=stub)
    assert stub.payloads == []


def test_same_input_is_scored_once_and_cached(tmp_path):
    db_path = tmp_path / "jobfit.sqlite3"
    init_db(db_path)
    conn = connect(db_path)
    stub = StubModel(model_reply(output().model_dump()))

    first_key, first = score(CV, "jd", conn=conn, api_key="k", model="m", call=stub)
    second_key, second = score(CV, "jd", conn=conn, api_key="k", model="m", call=stub)
    other_key, _ = score(CV, "jd", conn=conn, api_key="k", model="other-model", call=stub)
    conn.close()

    assert first_key == second_key != other_key
    assert first == second
    assert len(stub.payloads) == 2


def test_terms_do_not_match_inside_symbol_names():
    assert find_span("Skills: C++, C#, R&D, Node.js", "C") is None
    assert find_span("R&D team", "R") is None
    assert find_span("Built on Node.js", "Node") is None
    assert find_span("Skills: C++, C", "C++") == (8, 11)
    assert find_span("I write C.", "C") == (8, 9)


def test_highlight_offsets_count_utf16_units():
    cv = "Linh \U0001F4E7 a@b.com\nPython"
    result = build_result(output(keywords=[("Python", "required")]), cv, "m")
    [h] = result.highlights
    assert (h.start, h.end) == (16, 22)
    assert cv.encode("utf-16-le")[2 * h.start : 2 * h.end].decode("utf-16-le") == "Python"


def test_overlapping_gap_evidence_is_kept_off_the_cv_not_lost():
    line = "Ran Meta Ads campaigns for new product launches"
    result = build_result(output(gaps=[gap("medium", line), gap("high", "Meta Ads campaigns")]), CV, "m")
    assert [g.span is not None for g in result.gaps] == [True, False]
    assert len(result.highlights) == 1


def test_client_errors_fail_without_retry():
    error = httpx2.HTTPStatusError("402", request=httpx2.Request("POST", "https://x"), response=httpx2.Response(402))
    stub = StubModel(error)
    with pytest.raises(ScoringError):
        request_scores("cv", "jd", api_key="k", model="m", call=stub)
    assert len(stub.payloads) == 1


def test_rate_limit_is_retried():
    error = httpx2.HTTPStatusError("429", request=httpx2.Request("POST", "https://x"), response=httpx2.Response(429))
    stub = StubModel(error, model_reply(output().model_dump()))
    assert request_scores("cv", "jd", api_key="k", model="m", call=stub)
    assert len(stub.payloads) == 2


def test_cache_version_covers_rules_and_scorer_code():
    assert {p.name for p in SCORER_FILES} == {"rubric.json", "SKILL.md", "rules.py", "scoring.py"}

"""Scoring a CV against a job description.

The model only extracts and classifies facts (JD keywords, experience,
bullets, education, gaps); the cv-rubric skill is its system prompt. Code
turns those facts into every category score (app.rules), the overall score,
the band, which keywords the CV contains, and where each gap sits on the CV.
Results are cached by input, model and rubric, so the same CV and JD always
get the same score.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Literal, get_args

import httpx2
from pydantic import BaseModel, ValidationError

from app import rules
from app.settings import ROOT

RUBRIC_PATH = ROOT / "rubric.json"
SKILL_PATH = ROOT / ".claude" / "skills" / "cv-rubric" / "SKILL.md"
RUBRIC = json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))
SYSTEM_PROMPT = re.sub(r"\A---\n.*?\n---\n", "", SKILL_PATH.read_text(encoding="utf-8"), flags=re.S).strip()
SCORER_FILES = [RUBRIC_PATH, SKILL_PATH, Path(rules.__file__), Path(__file__)]
SCORER_VERSION = hashlib.sha256(b"".join(path.read_bytes() for path in SCORER_FILES)).hexdigest()

CATEGORIES = RUBRIC["categories"]
CATEGORY_IDS = [c["id"] for c in CATEGORIES]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_OUTPUT_TOKENS = 4000

Severity = Literal["high", "medium", "low"]
SEVERITIES = list(get_args(Severity))
Importance = Literal["required", "preferred"]
Tone = Literal["strong", "partial", "weak"]


class ScoringError(Exception):
    """The model could not produce a valid score."""


class Keyword(BaseModel):
    term: str
    importance: Importance


class Experience(BaseModel):
    years_required: float | None
    years_relevant: float | None
    seniority: Literal["meets", "one_level_below", "two_or_more_below"]
    domain: Literal["same", "adjacent", "different"]
    unmet_requirements: list[str]


class Bullet(BaseModel):
    text: str
    has_outcome: bool


class EducationItem(BaseModel):
    requirement: str
    importance: Importance
    met: bool


class ModelGap(BaseModel):
    category: str
    severity: Severity
    requirement: str
    evidence: str | None


class ModelOutput(BaseModel):
    """The facts a scoring call returns."""

    jd_keywords: list[Keyword]
    experience: Experience
    bullets: list[Bullet]
    education: list[EducationItem]
    gaps: list[ModelGap]

    def check_rubric(self):
        """Raise ValueError unless every gap names a rubric category."""
        for gap in self.gaps:
            if gap.category not in CATEGORY_IDS:
                raise ValueError(f"unknown gap category {gap.category}")
        return self


class CategoryScore(BaseModel):
    id: str
    name: str
    weight: int
    score: int
    rationale: str


class Gap(ModelGap):
    """A gap with where its evidence sits on the CV, or null when it is not marked there.

    Offsets count UTF-16 code units, as JavaScript string indices do.
    """

    span: tuple[int, int] | None




class Highlight(BaseModel):
    """A marked range of the CV; offsets count UTF-16 code units."""

    start: int
    end: int
    tone: Tone
    note: str


class ScoreResult(BaseModel):
    overall: int
    band: str
    categories: list[CategoryScore]
    matched_keywords: list[str]
    missing_keywords: list[str]
    gaps: list[Gap]
    highlights: list[Highlight]
    model: str


def obj(properties):
    """A strict JSON schema object where every property is required."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def enum(*values):
    return {"type": "string", "enum": list(values)}


def response_schema():
    """JSON schema for Structured Outputs: facts only, never a score."""
    text = {"type": "string"}
    nullable_number = {"type": ["number", "null"]}
    return obj(
        {
            "jd_keywords": {"type": "array", "items": obj({"term": text, "importance": enum("required", "preferred")})},
            "experience": obj(
                {
                    "years_required": nullable_number,
                    "years_relevant": nullable_number,
                    "seniority": enum("meets", "one_level_below", "two_or_more_below"),
                    "domain": enum("same", "adjacent", "different"),
                    "unmet_requirements": {"type": "array", "items": text},
                }
            ),
            "bullets": {"type": "array", "items": obj({"text": text, "has_outcome": {"type": "boolean"}})},
            "education": {
                "type": "array",
                "items": obj({"requirement": text, "importance": enum("required", "preferred"), "met": {"type": "boolean"}}),
            },
            "gaps": {
                "type": "array",
                "items": obj(
                    {
                        "category": enum(*CATEGORY_IDS),
                        "severity": enum(*SEVERITIES),
                        "requirement": text,
                        "evidence": {"type": ["string", "null"]},
                    }
                ),
            },
        }
    )


def term_pattern(term):
    """Regex for term as a whole word or phrase, any case, any run of whitespace.

    Symbols that extend a term count as part of it, so "C" does not match in
    "C++", "C#" or "R&D", and "Node" does not match in "Node.js".
    """
    words = [re.escape(word) for word in term.split()]
    return re.compile(r"(?<![\w+#&.])" + r"\s+".join(words) + r"(?![\w+#&]|\.\w)", re.I)


def find_span(text, phrase):
    """Return (start, end) of the first match of phrase in text, or None."""
    if not phrase:
        return None
    match = term_pattern(phrase).search(text)
    return (match.start(), match.end()) if match else None


def band_for(overall):
    """Name of the rubric band that contains the overall score."""
    return next(name for name, b in RUBRIC["bands"].items() if b["min"] <= overall <= b["max"])


def utf16(text, span):
    """Convert a (start, end) span over Python characters to UTF-16 code units."""
    start, end = span
    before = len(text[:start].encode("utf-16-le")) // 2
    return before, before + len(text[start:end].encode("utf-16-le")) // 2


def overlaps(span, spans):
    return any(span[0] < end and start < span[1] for start, end in spans)


def unique_keywords(keywords):
    """Drop blank and repeated terms, keeping the first importance seen."""
    seen = {}
    for k in keywords:
        term = k.term.strip()
        if term and term.lower() not in seen:
            seen[term.lower()] = Keyword(term=term, importance=k.importance)
    return list(seen.values())


def build_result(output, cv_text, model):
    """Turn the model's facts into a ScoreResult using only code."""
    keywords = unique_keywords(output.jd_keywords)
    matched = [k.term for k in keywords if find_span(cv_text, k.term)]
    missing = [k.term for k in keywords if k.term not in matched]

    rule_results = {
        "skills_keywords": rules.skills_score(keywords, set(matched)),
        "experience_relevance": rules.experience_score(output.experience),
        "achievements_impact": rules.achievements_score(output.bullets),
        "education_certifications": rules.education_score(output.education),
        "structure_clarity": rules.structure_score(cv_text, output.bullets),
    }
    categories = []
    for c in CATEGORIES:
        score, rationale = rule_results[c["id"]]
        categories.append(CategoryScore(id=c["id"], name=c["name"], weight=c["weight"], score=score, rationale=rationale))
    overall = rules.round_half_up(sum(c.weight * c.score for c in categories) / 100)

    gaps, highlights, taken = [], [], []
    for gap in output.gaps:
        span = find_span(cv_text, gap.evidence)
        if span and overlaps(span, taken):
            span = None
        if span:
            taken.append(span)
            start, end = utf16(cv_text, span)
            tone = "weak" if gap.severity == "high" else "partial"
            highlights.append(Highlight(start=start, end=end, tone=tone, note=gap.requirement))
        gaps.append(Gap(**gap.model_dump(), span=utf16(cv_text, span) if span else None))
    for term in matched:
        for m in term_pattern(term).finditer(cv_text):
            if not overlaps(m.span(), taken):
                taken.append(m.span())
                start, end = utf16(cv_text, m.span())
                highlights.append(Highlight(start=start, end=end, tone="strong", note=f"Matches JD keyword: {term}"))
    highlights.sort(key=lambda h: h.start)

    return ScoreResult(
        overall=overall,
        band=band_for(overall),
        categories=categories,
        matched_keywords=matched,
        missing_keywords=missing,
        gaps=gaps,
        highlights=highlights,
        model=model,
    )


def openrouter_call(payload, api_key):
    """POST a chat completion to OpenRouter and return the parsed response body."""
    response = httpx2.post(
        OPENROUTER_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def request_scores(cv_text, jd_text, *, api_key, model, call=openrouter_call):
    """Ask the model to judge the CV, retrying once, and return validated ModelOutput."""
    if not api_key or not model:
        raise ScoringError("OPENROUTER_API_KEY and OPENROUTER_MODEL must be set.")
    payload = {
        "model": model,
        "temperature": 0,
        "seed": 0,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"JOB DESCRIPTION:\n{jd_text}\n\nCV:\n{cv_text}"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "cv_score", "strict": True, "schema": response_schema()},
        },
        "provider": {"require_parameters": True},
    }
    last_error = None
    for _ in range(2):
        try:
            body = call(payload, api_key)
            content = body["choices"][0]["message"]["content"]
            return ModelOutput.model_validate_json(content).check_rubric()
        except httpx2.HTTPStatusError as exc:
            if exc.response.status_code != 429 and exc.response.status_code < 500:
                raise ScoringError(f"OpenRouter rejected the request: {exc}") from exc
            last_error = exc
        except (httpx2.HTTPError, KeyError, IndexError, TypeError, ValidationError, ValueError) as exc:
            last_error = exc
    raise ScoringError(f"Scoring failed after a retry: {last_error}") from last_error


def cache_key(cv_text, jd_text, model):
    """Content hash of everything that can change a score."""
    return hashlib.sha256(json.dumps([cv_text, jd_text, model, SCORER_VERSION]).encode()).hexdigest()


def score(cv_text, jd_text, *, conn, api_key, model, call=openrouter_call):
    """Return (cache key, ScoreResult), from the scores table when this input was seen before."""
    key = cache_key(cv_text, jd_text, model)
    row = conn.execute("SELECT result_json FROM scores WHERE key = ?", (key,)).fetchone()
    if row:
        return key, ScoreResult.model_validate_json(row["result_json"])
    output = request_scores(cv_text, jd_text, api_key=api_key, model=model, call=call)
    result = build_result(output, cv_text, model)
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO scores (key, result_json) VALUES (?, ?)",
            (key, result.model_dump_json()),
        )
    return key, result

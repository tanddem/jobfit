---
name: cv-rubric
description: Single source of truth for how JobFit scores a CV against a job description and how CV content may be rewritten. Use whenever a task touches scoring, the rubric, gaps, keywords, fixtures, or rewriting CV bullets.
---

# cv-rubric

This skill describes what a correct result looks like. It contains no code.
`rubric.json` at the project root is the machine-readable copy of the
categories and weights below; the two must always agree.

## Categories and weights

Every category is scored 0-100. Weights sum to 100.

| id | Name | Weight | Measures |
|---|---|---|---|
| `skills_keywords` | Skills and keywords | 35 | Required and preferred skills, tools and terms from the JD that appear in the CV |
| `experience_relevance` | Experience relevance | 25 | Years of experience, seniority and domain compared with what the JD asks for |
| `achievements_impact` | Achievements and impact | 20 | Share of experience bullets that state a measurable outcome (number, percentage, money, scale) |
| `education_certifications` | Education and certifications | 10 | Degree, field of study and certifications the JD requires or prefers |
| `structure_clarity` | Structure and clarity | 10 | Standard sections present, dated roles, concise bullets a reader can scan |

### Scoring rules

The model never scores. It reports the facts listed under "Facts the model
returns", and code applies these rules to them. Every score is clamped to
0-100 and rounded half up to an integer.

- `skills_keywords`: each JD keyword is `required` or `preferred`. A keyword is matched when the CV contains it as a whole word or phrase, ignoring case. Required keywords count 2, preferred count 1. Score = 100 x matched points / total points. No JD keywords gives 100.
- `experience_relevance`: start at 100, then subtract
  - 10 per year short of the years the JD requires, at most 40 (relevant years only)
  - 10 when the CV's seniority is one level below the JD's, 25 when two or more levels below
  - 10 when the CV's domain is adjacent to the JD's, 25 when it is different
  - 10 per other unmet experience requirement (for example team leadership), at most 30
- `achievements_impact`: score = 100 x experience bullets with a measurable outcome / all experience bullets. An outcome is a number, percentage, amount of money or scale tied to a result. A count of activities ("two events") or a vague claim ("improved performance") is not an outcome. No experience bullets gives 0.
- `education_certifications`: start at 100 and subtract 15 per unmet preferred item. Any unmet required item caps the score at 40. No education requirements in the JD gives 100.
- `structure_clarity`: computed from the CV text alone. Start at 100 and subtract
  - 15 per missing section among summary (or profile), experience, skills, education
  - 20 when no role carries a year
  - 5 per experience bullet longer than 250 characters, at most 20

### Overall score and bands

The overall score is the weighted sum of category scores divided by 100,
rounded half up to an integer. It is computed in code, never by the model.

| Band | Range | Colour token |
|---|---|---|
| strong | 75-100 | Strong |
| partial | 50-74 | Partial |
| weak | 0-49 | Weak |

## Facts the model returns

A scoring call extracts and classifies; it never returns a score.

- `jd_keywords`: the skills, tools and qualifications the JD asks for, each with
  - `term`: a short term exactly as the JD spells it (for example `PostgreSQL`, `Google Ads`, `A/B testing`)
  - `importance`: `required`, or `preferred` when the JD marks it nice to have
- `experience`:
  - `years_required`: relevant years the JD asks for, or null
  - `years_relevant`: years of experience in the CV that are relevant to the JD, or null when the CV gives no dates
  - `seniority`: `meets`, `one_level_below` or `two_or_more_below`
  - `domain`: `same`, `adjacent` or `different`
  - `unmet_requirements`: other experience requirements the CV does not show, each a short phrase
- `bullets`: every experience bullet, each with
  - `text`: copied character for character from the CV
  - `has_outcome`: true when it states a measurable outcome as defined above
- `education`: each degree or certification the JD asks for, with `requirement`, `importance` and `met`
- `gaps`: each gap has
  - `category`: a category id
  - `severity`: `high` (a JD requirement is absent), `medium` (present but weak or unproven), or `low` (a polish issue)
  - `requirement`: the JD requirement or rubric criterion that is not met
  - `evidence`: the CV text the gap refers to, copied character for character from the CV (one bullet or line at most), or null when the CV has nothing

Code computes every category score with the rules above, the overall score
from the weights, which keywords are matched or missing, and where each
gap's `evidence` sits on the CV.

## Gap severity

- A required JD skill or qualification that the CV never mentions is always `high`.
- A nice-to-have JD skill that the CV never mentions is `medium`.
- A requirement the CV mentions without proof (no years, no outcome) is `medium`.
- Formatting and wording issues are `low`.

## Rewrite rules

- Never invent experience, employers, dates, metrics, tools or credentials.
- A rewrite may only use facts found in the CV or stated by the user in the Optimise conversation.
- Rephrase what is genuinely there: stronger verbs, the outcome first, JD terminology where it truthfully applies.
- When the user says they lack the experience, record the gap as unfillable and move on. Do not soften it into a claim.
- One question at a time, scoped to one gap.

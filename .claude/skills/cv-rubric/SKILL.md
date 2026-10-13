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

- `skills_keywords`: required JD skills count twice as much as preferred ones. Score is the weighted share found in the CV. A skill counts only if the CV states it, not if it can be guessed from a job title.
- `experience_relevance`: start at 100 and subtract for each shortfall. Missing years, a lower seniority level and a different domain each cost points in proportion to how far off they are.
- `achievements_impact`: score is the share of experience bullets with a concrete, measurable outcome. Vague claims ("improved performance") do not count.
- `education_certifications`: 100 when every required item is met. A missing required item caps the score at 40; a missing preferred item costs less.
- `structure_clarity`: deduct for missing sections (summary, experience, skills, education), undated roles, and bullets longer than two lines.

### Overall score and bands

The overall score is the weighted sum of category scores divided by 100,
rounded to the nearest integer. It is computed in code, never by the model.

| Band | Range | Colour token |
|---|---|---|
| strong | 75-100 | Strong |
| partial | 50-74 | Partial |
| weak | 0-49 | Weak |

## Score output schema

A scoring call returns, per category, a score and the evidence behind it.
It does not return the overall score or the weights.

- `categories`: one entry per category id, each with `score` (integer 0-100) and `rationale` (one sentence)
- `matched_keywords`: JD terms found in the CV
- `missing_keywords`: JD terms absent from the CV
- `gaps`: each gap has
  - `category`: a category id
  - `severity`: `high` (a JD requirement is absent), `medium` (present but weak or unproven), or `low` (a polish issue)
  - `requirement`: the JD requirement or rubric criterion that is not met
  - `evidence`: the CV text the gap refers to, or null when the CV has nothing

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

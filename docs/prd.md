# Product requirements

## Problem

AML teams that fall behind end up with alerts spread across several monitoring systems, each with its own customer ID. Analysts work alert by alert, research the same customer more than once, and leadership reports a raw alert count that hides where the risk is. When a regulator sets a deadline, the bank cannot say with confidence how many people it needs.

## Goal

Give an AML operations team one ranked queue of customer cases, built from every alert source they have, plus a staffing plan they can defend.

## Users

- **Operations manager**: owns the queue and the staffing plan.
- **Analyst**: works cases from the top of the queue.
- **Identity reviewer**: settles the matches the system was not sure about.
- **BSA Officer and QA lead**: need evidence for examiners.

## Requirements

| # | Requirement | How this demo meets it |
|---|---|---|
| R1 | Onboard a new alert source without code changes | Each source is a JSON config in `config/sources/`. A test onboards a fourth source with config only |
| R2 | Account for every row read | Each source report reconciles: loaded + duplicates + closed + rejected = rows read. The load fails if it does not add up |
| R3 | Never guess a customer match | Matches below 90% confidence go to the identity review queue with the reason and the candidates |
| R4 | Measure matching accuracy | Automatic matches are scored against an answer key: 4,923 of 4,923 correct |
| R5 | One case per customer | Every automatically matched alert lands in exactly one case. A test checks that cases plus the review queue equal all loaded alerts |
| R6 | Explainable priority | The score is a list of named points. The analyst sees each reason and its points |
| R7 | Staffing plan against a deadline | Clear dates for 4 to 30 analysts, alert by alert versus by case, with the assumptions on screen |
| R8 | Reproducible QA sample | 10% of cases drawn with a stored random seed |

## Out of scope for the pilot

- Writing back to Actimize or the case management system. The pilot reads exports only.
- Machine learning scoring. Weighted points are easier to explain to an examiner in month one; a model can be tested against them later.
- SAR drafting.

## Success measures

See [pilot-plan.md](pilot-plan.md).

## Risks

| Risk | Mitigation |
|---|---|
| A wrong automatic match merges two customers | High confidence threshold, answer key test, QA sample includes matched-by method |
| Priority weights are seen as arbitrary | Weights set with the operations manager and BSA Officer, kept in one file, every case shows its reasons |
| Handle time assumptions are wrong | Replace them with measured times after two weeks of the pilot and rerun the plan |
| Grouping hides an urgent alert inside a large case | Case priority uses the most severe typology in the case and the oldest alert age |

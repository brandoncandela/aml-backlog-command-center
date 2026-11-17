# Pilot plan

Four weeks, one team of analysts, working the case queue in parallel with the current process on a slice of the backlog.

## Setup

- 2 analysts work the case queue. The rest keep working alert by alert.
- Both groups record start and end time per decision.
- QA reviews the fixed seed sample from both groups.

## What we measure

| Measure | Target | Why it matters |
|---|---|---|
| Analyst minutes per alert closed | 30% lower in the case group | This is what the staffing plan depends on |
| Automatic match precision, from QA | 99% or better | A wrong match puts activity in the wrong customer file |
| Identity review queue age | Under 3 working days | If this backs up, alerts stall before they reach a case |
| QA pass rate | No worse than the alert by alert group | Faster is only useful if quality holds |
| P1 cases decided in the first two weeks | All of them | The highest risk customers should not wait behind old low risk alerts |

## Decision at the end of week 4

- **Go**: minutes per alert down at least 25%, precision at least 99%, QA pass rate holds. Move the whole team to the case queue and rerun the staffing plan with measured times.
- **Adjust**: savings are real but QA slips. Keep the case queue, add a second QA pass on P1 cases, and recheck after two weeks.
- **Stop**: precision under 99% or no time savings. Go back to the alert queue and look at what went wrong in matching before trying again.

## Reporting

A one page weekly update to the BSA Officer: alerts closed, cases closed, projected clear date at current pace, and anything blocking.

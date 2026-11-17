# Discovery notes

Larkspur Bank is fictional. These notes are written the way I would write them after the first week on site with a real customer, so the rest of the project has something concrete to answer to.

## The situation

- About 5,300 open alerts across three systems. The oldest are from March.
- A consent order requires the backlog to be cleared by March 31, 2027.
- The team has 6 analysts today. The vendor quote for contractors assumes 9 or more.
- Nobody can say how many distinct customers are behind the alerts, because each system uses its own ID.

## Who I talked to

| Person | What they need | What hurts today |
|---|---|---|
| BSA Officer | Proof for the regulator that the backlog will be cleared on time, and that nothing risky is waiting at the bottom of the pile | The weekly number she reports is alert count, which says nothing about risk or customers |
| Operations manager | A staffing number she can defend to finance, and a daily queue her team can trust | Analysts pick alerts oldest first, then rediscover the same customer three times in a week |
| Level 1 analyst | One place to see everything about a customer before deciding | Three screens, three IDs, and a spreadsheet to find out if the fraud team already looked at the person |
| QA lead | A sample she can defend to examiners | The current sample is picked by hand, so it cannot be reproduced |
| Data engineer | Not to be asked to write a new pipeline for every system | Every vendor wants a custom extract |

## What the data actually looks like

- **Actimize export (CSV).** Uses its own party key. A crosswalk to the core banking CIF exists but covers about 88% of parties. A re-run batch left duplicate rows. A failed batch wrote `00/00/0000` as the alert date.
- **Legacy SQL rules (pipe delimited).** Uses the CIF but strips leading zeros about half the time. Dates come in two formats. A few customer numbers do not exist in core at all, left over from a migration.
- **Fraud referrals (JSON).** No customer ID. A name, sometimes a date of birth, sometimes a full account number, sometimes only the last four digits.

## What I took away

1. The real unit of work is the customer, not the alert. Grouping should come first, and everything else (priority, staffing, QA) follows from it.
2. Matching has to be honest about uncertainty. A wrong match is worse than no match, because it puts one customer's activity in another customer's file.
3. Onboarding a new source should be a config file, not a code change, or the next system will stall the program again.
4. The staffing number must show its assumptions, because finance and the BSA Officer will both challenge it.
5. QA has to be reproducible. A fixed random seed is a cheap way to give examiners that.

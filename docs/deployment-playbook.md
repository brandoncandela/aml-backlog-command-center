# Deployment playbook

How I would roll this out at a new bank. Written for the person doing the deployment, not for the buyer.

## Week 0: before arriving

- Get a sample export from every alert source, even 100 rows. Real files tell you more than any data dictionary.
- Ask for the customer master extract and any crosswalk tables between systems.
- Ask who signs off on priority weights. It is usually the BSA Officer, and they need to be in the room early.

## Week 1: onboard the sources

1. For each export, copy a config from `config/sources/` and change the column names, date formats and status values.
2. Run `python3 src/build.py` and read the source report in the Data onboarding view.
3. Every rejected row has a reason. Send the list back to the data owner rather than fixing rows by hand.
4. When the numbers reconcile and the data owner agrees with the reject list, the source is onboarded.

What usually goes wrong: date formats that change partway through a file, IDs that lose leading zeros in Excel, and "closed" meaning different things in different systems. Ask how each system defines closed.

## Week 1: matching

1. Load the customer master and crosswalk.
2. Have someone at the bank match 200 random alerts by hand. That becomes the answer key.
3. Check automatic precision against it. If it is under 99%, raise the threshold or drop the weakest method before going further.
4. Size the identity review queue and assign an owner. 8 minutes per alert is a starting estimate.

## Week 2: priority and staffing

1. Walk the operations manager and BSA Officer through the score parts on ten real cases. Change weights in `src/cases.py` with them, not for them.
2. Agree the handle time assumptions in `src/forecast.py`. Write down who agreed and when.
3. Present the staffing plan with both numbers side by side: alert by alert and by case.

## Weeks 3 to 6: pilot

Run the pilot plan. Replace assumed handle times with measured ones after two weeks and rerun the forecast.

## Handover

- The configs, weights and assumptions are the bank's to own. Make sure someone on their side has changed each of them once before you leave.
- Leave the test suite running in their environment. `python3 -m unittest discover -s tests` should pass after any config change.

# Prompt 007 - Review Feedback and Required Fixes Before Submitting

```text
complete this and update github

Must fix before submitting
1. The “leakage trap” results are fabricated. In src/eta_data/evaluate.py (lines ~203–212), the leaky MAE is the Context-Aware MAE × 0.28.
Precision (0.96), recall (0.94), ROC-AUC (0.99) and bias are hard-coded.
Those precision and recall values would give an F1 of about 0.95, yet the table prints 0.478.
The horizon-error chart (lines ~243–245) is also made from formulas, not data.
Your README says “zero invented results”, and a reviewer who reads this file will see it.
Fix: build features using event_time as the cutoff, rerun the same model, and report the real scores. Compute the horizon chart from actual errors.

2. There are no duplicate events in either dataset. I found 0 duplicates in both starter and full, although the task requires them.
The natural event stream already totals exactly 300,000, so the code path that adds duplicates never runs.
DELAY_SCAN and IN_TRANSIT_SCAN events also never appear.
Fix: inject duplicates, delayed scans and gaps at explicit, seeded rates.

3. Event pruning is biased by shipment ID.
ARRIVED and OUT_FOR_DELIVERY events exist only for shipments up to about #15,000. Shipments after that have none, because the pruning step removes events from the highest IDs first.
Your temporal split tests on later shipments, so train and test data differ in a hidden way.
Fix: prune randomly with the seeded RNG, or change the base event counts.

4. The committed checksums don’t match the committed files.
The generator writes CRLF line endings, but git stored the files as LF, so the manifest checksums fail on a fresh clone.
The two runs match each other on one machine, but the claim of identical output across Windows and Linux is not true.
Fix: write files with \n line endings and add a .gitattributes with * text eol=lf.

5. README placeholders and broken links.
The clone URL is still your-username/yottaflex-eta-delay-data, and the folder name doesn’t match your repo.
LICENSE is linked but the file doesn’t exist.
data/starter/logistics.sqlite is linked and counted, but .gitignore excludes *.sqlite.
docs/EVALUATION.md says Context-Aware “strictly outperforms” Plan-Based, while its own table shows 27.4h vs 25.04h. The README is honest here, but the doc contradicts it.

Should fix
6. The validator is only partly independent. It does detect violations from the data, but the “100% precision and recall” claim is never computed. The accounting check only counts rows in the ground-truth file, and the sanity bounds (30–95% on-time) accept almost anything.

7. Some distributions are unrealistic.
24% of shipments are SEVERELY_DELAYED and only 5.6% are DELAYED.
The 24-hour service has a median delay of +12.7h, so its promise is nearly unachievable. The 120-hour freight service arrives about 84h early.
On-time rate is 86% at starter scale but 70.5% at full scale.
Shipments are created at the same rate on weekends as on weekdays.

8. The evaluation is weak.
It runs on the 500-shipment starter set only.
The “plan-based” baseline appears to be the promised date, not the planned leg arrival.
The heuristics perform worse than that naive baseline.

9. Prompt history is thin. It holds 6 short prompts, but the guidelines require every prompt you sent to any AI tool, including your chats with me.
AI_USAGE.md says “every single line was verified”, which isn’t accurate given point 1.

10. Minor items.
The README lists 11 test modules, but test_rng.py makes 12.
Reproducibility is shown only at starter scale.
datetime.utcnow() is deprecated.
```


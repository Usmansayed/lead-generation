# Test fixtures

## calibration_leads.json

110 leads with **known expected outcomes** for tuning the static filter and relevance rules.

- **expected_should_pass**: `true` = should pass static filter (go to AI); `false` = should be rejected.
- **note**: Why we expect this outcome (for tuning).

Use the calibration script from project root:

```bash
python scripts/calibrate_static_filter.py
python scripts/calibrate_static_filter.py --threshold 5   # try different threshold
python scripts/calibrate_static_filter.py --verbose       # show every lead
```

Then adjust:

- **config/static_scoring_rules.yaml** — `minimum_threshold` (higher = fewer leads to AI).
- **config/filters.yaml** — `negative_patterns`, `minimum_word_count`.
- **config/relevance_keywords.yaml** — intent tiers and phrases.

To add or change calibration leads: edit `calibration_leads.json` and re-run the script.

See `docs/STATIC_FILTER_ASSESSMENT.md` for how good the filter is and how to improve it.

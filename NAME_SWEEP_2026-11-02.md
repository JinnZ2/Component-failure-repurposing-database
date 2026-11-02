# Name sweep 2026-11-02

One personal name (written `<name>` below) was removed from file contents. Git history was not rewritten,
so past commit messages and past file versions still carry it. Commit messages from now
on carry no name.

## Rule applied

```text
"Co-authored (<name> + Claude)" and similar headers  -> "Co-authored" (the date is kept)
"[stated] (<name>)"                                   -> "[stated]"
"OBSERVED by <name>", "OBSERVED (<name>)"              -> "OBSERVED (field report)"
any other attribution                                -> name dropped, status tag kept
"<name>'s method/frame/tool"                          -> "the method / a working tool"
```

Only the name changed on each line. Vendored and upstream third-party files were not touched.

## Files changed (replacements)

```text
components/_template.md                                        1
data/README_ims_bearings.md                                    1
results/real_data_titration_capacitor_electrical_stress.md     1
scenario_engine/claims/NOISE_PRECURSOR_CLAIMS.json             1
scenario_engine/claims/noise_precursor.py                      1
scenario_engine/tests/test_noise_precursor_validator.py        1
scenario_engine/tests/test_noise_titration.py                  1
scenario_engine/tests/test_real_data_scripts.py                1
scenario_engine/validators/noise_precursor.py                  1
scripts/fetch_ims_bearings.py                                  1
scripts/real_data_titration.py                                 2
src/noise_titration.py                                         1
```

12 files, 13 replacements.

## Left in place, for the owner's call

These are identity or rights records, not attributions. Removing the name from them would
change what the line records, so they are listed here instead of edited:

```text
CITATION.cff                               citation author record (given-names)
metadata.json                              author record
tools/corpus_hardening/configs/*.json      author records in 16 config files (one per target repo)
vendor/                                    upstream copy; no hits, and never edited here
```

## Where removing the name changed meaning

None found. Every change is in a co-authorship header or the `co_authored` field.

## Test results

The suites were run before and after the sweep, and the counts below match. See the
commit message for the exact commands.

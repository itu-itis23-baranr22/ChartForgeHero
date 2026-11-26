# Measuring against human charts

How ChartForgeHero is scored against charts made by people, and where its settings live. Back to the [README](../README.md).

## Running the evaluation
```
python -m chartgen evaluate references
python -m chartgen evaluate references --split test --output report.json
```

References are `.sng` files or folders holding `notes.chart` or `notes.mid` with their audio, kept in
`references/train/` and `references/test/`. Those folders are ignored by git: no reference may enter
the repository. The tool runs the real analysis on each and reports every metric per song and on
average, with each split on its own.

Weights and thresholds may only be tuned on `train`, whose scores are flattered by that tuning. A new
reference goes to `test`, and is measured before anything else happens.
`CHARTGEN_REFERENCE_DIR=references pytest -m real` runs this as a test.

Each song's structure is compared too, where the human chart has it: section boundaries (F1 within one
bar, next to naive boundaries every N bars), star power phrases per instrument, and the preview start.

The report shows each difficulty next to the human's, along with what two naive reductions of the same
Expert chart would score: deleting every Nth note, and keeping beats first. On Californication, the
reference the tests run against, every drum level must beat both and every bass level must beat
"beats first". It also says how far each
lane's share is from the human's (10 points is the limit, which only warns) and which soft targets a
level misses.

The weights of the fret mapper live in `chartgen/chart/fret_weights.toml`, and bass has its own in
`bass_fret_weights.toml` next to it. The rules that keep a chart playable are in
`chartgen/chart/fret_mapping.py`, and tests check them under random weights.
The limits for vocal bleed live in `chartgen/audio/vocal_bleed.toml`, and the rule for bass notes far
below the song's median note, which is off, in `chartgen/audio/quiet_notes.toml`. How difficulties are reduced
lives in `chartgen/chart/difficulty.toml`, and for bass in `bass_difficulty.toml`, whose soft targets only
warn. For bass, the report also gives each level's orange notes by pitch, and warns if more than 70% are
one pitch. The rules that always hold are in
`chartgen/chart/difficulty.py`, and the file cannot weaken them.

## Where the README's numbers come from

The F1 table in the README is the mean over the training songs after the last tuning step (2026-11-16):
guitar and bass Expert over all 8, their Hard, Medium and Easy over the 7 whose human chart has them
(Fat Lip has Expert only); drums over the 7 with drums (Parallel Universe's drum chart was skipped),
their lower levels over 6. Guitar Expert on the 4 test songs is 0.684 on average and 0.744 as the median
(0.778 on average without Queen and 1981). The measurements and every tuning step are
recorded in [STATUS.md](STATUS.md) (in Turkish).

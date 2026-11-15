# Specification

The project owner's specification, kept here so that later phases can work from it.
Decisions made since it was written are listed first and take precedence.

## Decisions that change the original text

1. **There was no existing code.** The original text assumes a finished `core/` package, 103
   passing tests and an existing Viterbi fret mapper. None of them existed. The project was
   started from scratch, so the foundation was built first, and the Viterbi mapper and difficulty
   reduction must be written in Phase B rather than reused.
2. **Drums are 4-lane Pro: a kick and four pads.** The owner's first request called this "5-lane"; on
   2026-11-10 the owner confirmed that was a slip and that the layout meant is the one the original
   mapping describes, 0 = kick to 4 = green. In `.chart`, `N 4` is green on 4-lane and orange on 5-lane,
   and 5-lane green is `N 5`, so `N 5` is never written on drums. Cymbal flags 66/67/68 exist only on
   4-lane Pro and are part of the first version (decision 32). Every drum chart comes with
   `pro_drums = True`; `five_lane_drums` is never set.
3. **No stem audio is ever dropped.** The original text produced no audio file for a stem that
   fails the presence check, which would silently remove, for example, a quiet piano. Such stems,
   and those of instruments that were not requested, are mixed into `song.ogg`.
4. **libsndfile instead of ffmpeg.** ffmpeg was not installed; libsndfile is already a dependency
   for decoding and also writes Ogg Vorbis. Lengths and alignment are verified after encoding.
5. **Validator additions.** A `[SyncTrack]` must have `B` and `TS` events at tick 0.
6. **Phase B is split** into B1 (time signature, sustains, Viterbi mapping at Expert), B2 (difficulty
   reduction) and B3 (bass and keys; a song without a guitar still builds). For each, acceptance
   criteria and a test plan are approved before any code is written.
7. **Tempo events are decided in milliseconds, not percent.** A song keeps one tempo unless a
   region's beats stray more than `--max-beat-drift-ms` (default 25) from the grid; then that region
   gets an event. Each event must measurably bring onsets closer to the grid or it is merged away, and
   `analysis.json` records its reason and gain. Regions can stay over the limit when an event there
   would not help, which the decision text states.
8. **Bars read stems.** The tempo still comes from the original mix as specified, but bar phase uses
   the separated drums, bass and pitched stems when available: clearer on every measured song
   and about ten times faster. Without stems it falls back to a harmonic/percussive split of the mix.
9. **Chords are part of B1**, at the owner's request. A distorted-chord alternative such as
   `basic-pitch` must not be added before checking version, license and Windows/Python compatibility
   and asking the owner.
10. **Reference charts.** The owner's human-made charts are the objective yardstick. They live outside
   the repository, in `references/train/` and `references/test/`, and `chartgen evaluate` reports the
   two apart. Weights and thresholds may be tuned on `train` only. Californication was used for tuning,
   so it is `train`. New references go to `test`: measure them first, tune nothing, then ask the owner.
11. **Vocal bleed.** A note is removed if the vocals are louder than the stem at that moment, the stem
   is well below its usual level and it does not stay. Vocal loudness alone would remove real guitar.
   Limits are in `chartgen/audio/vocal_bleed.toml`; `analysis.json` lists every vocal-dominant note,
   whether it was removed and why.
12. **The direction target of 65% is deferred.** 60% was accepted by the owner for now; it is to be
   measured again on test references.
13. **The median-based chord limit is a temporary measure** for heavy distortion. It warns in the
   terminal and in `analysis.json` whenever it is in force.
14. **No commit unless the checks pass.** The hook in `.githooks` runs `scripts/check.ps1` on every
   commit (`git config core.hooksPath .githooks`): the quick tests and the validator, under a minute.
   Before each phase commit, `scripts/check.ps1 -Full` runs every test, with real Demucs and the
   reference songs, and the report says so. `scripts/check.ps1 -Mid` runs everything but the real
   songs and references, for a check in between.
15. **Separation is reproducible.** Demucs draws a random time shift for each pass, which made two
   caches of one song differ by up to 0.01 note F1. The shift is now seeded, and the cache key names
   the model, device kind, seed and shifts. A first build reads its stems back from the cache, so it
   sees the same 24-bit samples as every later build. Checked bit for bit on one CPU. GPU results are
   not verified, neither against each other nor against the CPU, so they never share a cache entry.
16. **Difficulty rules are split in two.** Hard rules are structural, live in
   `chartgen/chart/difficulty.py`, cannot be weakened from the configuration and raise an error if
   broken: positions form a chain Easy, Medium, Hard, Expert by tick, while frets may differ per level;
   Easy has no chords and no orange; Medium has no orange and chords of at most two notes; a sustain
   never runs into the next note; every phrase of more than four notes keeps a note on Easy; the
   result is deterministic. Everything else is a soft target in `chartgen/chart/difficulty.toml`:
   density, chord share, lane shares, on-beat share, shortest gap, sustain share. Missing one warns in
   the terminal and in `analysis.json` and fails nothing. The ranges come from one calm song and are
   to be set again on test references.
17. **Three-note chords on Hard are a setting**, `three_note_chords`, off by default.
18. **Chord rule.** Hard and Medium keep a chord's lowest two notes, Easy its lowest note. The kept
   notes never change their distance from each other; the chord may slide along the neck to fit the
   level. Lowest plus highest was the first idea, but the human chart measured keeps the lowest two in
   84% of its reduced chords against 16%, and lowest plus highest needs shapes this project forbids.
   On Hard and Medium chords prefer low frets (`chord_lane_map`), but only weakly (`chord_fidelity`):
   our analysis mostly hears two voices and places them high, where a human writes a wide chord whose
   lowest two notes sit low. A strong pull passes every lane target and makes most chords one shape.
19. **HOPOs are measured on every level** and reported by `evaluate` and `analysis.json`. The game
   derives natural HOPOs from spacing: a single note at most `65/192 * resolution` ticks after the
   previous position, and not the same single fret as it. A force flag flips that, so it may only ever
   land on a natural HOPO. Medium and Easy force every natural HOPO to a strum; Hard keeps them
   (`keep_auto_hopos`). The share on each level is a soft target that changes nothing about the chart:
   it follows style more than quality. Fast chords cannot be HOPOs and fast single notes can, so one
   song's human guitar has 0.9% on Expert and its human bass 12.3%.
20. **A note that could not be snapped still has a place in the bar**: the nearest sixteenth. Otherwise
   a slightly late beat counts as a rhythm of its own. On the measured chart this raised note F1 on
   Hard from 0.70 to 0.73 and on Easy from 0.54 to about 0.75.
21. **The grid's beat is checked against the kick.** A 3-3-2 groove leads the tracker onto snares half a
   beat from the pulse, which no onset measure can see, since every note stays on a sixteenth. The
   grid moves half a beat if the drum stem is really there, its kick lands at least twice as hard
   between the grid's beats, the snare does not mark those beats (off-beats at least 0.8 of beats), at
   least half the song's sections agree and the lead is two standard errors or more. This also applies
   with `--bpm`. It needs the drum stem. The limits rest on five songs, one of which moved, and that
   one has no human chart. A bare 3-3-2 with nothing else up high looks like a backbeat and stays off.
22. **An opening that does not fit is not drift.** When tempo events are turned down, the grid is
   measured from where the onsets start to fit it, with each beat counted from its nearest eighth note,
   because a tracker on the off-beat is half a beat from a grid that is right. The opening is reported
   in `analysis.json` and in a warning. This changes what is reported and never the tempo map.
23. **Tied bar phases go to the harder kick.** Below one standard error the phases are a tie. The bars
   still report low confidence, so the warning to check them by ear stays on.
24. **Bass reads its real pitch and has no chords.** One note at a time means `librosa.pyin` works, with
   no new dependency, and it raised the direction of the moves from 0.44 to 0.655 on the human chart.
   A note with no readable pitch falls back to what the mapper does without one. No chords is a hard
   rule on every level: the mapper cannot choose one, the track is checked, and so is the written file.
   The vocal bleed check stays off for bass, where 83% of the notes it removed were real.
25. **No instrument has a note in an opening that is not part of the song.** The owner's decision, and a
   hard rule. No separate tempo is written for such an opening. Its start gets the section `Intro`, and
   the first clear onset after it, snapped to a sixteenth, gets the section `Song`, or practice mode
   would call the whole song the intro. A song with no such opening gets no section at all.
   The charter drops a note by where it lands, the build checks every track of any instrument, and the
   validator checks the written chart against what `analysis.json` reports.
26. **`--click-overlay` writes `debug/debug_click.wav`**, keeping the song's own files on their own.
27. **The quiet note rule exists and is off.** A bass note far below the song's median bass note may be
   the kick leaking in. The owner set two conditions for turning it on: note F1 on the human bass chart
   drops by at most 0.005, and none of the 11 Toca notes checked by ear is removed. 18 to 20 dB fail the
   second on one note. 24 dB meets both but catches 2 of Danza's 16 suspect notes, which by ear are mostly
   not real. Suspect notes of Danza and real ones of Toca lie equally far below their medians, so this
   measure cannot tell them apart. `analysis.json` lists the notes it points at either way. General kick
   filtering was rejected: on the human chart, 96% of the bass notes that land on a kick are real.
28. **Bass has its own settings and four levels.** `chart/bass_fret_weights.toml` and
   `chart/bass_difficulty.toml` have the same keys as guitar's files, which stay as they are: tests pin
   their hashes. The reduction is the same code and its hard rules apply, with no chord on any level.
   Guitar's weights kept bass off orange altogether (0.1% against the human chart's 14.7%): a line climbing
   from blue did better staying there, however far it climbed. The chosen weights match the share of
   orange, not its notes, since the human chart also has orange on low notes. Because they were chosen on
   Californication, its bass counts as train. Hard's shortest gap of 0.25 s also allows an eighth note
   (`min_gap_beats`), so that it does not thin out a fast song. Below 120 BPM that changes nothing.
29. **Which pitches are orange is reported.** `analysis.json` and `evaluate` give each level's orange notes
   by pitch. More than 70% on one pitch warns (`orange_pitches` in `bass_difficulty.toml`) and fails nothing.
   A guitar's notes have no pitch to read, so this applies to bass only.
30. **Keys are not verified on real data.** None of the five songs measured has a piano stem that counts as
   present, and the one human keyboard chart has 17 positions. Keys therefore follow guitar's path and
   files, have no soft targets, and were tested on synthetic audio only. Builds say so in the terminal and
   in `analysis.json`. The presence limit for piano stays where it was. Once a song with a dominant piano
   turns up, keys are to be checked in the game and with `evaluate`.
31. **Section names are guarded.** An instrument may only be written under its own name: guitar `*Single`,
   bass `*DoubleBass`, keys `*Keyboard`, drums `*Drums`. GHL and 6-fret sections are never generated. The
   validator keeps its own table of these names rather than reading the writer's.
32. **Drum gems and how they are written.** The owner approved the Phase C plan on 2026-11-10, with cymbal
   flags in the first version. Kick `N 0`, snare red `N 1`, hi-hat yellow cymbal `N 2` + `N 66`, ride blue
   cymbal `N 3` + `N 67`, crash green cymbal `N 4` + `N 68`, high and mid tom yellow and blue `N 2` and
   `N 3`, floor tom green `N 4`. Red is never a cymbal. Never written on drums: `N 5`, 2x kick `N 32`,
   accents, ghosts, sustains, rolls and fills. The writer refuses the notes and has no way to write rolls
   or fills; the validator rejects every one of these notes.
   Reading a human chart follows the game: song.ini tags first, then the notes. In `.chart` a pad is a tom
   unless a cymbal flag marks it; in `.mid` yellow, blue and green are cymbals unless a tom marker (110-112)
   covers them. A chart that is not Pro has no cymbals. 5-lane charts and disco flip are left out rather
   than read wrong.
33. **Drum hard rules.** In code and in the validator, and drum settings, which live in their own
   `drum_*.toml` files, cannot loosen them: every level is made of the gems of the level above, at the same
   ticks, so a kick stays a kick and a cymbal a cymbal; at most two pads at once on every level, for two
   hands; at most two gems at once on Hard and Medium; on Easy never the kick together with a pad; nothing
   on a sixteenth on Medium and Easy; no sustain; no note in an opening that is not part of the song; the
   result is deterministic. Density, gem shares, on-beat share and the shortest gap are soft targets.
34. **Drum classification.** Thresholds are relative to the stem's own strong hits; no threshold may fix
   the density. The same pattern at two levels must give the same hits, which is tested and part of the
   acceptance criteria. Toms and crash cannot be measured on the one reference (16 tom gems, 41 green
   cymbals), so builds mark them as not verified, in the terminal and in `analysis.json`. The classifier is
   also measured against the reference's own drum channels (`drums_1` kick, `drums_2` snare, `drums_3`
   the rest), for diagnosis only. Guitar and bass stay byte for byte as they are, pinned by hashes in
   `check.ps1 -Full`.
35. **How drums are heard (C.1).** Three detectors side by side: the kick at 30-130 Hz and the snare at
   150-600 Hz on linear spectral flux, the cymbals at 7-11 kHz on decibel flux. Each calls a high percentile
   of its own peaks a strong hit and keeps the peaks that reach a share of it. Leaks are judged by comparing
   two bands at one moment from one spectrum: the snare band must rise at least as much as the kick band,
   the kick band at least 0.3 times the snare band, and a cymbal's high band must come within 48 dB of the
   stem's loud level. NMF is not used: under these thresholds a linear band found the kick better (F1
   0.962 against 0.952) and costs no extra fit. Hi-hat, ride and crash are told apart by how long the
   high band rings. The chart keeps one gem per lane (a cymbal wins it over a tom) and at most two pads per
   tick (the snare first, then the louder cymbal).
36. **How drums are reduced (C.2).** Hard comes from Expert, Medium from Hard, Easy from Medium. Where a
   position holds more than a level allows, gems give way in the order of `drum_difficulty.toml`: the snare
   stays longest, then the crash, the ride, the kick, the hi-hat and the toms. Hard and Medium keep two
   gems; Easy keeps one, and a second only if it is the snare, the crash or the ride. Positions are then
   chosen best score first (place in the bar, how hard the hit was, a weight per gem) up to 76 / 64 / 54%
   of Expert, at least a sixteenth apart on Hard and an eighth on Medium and Easy; the snare on beats 2
   and 4 always stays. These values come from the one human drum chart (Californication, train). The hard
   rules of decision 33 are in code and in the validator; the file cannot decide any of them.
37. **Phase D, approved 2026-11-11.** Steps D.0 (measuring, no audio analysis, outputs unchanged), D.1
   sections, D.2 preview, D.3 star power, with approval after each.
   - Sections are named by structure: a repeated part gets the same letter (`section A1`, `section B1`,
     `section A2`...), ASCII only. An opening that is not part of the song keeps `Intro` and `Song`. A song
     whose texture hardly changes gets no forced sections: it keeps only those, and the build warns.
   - Boundaries are scored within one bar against the human's, and must beat naive boundaries every N
     bars in every case; F1 0.55 is the floor, the final threshold is proposed after D.1 is measured.
   - The preview starts four bars before the second start of the most energetic repeated section. With
     no sections it falls back to the loudest window, moved onto a bar line.
   - Star power on guitar, bass, keys and drums: phrases of one bar, about every 20 to 30 seconds. How the
     game activates drum star power, and whether it needs fills, is checked in the game in D.3.
   - No lyrics: they would need speech recognition and alignment (noted for later in STATUS.md).
   `vocals.ogg` has been written since Phase A.
38. **How sections are found (D.1).** Each bar is described by the chroma of the pitched stems, the MFCC
   and loudness of the mix and the loudness of the vocals, standardised over the song with a floor on each
   spread, so that a loop that never changes is not blown up into sections. A section starts where Foote's
   novelty over an eight-bar checkerboard reaches 0.18 (on a scale where two unrelated parts score 0.5),
   strongest first and at least four bars from any other; there is no fixed count. A section takes the
   letter of an earlier one whose bars, side by side from the start, are 0.6 similar on average. After an
   opening, `Intro` and `Song` stay and the found sections start after `Song`; the part `Song` starts is
   lettered like any other (it is `A1`, still written as `Song`), so its return is `A2` (owner,
   2026-11-12). Settings in `audio/sections.toml`; bar lines, the four-bar minimum and ASCII names are hard
   rules in code and in the validator. On Californication (train) the boundary F1 within one bar is 0.750
   against 0.385 at best for naive boundaries; the test requires at least 0.70 (owner, 2026-11-12). A lower
   letter threshold was measured and rejected: from 0.55 down, pairs Californication's human calls
   different parts get one letter (0.86 of same-letter pairs the same kind at 0.6, 0.72 at 0.55, 0.64 at
   0.5).
39. **How the preview is placed (D.2).** `preview_start_time` is four bars before the second start of the
   letter that comes back whose bars are loudest in the mix on average (mean RMS in dB over all its bars;
   the part `Song` starts counts as its letter's first). With no letter that comes back, or no sections,
   it is the loudest 30 seconds after any opening, moved to the nearest bar line, and the build warns.
   Hard rules in code (`chart/preview.py`): on a bar line, not before `Song`, and the 30 seconds fit in the
   song (moved earlier bar by bar if not); only a song shorter than the preview after its start begins it
   with the song. The validator checks on its own, from `notes.chart` and `song.ini`, that the preview is
   not before `Song` and that it fits. On Californication (train) it lands 0.18 s from the human's
   (174.6 s against 174.4 s, four bars before chorus 2); the loudest window was 285.1 s. Acceptance
   criterion, approved 2026-11-15 and in the test: at most one bar, of the human chart, from the human's.
40. **Star power (D.3), approved 2026-11-15.** Every charted instrument gets phrases (`S 2`) one bar long,
   the same on all four of its levels, placed on its own notes: the first about 15 s after the song starts,
   each next in the bar closest to 25 s after the last, 20 to 30 s apart, among the bars that hold a note on
   every level; bars with two or more notes on Easy come first. Hard rules in code (`chart/star_power.py`)
   and, on its own, in the validator: a phrase starts on a bar line, phrases do not overlap, every phrase
   holds a note (in code on every level), and no phrase starts before the song does (`Song` after an
   opening). Soft targets in `chart/star_power.toml`: 1.5 to 3 phrases a minute, no gap over 30 s, two
   notes on Easy. Drums get no activation fills (`S 64`): how the game activates drum star power without
   them was not checked in the game, and `analysis.json` says so (`star_power.not_verified_in_game`). The
   owner chose to leave the drum test for later; the experiment is kept in `outputs/_experiments/`.
41. **Tempo octave (reference tuning, step 1, 2026-11-15).** The tempo search still stops at 160 BPM, so a
   faster song is first found at half its tempo. Then the snare decides (`check_double_time` in
   `audio/meter.py`): the drum classifier's snares are placed on the eighth-note grid, and in windows of 8
   beats it is counted whether they fall on both even and odd beats. A backbeat at the right tempo falls
   on one parity (beats 2 and 4), read at half tempo on every beat. The beat is split in two when at least
   65% of the counting windows show both parities, at least 8 windows count, at most 60% of the snares come
   with a kick (more means the kick leaks into the snare band, as in Toca Toca), and the split tempo stays
   at 230 BPM or below. `--bpm` is never split. Every beat that was on the grid stays on it. Values from
   the train references and the owner's songs only. Drum levels also get a floor in seconds next to their
   floor in beats (`min_gap_s` in `chart/drum_difficulty.toml`: Hard 0.10, Medium 0.20, Easy 0.20), below
   every human value in train and without effect at 150 BPM or slower; otherwise a split tempo would let
   eighth notes into Easy.

## Phase B1 targets (one reference song so far)

| Metric | Before B1 | Target |
|---|---|---|
| Note position F1 (70 ms) | 0.72 | at least 0.72 |
| Direction when the human changes lane | 47% | at least 65% |
| Direction over all steps | 41% | at least 60% |
| Chord or single note agreement | no chords | at least 65% |
| Sustain F1 | no sustains | at least 50% |
| Bars agreeing with the human | 97.7% (4/4 assumed) | at least 95%, now detected |

Also: 5 real songs read as 4/4; low bar confidence warns and is written to `analysis.json`; bars
improve on `LastResort.wav`; a bot plays the result; the owner plays one song and approves it.

21. **Lane shares are a soft target on every level.** Each lane's share may stray at most 10 points from
   the human's. `evaluate` compares with the human chart of each song. A build has no human chart, so
   it compares with the shares in `difficulty.toml`, which come from one calm song, and warns.

## Phase B2 targets (one reference song so far; these are soft)

Compared with the human on the same level. "Beats first" and "every Nth" are naive reductions of the
same Expert chart, to the human's note count, measured by `chartgen evaluate`. Expert itself has two
soft targets: each lane's share within 10 points of the human's, and automatic HOPOs at most 5%.

| Metric | Hard | Medium | Easy |
|---|---|---|---|
| Positions / Expert | 60-75% | 37-50% | 22-33% |
| Chord share | 40-70% | 40-70% | none (hard rule) |
| Orange share | at most 10% | none (hard rule) | none (hard rule) |
| Blue share | | | at most 5% |
| On the beat | at least 50% | at least 70% | at least 65% |
| On sixteenths | at most 5% | at most 5% | at most 5% |
| Shortest gap | at least 0.15 s | at least 0.30 s | at least 0.50 s |
| Sustain share | 9-29% | 6-26% | 10-30% |
| Each lane's share | human +/- 10 points | human +/- 10 points | human +/- 10 points |
| Automatic HOPOs | at most 3% | at most 1% | at most 1% |
| Note F1 must beat "beats first" of | 0.68 | 0.59 | 0.38 |

## Goal

A Python project that produces playable Clone Hero song folders from local MP3/WAV files the user
owns: separate the song into instruments and vocals, generate a chart per instrument and create the
complete song folder Clone Hero reads.

Out of scope: pirated downloads, pulling audio from streaming sources, DRM bypass. The tool only
processes local files the user provides.

## Clone Hero requirements (official manual)

- Each song sits in its own folder under `Songs/` with at least `notes.chart` (or `notes.mid`), an
  audio file and `song.ini`.
- A `song.ini` missing `name` or `artist` makes it a "bad song", which does not appear.
- Playable instruments: Guitar, Bass, Rhythm, GuitarCoop, Keys, Drums, ProDrums (plus 6-fret
  variants). Vocals are not a playable instrument.
- With only `song.ogg`, per-instrument volume does not work, so each stem gets its own audio file.
- CLI preview: `"<CloneHero>" --song "<folder>" --player Guitar,Expert -i` (a bot plays the chart;
  at most 4 players; `-i` shows instrument names on the highway).

## Stem, file and chart mapping

Model: Demucs `htdemucs_6s` (drums, bass, other, vocals, guitar, piano)

| Stem | Audio file | .chart sections |
|---|---|---|
| guitar | guitar.ogg | [ExpertSingle] [HardSingle] [MediumSingle] [EasySingle] |
| bass | bass.ogg | [ExpertDoubleBass] ... [EasyDoubleBass] |
| drums | drums.ogg | [ExpertDrums] ... [EasyDrums] |
| piano | keys.ogg | [ExpertKeyboard] ... [EasyKeyboard] |
| vocals | vocals.ogg | No chart; optionally phrase_start/lyric/phrase_end in [Events] |
| other | song.ogg | None (backing track) |

Rules:

- All audio files have the same length and are sample-aligned (verified after encoding).
- Decide per stem from energy/RMS whether the instrument is there. If not: no chart section and
  `diff_* = -1` in `song.ini` (see decision 3 for its audio).
- The `piano` stem of this model is weak, so Keys uses a higher presence threshold.
- Stem bleed creates false onsets: apply a noise gate and an adaptive onset threshold per stem.

## Analysis rules

- The tempo map (BPM, beat grid, time signature) comes once from the ORIGINAL MIX; all instruments
  share the same [SyncTrack].
- Onset, pitch, sustain and chord detection run on the STEM.
- Guitar, bass, keys: playability-aware fret mapping (Viterbi) and difficulty reduction based on
  salience, beat strength and phrases, NOT "delete every Nth note". No one-to-one pitch-to-fret mapping.
- Drums: percussion classification instead of fret mapping (kick, snare, hi-hat, tom, cymbal). For
  the first version a simple classifier on spectral band energy is enough. Output: 0=kick, 1=red/snare,
  2=yellow, 3=blue, 4=green. ProDrums cymbal flags (66/67/68) are a later phase. (Decisions 2 and 32:
  this layout is 4-lane Pro, and the cymbal flags moved into the first version.)

## Output format

`.chart`: Resolution = 192, [Song], [SyncTrack] (B value is BPM x 1000, TS), [Events] (section
markers), instrument sections. Note line: `tick = N fret length` (0-4 = G R Y B O, 5 = forced,
6 = tap, 7 = open); star power: `tick = S 2 length`.

`song.ini` (under `[song]`): name, artist, album, genre, year, charter, song_length (ms),
preview_start_time, delay, diff_guitar, diff_bass, diff_drums, diff_keys.

Folder: `outputs/<Artist - Title>/` with notes.chart, song.ini, song.ogg and the stem .ogg files.

## Phases and acceptance criteria

**Phase A: stem separation and packaging.** From one MP3, a folder with separated stems and a simple
onset-based guitar chart. Clone Hero does not call it a bad song when scanning; a bot plays it in the
CLI preview.

**Phase B: a chart per instrument.** Guitar, bass and keys at 4 difficulty levels; optimizer and
Viterbi mapping work on stem input.

**Phase C: drums.** Drum chart at 4 difficulties; kick/snare separation correct in a synthetic test.

**Phase D: vocals and finishing touches.** vocals.ogg packaged; optional phrase/lyric events; section
detection; star power placement.

## Testing and debugging

- Unit tests and synthetic input tests: a 120 BPM 4/4 click; a synthetic kick/snare pattern; a mix of
  two sine stems.
- Tests running Demucs on synthetic audio are marked `@pytest.mark.slow`, tests on the owner's songs
  and the references `@pytest.mark.real`; the default run skips both and passes without downloading
  the model (separation is mocked). A real song is loaded once per test session and shared by its
  tests; `scripts/check.ps1 -Mid` runs everything but the real songs.
- Each stage has its own terminal output and duration; each build writes `analysis.json` (BPM, stem
  presence scores, note counts per instrument, difficulty distribution).
- A `.chart` validator parses the generated file again and checks tick order, section names and fret
  ranges.

## Way of working (mandatory)

- Do not create everything at once. For each phase, deliver in order and wait for approval:
  1. What will be done and why
  2. File structure (new and changed files)
  3. Code
  4. Terminal commands to run
  5. Expected output
  6. Possible errors and solutions
  7. Next step
- Real, working code rather than pseudo-code: type hints, docstrings, error handling, logging,
  testability.
- Before adding a dependency, state why and which version.
- All existing tests must still pass at the end of each phase.

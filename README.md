# chartgen

Generates playable [Clone Hero](https://clonehero.net/) song folders from local audio files
you own: it separates a song into stems, charts them, and packages everything the game needs.

It only processes files you give it. It does not download audio or touch streaming services.

## Status

| Phase | Scope | State |
|---|---|---|
| Foundation | Format-independent chart model, `.chart` exporter, validator | Done |
| A | Stem separation, packaging, simple onset-based guitar chart | Done |
| Tempo check | `--click-overlay`, `--bpm`, `--max-beat-drift-ms`, explained tempo events | Done |
| B1 | Time signature, chords, sustains, Viterbi fret mapping, vocal bleed removal (Expert) | Done |
| B2 | Difficulty reduction to Hard, Medium and Easy | Done |
| B3 | Bass and keys; a song no longer needs a guitar | Done; keys not verified on real data |
| C | Drums (4-lane Pro): percussion classification, four difficulties | In progress: C.0 format, C.1 Expert and C.2 lower levels done; waiting for play-testing |
| D | Sections, preview, star power, vocals | Done; drum star power activation not checked in the game, no lyrics |

Guitar, bass, keys and drums are charted at all four difficulties, so a song needs at least one of the four.
Drums are 4-lane Pro with cymbals; toms and the crash are not verified on real data, and a build says so.
Keys have only been tested on synthetic audio, and a build says so. Telling chords from single notes on heavily distorted guitar is unverified. 3/4 and 6/8 have only
been tested on synthetic audio.

See [docs/SPEC.md](docs/SPEC.md) for the full specification.

## Install

Needs Python 3.11 or newer. No external programs: audio is read and encoded by libsndfile.

```
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[separation,editor,dev]"
```

`requirements.lock.txt` records the exact versions this was tested with.

The first build downloads the Demucs `htdemucs_6s` weights from Hugging Face. Without a GPU,
separation took 74-99 s for songs of 166-235 s on a 16-thread CPU. Each song is only ever separated
once: stems are cached under `.cache/stems`, at about 160 MB per song. The same file gives the same
stems: the randomness in Demucs is seeded, and the cache key names the model, device kind, seed and
shifts.

**GPU:** identical stems are verified bit for bit on one CPU only. Whether a GPU repeats its own results,
or matches the CPU, has not been checked. Each kind of device therefore gets its own cache entry, and
a chart built on a GPU may differ slightly from one built on a CPU.

## Usage

```
python -m chartgen build song.mp3 --artist "Artist" --title "Title" --instruments guitar,bass,drums
python -m chartgen validate "outputs/Artist - Title"
```

The song appears in `outputs/Artist - Title/`:

| File | Content |
|---|---|
| `notes.chart` | The chart |
| `song.ini` | Metadata; `diff_*` is `-1` for instruments without a chart |
| `song.ogg` | Backing track: the `other` stem plus every stem without its own file |
| `guitar.ogg`, `bass.ogg`, `drums.ogg`, `keys.ogg`, `vocals.ogg` | Stems that are really present |
| `analysis.json` | Tempo and why, stem presence scores, note counts, stage timings, warnings |
| `debug/debug_click.wav` | Only with `--click-overlay` |

Preview it with bot players, without scanning your library:

```
"<path to Clone Hero.exe>" --song "<song folder>" --player Guitar,Expert --player Guitar,Hard --player Guitar,Medium --player Guitar,Easy -i
```

A build prints this command for each instrument it charted, for example `--player Bass,Expert`. Drums
are 4-lane Pro and play as `ProDrums`: with `Drums` the game shows every cymbal as a pad.

To add it to your library, copy the folder into Clone Hero's `Songs` folder and press
*Settings > General > Scan Songs*. Songs the game rejects are listed in `badsongs.txt`.

### Checking the tempo by ear

```
python -m chartgen build song.mp3 --artist "Artist" --title "Title" --click-overlay
python -m chartgen build song.mp3 --artist "Artist" --title "Title" --bpm 97 --click-overlay --force
```

`--click-overlay` adds `debug/debug_click.wav`: the original mix with a metronome taken from the written
`notes.chart`, the first beat of each bar an octave higher. A wrong tempo audibly slides away from
the drums. `--bpm` forces one exact tempo; the phase and the first downbeat are still detected.
`--max-beat-drift-ms` sets how far a region's beats may stray from one tempo before it gets an event.

`--drum-ear-test` adds `debug/drums_kick.wav`, `drums_snare.wav`, `drums_hihat.wav`, `drums_ride.wav`,
`drums_crash.wav` and `drums_toms.wav`: the drum stem with a click on every hit of that part, read back
from the written chart. Each click should fall on that part, and the part should not sound without one.

## Web editor (in progress)

Opens the song folders in `outputs/` in your browser, on this machine only (127.0.0.1): the chart drawn
over time, one instrument and level at a time with the level below it faint, bars, tempo changes,
sections, star power and what the validator says. Read-only for now; playback, editing, saving and
copying to the game follow (phase E, `docs/SPEC.md` decisions 49-57).

```
pip install -e ".[editor]"
chartgen edit                  # serves http://127.0.0.1:8765/ and opens it
chartgen edit --port 9000 --no-browser --outputs other_folder
```

Scroll with the wheel or the arrow keys, zoom with Ctrl and the wheel or plus and minus, click a note
to see its bar, tick and time. The page loads nothing from the internet; its fonts (Barlow Semi
Condensed and Cascadia Mono, SIL Open Font License) ship with it.

## Measuring against human charts

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
Expert chart would score: deleting every Nth note, and keeping beats first. It also says how far each
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

## How it works

1. **Separate** the song with Demucs, cached by the file's SHA-256.
2. **Check presence**: a model always outputs all six stems, so each is compared with the mix,
   and a stem that is only bleed gets no chart. Its audio moves to `song.ogg` rather than vanishing.
3. **Track tempo** once on the original mix; all instruments share this map. A whole-song analysis
   finds the tempo, because a beat tracker left to itself read 129 BPM for a 97 BPM song. Told that
   tempo, the same tracker finds the beats. A song keeps one tempo unless a region's beats stray more
   than `--max-beat-drift-ms` (25 by default) from it. Then that region gets a tempo event, but only
   if the event brings the onsets around it closer to the grid. `analysis.json` records each event's
   reason and gain. Against a human-made map of one real song: 94% of beats within 35 ms, using 25
   tempo events where the human used 123. The drum stem then checks the beat itself: a 3-3-2 groove
   can lead the tracker half a beat off the kick, so the grid moves if the kick and the snare both say
   so. An opening whose onsets do not fit the grid, such as the talking start of a video, is reported
   apart and warned about rather than counted as drift. No instrument gets a note there. Its start
   is marked with the section `Intro`, and the song's own start with the section `Song`.
   Sections follow where the song's texture changes: harmony, timbre, loudness and voice, compared bar
   by bar. They start on bar lines, last at least four bars and are named by structure: a part that
   comes back gets the same letter (`A1`, `B1`, `A2`...). After an opening, the part `Song` starts is
   `A1` too, so its return is `A2`. A song that hardly changes gets none, and the build says so.
   The song list's preview starts four bars before the second start of the loudest part that comes
   back, so it runs into a part already heard once. Without one it is the loudest 30 seconds on a bar
   line. It never starts in an opening, and its 30 seconds fit in the song.
   Every instrument gets star power: one-bar phrases about every 25 seconds, the same on all four of
   its levels, each on a bar line and holding a note on every level. Drums get no activation fills;
   how the game activates drum star power without them has not been checked in the game.
4. **Detect onsets** on each stem, behind a noise gate and an adaptive threshold that reject bleed.
5. **Remove vocal bleed**: a note where the singer is louder than a stem that is unusually quiet and
   does not stay is a trace of the vocals, not an instrument. `analysis.json` lists these.
6. **Read each note**: how its spectrum moves relative to its neighbours, whether it repeats the
   previous note, whether it is a chord, and how long it rings.
7. **Map to frets** with the Viterbi algorithm, following the contour within each phrase and never a
   fixed pitch for each fret, so the same riff played higher elsewhere keeps its shape.
8. **Reduce to Hard, Medium and Easy**: each level keeps the notes that matter most from the level
   above: where they fall in the bar, how hard they are struck, whether they are held, where they sit
   in their phrase. A phrase's first note always stays. Chords keep their lowest notes, and Viterbi
   then fits the result to the frets the level allows. Medium and Easy turn automatic HOPOs into
   strums. `analysis.json` holds each level's numbers and which soft targets it missed.
9. **Package and verify**: every encoded file is decoded again and must match its source's length
   exactly with zero lag, and the finished folder must pass an independent validator. The folder
   appears only once all of that succeeded, so a failed build leaves nothing behind.

## Development

```
pytest                 # no model download: separation is mocked
pytest -m slow         # runs real Demucs on synthetic audio
pytest -m real         # your songs and the references; set CHARTGEN_MUSIC_DIR and CHARTGEN_REFERENCE_DIR
scripts\check.ps1      # quick tests and the validator, under a minute: runs on every commit
scripts\check.ps1 -Mid    # every test but the real songs and references
scripts\check.ps1 -Full   # every test, with real Demucs and the references: before a phase commit
node --test tests\js\tempo.test.mjs tests\js\view.test.mjs   # the editor's JavaScript (check.ps1 runs it too)
git config core.hooksPath .githooks     # makes every commit run the quick check
```

The check validates every folder in `outputs/` but those whose name starts with `_`, such as
`outputs/_songs_backup/`, where old copies of song folders from the game are kept.

The code is layered so that `chartgen.core` knows nothing about Clone Hero:

```
chartgen/
  core/       chart model, tempo map, exporter interface
  audio/      loading, separation, presence, tempo, meter, onsets, pitch, sustain, vocal bleed
  chart/      stems to tracks: charter, fret mapping, difficulty reduction, HOPOs, and their settings
  clonehero/  .chart and song.ini writers, packaging, validation
  evaluation/ reference charts and metrics
  pipeline.py the build, stage by stage
  cli.py      command line
```

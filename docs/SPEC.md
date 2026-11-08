# Specification

The project owner's specification, kept here so that later phases can work from it.
Decisions made since it was written are listed first and take precedence.

## Decisions that change the original text

1. **There was no existing code.** The original text assumes a finished `core/` package, 103
   passing tests and an existing Viterbi fret mapper. None of them existed. The project was
   started from scratch, so the foundation was built first, and the Viterbi mapper and difficulty
   reduction must be written in Phase B rather than reused.
2. **Drums are 4 pads plus kick, not 5-lane.** In `.chart`, `N 4` is orange on 5-lane but green on
   4-lane, and 5-lane green is `N 5`. The original mapping (0-4) is therefore a 4-lane layout, and
   the cymbal flags 66/67/68 planned for later only exist on 4-lane Pro. Do not set
   `five_lane_drums`.
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
8. **Reference chart.** The owner's Harmonix `.sng` of one song holds a human tempo map and chart, used
   as an objective yardstick. It is a single song, so limits must not be tuned to it alone, and no part
   of it may enter the repository.

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
  2=yellow, 3=blue, 4=green. ProDrums cymbal flags (66/67/68) are a later phase.

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
- Tests needing Demucs are marked `@pytest.mark.slow`; the default run passes without downloading
  the model (separation is mocked).
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

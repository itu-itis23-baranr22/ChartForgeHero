# Building songs

How to turn an audio file into a Clone Hero song folder with `chartgen build`, what the folder holds, and how to check the result. Back to the [README](../README.md).

## Install notes

`requirements.lock.txt` records the exact versions this was tested with.

The first build downloads the Demucs `htdemucs_6s` weights from Hugging Face. Without a GPU,
separation took 74-99 s for songs of 166-235 s on a 16-thread CPU. Each song is only ever separated
once: stems are cached under `.cache/stems`, at about 160 MB per song. The same file gives the same
stems: the randomness in Demucs is seeded, and the cache key names the model, device kind, seed and
shifts.

**GPU:** identical stems are verified bit for bit on one CPU only. Whether a GPU repeats its own results,
or matches the CPU, has not been checked. Each kind of device therefore gets its own cache entry, and
a chart built on a GPU may differ slightly from one built on a CPU.

## Build and validate
```
python -m chartgen build song.mp3 --artist "Artist" --title "Title" --instruments guitar,bass,drums
python -m chartgen validate "outputs/Artist - Title"
```

Guitar, bass, keys and drums are charted at all four difficulties; `--instruments` picks them (all four
by default), so a song needs at least one of the four. Drums are 4-lane Pro with cymbals; toms and the
crash are not verified on real data, and a build says so. Keys have only been tested on synthetic audio,
and a build says so. Telling chords from single notes on heavily distorted guitar is unverified. 3/4 and
6/8 have only been tested on synthetic audio.

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

## Checking the tempo by ear

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

## What a build does

The stages in the order `chartgen build` runs them (`chartgen/pipeline.py`):

1. **Separate** the song with Demucs, cached by the file's SHA-256.
2. **Check presence**: a model always outputs all six stems, so each is compared with the mix,
   and a stem that is only bleed gets no chart. Its audio moves to `song.ogg` rather than vanishing.
3. **Track tempo** once on the original mix; all instruments share this map. A whole-song analysis
   finds the tempo between 60 and 160 BPM, because a beat tracker left to itself read 129 BPM for a
   97 BPM song. Told that tempo, the same tracker finds the beats. A song keeps one tempo unless a
   region's beats stray more than `--max-beat-drift-ms` (25 by default) from it. Then that region gets a
   tempo event, but only if the event brings the onsets around it closer to the grid. `analysis.json`
   records each event's reason and gain. Against a human-made map of one real song: 94% of beats within
   35 ms, using 25 tempo events where the human used 123. The drum stem then checks the beat itself: a
   3-3-2 groove can lead the tracker half a beat off the kick, so the grid moves if the kick and the
   snare both say so. A song faster than 160 BPM is first found at half its tempo; when the snare falls
   on both the odd and the even beats in at least 65% of the song's 8-beat windows, the tempo is doubled
   (up to 230 BPM). An
   opening whose onsets do not fit the grid, such as the talking start of a video, is reported apart and
   warned about rather than counted as drift. No instrument gets a note there. Its start is marked with
   the section `Intro`, and the song's own start with the section `Song`.
4. **Find sections** where the song's texture changes: harmony, timbre, loudness and voice, compared
   bar by bar. They start on bar lines, last at least four bars and are named by structure: a part that
   comes back gets the same letter (`A1`, `B1`, `A2`...). After an opening, the part `Song` starts is
   `A1` too, so its return is `A2`. A song that hardly changes gets none, and the build says so.
5. **Chart each instrument**: detect onsets on its stem behind a noise gate and an adaptive threshold
   that reject bleed; remove vocal bleed (a note where the singer is louder than a stem that is unusually
   quiet and does not stay is a trace of the vocals, not an instrument; `analysis.json` lists these);
   read each note (how its spectrum moves relative to its neighbours, whether it repeats the previous
   note, whether it is a chord, and how long it rings); map it to frets with the Viterbi algorithm,
   following the contour within each phrase and never a fixed pitch for each fret, so the same riff
   played higher elsewhere keeps its shape. Drum hits are classified instead.
6. **Reduce to Hard, Medium and Easy**: each level keeps the notes that matter most from the level
   above: where they fall in the bar, how hard they are struck, whether they are held, where they sit
   in their phrase. A phrase's first note always stays. Chords keep their lowest notes, and Viterbi
   then fits the result to the frets the level allows. Medium and Easy turn automatic HOPOs into
   strums. `analysis.json` holds each level's numbers and which soft targets it missed.
7. **Place star power** on every instrument: one-bar phrases, the first 9 bars into the song and then
   about every 10 bars (7 to 13), the same on all four of its levels, each on a bar line and holding a
   note on every level. Drums get no activation fills; how the game activates drum star power without
   them has not been checked in the game.
8. **Package**: the chart, one `.ogg` per present stem and `song.ogg`, and `song.ini`. The song list's
   preview starts four bars before the second start of the loudest part that comes back, so it runs
   into a part already heard once. Without one it is the loudest 30 seconds on a bar line. It never
   starts in an opening, and its 30 seconds fit in the song. Every encoded file is decoded again and
   must match its source's length exactly with zero lag.
9. **Validate**: the finished folder must pass an independent validator. The folder appears only once
   all of that succeeded, so a failed build leaves nothing behind.

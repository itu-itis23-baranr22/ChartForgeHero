# chartgen

Generates playable [Clone Hero](https://clonehero.net/) song folders from local audio files
you own: it separates a song into stems, charts them, and packages everything the game needs.

It only processes files you give it. It does not download audio or touch streaming services.

## Status

| Phase | Scope | State |
|---|---|---|
| Foundation | Format-independent chart model, `.chart` exporter, validator | Done |
| A | Stem separation, packaging, simple onset-based guitar chart | Done |
| B | Guitar, bass and keys with Viterbi fret mapping and four difficulties | Planned |
| C | Drums: percussion classification, four difficulties | Planned |
| D | Vocal events, sections, star power | Planned |

Phase A's guitar chart is a pipeline test, not a good chart: lanes follow the brightness of each
attack, not the melody, and there is only one difficulty. Time signature is assumed to be 4/4.
Until Phases B and C, a song whose guitar stem is rejected as absent cannot be built, because no
other instrument can be charted yet.

See [docs/SPEC.md](docs/SPEC.md) for the full specification.

## Install

Needs Python 3.11 or newer. No external programs: audio is read and encoded by libsndfile.

```
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[separation,dev]"
```

`requirements.lock.txt` records the exact versions this was tested with.

The first build downloads the Demucs `htdemucs_6s` weights from Hugging Face. Without a GPU,
separation took 74-99 s for songs of 166-235 s on a 16-thread CPU. Each song is only ever separated
once: stems are cached under `.cache/stems`, at about 160 MB per song.

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
| `analysis.json` | Tempo, stem presence scores, note counts, stage timings, warnings |

Preview it with bot players, without scanning your library:

```
"<path to Clone Hero.exe>" --song "<song folder>" --player Guitar,Expert -i
```

To add it to your library, copy the folder into Clone Hero's `Songs` folder and press
*Settings > General > Scan Songs*. Songs the game rejects are listed in `badsongs.txt`.

## How it works

1. **Separate** the song with Demucs, cached by the file's SHA-256.
2. **Check presence**: a model always outputs all six stems, so each is compared with the mix,
   and a stem that is only bleed gets no chart. Its audio moves to `song.ogg` rather than vanishing.
3. **Track tempo** once on the original mix; all instruments share this map. The whole song is
   analysed first rather than beat by beat, because a beat tracker read 129 BPM for a 97 BPM song.
   A song gets one tempo if it holds one, small bends if a drummer drifts without a click, and a
   tracked tempo curve only if the tempo really changes.
4. **Detect onsets** on each stem, behind a noise gate and an adaptive threshold that reject bleed.
5. **Package and verify**: every encoded file is decoded again and must match its source's length
   exactly with zero lag, and the finished folder must pass an independent validator. The folder
   appears only once all of that succeeded, so a failed build leaves nothing behind.

## Development

```
pytest                 # no model download: separation is mocked
pytest -m slow         # runs real Demucs
```

The code is layered so that `chartgen.core` knows nothing about Clone Hero:

```
chartgen/
  core/       chart model, tempo map, exporter interface
  audio/      loading, separation, presence, tempo, onsets
  chart/      stems to tracks
  clonehero/  .chart and song.ini writers, packaging, validation
  pipeline.py the build, stage by stage
  cli.py      command line
```

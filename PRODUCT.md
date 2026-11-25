# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Owner's decision (2026-11-24, SPEC 49-57): a FastAPI backend served by `chartgen edit` on 127.0.0.1 only;
the page is plain HTML, CSS and JavaScript modules, drawn on a canvas, with the Web Audio API. No npm
packages, no build step, no CDN: every file is served locally. Tested with pytest, Node's built-in test
runner and Playwright 1.65.1.

## Users

- The owner, who builds Clone Hero song folders from audio they own with `chartgen build`, then checks and
  corrects the generated charts by ear and by eye before playing them.
- Other people who clone the public repository and do the same with their own songs. They meet the editor
  without the owner's background, so empty states, first steps and error messages must explain themselves.

Both work at a wide desktop monitor with a mouse and a keyboard.

## Product Purpose

The web editor (Phase E) opens a song folder that chartgen generated (`outputs\<Artist - Title>`), shows its
chart against the music, plays the separated stems in sync with a playhead, lets the user correct notes by
hand, saves only charts the game will accept, keeps a backup of every save, and copies the result to Clone
Hero's `Songs` folder. Success: a wrong note heard in the game can be found, fixed and saved in minutes, and
nothing the user corrected is ever lost silently.

## Positioning

It is the editor of chartgen's own output: it opens a generated folder with its stems and its `analysis.json`
(tempo, warnings), checks every save with the same validator that guards every build, and refuses to let a
rebuild overwrite hand edits. General chart editors know nothing of either.

## Operating Context

- Song folders hold `notes.chart`, `song.ini`, `analysis.json` and one `.ogg` per stem (`song.ogg`,
  `guitar.ogg`, `bass.ogg`, `drums.ogg`, `keys.ogg`, `vocals.ogg`; four or five per song).
- Charts have four instruments (guitar, bass, 4-lane Pro Drums, keys) at four levels (Expert, Hard, Medium,
  Easy), one shared tempo map (resolution 192 ticks per beat), sections and star power phrases.
- The final check is playing the song in Clone Hero; copying to `Songs` happens with the game closed.
- Song and artist names can hold non-ASCII letters (for example "Mor ve Ötesi", "Şarkı Testi").

## Capabilities and Constraints

- Local only: nothing leaves the machine.
- Interface language: English (owner, 2026-11-24).
- Edits run on the server; the page draws, plays and sends operations. Undo and redo.
- Saving validates the whole folder; a hard-rule error saves nothing and says why. Hard rules include: a lower
  level's positions are also in the level above; at most 2-note chords on Medium and single notes on Easy;
  bass has no chords; drums have no sustains or open notes, no sixteenths on Medium and Easy; star power and
  sections sit on bar lines.
- Out of scope: editing the tempo map. Optional later (E.4): editing sections, star power and the preview, a
  pitch-keeping slow-down, a game-like highway preview.
- Terminology: lanes or frets (green, red, yellow, blue, orange), open note, sustain, chord, forced, tap,
  star power phrase, section, tick, bar, beat, Expert/Hard/Medium/Easy, kick, snare (red), cymbal and tom
  (yellow, blue, green), stem.

## Brand Commitments

- The name is chartgen.
- Fret colours follow Clone Hero: green, red, yellow, blue, orange (owner's binding constraint). On drums a
  cymbal and a tom of the same colour must look different.

## Evidence on Hand

- Ten local song folders in `outputs\` built from the owner's own audio. They are never committed or
  published; mockups use made-up sample data.
- No screenshots, users, testimonials or benchmarks exist; none may be invented.

## Product Principles

- Never lose the user's work silently: backups on every save, rebuilds refuse to overwrite edits.
- The game's rules are the editor's rules: an invalid chart is explained, never saved.
- What you see is what you hear: the playhead and the audio agree within a frame, and that is measured.
- One implementation of the format: the editor reuses chartgen's model, writer and validator.
- Local and private by design.

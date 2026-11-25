---
version: 1
slug: "chartgen-editor-static-index-html"
primary_target: "chartgen/editor/static/index.html"
related_targets: []
---

## Scope

The chartgen web editor (Phase E, SPEC 49-57): the song list and the editing screen served by `chartgen edit`.
Mode: Operate. Audience: the owner and other people who build Clone Hero songs from their own audio with
chartgen; wide desktop monitor, mouse and keyboard. Job: hear a wrong note, find it, fix it, save a chart the
validator accepts, copy it to the game. Interface language: English.

Owner's constraints (2026-11-24): the first view is one level with the next level down faint beneath it; notes
must look as they do in Clone Hero (fret colours, cymbal versus tom, sustain); nothing crowded, no small text;
standard controls only; no flashy effects (glow, neon, decorative motion). Local only: no CDN, no npm.

## Direction contract

THESIS: The editor is the session's track sheet: numbered, ruled, written in by hand. It refuses the category
default, a grey DAW with one blue accent.

OWN-WORLD: Petrol-tinted graphite ground (#111A1D) with a committed petrol shell (#12343C) for the header and
the transport; faint printed form rules; marker-white ink (#ECEFF1) for what the user writes (song, sections).
Fret colours sit on the ground as in the game: dark #2EB14E #D42F35 #F2C230 #2F7CF6 #DE6F1C, light #3DAE5A
#C1272D #D9A40E #1F66D9 #DB6A12. Labels in a DIN-like semi-condensed sans, every number in tabular mono.
The light theme is the paper sheet under the same petrol shell.

STORY: The visitor opens a generated song, hears where a note is wrong, finds it on the timeline, fixes it,
sees the problems list agree, saves, and copies the song to the game.

FIRST VIEWPORT: Petrol header with song, instrument tabs, level control, unsaved count and Save; a tool row;
left, numbered lane cells; centre, a ruler of boxed bar numbers with written section names and the star power
band, five lanes, the next level as a translucent ply, the stem waveform; right, Problems over Selected note;
bottom, the petrol transport with play, tabular time, speed, metronome, latency and the stems. Signature move:
stems and lanes are numbered track cells; muting strikes the name through, solo circles the number.

FORM: Track Sheet, candidate 3 of 7 grounded (tab songbook, festival timetable, track sheet, gaffer setlist,
vinyl back sleeve, Nashville chart, gig poster). seed:98c333fe73bf7948

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Approvals

- Direction: the owner picked Track Sheet on the decision page (2026-11-24, no steer).
- Static mockup approved by the owner (2026-11-24): `.impeccable/mocks/editor/` (dark and light guitar, drums,
  song list, empty state). It is the composition E.0-E.4 build towards.
- Fonts: self-hosted OFL faces, Barlow Semi Condensed and Cascadia Mono (owner, 2026-11-24), replacing the mockup's
  Windows faces.

## Raises kept from the declined challengers

- Gate board: a validation finding stays marked on the timeline until the user visits it.
- Acetate manual: levels are plies; only the edited level is opaque, the level below is translucent and never competes.
- Bitmap specimen: one gem form at every zoom, snapped to device pixels.
- Title card wall: detail only on focus; a note's tick, time and lanes live in the inspector, not on the timeline.
- Datamatics: every number in one tabular mono face; the clock never jitters during playback.

## Unresolved

- Validator messages are shown as the validator writes them ("[HardSingle] has tick 6160, but [ExpertSingle]
  does not"); plain-language wording with the recovery belongs to E.2's live checks.
- Palette exception: dark-mode yellow sits above the dataviz lightness band (L 0.83 > 0.67) by brand commitment
  (Clone Hero's yellow). Light-mode green and yellow are below 3:1 against the ground; gems carry a dark rim and
  lanes are labelled, which is the required relief.

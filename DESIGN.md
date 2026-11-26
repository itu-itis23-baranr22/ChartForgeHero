---
name: chartgen editor
description: A local editor that shows, plays and corrects the Clone Hero charts chartgen generates.
colors:
  graphite-ground: "#111a1d"
  track-panel: "#152126"
  track-panel-raised: "#1a272d"
  form-rule: "#2b3b41"
  form-rule-faint: "#1f2c31"
  marker-white: "#eceff1"
  pencil-grey: "#aab5ba"
  faint-pencil: "#85939a"
  petrol-shell: "#12343c"
  petrol-shell-raised: "#174450"
  petrol-line: "#2c5c68"
  petrol-well: "#0d2a31"
  shell-ink: "#e6f0f1"
  shell-ink-muted: "#a8c3c8"
  star-power-cyan: "#86d3e3"
  error-coral: "#ff7a7a"
  warning-amber: "#f5b83d"
  fret-green: "#2eb14e"
  fret-red: "#d42f35"
  fret-yellow: "#f2c230"
  fret-blue: "#2f7cf6"
  fret-orange: "#de6f1c"
  open-violet: "#a66de0"
  paper-ground: "#f3f5f4"
  paper-panel: "#e9eeed"
  paper-rule: "#bfcaca"
  paper-ink: "#12191c"
  paper-ink-muted: "#3f4d54"
  paper-star-power: "#2a8fa8"
  paper-error: "#c0262d"
  paper-fret-green: "#3dae5a"
  paper-fret-red: "#c1272d"
  paper-fret-yellow: "#d9a40e"
  paper-fret-blue: "#1f66d9"
  paper-fret-orange: "#db6a12"
  paper-open-violet: "#7b3fc4"
  wave-grey: "#5c6c73"
  paper-wave-grey: "#aebbbb"
typography:
  headline:
    fontFamily: "Barlow SC, Barlow Semi Condensed, Bahnschrift, Segoe UI, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.4
  title:
    fontFamily: "Barlow SC, Barlow Semi Condensed, Bahnschrift, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Barlow SC, Barlow Semi Condensed, Bahnschrift, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Barlow SC, Barlow Semi Condensed, Bahnschrift, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    letterSpacing: "0.04em"
  section-mark:
    fontFamily: "Barlow SC, Barlow Semi Condensed, Bahnschrift, Segoe UI, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 700
  data:
    fontFamily: "Cascadia Mono CG, Cascadia Mono, Consolas, monospace"
    fontSize: "15px"
    fontWeight: 400
    fontFeature: "tnum, lnum"
  clock:
    fontFamily: "Cascadia Mono CG, Cascadia Mono, Consolas, monospace"
    fontSize: "26px"
    fontWeight: 600
    fontFeature: "tnum, lnum"
rounded:
  hairline: "2px"
  control: "3px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "20px"
  xl: "24px"
components:
  button-ghost:
    textColor: "{colors.pencil-grey}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
  button-ghost-hover:
    backgroundColor: "{colors.track-panel-raised}"
    textColor: "{colors.marker-white}"
  level-segment-active:
    backgroundColor: "{colors.shell-ink}"
    textColor: "{colors.petrol-shell}"
    padding: "7px 13px"
  instrument-tab-active:
    backgroundColor: "{colors.petrol-shell-raised}"
    textColor: "{colors.shell-ink}"
    rounded: "{rounded.control}"
    padding: "7px 13px"
  track-cell:
    textColor: "{colors.faint-pencil}"
    typography: "{typography.data}"
    width: "28px"
    height: "22px"
  play-button:
    backgroundColor: "{colors.shell-ink}"
    textColor: "{colors.petrol-shell}"
    rounded: "{rounded.pill}"
    size: "48px"
  problem-item:
    textColor: "{colors.pencil-grey}"
    padding: "11px 13px"
---

# Design System: chartgen editor

## Overview

**Creative North Star: "The Track Sheet"**

The editor is the session's paperwork: the printed track sheet clipped to a multitrack tape box, with numbered cells,
faint ruled lines and names written in marker. It is a working screen first (Operate): a header, a tool row, the lanes,
a problems list and a transport sit where anyone who has used an editor expects them, and the world shows only in
type, colour, density and one signature, the numbered track cell.

Colour is committed at the shell, not scattered: a petrol header and transport frame a petrol-tinted graphite field,
and the only saturated colours inside it are the five fret colours of Clone Hero, which belong to the notes alone.
Density is a desk tool's: 15px body, nothing under 12px, numbers in a tabular mono that never jitters. The light
theme is the same sheet on paper under the same petrol shell. Motion is almost absent: state changes take 150ms and
keyboard actions never animate.

**Key Characteristics:**
- Petrol shell (header, transport) around a petrol-tinted graphite field; a paper field in the light theme.
- Numbered track cells for lanes and audio files; bar numbers in boxed cells; section names written in and underlined.
- Notes drawn as the game draws them: round gems, cymbal plates, a kick bar, sustain tails.
- One semi-condensed DIN-like sans for words, one tabular mono for every number.
- Flat, ruled, no shadows; depth only as plies (the level below is translucent).

## Colors

A restrained field with a committed shell: neutrals tinted towards petrol, the shell in deep petrol, and the game's five
fret colours reserved for notes.

### Primary
- **Petrol Shell** (#12343c): the header and the transport bar, in both themes; its raised step (#174450) marks the
  selected instrument tab, its line (#2c5c68) frames shell controls.
- **Marker White** (#eceff1): what the user reads first on the dark field: song and section names, selected tabs, the
  selection outline around a note group, the primary action.

### Secondary
- **Star Power Cyan** (#86d3e3; paper #2a8fa8): star power bands on the ruler, the focus ring, text selection,
  and the ring that marks for a moment a note an edit changed on the level below (linked levels).

### Tertiary
- **The Fret Colours** (green #2eb14e, red #d42f35, yellow #f2c230, blue #2f7cf6, orange #de6f1c; paper steps
  #3dae5a, #c1272d, #d9a40e, #1f66d9, #db6a12): notes, lane swatches and nothing else. Validated with the dataviz
  palette check: red and green stay apart under deuteranopia (ΔE 8.6 dark, 12.6 light). Dark-mode yellow sits above
  the lightness band by brand commitment; light-mode green and yellow carry a dark rim and lane labels as relief.
- **Open Violet** (#a66de0; paper #7b3fc4): open notes, drawn as a bar across the lanes.

### Neutral
- **Graphite Ground** (#111a1d): the field behind the timeline and the song list; paper ground (#f3f5f4) in light.
- **Track Panel** (#152126): the lane column, the tool row and the side panel; raised (#1a272d) for hover.
- **Form Rule** (#2b3b41) and **Faint Rule** (#1f2c31): cell borders, bar lines, lane centre lines and beat lines.
- **Pencil Grey** (#aab5ba) and **Faint Pencil** (#85939a): secondary text and labels.
- **Wave Grey** (#5c6c73; paper #aebbbb): the waveform under the lanes, quieter than any note.
- **Error Coral** (#ff7a7a; paper #c0262d) and **Warning Amber** (#f5b83d; paper #9a6700): problems only, always
  with a drawn icon and words.

### Named Rules
**The Frets Belong to the Game Rule.** Green, red, yellow, blue and orange appear only on notes and their lane
swatches, never on buttons, links, states or decoration.

**The Petrol Frame Rule.** The shell colour stays the same in both themes; only the field between header and transport
changes from graphite to paper.

## Typography

**Body Font:** Barlow Semi Condensed (self-hosted OFL, with Bahnschrift and Segoe UI behind it)
**Label/Mono Font:** Cascadia Mono (self-hosted OFL, with Consolas behind it)
The self-hosted files are declared as "Barlow SC" and "Cascadia Mono CG", so that a copy installed on the machine
never stands in for them; the names behind them in the stacks are the same families.

**Character:** the printed-form sans of a track sheet, narrow and plain, set against a typewriter-like mono for
everything that is a number.

### Hierarchy
- **Headline** (600, 24px, 1.4): the song list's title.
- **Title** (600, 16px, 1.4): side panel headings, the song name in the header.
- **Body** (400, 15px, 1.4): controls, problems, the song list.
- **Label** (400, 13px, 0.04em, uppercase): lane group labels ("Expert", "Hard · below") and table headings.
- **Section Mark** (700, 17px, underlined 2px): section names written on the ruler.
- **Data** (400, 12-16px, tabular lining figures): ticks, times, bar.beat, BPM, track numbers.
- **Clock** (600, 26px, tabular): the transport clock.

### Named Rules
**The Tabular Numbers Rule.** Every number is set in the mono with tabular lining figures; a clock that moves never
changes width. Words stay in the sans, even next to a number.

## Layout

A fixed desktop grid: header 56px, tool row 46px, then three columns (lane cells 184px, timeline, side panel 344px),
then the transport 96px. The timeline is a canvas that stays in place over a wide spacer, so the browser's own
horizontal scrollbar moves through the song; time runs left to right in seconds, so tempo changes show as bars of
different width. Lanes take 44-76px each by the window's height; the ruler above them is 92px (bar cells, tempo and
time signature marks, sections, star power). The level below sits under the lanes as a ply of five 13px rows; under it a 56px waveform row shows the
instrument's own stem (the backing track when it has none), labelled with its file. Spacing
steps are 6, 8, 12, 20 and 24px. Below 1100px wide the editor does not try to fit: it says so and asks for a wider
window.

## Elevation & Depth

Flat. No shadows anywhere: separation comes from the panel tone against the field and from 1px form rules. The one
depth device is the ply: the level being shown is opaque, the level below is a translucent band of small dots.

### Named Rules
**The Ply Rule.** Only the level being edited is opaque; any other level is a translucent ply below it and never
competes for attention.

## Shapes

Square-cut cells and controls with barely softened corners (3px; 2px for key caps), round gems, a pill for the play
button and tags. Cymbals are a flattened hexagonal plate with a centre line, toms are circles, the kick is a rounded
bar in its own row: the shapes the game uses, so that a cymbal never needs its colour to be told from a tom.

## Components

### Buttons
- **Shape:** square-cut (3px).
- **Ghost (tool row):** pencil-grey text, no fill; hover lifts to the raised panel with marker-white text (150ms).
- **Shell buttons:** shell-muted text on petrol; the active level segment inverts to shell ink on petrol.
- **Pressed (tool row):** a tool or toggle that is on sits on the raised panel with a form rule and marker-white
  text (Select or Draw, Other levels); a toggle also says its state in words ("Other levels On / Off").
- **Focus:** a 2px star-power-cyan ring, 2px offset, on every control.

### Tool Row (editing, E.2)
- In order: the tools Select (V) and Draw (D), Grid (a native select, 1/4, 1/8, 1/12, 1/16, 1/24: the twelfths
  and twenty-fourths are triplets, E.4), zoom, Undo and Redo (their
  titles name the step), Other levels with its state in words, Level below, then a status line that says what an
  edit also changed ("Also changed: Hard 2 notes") or how far the audio has loaded. Why something was refused is a
  notification (below), not this line.
  Below 1500px the key caps and the "bars in view" count are left out; the keys stay in the titles and the legend.
- The header's end shows the count of unsaved edits and Save (E.3): the one filled button in the shell, shell
  ink on petrol like the active level, outlined and quiet when there is nothing to save; "Saving…" while it
  writes. With errors under Problems it stays pressable: it says how many and takes the user there.
- Copy to game (E.4) sits before Save as a shell ghost (shell-muted text, shell rule; hover lifts to the raised
  petrol), "Copying…" while it works; its title names the Songs folder. With unsaved edits it answers with the
  "Save first" warning (with Save) and copies nothing. Without a Songs folder it looks disabled like a missing level
  and a click says how to set one (`--songs`). The result (copied, backed up where, or refused because the game is
  running) is a notification.

### Notifications (E.4, toast.js)
- What a save or a copy to the game did, and why something was refused, as a stack of boxes over the lower right
  of the timeline (20px from the side panel and from the transport, 440px wide), so they never cover Problems,
  Save or the transport. Each box: a drawn 22px icon, a title in words (16px semibold: "Saved", "Copied to game",
  "Save first", "Not saved: 1 error", "Clone Hero is running"), at most one line of explanation (15px), and a close
  button. Colour is never alone: the icon's shape and the title say the same.
- **Success** is the shell speaking: petrol shell (#12343c) with the petrol line and shell ink, the same in both
  themes, a star-power-cyan disc with a check. It goes by itself after 5 seconds (8 with a path to copy), and
  waits while the pointer or the focus is on it.
- **Warning** (amber triangle) and **error** (coral disc) are boxes of the raised panel tinted 8% towards their
  colour, framed 1px in it. They stay until closed or answered, and offer the next step as plain buttons, the
  first one filled marker white: "Save" (Save first), "Copy again" (the game was running), "Go to Problems" (a save
  or copy refused for errors), "Reload the page" (out of date). Using an action closes the box.
- A path (the backup of a save or of the game's files) is written in the mono, 13px, on a well (Petrol Well in a success, the panel otherwise), from the outputs
  folder, breaking after folder separators; its title is the full path, and "Copy path" copies the full path
  ("Copied" with a check for two seconds; where the clipboard is refused it writes the full path and selects it
  for Ctrl+C).
- One box per subject (save, copy, edit, audio): a new message takes the old one's place, so they never pile up.
  Edits that are refused ("Not changed", "Not pasted") are warnings too; the small facts of every edit stay in the
  status line, because a box for each click would be noise. Opening another song or the list closes them all.
- Successes are `role="status"`, warnings and errors `role="alert"`, in a region called Notifications. A box
  enters in 150ms (fade and 8px rise, ease-out) and leaves in 150ms (fade); with reduced motion neither moves.

### Draft Box (E.3)
- Under the tool row, above the ruler, until answered: raised panel with a 1px form rule (not coral: nothing is
  wrong). A draft from an earlier session reads "N unsaved edits of this song from <date time> were kept in a
  draft" with Restore (filled marker white) and Discard; a draft set aside names its file in full with Dismiss.

### Navigation
- **Instrument tabs:** text tabs in the header; the selected one sits on the raised petrol with a petrol line.
  An instrument with no chart looks disabled (45%) but still answers: its title and a click say "This song has no
  keys chart." in the tool row, and nothing else changes.
- **Level control:** a segmented control of Expert, Hard, Medium and Easy; a level the song lacks looks disabled
  the same way and says "This song has no Hard guitar chart." on hover and click (a Phase A folder has Expert only).

### Track Cell (signature)
- A 28 × 22px ruled cell holding a two-digit number in the mono, in front of every lane and every audio file. Lanes
  read 01-05 top to bottom; audio files keep the order song, guitar, bass, drums, keys, vocals.
- In the transport every audio file is a stem cell: its number, its name, M and S buttons and a volume slider.
  Muting strikes the name through, solo circles the number, and a stem silenced by another stem's solo turns pencil
  grey. On a narrow window the stem cells scroll sideways rather than shrink.

### Transport
- The play pill (Space anywhere but in a text field), the clock of the playhead with bar.beat and tick, then
  Speed (a native select, 0.50× to 1.00×), Keep pitch (E.4), Metronome (shell buttons that invert when on, "On" /
  "Off" in the mono) and Latency (a number in ms), each a label over its control, then the stem cells. Until the
  audio is decoded every control is at 45% and the tool row says how many files are loaded; a file that cannot be
  decoded is named in an error notification. Keep pitch below 1.00× has the editor stretch each stem once; the tool row
  counts them ("Slowing the audio down without lowering it: 1 of 2 files") and then says "Keep pitch is on at 0.75×."; until then
  the song plays at the lower pitch.

### Problem Item
- A ruled box with a drawn icon (coral disc for an error, amber triangle for a warning), the place in semibold
  ink ("Bar 16.4 · Hard guitar", the bar.beat in the mono), the message in plain words (the validator's own words in
  its title), and a "Go to" button when the message names a track and tick; going there switches instrument and
  level and marks the column. The list is the live check: it follows every edit.

### Version Warning
- When the page and the editor server are different versions: a box above everything under the header, raised
  panel with a 1px coral frame, the coral alert icon, one sentence that says what to do (reload, or restart
  chartgen edit), and a "Reload the page" button. Editing stops until the page is reloaded. A page that does
  not start at all shows the same box with "The editor did not start" and how to recover.

### Inspector and Key Legend
- "Selected" with the count; one chord shows its place, tick, time, lanes, sustain and flags; several notes show
  where they start and end. Under it a two-column legend of key caps and what they do, always visible.
- Song facts (E.4) end with plain ruled buttons, wrapping: Add a section, Add star power, Set the preview, and one
  line that says they go on the bar the playhead is in. A section, star power phrase or the preview selected on the
  ruler takes the place of the note facts: its facts, then its actions as the same plain buttons in words ("One bar
  earlier", "One bar longer", "Move it to the playhead's bar", Delete). A section has a Name field (focused right
  after Add a section; Enter renames); star power has the checkbox "Change every level the same way", on by default.

### Timeline
- Gems are circles in the fret colour with a 2px ring of the field colour and a light rim; sustain tails are 9px
  bars of the same colour. Bar numbers sit in boxed cells.
- Each selected note has its own 2px marker-white outline in its shape (ring, wider ring for a cymbal, rounded bar for
  the kick or an open note). A selection box is a 1px marker-white frame over an 8% marker-white wash. While notes
  are dragged they are drawn where they would land, snapped to the grid; the Draw tool shows the note it would add
  at 50%, with the sustain being drawn. A note an edit changed on the level below gets a star-power-cyan ring on
  the ply for 1.5 seconds; it appears and goes without motion.
- Pointer: the ruler and the waveform move the playhead; a note under the pointer shows a grab cursor, the Draw tool
  a crosshair.
- The ruler (E.4) carries, under the bar cells: tempo and time signature marks, section names (17px bold with an
  underline), this track's star power as a 7px star-power-cyan band, and the preview's start as a 2px pencil line
  with "Preview" in 13px semibold beside it (a tempo label it would cover moves just after it). Clicking a section,
  a band or the preview selects it: a 2px marker-white frame around it, no fill. Delete removes a section or a band
(the preview only moves), Escape lets go.
- The playhead is a 2px marker-white line from a small triangle in the ruler to the bottom, at the time being heard
  (less the latency setting). While playing, the view turns a page when the playhead passes 85% of it, without
  scrolling smoothly; a view the user scrolled away is left alone. Clicking the ruler or the waveform moves it.

## Do's and Don'ts

### Do:
- **Do** draw notes as Clone Hero draws them: round gems, cymbal plates, a kick bar, sustain tails, fret colours.
- **Do** keep every number in Cascadia Mono with tabular figures, and every word in Barlow Semi Condensed.
- **Do** keep text at 12px or larger; body text is 15px.
- **Do** use standard controls: native scrollbars (themed), tabs, segmented buttons, checkboxes, plain buttons.
- **Do** draw icons as SVG in one stroke weight (1.75 on a 24px grid).

### Don't:
- **Don't** add glow, neon, gradients or decorative motion; state changes take 150ms and keyboard actions never animate.
- **Don't** use a fret colour for anything that is not a note.
- **Don't** set a typed character ("!", "×", an emoji) as an icon.
- **Don't** load anything from outside the machine: fonts, scripts and styles are served by the editor itself.

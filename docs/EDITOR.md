# The web editor

`chartgen edit` opens the songs in `outputs/` in your browser so you can hear, correct, save and copy them into the game. Back to the [README](../README.md).

## What it is
Opens the song folders in `outputs/` in your browser, on this machine only (127.0.0.1): the chart drawn
over time, one instrument and level at a time with the level below it faint, bars, tempo changes,
sections, star power and what the validator says, with the song's audio to play along, and lets you
correct and save the notes, sections, star power and the preview, and copy the song into Clone Hero
(phase E, [SPEC.md](SPEC.md) decisions 49-57). Use Chrome or Edge: the audio is Ogg Vorbis. After an update the page loads the new files by itself; a page that was
left open during the update says so and asks to be reloaded.

## Start it

```
pip install -e ".[editor]"
chartgen edit                  # serves http://127.0.0.1:8765/ and opens it
chartgen edit --port 9000 --no-browser --outputs other_folder
chartgen edit --songs "D:\Games\Clone Hero\Songs"   # where Copy to game copies to
```

## Moving around

Scroll with the wheel or the arrow keys, zoom with Ctrl and the wheel or plus and minus, click a note
to see its bar, tick and time. The page loads nothing from the internet; its fonts (Barlow Semi
Condensed and Cascadia Mono, SIL Open Font License) ship with it.

## Playback

Space plays and pauses; clicking the ruler or the waveform moves the playhead. Every audio file
has its own mute (M), solo (S) and volume, and muting never restarts the music. Speed goes down to 0.5x
(the pitch drops with it, unless Keep pitch is on: then the editor stretches each audio file once for that
speed, which takes some seconds per file the first time, and keeps the copies in `outputs/_editor_cache/`;
until they are ready the song plays on at the lower pitch), the metronome clicks the chart's own tempo map with the downbeats higher, and
Latency draws the playhead later by that many milliseconds when it runs ahead of what you hear (Bluetooth
headphones need 150 to 250). A song's audio is decoded into memory: about 70 MB per file for a
three-minute song, so a song with five files takes about 350 MB in the browser
(`node tests\browser\memory.mjs http://127.0.0.1:8765 "Artist - Title"` measures it for one song).

## Editing

Select (V) picks notes (Shift or Ctrl and click to add more, drag a box around them) and moves
them by dragging; Draw (D) adds a note where you click and draws its sustain as you drag right. Notes land
on the grid (1/4, 1/8, 1/16, or the triplet grids 1/12 and 1/24). Without the mouse: `.` and `,` select
the next and the previous note or chord (with Shift they add it to the selection), Ctrl and the left or right
arrow move the playhead one grid step, and 1 to 5 add a note on that numbered lane at the playhead (on
drums 5 is the kick). With notes selected: Delete, the arrow keys (a grid step left or right, a
lane up or down), Shift and the arrows (a shorter or longer sustain), F forced, T tap, C cymbal or tom;
Ctrl+C and Ctrl+V copy and paste at the playhead, Ctrl+A selects the level, Ctrl+Z undoes and Ctrl+Y (or
Ctrl+Shift+Z) redoes. With "Other levels" on (the default) a note deleted or moved also goes from the levels below, and a
note added to a lower level is added to the levels above that lack it, so every level keeps the notes of
the level below it; what changed there is ringed for a moment on the level below and named in the tool
row. A sustain that an edit runs into the next note is cut to end on it. What the game cannot read (two
notes on one lane at one tick, a drum sustain, a cymbal on red) is refused with a message; what only breaks
a rule of the validator (a chord on Easy, a Hard note Expert lacks) is allowed and shown at once under
Problems, in plain words with its bar and beat.

## Sections, star power and the preview

Under Song, Add a section, Add star power and Set the preview put
one on the bar the playhead is in (they always start on a bar line). A new section's name field is focused:
type the name and press Enter. Click a section name, a star power band or the preview mark on the ruler to
select it: a section is renamed, moved a bar earlier or later or deleted; star power is moved, made a bar
shorter or longer or deleted (the Delete key works for both); the preview moves to the playhead's bar. Star power is added and changed on every level that has notes unless "Change every
level the same way" is unticked. The validator's rules apply here as well, as errors under Problems that
keep Save from writing until they are fixed: a section lasts at least 4 bars, and the preview starts after
the opening and its 30 seconds end before the song does.

## Saving

Save (or Ctrl+S) writes the chart to the song folder. A chart with an error under Problems is not
saved: Save says how many and takes you there. Before writing, the folder's `notes.chart` and `song.ini`
are copied to `outputs/_editor_backups/<song>/<date_time>_<file>` (every save keeps its own copies);
`song.ini` changes only in its `diff_*` values and `preview_start_time`. A `notes.chart` that changed on disk after you opened the
song (a rebuild, another tool) is not overwritten. Unsaved edits are kept by the running editor and, a
second after each edit, in a draft in `outputs/_editor_drafts/`: open the song again after the editor
stopped and it offers to restore them. A draft made on a `notes.chart` that has changed since is never
restored; it is set aside as `<song>.<date_time>.stale.json` and the page names the file.

## Copying into the game

Copy to game copies the saved song into Clone Hero's Songs folder (`Documents\Clone Hero\Songs`, or the
folder given with `--songs`); with unsaved edits it asks you to save first. Close the game before copying:
the editor checks and refuses while it runs. If the song is already there with the same audio (same `.ogg`
names, and the same bytes or the same decoded sound), only `notes.chart` and `song.ini` are replaced and
those two are backed up; otherwise the whole folder is replaced and the old one is backed up whole. Backups
go to `outputs/_songs_backup/<date_time>_editor/<song>/`. If the game still shows the old song, scan the
songs again from its settings.

## Notifications

Saves, copies and refusals appear as notifications over the lower right of the timeline. "Saved" and
"Copied to game" go by themselves after a few seconds (not while the pointer is on them) and name the backup
folder, with Copy path; a warning or an error ("Save first", "Clone Hero is running", "Not saved: 1 error")
stays until you close it and offers the next step (Save, Copy again, Go to Problems).

## Rebuilding a song you edited

`build --force` refuses a folder with hand edits (saved in the editor, or a
`notes.chart` changed by any tool) and says why; `--discard-edits` moves that folder to
`outputs/_edited_backup/` and builds anew. `chartgen protect` lists which folders are protected;
`chartgen protect --record --inputs <folders with the audio>` protects folders built before this check
existed, but only those whose fresh build gives the same `notes.chart` byte for byte.

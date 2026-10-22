# CLAUDE.md — Midi Evolver

Working notes for this repo. A REAPER JSFX (`Midi Evolver.jsfx`) that turns
held chords into evolving motion - the idea of Spitfire's *Olafur Arnalds
Cells* and Orchestral Tools' *Time Macro/Micro*, in MIDI only - and a
background ReaScript (`reascripts/Midi Evolver Helper.lua`) that turns the
JSFX's recorded take into a `.mid` to drag from the Media Explorer, or an
item on the track. **The user is a musician, not a programmer - explain in
those terms.**

Built in the shape of its sister repos: **AutoCC** (closest: the family's
other JSFX - its window framework, its ysfx checker, its notes on the JSFX
language), **Midi Variator** (the dice, the clash guard, feel), **Good Idea**
(a variation is a number; the `.mid` writer; the export folder; the docs'
shape). When in doubt about the window, do what AutoCC does; about the
helper, what Good Idea's `gi_place.lua` does.

The JSFX facts below are from the **REAPER 7.79 JSFX Programming Reference**
and the **REAPER API functions page** the user uploaded on 2026-10-21; each
one the code depends on was checked there. Trust this file over recollection;
when REAPER's own docs disagree, the docs win and this file is corrected.

## Shape of it

| | |
| --- | --- |
| `Midi Evolver.jsfx` | The plug-in: the engine (`@init`, `@block`), the take, the window (`@gfx`). No build step - the file is the product. |
| `reascripts/Midi Evolver Helper.lua` | The background script: attaches to gmem, loops on `defer`, answers requests. Loads the two below from beside itself. |
| `reascripts/me_midi.lua` | Pure Lua: the take decoded, notes paired, the `.mid` written (and read back). No `reaper.`. |
| `reascripts/me_place.lua` | Everything that touches REAPER: the request, which track, Drag Out, Insert, the answer, the loop. |
| `tools/host.cpp`, `tools/build_host.sh` | The JSFX run headlessly in ysfx (AutoCC's uihost, plus MIDI out, tempo and transport). |
| `tools/enginecheck.py` | What the JSFX plays, checked through the host. |
| `tools/uicheck.py` | The window, checked through the host (AutoCC's checker for this window), and the gmem protocol on both sides. |
| `tools/demo.py` | A hold printed bar by bar as note names. **Read it before and after any musical change.** |
| `tools/bite.py` | Breaks the JSFX on purpose in a copy and runs a checker: proves a check bites. |
| `tools/test.sh` | Every suite. |
| `tests/` | The helper's Lua tests (`test_midi`, `test_helper`) and the mocked REAPER. |
| `docs/decisions/` | Why things are the way they are, one file per decision. |
| `docs/sessions/` | What happened in a session, written at the end of it. |
| `docs/READING.md` | Which parts of the Educational Materials the music rests on. |
| `docs/COLOUR.md`, `docs/apple-hig-review.md` | The house scheme; the window against Apple's HIG. |

## 1. JSFX language facts this code relies on

AutoCC's list (its CLAUDE.md §2) holds here too; the ones this code leans
on, plus three learned the hard way in this repo:

- **Names are case-insensitive.** `nl` and `NL` are one variable - a row's
  line count once overwrote the number of layers and only the bass row was
  drawn. `tools/uicheck.py` fails on any two names that differ only in case.
- **No `1e12` notation**: write `1000000000000`. The checker looks.
- **A function must be defined before it is used**, also inside another
  function's body (`play` after `schedule`, `tline` before `tickbox`).
- `&`/`|` bind tighter than `==`; `||` and `&&` have equal precedence,
  left to right; `?:` binds tighter than `=` and `+=` (so `p += c ? 1 : -1`
  is `p += (c ? 1 : -1)`), and `a ? b = 1 : c = 2` assigns as it reads.
  Parenthesise when mixing anyway.
- `%` works on integers that may be 32-bit: the dice use `floor` instead.
- `@init` runs on load, on a sample-rate change **and when the transport
  starts**. `@serialize` is non-empty and `init_done` guards the first-time
  set-up, so pressing Play while holding keeps everything sounding (a reset
  there would leave notes stuck). **Do not empty `@serialize`.**
- `midirecv` consumes; everything not used is passed on with `midisend` (or
  queued with `q_add`). Messages are sent **sorted by sample offset**, a
  note-off before a note-on at the same offset.
- `@gfx` runs in another thread (~30 Hz). It writes **sliders and request
  flags** (`panic_req`, `rec_req`) only; `@block` acts on them. Clear, Undo
  and Drag Out touch the take only while it is not being written.
- `sliderchange(sliderN)` with the slider named (`set_slider` spells every
  one out) and `sliderchange(-1)` from `@gfx` on mouse-up for a REAPER undo
  point.
- `options:gmem=MidiEvolver` gives an 8M-slot shared memory; Lua reads it
  with `gmem_attach("MidiEvolver")`, `gmem_read`, `gmem_write`.
- `get_host_placement()` (REAPER 6.74+) returns the track's index, -1 for
  the master. Whether it counts from 0 is not said; the helper checks (§4).
- `time_precise()` seeds a new variation; `rand()` is mixed in.
- Graphics, keys, fonts, Retina, `mouse_cap`, `gfx_getchar` once a frame:
  exactly AutoCC's, and so are its two ysfx differences (arrow codes, Shift
  in `mouse_cap`) that the checker works round with `t_getchar`.

## 2. The engine

### The clock

`bt` is REAPER's beat (`beat_position`) while it plays and the plug-in's own
count while it is stopped; `vt` never jumps (the live view and the energy use
it); `rt` is the take's own clock (beats since the take began, through any
loop or jump). Steps fall on a grid counted from `origin`: **beat 0 while
REAPER plays** (its bar lines), **the hold's first moment while it is
stopped**. A start, a jump or a loop going round moves `bt` to REAPER's and
shifts every pending note-off by the same amount, so lengths are kept and
nothing hangs.

`run_to(tb)` runs the music forward **one event at a time in time order** -
a note ending, a pending note, a chord settling, a layer's step - so a note
never meets the end of a note that should have come first. The next step is
the next grid line at least 0.01 beat on (`next_grid(t + 0.01, g)`): with
`+0.0001` a one-beat grid returned the same beat forever.

### Holding, and the chord ([0002](docs/decisions/0002-the-held-keys-are-the-harmony.md))

A key changes the chord **25 ms later** (`settle_beats`), so a chord played
a little spread is one change and one hold start. The chord is a **ladder**:
its pitch classes above the lowest key, `tone(i, base)` the i-th rung above
`base`. Patterns store rungs, not pitches, so a new chord is followed at the
next step; the bass restrikes and the pad re-voices at once. One key alone is
a root with its fifth.

**Colour tones** ([0005](docs/decisions/0005-colour-tones-never-a-semitone-from-the-chord.md)):
a whole tone above a chord tone, never a semitone from any (C E G gives D and
A). Used by the pad (sometimes, with Change and energy), the arpeggio (an
off-beat step, as an unaccented neighbour) and the sparkle.

### Energy and pace ([0004](docs/decisions/0004-energy-over-a-pace.md))

`u` = beats held / (Pace × bar). `shape_at(u, seed)`: Build `smooth(u)`,
Swell `0.5 - 0.5cos(πu)`, Fade `1 - smooth(u)`, Wander smooth noise through
the variation's points (point 0 is 0); scaled between Start and Peak.
`energy_at` adds a breathing drift (± 4% × Change). `rate_f = √(8/pace)`
(0.5-2) scales how often patterns change, so a fast pace changes more often
as well as sooner.

### The layers ([0003](docs/decisions/0003-layers-are-planes-that-come-in-in-order.md))

| L | | grid | register |
| --- | --- | --- | --- |
| 0 | Bass | bar → half bar → beat (at 0.35 and 0.7) | root in G1–F#2 |
| 1 | Pad | re-voice every 2 bars (pace ≥ 8) or every bar | bottom in G2–F#3, then a fifth+, then close; every chord tone first |
| 2 | Pulse | quarter → eighth (0.45) → sixteenth (0.9); Euclidean k of n | two rungs near the top of an octave above G3–F#4 |
| 3 | Arpeggio | eighth → triplet (0.4) → sixteenth (0.7) | from G3–F#4, one octave to three |
| 4 | Sparkle | sixteenth, sparse | from G4–F#5 |
| 5 | (your own keys, when Held Keys is Played) | | |

The enabled layers come in in order at `0.85 × k / n` of the energy (the
first at once) and leave 0.04 below it. Each layer has its own random
stream (`rs_base[L]`); feel has stream 5.

**One of each pitch on a channel**: `note_on` re-strikes a sounding pitch
and **keeps the longer end** when the sounding note is longer (the pad's
held voice under an arpeggio note); a strike of the same pitch at the same
moment is skipped; and `an_end` never ends a note before its own start plus
two samples (a note pushed late by Feel used to start after the release
that ended it, and stuck).

### The take ([0007](docs/decisions/0007-the-take.md))

Every message sent goes into `rec_base` (beat, status, data 1, data 2) while
`take_live`. Without Record a take is one hold (`take_kind` 1); with Record
it gathers holds and the pauses between (`take_kind` 2), and **a recorded
take is not replaced by a later hold** until it is cleared or Record starts
again. A take ends at the end of the block that holds its last note-offs
(`take_end_req`). It is saved in `@serialize`. Times are beats on the take's
own clock.

### Memory map (keep this current; overlaps are silent corruption)

| Region | Address | Size |
| --- | --- | --- |
| held / down / velocity | 0 / 128 / 256 | 128 each |
| chord pitches `ch_base` | 384 | 128 |
| pitch classes, chord classes, colours | 512 / 528 / 544 | 16 / 12 / 16 |
| layer arrays `L_on` … `L_eprev` | 600 | 16 × 8 |
| random streams `rs_base` | 760 | 8 |
| patterns `pat_base` | 800 | 5 × 32 |
| pad voices (+16 old, +32 covered) | 1000 | 44 |
| pending notes `pend_base` | 1100 | 64 × 6 |
| sounding notes `an_base` | 1600 | 256 × 8 |
| pitch → slot `snd_base` | 3700 | 16 × 128 |
| output queue `oq_base` (+4 to sort with) | 5800 | 1024 × 4 + 4 |
| input `ev_base` | 10000 | 512 × 4 |
| keyboard stops `focus_base` (window) | 12100 | 64 × 6 |
| live view `roll_base` (window reads) | 12600 | 512 × 5 |
| the take `rec_base` | 65536 | 100000 × 4 |
| (the checker's log, gmem copy) | 3000000, 6000000 | |

## 3. The window

AutoCC's framework, unchanged where it could be: `btn`, `ubtn`, `optctl`,
`field`, `tickbox` (new: the layer box), `focus_mark`, `hint`, the message
bar at the top, `flow`, `cell`, `wrap_text`, `plate_text`, `bwid`, `ui_s`.
Its rules are this window's ([0008](docs/decisions/0008-the-window-follows-apples-guidelines.md)):

- every size through `ui_s`; controls 28 points (`ch`), 12 apart (`gap`);
  a button never narrower than its label;
- every line of text 7:1 (`C_TEXT`, `C_LABEL2`); `C_DIM` only for a control
  that is off; `C_WARN_TEXT` for a warning in words, never the house red;
- the ground is the house `#23272E` (AutoCC's is darker; COLOUR.md wins);
- every control registers with `focus_mark` in reading order and starts
  its hint with its own name; a chosen button carries the ink bar;
- messages at the top until Dismiss (Clear's has Undo beside it), never on
  a timer; text wraps, never "…";
- the layout needs `LAYOUT_W` (400) points across; a layer row puts its
  fields under the name when narrow;
- the window writes sliders through `set_slider(n, v)`, which names every
  slider; a new slider needs a line there and a control, or the static
  check fails.

Top to bottom: the message bar; **Motion** (the last two bars, sounding notes
yellow, finished ones grey) and the **Energy** strip (the shape over two
paces, layers' entry marks at the sides, the hold's place); **Evolution**
(Shape, Panic; Pace, Change, Start, Peak, Feel, Variation); **Layers** (box,
name, what it does and whether it plays, Channel, Octave, Level, a meter);
**Recorder** (Record, Clear, Drag Out…, Insert; Place Take; what the take is;
whether the helper is running); **MIDI** (Keys From, Held Keys, Sustain
Pedal, Dynamics).

## 4. The helper and the protocol ([0001](docs/decisions/0001-a-jsfx-that-plays-and-a-helper-that-places.md))

gmem slots, the same constants in the JSFX (`G_…`) and `me_place.lua`
(`M.G`); `tools/uicheck.py` fails if they differ:

| slot | | written by |
| --- | --- | --- |
| 0 | 7301: protocol 1 | JSFX |
| 1 | heartbeat, moved every loop | helper |
| 2 | request number - **written last** | JSFX |
| 3 | 1 Drag Out, 2 Insert | JSFX |
| 4 | `get_host_placement()` | JSFX |
| 5 | project QN where the take began, or -1 | JSFX |
| 6 | messages | JSFX |
| 7, 8, 9 | tempo, time signature at the take's start | JSFX |
| 10 | Place Take | JSFX |
| 11 | request answered - **written last** | helper |
| 12 | 1 saved, 2 inserted, < 0 could not | helper |
| 13 | take length in QN | JSFX |
| 14 / 15 | the asking / answered plug-in (`inst_id`) | JSFX / helper |
| 199, 200- | the answer's words, a character a slot | helper |
| 1000- | messages: beat, status, data 1, data 2 | JSFX |

- The helper treats requests made before it started as old (its first
  `handled` is the current number) - the window has already said to start
  the helper and click again.
- The JSFX shows an answer only for its own request number **and** its own
  `inst_id`; three seconds without one says the helper didn't answer.
- **Which track**: the index from `get_host_placement` if that track has a
  Midi Evolver on it (main or input FX), else the one before (in case it
  counts from 1), else the only track with one, else the selected track.
- **Drag Out**: a `Midi Evolver` folder beside the saved project (else in
  REAPER's resource folder, said so), `Midi Evolver YYYY-MM-DD HH.MM.SS.mid`,
  format 0, 960 PPQ, the take's tempo and metre, whole bars long;
  `OpenMediaExplorer(path, false)` selects it there to drag.
- **Insert**: `CreateNewMIDIItemInProj` in seconds, notes with noSort and one
  `MIDI_Sort`, CCs, the take named, one undo block ("Midi Evolver: insert
  take"); Where Played at the take's QN, else at the edit cursor.
- The script: `set_action_options(5)` (re-running stops it; its action
  shows on), `atexit` → `set_action_options(8)`.

## 5. Conventions

- **Run `tools/test.sh` after any change**, and `tools/demo.py` after a
  musical one - read the notes, not only the counts.
- **Prove a new check bites**: `python3 tools/bite.py engine|ui "what"
  "old" "new"` must say BIT. The session log lists what was bitten.
- Every musical constant has its reason in a comment where it is set;
  change the reason with the number.
- The mock (`tests/reaper_mock.lua`) is written from the API page's
  signatures; add a function from the page when the helper starts using one.
- Text on screen follows Apple's writing guidelines (title-style controls,
  sentence-case hints and messages that say what to do, em dashes, curly
  quotes, "click").
- Don't claim REAPER-verified behaviour that hasn't been REAPER-verified.
- Commit and push early: a session's container can restart.

## 6. Unverified in REAPER

Nothing here has been run inside REAPER. Checked in ysfx (the JSFX) and
against the mock (the helper); only REAPER can confirm:

- that `get_host_placement()` counts tracks from 0 (the helper copes either
  way, by looking for the plug-in by name);
- that `beat_position` is quarter notes in time signatures other than /4
  (the reference says "beats = quarternotes in /4 time signatures");
- that the window's keys reach it (Tab, Return, the arrows, Esc) - AutoCC's
  open question too;
- how live it feels: REAPER processes a record-armed, monitored track in real
  time; on a track playing back items it may run ahead (anticipative FX),
  which the MIDI is unaffected by but the live view could be;
- that `OpenMediaExplorer` opens with the file selected and draggable on
  both Mac and Windows;
- `set_action_options` showing the helper's action as on.

## 7. Where it stands

| | |
| --- | --- |
| 1.0 | First version, 2026-10-21, on `claude/jsfx-evolving-midi-motion-x4zzwq`. Five layers, four shapes, the recorder, the helper. **Not yet run in REAPER.** |

**Ideas raised but not started** - the user decides which, if any: a scale
or key to draw colour tones from instead of the held notes; more layers
(a counter-melody, a second arpeggio at another speed for more phasing);
per-layer patterns to choose from (Cells' different "cells"); a latch, so a
chord keeps evolving until the next is played; swing; articulation
keyswitches per layer; the take as a ReaPack-free drag straight from the
window if REAPER ever lets a JSFX start one.

**Publishing a version to ReaPack**: commit and push the code; then add a
new `<version>` to `index.xml` with every `<source>` pinned to that commit's
hash, check each raw URL returns 200, and commit that separately. Never edit
an existing `<version>`. Bump `version:` in the JSFX and `@version` in the
helper to match.

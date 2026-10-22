# 0004. One energy, shaped over a pace of bars; Change apart from Pace

Taken 2026-10-21. Stands.

## Context

"The evolution should be different each time and evolve slower or faster
based on chosen settings." Two things evolve: how much is going on (layers,
speed, register, loudness) and the patterns themselves. Hutchinson's
chapter on minimalism names the two processes Cells-like music is built on:
**Reich's phasing** (loops of different lengths going out of step;
rotation) and **Glass's additive process** (a figure growing or shrinking a
note at a time; *Einstein on the Beach* lengthening chords by adding
subdivisions).

## Decision

- **Energy**, 0 to 1, is one curve over the hold: **Build** (rise over the
  pace, then stay), **Swell** (rise and fall, again), **Fade** (from the top
  down), **Wander** (smooth noise through the variation's own points),
  between **Start** and **Peak**, with a slow breathing drift of a few
  percent.
- **Pace** is in **bars**, 1 to 64: tempo-relative, so a pace fits a phrase
  at any tempo.
- Energy decides which layers play (0003), the bass's and pulse's rate, the
  arpeggio's subdivision (**eighths → triplets → sixteenths**: Glass's added
  subdivisions) and span (one octave to three), the pad's number of voices,
  velocities, and the sparkle's density.
- **Change** is separate: how much the patterns mutate as they go round. The
  arpeggio is a loop of **5 to 7 notes against a bar of 4**, so it phases
  against the bar (Reich); at the end of each time round it may turn (start
  from its second note), grow a note or lose one (Glass - growing more
  likely while the energy rises, shrinking while it falls), or move a note
  to its neighbour or an octave. The pulse's accents rotate; the pad moves a
  voice; the bass adds a fifth or an octave.
- **A faster pace also changes the patterns more often** (`√(8/pace)`,
  0.5×–2×): "evolve faster" should be heard in both.

## Consequences

- At Change 0% with a steady energy the arpeggio repeats exactly (a test
  holds it), so the motion is then only the energy's.
- The energy strip in the window draws the shape over two paces, with the
  hold's place on it.

## Alternatives

Pace in seconds: rejected, a pace in bars stays musical when the tempo
changes. One "speed" control for both: rejected, a slowly growing texture
with busy, restless patterns (or the other way round) is a real choice.

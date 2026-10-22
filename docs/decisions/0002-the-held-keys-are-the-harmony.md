# 0002. The held keys are the harmony

Taken 2026-10-21. Stands.

## Context

Cells and Time Micro play from the notes you hold: the chord is the
material, the engine the motion. The family's scripts pick a key and a
scale (ScaleView's tables); Midi Variator reads the scale from the notes it
has.

## Decision

- **No key or scale to choose.** What you hold is all the harmony there is:
  its pitch classes above the lowest key make a **ladder**, and every layer
  climbs it. Patterns store rungs, not pitches, so a new chord is followed
  at the next step without a pattern being lost.
- **One key alone is a root with its fifth**, a drone's open sound, rather
  than a ladder of octaves.
- **A chord settles for 25 ms** before it counts, so a chord played a
  little spread is one change and one hold, not three.
- Changing the chord mid-hold: the bass restrikes on the new root at once,
  the pad re-voices (keeping the voices both chords share); the rest follow
  on their next step. The hold, and its energy, go on.

## Consequences

- Nothing can be out of key with what you play; the colour tones (0005) are
  the only notes not held, and they are measured against what is held.
- 25 ms of latency at the start of a hold and a change - well under a
  sixteenth at any tempo.

## Alternatives

A key and scale picker (ScaleView's), with colour tones drawn from the
scale. Kept as an idea in CLAUDE.md; it would add a setting the held notes
already answer.

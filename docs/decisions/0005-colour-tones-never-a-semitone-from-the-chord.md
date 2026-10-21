# 0005. Colour tones: a whole tone above a chord tone, never a semitone from one

Taken 2026-10-21. Stands.

## Context

Only chord tones, all the time, is plain; Cells and Time Micro shimmer with
added notes. With no scale chosen (0002), the added notes must come from
what is held, and must never grind.

## Decision

- A **colour tone** is a pitch class a whole tone above a chord tone (its
  9th, 11th or 13th) that is **not a semitone from any held pitch class** -
  Midi Variator's clash guard (no new semitone, major seventh or minor
  ninth against anything sounding), in pitch classes. Over C E G: D and A;
  never F (a semitone from E) or B (from C). Over C E G B: D only.
- Where they go: the **pad** may move a voice to one (with Change and
  energy); the **arpeggio** only on an off-beat step, as an **unaccented
  neighbour** that the next step leaves (Open Music Theory's embellishing
  tones); the **sparkle** freely, being high and soft.

## Consequences

- A test plays ten chords at Change 100% and finds every note outside the
  chord a whole tone above a chord tone and a semitone from none.
- Chords with many notes have few colours; that is right - they are colour
  enough.

# 0003. Five layers, each a plane in its own register, coming in in order

Taken 2026-10-21. Stands.

## Context

What makes Cells and Time Macro sound like motion rather than an
arpeggiator is several patterns at once, each with its own role, adding up
over time. The orchestration books in the user's Educational Materials say
how such layers stay clear (Good Idea's `docs/READING.md` has the notes):

- Belkin: **planes of tone** - the ear follows one foreground; background
  is *movement* (repeated notes, arpeggiation, "limited to one or two mildly
  varied motives, with a high degree of consistency", lightened with rests)
  or *resonance* (held notes); planes are kept apart by **register** and
  rhythm; **crescendo = add instruments in order**, and keep something back
  for the climax.
- Belkin and *Orchestration Analysis*: chords follow the overtone series,
  **wide at the bottom, close at the top**, no hole in the middle;
  doubling by **displacement in time** (an echo).

## Decision

Five layers, in the order they come in:

| | plane | register |
| --- | --- | --- |
| **Bass** | resonance, then a pulse: a bar, a half bar, a beat | G1–F#2 |
| **Pad** | resonance: the chord held, every chord tone first, a fifth or more above the bottom then close; one voice moves at a time; voices added as it grows | from G2–F#3 |
| **Pulse** | movement: repeated notes on a Euclidean rhythm that fills in, its accents turning a step at a time | above G3–F#4 |
| **Arpeggio** | movement: a looping figure (0004) | from G3–F#4, one to three octaves |
| **Sparkle** | the climax: high, sparse, soft, some echoed three sixteenths later | from G4–F#5 |

The layers that are on come in at `0.85 × k / n` of the energy - the first
at once, the last near the top - and leave just below it. Each has its own
Channel, Octave and Level, so each can go to its own instrument.

**One of each pitch on a channel.** When two layers share a channel and a
pitch, a quick note on a pitch already held longer re-strikes it and keeps
the longer end - the arpeggio never cuts the pad's held E short.

## Consequences

- The pulse stays in eighths until the very top (0.9), with at most three
  quarters of its steps sounding, so the arpeggio can be heard through it.
- Every layer on channel 1 (the default) works with one instrument; on
  separate channels, with several.

## Alternatives

Any number of identical "cells" with a pattern each (Cells' own model).
Rejected for a first version: five named roles are easier to hear and to
set; more cells, or a choice of pattern per layer, are ideas in CLAUDE.md.

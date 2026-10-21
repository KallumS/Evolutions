# 0006. A new variation each hold, with a number to lock

Taken 2026-10-21. Stands.

## Context

"The evolution should be different each time." But a musician who finds a
good one wants it again. Good Idea's answer to the same wish: an idea is a
number (its 0002); Midi Variator's dice are a seeded Park-Miller generator
with a stream per part.

## Decision

- Every hold draws a **variation number** (1–99999, from `time_precise`):
  the arpeggio's figure and length, the pulse's notes and rotation, every
  later mutation and the feel all come from it.
- **Variation: Locked** keeps the last number: every hold then starts the
  same way. The window shows the number.
- Each layer has **its own random stream**, and the feel another, so one
  layer's choices never move another's.

## Consequences

- Locked and played the same way, a hold is the same note for note (a test
  holds it, feel included). Played differently - another chord, held
  longer, a chord change at another moment - it is steered differently;
  the window's message says so.
